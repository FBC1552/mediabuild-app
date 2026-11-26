"""Observabilidade de acesso e de erro para a tela de administração (D-014).

Tudo aqui exige papel `admin`.

**Os agregados de `/admin/resumo` são calculados em SQL.** A tentação seria
carregar a lista de eventos e contar em Python — funciona hoje, com o banco
vazio, e vira um timeout silencioso quando a tabela de eventos passar de
algumas centenas de milhares de linhas, que é exatamente quando alguém abre
a tela para entender o que está acontecendo. `eventos_erro` é a tabela que
mais cresce no sistema.

O agrupamento por dia usa o **fuso da aplicação** (`app/tempo.py`, D do
`FUSO_HORARIO`), não UTC: "logins de ontem" é uma pergunta humana, e ela só
tem resposta dentro de um fuso. Sem o `AT TIME ZONE`, tudo que acontece
depois das 21h no Brasil apareceria no dia seguinte.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, literal_column, select
from sqlalchemy.orm import Session

from app.autorizacao import agora, exige_admin
from app.config import settings
from app.db import get_session
from app.models import EventoAcesso, EventoErro, Papel, Sessao, TipoEventoAcesso, Usuario
from app.schemas import (
    CaminhoComErro,
    EventoAcessoLer,
    EventoErroLer,
    LoginsDoDia,
    ResumoAdmin,
)
from app.tempo import fim_do_intervalo, inicio_do_intervalo

router = APIRouter(prefix="/admin", tags=["monitoramento"], dependencies=[Depends(exige_admin)])

# Teto do `limite`. Não é preferência: sem ele, `?limite=10000000` é um
# negador de serviço de uma linha, e a tela nunca precisa de mais que isto.
LIMITE_MAXIMO = 500
LIMITE_PADRAO = 100


@router.get("/acessos", response_model=list[EventoAcessoLer])
def acessos(
    desde: datetime | None = None,
    ate: datetime | None = None,
    tipo: TipoEventoAcesso | None = None,
    limite: int = Query(default=LIMITE_PADRAO, ge=1, le=LIMITE_MAXIMO),
    session: Session = Depends(get_session),
):
    """Eventos de acesso, mais recentes primeiro.

    O `usuario_login` sai por LEFT JOIN e vem nulo quando a conta já foi
    excluída — o evento sobrevive a ela de propósito. `login_tentado`
    continua preenchido nesse caso, então a linha nunca fica anônima.
    """
    consulta = (
        select(EventoAcesso, Usuario.login)
        .join(Usuario, Usuario.id == EventoAcesso.usuario_id, isouter=True)
        .order_by(EventoAcesso.ocorrido_em.desc())
        .limit(limite)
    )
    if desde is not None:
        consulta = consulta.where(EventoAcesso.ocorrido_em >= inicio_do_intervalo(desde))
    if ate is not None:
        consulta = consulta.where(EventoAcesso.ocorrido_em <= fim_do_intervalo(ate))
    if tipo is not None:
        consulta = consulta.where(EventoAcesso.tipo == tipo)

    return [
        EventoAcessoLer.model_validate(evento).model_copy(update={"usuario_login": login})
        for evento, login in session.execute(consulta)
    ]


@router.get("/erros", response_model=list[EventoErroLer])
def erros(
    desde: datetime | None = None,
    ate: datetime | None = None,
    status: int | None = Query(default=None, ge=400, le=599),
    limite: int = Query(default=LIMITE_PADRAO, ge=1, le=LIMITE_MAXIMO),
    session: Session = Depends(get_session),
):
    """Respostas com status >= 400, mais recentes primeiro.

    `status` filtra o código exato. Faixa (`4xx`/`5xx`) sai pronta no
    `/admin/resumo` — não vale inventar uma sintaxe de faixa neste
    parâmetro para uma pergunta que já tem resposta lá.
    """
    consulta = (
        select(EventoErro, Usuario.login)
        .join(Usuario, Usuario.id == EventoErro.usuario_id, isouter=True)
        .order_by(EventoErro.ocorrido_em.desc())
        .limit(limite)
    )
    if desde is not None:
        consulta = consulta.where(EventoErro.ocorrido_em >= inicio_do_intervalo(desde))
    if ate is not None:
        consulta = consulta.where(EventoErro.ocorrido_em <= fim_do_intervalo(ate))
    if status is not None:
        consulta = consulta.where(EventoErro.status == status)

    return [
        EventoErroLer.model_validate(evento).model_copy(update={"usuario_login": login})
        for evento, login in session.execute(consulta)
    ]


@router.get("/resumo", response_model=ResumoAdmin)
def resumo(
    dias: int = Query(default=7, ge=1, le=90),
    session: Session = Depends(get_session),
):
    agora_utc = agora()
    desde = agora_utc - timedelta(days=dias)

    # --- logins por dia, no fuso da aplicação ----------------------------
    dia_local = func.date(
        func.timezone(settings.fuso_horario, EventoAcesso.ocorrido_em)
    ).label("dia")
    linhas_login = session.execute(
        select(
            dia_local,
            func.count(case((EventoAcesso.tipo == TipoEventoAcesso.LOGIN_OK, 1))).label("ok"),
            func.count(case((EventoAcesso.tipo == TipoEventoAcesso.LOGIN_FALHA, 1))).label("falha"),
        )
        .where(
            EventoAcesso.ocorrido_em >= desde,
            EventoAcesso.tipo.in_([TipoEventoAcesso.LOGIN_OK, TipoEventoAcesso.LOGIN_FALHA]),
        )
        .group_by(literal_column("dia"))
        .order_by(literal_column("dia"))
    ).all()

    logins_por_dia = [LoginsDoDia(dia=linha.dia, ok=linha.ok, falha=linha.falha) for linha in linhas_login]
    total_ok = sum(linha.ok for linha in logins_por_dia)
    total_falha = sum(linha.falha for linha in logins_por_dia)
    tentativas = total_ok + total_falha
    # Sem tentativa nenhuma a taxa é 0.0, não nulo: ausência de dado não é
    # falha, e um nulo aqui obrigaria a tela a ter dois estados vazios.
    taxa = round(total_falha / tentativas, 4) if tentativas else 0.0

    # --- erros ------------------------------------------------------------
    top = session.execute(
        select(EventoErro.caminho, func.count(EventoErro.id).label("total"))
        .where(EventoErro.ocorrido_em >= desde)
        .group_by(EventoErro.caminho)
        .order_by(func.count(EventoErro.id).desc(), EventoErro.caminho)
        .limit(10)
    ).all()

    faixas = session.execute(
        select(
            func.count(case((EventoErro.status < 500, 1))).label("quatro"),
            func.count(case((EventoErro.status >= 500, 1))).label("cinco"),
        ).where(EventoErro.ocorrido_em >= desde)
    ).one()

    # --- estado atual -----------------------------------------------------
    # "Agora", não "na janela": quantas pessoas estão dentro do sistema
    # neste instante é a pergunta que a tela faz, e ela não depende de
    # `dias`.
    sessoes_ativas = session.scalar(
        select(func.count(Sessao.id)).where(
            Sessao.revogada_em.is_(None),
            Sessao.expira_em > agora_utc,
        )
    ) or 0

    por_papel = session.execute(
        select(Usuario.papel, func.count(Usuario.id))
        .where(Usuario.ativo.is_(True))
        .group_by(Usuario.papel)
    ).all()
    # Todos os papéis aparecem, inclusive com zero: a tela não deveria ter
    # que saber a lista de papéis para desenhar a linha que falta.
    usuarios_por_papel = {papel.value: 0 for papel in Papel}
    for papel, total in por_papel:
        usuarios_por_papel[papel.value] = total

    return ResumoAdmin(
        dias=dias,
        desde=desde.astimezone(UTC),
        logins_por_dia=logins_por_dia,
        taxa_falha_login=taxa,
        total_logins_ok=total_ok,
        total_logins_falha=total_falha,
        top_caminhos_com_erro=[
            CaminhoComErro(caminho=linha.caminho, total=linha.total) for linha in top
        ],
        erros_4xx=faixas.quatro,
        erros_5xx=faixas.cinco,
        sessoes_ativas=sessoes_ativas,
        usuarios_por_papel=usuarios_por_papel,
    )
