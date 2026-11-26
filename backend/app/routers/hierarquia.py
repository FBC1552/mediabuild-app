"""Campanhas, grupos de anúncio e anúncios.

Os três têm a mesma forma, então compartilham o helper `_crud`. O `match_id`
é sempre gerado pelo servidor (D-006) e nunca aceito do cliente.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Anuncio, Campanha, GrupoAnuncio, Nivel, TaxonomiaGerada
from app.schemas import (
    AnuncioCriar,
    AnuncioLer,
    CampanhaCriar,
    CampanhaLer,
    EntidadeAtualizar,
    GrupoCriar,
    GrupoLer,
    NoDaArvore,
)
from app.taxonomia.match_id import gerar_match_id

router = APIRouter(tags=["hierarquia"])


def _obter(session: Session, modelo, entidade_id: UUID, rotulo: str):
    entidade = session.get(modelo, entidade_id)
    if entidade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{rotulo} não encontrado(a).")
    return entidade


def _ultimas_taxonomias(
    session: Session, nivel: Nivel, entidade_ids: list[UUID]
) -> dict[UUID, TaxonomiaGerada]:
    """Nomenclatura mais recente de cada entidade, em uma consulta só.

    Uma consulta por filho seria N+1 numa tela que existe justamente para
    listar muitos filhos. A varredura desce por `criado_em` e o primeiro
    registro de cada entidade vence, então o dicionário fica com o mais
    recente sem precisar de janela.

    `criado_em` vem de `now()`, que no Postgres é o instante de início da
    transação: duas gerações da mesma entidade dentro da mesma transação
    empatam. Na prática cada geração é uma requisição, logo uma transação —
    o empate só aparece em teste, e nenhuma das duas é 'errada', já que
    nomenclatura gerada é imutável e ambas continuam no histórico (D-004).
    """
    if not entidade_ids:
        return {}

    ultimas: dict[UUID, TaxonomiaGerada] = {}
    for taxonomia in session.scalars(
        select(TaxonomiaGerada)
        .where(
            TaxonomiaGerada.nivel == nivel,
            TaxonomiaGerada.entidade_id.in_(entidade_ids),
        )
        .order_by(TaxonomiaGerada.criado_em.desc())
    ):
        ultimas.setdefault(taxonomia.entidade_id, taxonomia)
    return ultimas


def _montar_nos(entidades, pai: str, ultimas: dict[UUID, TaxonomiaGerada]) -> list[NoDaArvore]:
    nos: list[NoDaArvore] = []
    for entidade in entidades:
        taxonomia = ultimas.get(entidade.id)
        nos.append(
            NoDaArvore(
                id=entidade.id,
                pai_id=getattr(entidade, pai),
                nome_interno=entidade.nome_interno,
                match_id=entidade.match_id,
                nomenclatura=taxonomia.nomenclatura_final if taxonomia else None,
                taxonomia_id=taxonomia.id if taxonomia else None,
                gerado_em=taxonomia.criado_em if taxonomia else None,
                criado_em=entidade.criado_em,
            )
        )
    return nos


def _atualizar(session: Session, entidade, dados: EntidadeAtualizar):
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(entidade, campo, valor)
    session.commit()
    return entidade


# --------------------------------------------------------------------------
# campanhas
# --------------------------------------------------------------------------

@router.get("/campanhas", response_model=list[CampanhaLer])
def listar_campanhas(plataforma_id: UUID | None = None, session: Session = Depends(get_session)):
    consulta = select(Campanha).order_by(Campanha.criado_em.desc())
    if plataforma_id is not None:
        consulta = consulta.where(Campanha.plataforma_id == plataforma_id)
    return session.scalars(consulta).all()


@router.post("/campanhas", response_model=CampanhaLer, status_code=status.HTTP_201_CREATED)
def criar_campanha(dados: CampanhaCriar, session: Session = Depends(get_session)):
    campanha = Campanha(
        plataforma_id=dados.plataforma_id,
        nome_interno=dados.nome_interno,
        campos=dados.campos,
        match_id=gerar_match_id(session, Nivel.CAMPANHA),
    )
    session.add(campanha)
    session.commit()
    return campanha


@router.get("/campanhas/{campanha_id}", response_model=CampanhaLer)
def obter_campanha(campanha_id: UUID, session: Session = Depends(get_session)):
    return _obter(session, Campanha, campanha_id, "Campanha")


@router.get("/campanhas/{campanha_id}/grupos", response_model=list[NoDaArvore])
def grupos_da_campanha(campanha_id: UUID, session: Session = Depends(get_session)):
    """Filhos de uma campanha, com a nomenclatura mais recente de cada um.

    Existe para a árvore da hierarquia: `GET /grupos?campanha_id=` já
    filtrava, mas devolvia só as colunas da entidade, e a tela precisaria
    de uma requisição por grupo para descobrir se ele já tem nome.
    """
    _obter(session, Campanha, campanha_id, "Campanha")
    grupos = session.scalars(
        select(GrupoAnuncio)
        .where(GrupoAnuncio.campanha_id == campanha_id)
        .order_by(GrupoAnuncio.criado_em)
    ).all()
    ultimas = _ultimas_taxonomias(session, Nivel.GRUPO, [g.id for g in grupos])
    return _montar_nos(grupos, "campanha_id", ultimas)


@router.patch("/campanhas/{campanha_id}", response_model=CampanhaLer)
def atualizar_campanha(
    campanha_id: UUID, dados: EntidadeAtualizar, session: Session = Depends(get_session)
):
    """Editar os campos **não** altera taxonomias já geradas (D-004);
    gera-se uma nova, e a antiga permanece no histórico."""
    return _atualizar(session, _obter(session, Campanha, campanha_id, "Campanha"), dados)


@router.delete("/campanhas/{campanha_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_campanha(campanha_id: UUID, session: Session = Depends(get_session)):
    session.delete(_obter(session, Campanha, campanha_id, "Campanha"))
    session.commit()


# --------------------------------------------------------------------------
# grupos de anúncio
# --------------------------------------------------------------------------

@router.get("/grupos", response_model=list[GrupoLer])
def listar_grupos(campanha_id: UUID | None = None, session: Session = Depends(get_session)):
    consulta = select(GrupoAnuncio).order_by(GrupoAnuncio.criado_em.desc())
    if campanha_id is not None:
        consulta = consulta.where(GrupoAnuncio.campanha_id == campanha_id)
    return session.scalars(consulta).all()


@router.post("/grupos", response_model=GrupoLer, status_code=status.HTTP_201_CREATED)
def criar_grupo(dados: GrupoCriar, session: Session = Depends(get_session)):
    grupo = GrupoAnuncio(
        campanha_id=dados.campanha_id,
        nome_interno=dados.nome_interno,
        campos=dados.campos,
        match_id=gerar_match_id(session, Nivel.GRUPO),
    )
    session.add(grupo)
    session.commit()
    return grupo


@router.get("/grupos/{grupo_id}", response_model=GrupoLer)
def obter_grupo(grupo_id: UUID, session: Session = Depends(get_session)):
    return _obter(session, GrupoAnuncio, grupo_id, "Grupo de anúncio")


@router.get("/grupos/{grupo_id}/anuncios", response_model=list[NoDaArvore])
def anuncios_do_grupo(grupo_id: UUID, session: Session = Depends(get_session)):
    """Filhos de um grupo, com a nomenclatura mais recente de cada um."""
    _obter(session, GrupoAnuncio, grupo_id, "Grupo de anúncio")
    anuncios = session.scalars(
        select(Anuncio)
        .where(Anuncio.grupo_anuncio_id == grupo_id)
        .order_by(Anuncio.criado_em)
    ).all()
    ultimas = _ultimas_taxonomias(session, Nivel.ANUNCIO, [a.id for a in anuncios])
    return _montar_nos(anuncios, "grupo_anuncio_id", ultimas)


@router.patch("/grupos/{grupo_id}", response_model=GrupoLer)
def atualizar_grupo(
    grupo_id: UUID, dados: EntidadeAtualizar, session: Session = Depends(get_session)
):
    return _atualizar(session, _obter(session, GrupoAnuncio, grupo_id, "Grupo de anúncio"), dados)


@router.delete("/grupos/{grupo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_grupo(grupo_id: UUID, session: Session = Depends(get_session)):
    session.delete(_obter(session, GrupoAnuncio, grupo_id, "Grupo de anúncio"))
    session.commit()


# --------------------------------------------------------------------------
# anúncios
# --------------------------------------------------------------------------

@router.get("/anuncios", response_model=list[AnuncioLer])
def listar_anuncios(grupo_id: UUID | None = None, session: Session = Depends(get_session)):
    consulta = select(Anuncio).order_by(Anuncio.criado_em.desc())
    if grupo_id is not None:
        consulta = consulta.where(Anuncio.grupo_anuncio_id == grupo_id)
    return session.scalars(consulta).all()


@router.post("/anuncios", response_model=AnuncioLer, status_code=status.HTTP_201_CREATED)
def criar_anuncio(dados: AnuncioCriar, session: Session = Depends(get_session)):
    anuncio = Anuncio(
        grupo_anuncio_id=dados.grupo_anuncio_id,
        nome_interno=dados.nome_interno,
        campos=dados.campos,
        match_id=gerar_match_id(session, Nivel.ANUNCIO),
    )
    session.add(anuncio)
    session.commit()
    return anuncio


@router.get("/anuncios/{anuncio_id}", response_model=AnuncioLer)
def obter_anuncio(anuncio_id: UUID, session: Session = Depends(get_session)):
    return _obter(session, Anuncio, anuncio_id, "Anúncio")


@router.patch("/anuncios/{anuncio_id}", response_model=AnuncioLer)
def atualizar_anuncio(
    anuncio_id: UUID, dados: EntidadeAtualizar, session: Session = Depends(get_session)
):
    return _atualizar(session, _obter(session, Anuncio, anuncio_id, "Anúncio"), dados)


@router.delete("/anuncios/{anuncio_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_anuncio(anuncio_id: UUID, session: Session = Depends(get_session)):
    session.delete(_obter(session, Anuncio, anuncio_id, "Anúncio"))
    session.commit()
