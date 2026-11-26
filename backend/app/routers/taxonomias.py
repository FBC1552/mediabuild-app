"""Geração de nomenclaturas.

Não há PATCH nem DELETE aqui, de propósito: taxonomia gerada é imutável
(D-004). Editar a entidade e gerar de novo cria um registro novo; o antigo
continua no histórico, porque o nome pode já estar rodando numa plataforma
de anúncios.
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.exportacao import gerar_planilha, montar_linhas
from app.models import Anuncio, Campanha, GrupoAnuncio, Nivel, TaxonomiaGerada
from app.schemas import (
    PreviewPedido,
    PreviewResposta,
    TaxonomiaCriar,
    TaxonomiaHistoricoLer,
    TaxonomiaLer,
)
from app.taxonomia import gerar_detalhado, gerar_nomenclatura
from app.taxonomia.repositorio import (
    carregar_dicionario,
    carregar_limite,
    carregar_template,
)
from app.tempo import fim_do_intervalo, inicio_do_intervalo

router = APIRouter(prefix="/taxonomias", tags=["taxonomias"])

# Mesmo tamanho de um match ID real, para que a checagem de limite no
# preview seja fiel. O prefixo indica o nível.
_PLACEHOLDER = {Nivel.CAMPANHA: "C0000", Nivel.GRUPO: "G0000", Nivel.ANUNCIO: "A0000"}


def _resolver_entidade(session: Session, nivel: Nivel, entidade_id: UUID):
    """Devolve (entidade, plataforma_id, campanha_id) do nível pedido."""
    if nivel is Nivel.CAMPANHA:
        campanha = session.get(Campanha, entidade_id)
        if campanha is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campanha não encontrada.")
        return campanha, campanha.plataforma_id, campanha.id

    if nivel is Nivel.GRUPO:
        grupo = session.get(GrupoAnuncio, entidade_id)
        if grupo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Grupo de anúncio não encontrado.")
        return grupo, grupo.campanha.plataforma_id, grupo.campanha_id

    anuncio = session.get(Anuncio, entidade_id)
    if anuncio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anúncio não encontrado.")
    return anuncio, anuncio.grupo.campanha.plataforma_id, anuncio.grupo.campanha_id


def _template_ou_404(session: Session, plataforma_id: UUID, nivel: Nivel):
    template = carregar_template(session, plataforma_id, nivel)
    if template is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Não há template ativo para o nível {nivel.value} nessa plataforma. "
            "Cadastre um antes de gerar nomenclaturas.",
        )
    return template


@router.post("/preview", response_model=PreviewResposta)
def preview(dados: PreviewPedido, session: Session = Depends(get_session)):
    """Gera **sem persistir**. É o que alimenta o preview ao vivo do formulário.

    Não consome match ID: sem um informado, usa um placeholder de mesmo
    tamanho, para não queimar a sequência a cada tecla digitada.
    """
    template = _template_ou_404(session, dados.plataforma_id, dados.nivel)
    dicionario = carregar_dicionario(session, dados.plataforma_id)
    limite = carregar_limite(session, dados.plataforma_id, dados.nivel)

    provisorio = dados.match_id is None
    match_id = dados.match_id or _PLACEHOLDER[dados.nivel]

    nomenclatura = gerar_nomenclatura(template, dados.campos, dicionario, match_id, limite)

    return PreviewResposta(
        nomenclatura=nomenclatura,
        match_id_provisorio=provisorio,
        template_versao=template.versao,
        limite_caracteres=limite,
        caracteres=len(nomenclatura),
    )


@router.post("", response_model=TaxonomiaLer, status_code=status.HTTP_201_CREATED)
def criar(dados: TaxonomiaCriar, session: Session = Depends(get_session)):
    """Gera e persiste, usando o match ID da própria entidade.

    Colisão de nomenclatura vira 409 pela UNIQUE em `nomenclatura_final` —
    é a proteção do cruzamento com as planilhas de performance.
    """
    entidade, plataforma_id, campanha_id = _resolver_entidade(
        session, dados.nivel, dados.entidade_id
    )
    template = _template_ou_404(session, plataforma_id, dados.nivel)
    dicionario = carregar_dicionario(session, plataforma_id)
    limite = carregar_limite(session, plataforma_id, dados.nivel)

    resultado = gerar_detalhado(
        template, entidade.campos, dicionario, entidade.match_id, limite
    )

    taxonomia = TaxonomiaGerada(
        nivel=dados.nivel,
        entidade_id=entidade.id,
        # Cópias denormalizadas: é o que faz o filtro do histórico sobreviver
        # à exclusão da entidade.
        plataforma_id=plataforma_id,
        campanha_id=campanha_id,
        nomenclatura_final=resultado.nomenclatura,
        # Nome já fatiado por campo. Como `plataforma_id` e `campanha_id`,
        # precisa ser preenchido por **todo** caminho de escrita — é o que
        # o analista cruza com a planilha de performance.
        campos_gerados=resultado.campos_para_json(),
        template_versao=template.versao,
        lote_id=dados.lote_id or uuid4(),
    )
    session.add(taxonomia)
    session.commit()
    return taxonomia


def _consulta_filtrada(
    nivel: Nivel | None = None,
    entidade_id: UUID | None = None,
    lote_id: UUID | None = None,
    plataforma_id: UUID | None = None,
    campanha_id: UUID | None = None,
    busca: str | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
):
    """Filtros compartilhados entre a listagem, o histórico e a exportação."""
    consulta = select(TaxonomiaGerada).order_by(TaxonomiaGerada.criado_em.desc())

    if nivel is not None:
        consulta = consulta.where(TaxonomiaGerada.nivel == nivel)
    if entidade_id is not None:
        consulta = consulta.where(TaxonomiaGerada.entidade_id == entidade_id)
    if lote_id is not None:
        consulta = consulta.where(TaxonomiaGerada.lote_id == lote_id)
    # As datas chegam como calendário ("2026-08-04") e `criado_em` é UTC.
    # A conversão é sempre para instante com fuso, para que a comparação
    # não dependa do `TimeZone` da sessão do Postgres nem do relógio do
    # servidor — ver `app/tempo.py`.
    if desde is not None:
        consulta = consulta.where(TaxonomiaGerada.criado_em >= inicio_do_intervalo(desde))
    if ate is not None:
        consulta = consulta.where(TaxonomiaGerada.criado_em <= fim_do_intervalo(ate))

    # Colunas denormalizadas: o filtro continua valendo depois que a
    # campanha for apagada, e não custa três subconsultas polimórficas.
    if plataforma_id is not None:
        consulta = consulta.where(TaxonomiaGerada.plataforma_id == plataforma_id)
    if campanha_id is not None:
        consulta = consulta.where(TaxonomiaGerada.campanha_id == campanha_id)

    if busca:
        consulta = consulta.where(TaxonomiaGerada.nomenclatura_final.ilike(f"%{busca}%"))

    return consulta


@router.get("", response_model=list[TaxonomiaLer])
def listar(
    nivel: Nivel | None = None,
    entidade_id: UUID | None = None,
    lote_id: UUID | None = None,
    plataforma_id: UUID | None = None,
    campanha_id: UUID | None = None,
    busca: str | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    limite: int = 100,
    session: Session = Depends(get_session),
):
    consulta = _consulta_filtrada(
        nivel, entidade_id, lote_id, plataforma_id, campanha_id, busca, desde, ate
    )
    return session.scalars(consulta.limit(limite)).all()


# `/historico` e `/export` precisam vir antes de `/{taxonomia_id}`, senão
# seriam interpretados como UUID e a rota devolveria 422.
@router.get("/historico", response_model=list[TaxonomiaHistoricoLer])
def historico(
    nivel: Nivel | None = None,
    lote_id: UUID | None = None,
    plataforma_id: UUID | None = None,
    campanha_id: UUID | None = None,
    busca: str | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    limite: int = 200,
    session: Session = Depends(get_session),
):
    """Histórico já resolvido: nome da plataforma, da campanha e os campos.

    A listagem crua (`GET /taxonomias`) devolve só as colunas da tabela e
    deixaria a tela fazendo uma requisição por linha para descobrir a
    plataforma. Aqui a resolução é em lote, pela mesma função que a
    exportação usa.
    """
    consulta = _consulta_filtrada(
        nivel=nivel,
        lote_id=lote_id,
        plataforma_id=plataforma_id,
        campanha_id=campanha_id,
        busca=busca,
        desde=desde,
        ate=ate,
    )
    taxonomias = session.scalars(consulta.limit(limite)).all()

    return [
        TaxonomiaHistoricoLer(
            id=linha.id,
            nivel=linha.nivel,
            nomenclatura_final=linha.nomenclatura,
            plataforma=linha.plataforma,
            campanha=linha.campanha,
            nome_interno=linha.nome_interno,
            match_id=linha.match_id,
            caracteres=len(linha.nomenclatura),
            template_versao=linha.template_versao,
            campos=linha.campos,
            campos_gerados=linha.campos_gerados or None,
            lote_id=linha.lote_id,
            criado_em=linha.criado_em,
        )
        for linha in montar_linhas(session, taxonomias)
    ]


@router.get("/export")
def exportar(
    nivel: Nivel | None = None,
    entidade_id: UUID | None = None,
    lote_id: UUID | None = None,
    plataforma_id: UUID | None = None,
    campanha_id: UUID | None = None,
    busca: str | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    limite: int = 5000,
    session: Session = Depends(get_session),
):
    """Baixa as taxonomias filtradas em `.xlsx`.

    Aceita os mesmos filtros de `GET /taxonomias`; sem nenhum, exporta tudo
    (até `limite`). A coluna "Nomenclatura" vem primeiro porque é a que o
    analista cola na plataforma de anúncios.
    """
    consulta = _consulta_filtrada(
        nivel, entidade_id, lote_id, plataforma_id, campanha_id, busca, desde, ate
    )
    taxonomias = session.scalars(consulta.limit(limite)).all()

    conteudo = gerar_planilha(montar_linhas(session, taxonomias))
    carimbo = datetime.now().strftime("%Y%m%d-%H%M")

    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mediabuild-{carimbo}.xlsx"'},
    )


@router.get("/{taxonomia_id}", response_model=TaxonomiaLer)
def obter(taxonomia_id: UUID, session: Session = Depends(get_session)):
    taxonomia = session.get(TaxonomiaGerada, taxonomia_id)
    if taxonomia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Taxonomia não encontrada.")
    return taxonomia
