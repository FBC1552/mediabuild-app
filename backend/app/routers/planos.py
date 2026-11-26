"""Plano de mídia: rateio de verba em cascata e metas por anúncio.

Diferente de `app/routers/taxonomias.py`, este router **tem** PATCH e
DELETE em todos os níveis — o plano é um documento de trabalho mutável
(D-004 vale para nomenclatura gerada, não para este documento).

`/planos/export` está declarada antes de `/planos/{plano_id}`, pelo mesmo
motivo de `/taxonomias/export`: sem isso o FastAPI tentaria interpretar o
literal 'export' como UUID e devolveria 422.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.erros_plano import EntidadeForaDaHierarquia, KpiPrimarioInvalido, MetricaDesconhecida
from app.exportacao_plano import gerar_planilha_plano
from app.models import (
    Anuncio,
    Campanha,
    GrupoAnuncio,
    Metrica,
    Nivel,
    PlanoMidia,
    PlanoMidiaAnuncio,
    PlanoMidiaCampanha,
    PlanoMidiaGrupo,
    TaxonomiaGerada,
)
from app.schemas import (
    AnuncioDoPlanoAtualizar,
    AnuncioDoPlanoCriar,
    AnuncioDoPlanoLer,
    CampanhaDoPlanoAtualizar,
    CampanhaDoPlanoCriar,
    CampanhaDoPlanoLer,
    GrupoDoPlanoAtualizar,
    GrupoDoPlanoCriar,
    GrupoDoPlanoLer,
    PlanoMidiaAtualizar,
    PlanoMidiaCriar,
    PlanoMidiaLer,
    PlanoMidiaResumoLer,
    _LinhaPedido,
)

router = APIRouter(prefix="/planos", tags=["planos de mídia"])

_DUAS_CASAS = Decimal("0.01")
_TRES_CASAS = Decimal("0.001")


# --------------------------------------------------------------------------
# aritmética do rateio (D-A / D-B)
#
# O valor em reais é sempre a fonte da verdade; a porcentagem é forma de
# entrada (aceita na escrita) e forma de exibição (calculada de volta na
# leitura), nunca persistida. Isso é o que torna o desbalanço um estado de
# rascunho legítimo em vez de um valor ambíguo: a soma dos filhos pode não
# bater com o valor do pai, porque não existe uma % armazenada que precise
# "fechar" — só valores em reais, cada um gravado de uma vez.
# --------------------------------------------------------------------------


def _calcular_valor(valor_pai: Decimal, dados: "_LinhaPedido") -> Decimal:
    """Resolve `dados.valor` OU `dados.percentual` num valor em reais.

    Arredondamento bancário padrão (metade para cima) em duas casas — a
    mesma régua usada em qualquer nota fiscal. Como o valor calculado é
    gravado (não recalculado depois), o rateio nunca acumula erro de
    arredondamento a cada leitura; o erro, se houver, é de no máximo um
    centavo por linha, e é exatamente ele que compõe a `diferenca`
    reportada no nível acima quando os filhos não fecham 100%.
    """
    if dados.valor is not None:
        return dados.valor.quantize(_DUAS_CASAS, rounding=ROUND_HALF_UP)
    valor = (valor_pai * dados.percentual / Decimal(100)).quantize(
        _DUAS_CASAS, rounding=ROUND_HALF_UP
    )
    return valor


def _percentual(valor: Decimal, valor_pai: Decimal) -> Decimal | None:
    """Percentual do valor sobre o do pai, para exibição. `None` quando o
    pai é zero — a divisão não tem significado, e não é um erro do plano."""
    if valor_pai == 0:
        return None
    return (valor / valor_pai * Decimal(100)).quantize(_TRES_CASAS, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# resolução de entidades e busca das linhas do plano
# --------------------------------------------------------------------------


def _obter_plano_ou_404(session: Session, plano_id: UUID) -> PlanoMidia:
    plano = session.get(PlanoMidia, plano_id)
    if plano is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano de mídia não encontrado.")
    return plano


def _carregar_plano_completo(session: Session, plano_id: UUID) -> PlanoMidia:
    """Carrega o plano com a árvore inteira numa única viagem por nível
    (`selectinload`, não `joinedload`, para não multiplicar linhas ao
    juntar três coleções aninhadas)."""
    plano = session.scalar(
        select(PlanoMidia)
        .options(
            selectinload(PlanoMidia.campanhas)
            .selectinload(PlanoMidiaCampanha.grupos)
            .selectinload(PlanoMidiaGrupo.anuncios)
        )
        .where(PlanoMidia.id == plano_id)
    )
    if plano is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano de mídia não encontrado.")
    return plano


def _obter_linha_campanha_ou_404(
    session: Session, plano_id: UUID, linha_id: UUID
) -> PlanoMidiaCampanha:
    linha = session.scalar(
        select(PlanoMidiaCampanha).where(
            PlanoMidiaCampanha.id == linha_id, PlanoMidiaCampanha.plano_id == plano_id
        )
    )
    if linha is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Linha de campanha não encontrada neste plano."
        )
    return linha


def _obter_linha_grupo_ou_404(
    session: Session, plano_id: UUID, linha_campanha_id: UUID, linha_grupo_id: UUID
) -> PlanoMidiaGrupo:
    linha_campanha = _obter_linha_campanha_ou_404(session, plano_id, linha_campanha_id)
    linha = session.scalar(
        select(PlanoMidiaGrupo).where(
            PlanoMidiaGrupo.id == linha_grupo_id,
            PlanoMidiaGrupo.plano_midia_campanha_id == linha_campanha.id,
        )
    )
    if linha is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Linha de grupo não encontrada nesta campanha do plano."
        )
    return linha


def _obter_linha_anuncio_ou_404(
    session: Session,
    plano_id: UUID,
    linha_campanha_id: UUID,
    linha_grupo_id: UUID,
    linha_anuncio_id: UUID,
) -> PlanoMidiaAnuncio:
    linha_grupo = _obter_linha_grupo_ou_404(session, plano_id, linha_campanha_id, linha_grupo_id)
    linha = session.scalar(
        select(PlanoMidiaAnuncio).where(
            PlanoMidiaAnuncio.id == linha_anuncio_id,
            PlanoMidiaAnuncio.plano_midia_grupo_id == linha_grupo.id,
        )
    )
    if linha is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Linha de anúncio não encontrada neste grupo do plano."
        )
    return linha


def _ultima_nomenclatura(session: Session, nivel: Nivel, entidade_id: UUID) -> str | None:
    """A nomenclatura mais recente gerada para a entidade, se houver — o
    plano pode referenciar uma campanha/grupo/anúncio que ainda não passou
    pela aba Gerar. Fica nula nesse caso, estado normal (não um erro)."""
    taxonomia = session.scalar(
        select(TaxonomiaGerada)
        .where(TaxonomiaGerada.nivel == nivel, TaxonomiaGerada.entidade_id == entidade_id)
        .order_by(TaxonomiaGerada.criado_em.desc())
        .limit(1)
    )
    return taxonomia.nomenclatura_final if taxonomia else None


def _sincronizar_nomenclatura_se_pedido(
    session: Session,
    linha: PlanoMidiaCampanha | PlanoMidiaGrupo | PlanoMidiaAnuncio,
    nivel: Nivel,
    entidade_id: UUID,
    dados: CampanhaDoPlanoAtualizar | GrupoDoPlanoAtualizar | AnuncioDoPlanoAtualizar,
) -> None:
    """Aplica o verbo `sincronizar_nomenclatura=true` do PATCH (contrato
    fechado com o frontend): recopia `linha.nomenclatura` a partir da
    nomenclatura mais recente da entidade, a mesma que `_ultima_nomenclatura`
    já usa para calcular `nomenclatura_atual`/`nomenclatura_divergente` na
    leitura — os dois nunca discordam depois deste PATCH.

    `exclude_unset` de propósito: olhamos `model_fields_set`, não só o
    valor, porque o campo tem default `False` no schema — se olhássemos só
    o valor, um PATCH que nunca menciona o campo teria o mesmo efeito
    (nada) de um que manda `false` explícito, o que é o comportamento
    certo aqui mesmo, mas a checagem por `model_fields_set` é a mesma
    disciplina do resto deste router (flight/KPI/custo unitário) e evita
    reintroduzir esse raciocínio errado se o default mudar no futuro.

    Sem nomenclatura mais recente — entidade que nunca teve nome gerado, ou
    (só hipótese defensiva: `taxonomias_geradas` não tem rota de DELETE e
    `entidade_id` não tem FK por D-009, então isso não acontece por dentro
    da API) histórico que sumiu por fora dela — o snapshot NÃO é zerado: o
    plano tem que continuar mostrando o nome que já tinha, porque ele
    sobrevive de propósito à entidade que o gerou. É no-op silencioso, não
    erro 422: o pedido de sincronizar não é inválido, só não há nada mais
    novo para copiar; o resto do PATCH (valor, flight, KPI, custo unitário,
    metas) segue sendo aplicado normalmente na mesma chamada.
    """
    if "sincronizar_nomenclatura" not in dados.model_fields_set or not dados.sincronizar_nomenclatura:
        return
    atual = _ultima_nomenclatura(session, nivel, entidade_id)
    if atual is not None:
        linha.nomenclatura = atual


def _nomenclaturas_atuais_em_lote(
    session: Session, ids_por_nivel: dict[Nivel, set[UUID]]
) -> dict[UUID, str]:
    """Mesma informação de `_ultima_nomenclatura`, mas para um conjunto de
    entidades de uma vez — uma consulta por nível presente (no máximo 3),
    nunca uma por linha. Usado por `_carregar_plano_completo`/`obter` para
    expor `nomenclatura_divergente` em toda a árvore sem N+1; os endpoints
    de linha única (`POST`/`PATCH` de uma campanha/grupo/anúncio) seguem
    usando `_ultima_nomenclatura` diretamente, porque ali já é uma única
    entidade — o lote não compraria nada.

    `DISTINCT ON` faria o mesmo em menos SQL, mas fica preso ao dialeto
    Postgres de um jeito que o resto do módulo evita; a janela
    (`row_number() over (partition by ...)`) é portável e igualmente barata
    aqui, porque o conjunto de entidades por plano é pequeno.
    """
    atuais: dict[UUID, str] = {}
    for nivel, ids in ids_por_nivel.items():
        if not ids:
            continue
        janela = (
            select(
                TaxonomiaGerada.entidade_id,
                TaxonomiaGerada.nomenclatura_final,
                func.row_number()
                .over(
                    partition_by=TaxonomiaGerada.entidade_id,
                    order_by=TaxonomiaGerada.criado_em.desc(),
                )
                .label("posicao"),
            )
            .where(TaxonomiaGerada.nivel == nivel, TaxonomiaGerada.entidade_id.in_(ids))
            .subquery()
        )
        consulta = select(janela.c.entidade_id, janela.c.nomenclatura_final).where(
            janela.c.posicao == 1
        )
        for entidade_id, nomenclatura in session.execute(consulta).all():
            atuais[entidade_id] = nomenclatura
    return atuais


def _kpis_primarios_ativos(session: Session, plano: PlanoMidia) -> dict[UUID, bool]:
    """Para cada `kpi_primario_id` já escolhido em alguma campanha do
    plano, se a métrica referenciada ainda existe e está ativa agora — uma
    única consulta para o plano inteiro (não uma por campanha)."""
    ids = {c.kpi_primario_id for c in plano.campanhas if c.kpi_primario_id is not None}
    if not ids:
        return {}
    ativos = set(
        session.scalars(select(Metrica.id).where(Metrica.id.in_(ids), Metrica.ativo.is_(True)))
    )
    return {kpi_id: kpi_id in ativos for kpi_id in ids}


def _validar_metas(session: Session, metas: dict[str, int]) -> None:
    """D-005-like: meta presa a um código de métrica sem cadastro ativo é
    erro, não passa em silêncio — ela não apareceria em relatório nenhum."""
    if not metas:
        return
    ativos = set(session.scalars(select(Metrica.codigo).where(Metrica.ativo.is_(True))))
    for codigo in metas:
        if codigo not in ativos:
            raise MetricaDesconhecida(codigo, sorted(ativos))


def _validar_kpi_primario(session: Session, kpi_primario_id: UUID | None) -> Metrica | None:
    """KPI primário é sempre referência ao catálogo, nunca texto livre —
    `None` explicitamente limpa o KPI (estado válido: campanha sem KPI
    escolhido ainda). Quando informado, precisa existir e estar ativo
    *no momento da escrita*; depois disso pode ser desativado ou apagado
    sem quebrar a linha do plano — ver `PlanoMidiaCampanha.kpi_primario_id`
    e `_kpis_primarios_ativos` abaixo, que resolve isso na leitura."""
    if kpi_primario_id is None:
        return None
    metrica = session.get(Metrica, kpi_primario_id)
    if metrica is None or not metrica.ativo:
        ativos = sorted(session.scalars(select(Metrica.codigo).where(Metrica.ativo.is_(True))))
        raise KpiPrimarioInvalido(str(kpi_primario_id), ativos)
    return metrica


# --------------------------------------------------------------------------
# montagem da resposta (soma dos filhos e diferença calculadas aqui)
# --------------------------------------------------------------------------


def _montar_anuncio_ler(
    anuncio: PlanoMidiaAnuncio, valor_grupo: Decimal, nomenclatura_atual: str | None
) -> AnuncioDoPlanoLer:
    return AnuncioDoPlanoLer(
        id=anuncio.id,
        anuncio_id=anuncio.anuncio_id,
        nome_interno=anuncio.nome_interno,
        match_id=anuncio.match_id,
        nomenclatura=anuncio.nomenclatura,
        nomenclatura_atual=nomenclatura_atual,
        nomenclatura_divergente=nomenclatura_atual != anuncio.nomenclatura,
        valor=anuncio.valor,
        percentual=_percentual(anuncio.valor, valor_grupo),
        metas=anuncio.metas or {},
        criado_em=anuncio.criado_em,
        atualizado_em=anuncio.atualizado_em,
    )


def _montar_grupo_ler(
    session: Session,
    grupo: PlanoMidiaGrupo,
    valor_campanha: Decimal,
    nomenclaturas: dict[UUID, str] | None = None,
) -> GrupoDoPlanoLer:
    """`nomenclaturas`, quando fornecido (leitura do plano inteiro), evita
    uma consulta por linha; quando `None` (resposta de um único
    `POST`/`PATCH`), cai para `_ultima_nomenclatura` direta — é uma única
    entidade, o lote não ajudaria."""
    soma = sum((a.valor for a in grupo.anuncios), Decimal("0"))
    atual_grupo = (
        nomenclaturas.get(grupo.grupo_id)
        if nomenclaturas is not None
        else _ultima_nomenclatura(session, Nivel.GRUPO, grupo.grupo_id)
    )
    return GrupoDoPlanoLer(
        id=grupo.id,
        grupo_id=grupo.grupo_id,
        nome_interno=grupo.nome_interno,
        match_id=grupo.match_id,
        nomenclatura=grupo.nomenclatura,
        nomenclatura_atual=atual_grupo,
        nomenclatura_divergente=atual_grupo != grupo.nomenclatura,
        valor=grupo.valor,
        percentual=_percentual(grupo.valor, valor_campanha),
        custo_unitario_negociado=grupo.custo_unitario_negociado,
        soma_anuncios=soma,
        diferenca=grupo.valor - soma,
        anuncios=[
            _montar_anuncio_ler(
                a,
                grupo.valor,
                nomenclaturas.get(a.anuncio_id)
                if nomenclaturas is not None
                else _ultima_nomenclatura(session, Nivel.ANUNCIO, a.anuncio_id),
            )
            for a in grupo.anuncios
        ],
    )


def _montar_campanha_ler(
    session: Session,
    campanha: PlanoMidiaCampanha,
    verba_total: Decimal,
    nomenclaturas: dict[UUID, str] | None = None,
    kpis_ativos: dict[UUID, bool] | None = None,
) -> CampanhaDoPlanoLer:
    soma = sum((g.valor for g in campanha.grupos), Decimal("0"))
    atual_campanha = (
        nomenclaturas.get(campanha.campanha_id)
        if nomenclaturas is not None
        else _ultima_nomenclatura(session, Nivel.CAMPANHA, campanha.campanha_id)
    )
    if campanha.kpi_primario_id is None:
        kpi_ativo = None
    elif kpis_ativos is not None:
        kpi_ativo = kpis_ativos.get(campanha.kpi_primario_id, False)
    else:
        metrica = session.get(Metrica, campanha.kpi_primario_id)
        kpi_ativo = metrica is not None and metrica.ativo
    return CampanhaDoPlanoLer(
        id=campanha.id,
        campanha_id=campanha.campanha_id,
        plataforma_id=campanha.plataforma_id,
        nome_interno=campanha.nome_interno,
        match_id=campanha.match_id,
        nomenclatura=campanha.nomenclatura,
        nomenclatura_atual=atual_campanha,
        nomenclatura_divergente=atual_campanha != campanha.nomenclatura,
        valor=campanha.valor,
        percentual=_percentual(campanha.valor, verba_total),
        flight_inicio=campanha.flight_inicio,
        flight_fim=campanha.flight_fim,
        kpi_primario_id=campanha.kpi_primario_id,
        kpi_primario_codigo=campanha.kpi_primario_codigo,
        kpi_primario_rotulo=campanha.kpi_primario_rotulo,
        kpi_primario_ativo=kpi_ativo,
        soma_grupos=soma,
        diferenca=campanha.valor - soma,
        grupos=[_montar_grupo_ler(session, g, campanha.valor, nomenclaturas) for g in campanha.grupos],
    )


def _montar_plano_ler(session: Session, plano: PlanoMidia) -> PlanoMidiaLer:
    """Ponto único de leitura do plano completo — resolve nomenclatura
    atual e KPI ativo em lote (no máximo 4 consultas extra, independente
    do tamanho da árvore) antes de montar a resposta."""
    ids_por_nivel: dict[Nivel, set[UUID]] = {
        Nivel.CAMPANHA: set(),
        Nivel.GRUPO: set(),
        Nivel.ANUNCIO: set(),
    }
    for campanha in plano.campanhas:
        ids_por_nivel[Nivel.CAMPANHA].add(campanha.campanha_id)
        for grupo in campanha.grupos:
            ids_por_nivel[Nivel.GRUPO].add(grupo.grupo_id)
            for anuncio in grupo.anuncios:
                ids_por_nivel[Nivel.ANUNCIO].add(anuncio.anuncio_id)
    nomenclaturas = _nomenclaturas_atuais_em_lote(session, ids_por_nivel)
    kpis_ativos = _kpis_primarios_ativos(session, plano)

    soma = sum((c.valor for c in plano.campanhas), Decimal("0"))
    return PlanoMidiaLer(
        id=plano.id,
        nome=plano.nome,
        verba_total=plano.verba_total,
        observacoes=plano.observacoes,
        soma_campanhas=soma,
        diferenca=plano.verba_total - soma,
        campanhas=[
            _montar_campanha_ler(session, c, plano.verba_total, nomenclaturas, kpis_ativos)
            for c in plano.campanhas
        ],
        criado_em=plano.criado_em,
        atualizado_em=plano.atualizado_em,
    )


# --------------------------------------------------------------------------
# plano
# --------------------------------------------------------------------------


@router.get("", response_model=list[PlanoMidiaResumoLer])
def listar(session: Session = Depends(get_session)):
    """Índice sem a árvore inteira — só o total, a soma das campanhas já
    ratedas e a diferença, para não pagar o custo de montar cada plano
    completo numa tela de listagem."""
    subconsulta = (
        select(
            PlanoMidiaCampanha.plano_id.label("plano_id"),
            func.coalesce(func.sum(PlanoMidiaCampanha.valor), 0).label("soma"),
            func.count().label("quantidade"),
        )
        .group_by(PlanoMidiaCampanha.plano_id)
        .subquery()
    )
    consulta = (
        select(PlanoMidia, subconsulta.c.soma, subconsulta.c.quantidade)
        .outerjoin(subconsulta, subconsulta.c.plano_id == PlanoMidia.id)
        .order_by(PlanoMidia.criado_em.desc())
    )

    resultado: list[PlanoMidiaResumoLer] = []
    for plano, soma, quantidade in session.execute(consulta).all():
        soma = Decimal(soma or 0)
        resultado.append(
            PlanoMidiaResumoLer(
                id=plano.id,
                nome=plano.nome,
                verba_total=plano.verba_total,
                soma_campanhas=soma,
                diferenca=plano.verba_total - soma,
                quantidade_campanhas=quantidade or 0,
                criado_em=plano.criado_em,
                atualizado_em=plano.atualizado_em,
            )
        )
    return resultado


@router.post("", response_model=PlanoMidiaLer, status_code=status.HTTP_201_CREATED)
def criar(dados: PlanoMidiaCriar, session: Session = Depends(get_session)):
    plano = PlanoMidia(
        nome=dados.nome, verba_total=dados.verba_total, observacoes=dados.observacoes
    )
    session.add(plano)
    session.commit()
    return _montar_plano_ler(session, _carregar_plano_completo(session, plano.id))


# `/export` precisa vir antes de `/{plano_id}` — mesma armadilha de
# `/taxonomias/export` (ver docstring do módulo).
@router.get("/export")
def exportar(plano_id: UUID, session: Session = Depends(get_session)):
    """Baixa o plano em `.xlsx`, no layout achatado da planilha do cliente
    (uma linha por anúncio, taxonomias em colunas, TOTAL no pé)."""
    plano = _carregar_plano_completo(session, plano_id)
    conteudo = gerar_planilha_plano(session, plano)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M")

    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="plano-midia-{carimbo}.xlsx"'
        },
    )


@router.get("/{plano_id}", response_model=PlanoMidiaLer)
def obter(plano_id: UUID, session: Session = Depends(get_session)):
    return _montar_plano_ler(session, _carregar_plano_completo(session, plano_id))


@router.patch("/{plano_id}", response_model=PlanoMidiaLer)
def atualizar(plano_id: UUID, dados: PlanoMidiaAtualizar, session: Session = Depends(get_session)):
    plano = _obter_plano_ou_404(session, plano_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(plano, campo, valor)
    session.commit()
    return _montar_plano_ler(session, _carregar_plano_completo(session, plano_id))


@router.delete("/{plano_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(plano_id: UUID, session: Session = Depends(get_session)):
    plano = _obter_plano_ou_404(session, plano_id)
    session.delete(plano)
    session.commit()


# --------------------------------------------------------------------------
# linhas de campanha
# --------------------------------------------------------------------------


@router.post(
    "/{plano_id}/campanhas", response_model=CampanhaDoPlanoLer, status_code=status.HTTP_201_CREATED
)
def adicionar_campanha(
    plano_id: UUID, dados: CampanhaDoPlanoCriar, session: Session = Depends(get_session)
):
    plano = _obter_plano_ou_404(session, plano_id)
    campanha = session.get(Campanha, dados.campanha_id)
    if campanha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campanha não encontrada.")
    kpi = _validar_kpi_primario(session, dados.kpi_primario_id)

    linha = PlanoMidiaCampanha(
        plano_id=plano.id,
        campanha_id=campanha.id,
        # Denormalizado no momento da inserção, sem FK (D-009): o plano
        # continua legível e cruzável pelo match ID mesmo que a campanha
        # operacional seja apagada depois.
        plataforma_id=campanha.plataforma_id,
        nome_interno=campanha.nome_interno,
        match_id=campanha.match_id,
        nomenclatura=_ultima_nomenclatura(session, Nivel.CAMPANHA, campanha.id),
        valor=_calcular_valor(plano.verba_total, dados),
        flight_inicio=dados.flight_inicio,
        flight_fim=dados.flight_fim,
        kpi_primario_id=kpi.id if kpi else None,
        kpi_primario_codigo=kpi.codigo if kpi else None,
        kpi_primario_rotulo=kpi.rotulo if kpi else None,
    )
    session.add(linha)
    session.commit()
    return _montar_campanha_ler(session, linha, plano.verba_total)


@router.patch("/{plano_id}/campanhas/{linha_id}", response_model=CampanhaDoPlanoLer)
def atualizar_campanha(
    plano_id: UUID,
    linha_id: UUID,
    dados: CampanhaDoPlanoAtualizar,
    session: Session = Depends(get_session),
):
    plano = _obter_plano_ou_404(session, plano_id)
    linha = _obter_linha_campanha_ou_404(session, plano_id, linha_id)
    linha.valor = _calcular_valor(plano.verba_total, dados)

    # `exclude_unset`: flight/KPI só mudam quando enviados explicitamente
    # no corpo do PATCH — mesmo contrato de `PATCH /planos/{id}` acima.
    # `kpi_primario_id: null` explícito limpa o KPI; omitido, não mexe.
    campos_enviados = dados.model_fields_set
    if "flight_inicio" in campos_enviados:
        linha.flight_inicio = dados.flight_inicio
    if "flight_fim" in campos_enviados:
        linha.flight_fim = dados.flight_fim
    if "kpi_primario_id" in campos_enviados:
        kpi = _validar_kpi_primario(session, dados.kpi_primario_id)
        linha.kpi_primario_id = kpi.id if kpi else None
        linha.kpi_primario_codigo = kpi.codigo if kpi else None
        linha.kpi_primario_rotulo = kpi.rotulo if kpi else None

    _sincronizar_nomenclatura_se_pedido(session, linha, Nivel.CAMPANHA, linha.campanha_id, dados)

    session.commit()
    return _montar_campanha_ler(session, linha, plano.verba_total)


@router.delete("/{plano_id}/campanhas/{linha_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_campanha(plano_id: UUID, linha_id: UUID, session: Session = Depends(get_session)):
    linha = _obter_linha_campanha_ou_404(session, plano_id, linha_id)
    session.delete(linha)
    session.commit()


# --------------------------------------------------------------------------
# linhas de grupo
# --------------------------------------------------------------------------


@router.post(
    "/{plano_id}/campanhas/{linha_campanha_id}/grupos",
    response_model=GrupoDoPlanoLer,
    status_code=status.HTTP_201_CREATED,
)
def adicionar_grupo(
    plano_id: UUID,
    linha_campanha_id: UUID,
    dados: GrupoDoPlanoCriar,
    session: Session = Depends(get_session),
):
    linha_campanha = _obter_linha_campanha_ou_404(session, plano_id, linha_campanha_id)
    grupo = session.get(GrupoAnuncio, dados.grupo_id)
    if grupo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grupo de anúncio não encontrado.")
    if grupo.campanha_id != linha_campanha.campanha_id:
        raise EntidadeForaDaHierarquia(
            "grupo_id",
            f"O grupo '{grupo.nome_interno}' pertence a outra campanha, não a "
            f"'{linha_campanha.nome_interno}' — a linha desta campanha no plano.",
        )

    linha = PlanoMidiaGrupo(
        plano_midia_campanha_id=linha_campanha.id,
        grupo_id=grupo.id,
        nome_interno=grupo.nome_interno,
        match_id=grupo.match_id,
        nomenclatura=_ultima_nomenclatura(session, Nivel.GRUPO, grupo.id),
        valor=_calcular_valor(linha_campanha.valor, dados),
        custo_unitario_negociado=dados.custo_unitario_negociado,
    )
    session.add(linha)
    session.commit()
    return _montar_grupo_ler(session, linha, linha_campanha.valor)


@router.patch(
    "/{plano_id}/campanhas/{linha_campanha_id}/grupos/{linha_grupo_id}",
    response_model=GrupoDoPlanoLer,
)
def atualizar_grupo(
    plano_id: UUID,
    linha_campanha_id: UUID,
    linha_grupo_id: UUID,
    dados: GrupoDoPlanoAtualizar,
    session: Session = Depends(get_session),
):
    linha_campanha = _obter_linha_campanha_ou_404(session, plano_id, linha_campanha_id)
    linha = _obter_linha_grupo_ou_404(session, plano_id, linha_campanha_id, linha_grupo_id)
    linha.valor = _calcular_valor(linha_campanha.valor, dados)
    if "custo_unitario_negociado" in dados.model_fields_set:
        linha.custo_unitario_negociado = dados.custo_unitario_negociado
    _sincronizar_nomenclatura_se_pedido(session, linha, Nivel.GRUPO, linha.grupo_id, dados)
    session.commit()
    return _montar_grupo_ler(session, linha, linha_campanha.valor)


@router.delete(
    "/{plano_id}/campanhas/{linha_campanha_id}/grupos/{linha_grupo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_grupo(
    plano_id: UUID,
    linha_campanha_id: UUID,
    linha_grupo_id: UUID,
    session: Session = Depends(get_session),
):
    linha = _obter_linha_grupo_ou_404(session, plano_id, linha_campanha_id, linha_grupo_id)
    session.delete(linha)
    session.commit()


# --------------------------------------------------------------------------
# linhas de anúncio
# --------------------------------------------------------------------------


@router.post(
    "/{plano_id}/campanhas/{linha_campanha_id}/grupos/{linha_grupo_id}/anuncios",
    response_model=AnuncioDoPlanoLer,
    status_code=status.HTTP_201_CREATED,
)
def adicionar_anuncio(
    plano_id: UUID,
    linha_campanha_id: UUID,
    linha_grupo_id: UUID,
    dados: AnuncioDoPlanoCriar,
    session: Session = Depends(get_session),
):
    linha_grupo = _obter_linha_grupo_ou_404(session, plano_id, linha_campanha_id, linha_grupo_id)
    anuncio = session.get(Anuncio, dados.anuncio_id)
    if anuncio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anúncio não encontrado.")
    if anuncio.grupo_anuncio_id != linha_grupo.grupo_id:
        raise EntidadeForaDaHierarquia(
            "anuncio_id",
            f"O anúncio '{anuncio.nome_interno}' pertence a outro grupo, não a "
            f"'{linha_grupo.nome_interno}' — a linha deste grupo no plano.",
        )
    _validar_metas(session, dados.metas)

    linha = PlanoMidiaAnuncio(
        plano_midia_grupo_id=linha_grupo.id,
        anuncio_id=anuncio.id,
        nome_interno=anuncio.nome_interno,
        match_id=anuncio.match_id,
        nomenclatura=_ultima_nomenclatura(session, Nivel.ANUNCIO, anuncio.id),
        valor=_calcular_valor(linha_grupo.valor, dados),
        metas=dados.metas,
    )
    session.add(linha)
    session.commit()
    return _montar_anuncio_ler(
        linha, linha_grupo.valor, _ultima_nomenclatura(session, Nivel.ANUNCIO, anuncio.id)
    )


@router.patch(
    "/{plano_id}/campanhas/{linha_campanha_id}/grupos/{linha_grupo_id}/anuncios/{linha_anuncio_id}",
    response_model=AnuncioDoPlanoLer,
)
def atualizar_anuncio(
    plano_id: UUID,
    linha_campanha_id: UUID,
    linha_grupo_id: UUID,
    linha_anuncio_id: UUID,
    dados: AnuncioDoPlanoAtualizar,
    session: Session = Depends(get_session),
):
    linha_grupo = _obter_linha_grupo_ou_404(session, plano_id, linha_campanha_id, linha_grupo_id)
    linha = _obter_linha_anuncio_ou_404(
        session, plano_id, linha_campanha_id, linha_grupo_id, linha_anuncio_id
    )
    linha.valor = _calcular_valor(linha_grupo.valor, dados)
    if dados.metas is not None:
        _validar_metas(session, dados.metas)
        linha.metas = dados.metas
    _sincronizar_nomenclatura_se_pedido(session, linha, Nivel.ANUNCIO, linha.anuncio_id, dados)
    session.commit()
    return _montar_anuncio_ler(
        linha, linha_grupo.valor, _ultima_nomenclatura(session, Nivel.ANUNCIO, linha.anuncio_id)
    )


@router.delete(
    "/{plano_id}/campanhas/{linha_campanha_id}/grupos/{linha_grupo_id}/anuncios/{linha_anuncio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_anuncio(
    plano_id: UUID,
    linha_campanha_id: UUID,
    linha_grupo_id: UUID,
    linha_anuncio_id: UUID,
    session: Session = Depends(get_session),
):
    linha = _obter_linha_anuncio_ou_404(
        session, plano_id, linha_campanha_id, linha_grupo_id, linha_anuncio_id
    )
    session.delete(linha)
    session.commit()
