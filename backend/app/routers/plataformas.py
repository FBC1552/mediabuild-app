"""Plataformas, seus limites e templates."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import LimitePlataforma, Nivel, Plataforma, TemplateTaxonomia
from app.plataformas import criar_plataforma, niveis_faltando
from app.schemas import (
    LimiteAtualizar,
    LimiteLer,
    PlataformaAtualizar,
    PlataformaCriar,
    PlataformaLer,
    TemplateCriar,
    TemplateLer,
)
from app.taxonomia.tipos import Template, parse_tokens

router = APIRouter(prefix="/plataformas", tags=["plataformas"])


def buscar_plataforma(session: Session, plataforma_id: UUID) -> Plataforma:
    plataforma = session.get(Plataforma, plataforma_id)
    if plataforma is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plataforma não encontrada.")
    return plataforma


@router.get("", response_model=list[PlataformaLer])
def listar(apenas_ativas: bool = False, session: Session = Depends(get_session)):
    consulta = select(Plataforma).order_by(Plataforma.nome)
    if apenas_ativas:
        consulta = consulta.where(Plataforma.ativo.is_(True))
    return session.scalars(consulta).all()


@router.post("", response_model=PlataformaLer, status_code=status.HTTP_201_CREATED)
def criar(dados: PlataformaCriar, session: Session = Depends(get_session)):
    """Cria a plataforma já com template e limite para os três níveis (D-007)."""
    plataforma = criar_plataforma(
        session,
        nome=dados.nome,
        sigla=dados.sigla,
        limites=dados.limites,
        campos_extras=dados.campos_extras,
        separador=dados.separador,
    )
    session.commit()
    return plataforma


@router.get("/{plataforma_id}", response_model=PlataformaLer)
def obter(plataforma_id: UUID, session: Session = Depends(get_session)):
    return buscar_plataforma(session, plataforma_id)


@router.patch("/{plataforma_id}", response_model=PlataformaLer)
def atualizar(
    plataforma_id: UUID, dados: PlataformaAtualizar, session: Session = Depends(get_session)
):
    plataforma = buscar_plataforma(session, plataforma_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(plataforma, campo, valor)
    session.commit()
    return plataforma


@router.delete("/{plataforma_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(plataforma_id: UUID, session: Session = Depends(get_session)):
    """Bloqueado pelo banco (`ondelete=RESTRICT`) se houver campanhas."""
    plataforma = buscar_plataforma(session, plataforma_id)
    session.delete(plataforma)
    session.commit()


@router.get("/{plataforma_id}/integridade")
def integridade(plataforma_id: UUID, session: Session = Depends(get_session)):
    """Diagnóstico do invariante D-007: todos os níveis têm template e limite?"""
    plataforma = buscar_plataforma(session, plataforma_id)
    faltando = niveis_faltando(session, plataforma)
    return {
        "completa": not faltando,
        "faltando": {chave: [n.value for n in niveis] for chave, niveis in faltando.items()},
    }


# --------------------------------------------------------------------------
# limites
# --------------------------------------------------------------------------

@router.get("/{plataforma_id}/limites", response_model=list[LimiteLer])
def listar_limites(plataforma_id: UUID, session: Session = Depends(get_session)):
    buscar_plataforma(session, plataforma_id)
    return session.scalars(
        select(LimitePlataforma).where(LimitePlataforma.plataforma_id == plataforma_id)
    ).all()


@router.put("/{plataforma_id}/limites/{nivel}", response_model=LimiteLer)
def atualizar_limite(
    plataforma_id: UUID,
    nivel: Nivel,
    dados: LimiteAtualizar,
    session: Session = Depends(get_session),
):
    buscar_plataforma(session, plataforma_id)
    limite = session.scalar(
        select(LimitePlataforma).where(
            LimitePlataforma.plataforma_id == plataforma_id, LimitePlataforma.nivel == nivel
        )
    )
    if limite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Limite não encontrado para esse nível.")
    limite.limite_caracteres = dados.limite_caracteres
    session.commit()
    return limite


# --------------------------------------------------------------------------
# templates
# --------------------------------------------------------------------------

@router.get("/{plataforma_id}/templates", response_model=list[TemplateLer])
def listar_templates(
    plataforma_id: UUID, nivel: Nivel | None = None, session: Session = Depends(get_session)
):
    buscar_plataforma(session, plataforma_id)
    consulta = select(TemplateTaxonomia).where(TemplateTaxonomia.plataforma_id == plataforma_id)
    if nivel is not None:
        consulta = consulta.where(TemplateTaxonomia.nivel == nivel)
    return session.scalars(consulta.order_by(TemplateTaxonomia.versao.desc())).all()


@router.post(
    "/{plataforma_id}/templates/{nivel}",
    response_model=TemplateLer,
    status_code=status.HTTP_201_CREATED,
)
def nova_versao_de_template(
    plataforma_id: UUID,
    nivel: Nivel,
    dados: TemplateCriar,
    session: Session = Depends(get_session),
):
    """Publica uma nova versão e desativa a anterior.

    Versões antigas são preservadas: `taxonomias_geradas.template_versao`
    aponta para elas, e o histórico precisa continuar explicável.
    """
    buscar_plataforma(session, plataforma_id)
    # Valida antes de gravar; erro de template vira 422 e não 500. O
    # `Template` completo é construído de propósito: é ele que recusa
    # marcador contendo o separador.
    Template(
        separador=dados.separador,
        tokens=parse_tokens(dados.tokens),
        marcador_ausencia=dados.marcador_ausencia,
    )

    anteriores = session.scalars(
        select(TemplateTaxonomia).where(
            TemplateTaxonomia.plataforma_id == plataforma_id, TemplateTaxonomia.nivel == nivel
        )
    ).all()
    proxima_versao = max((t.versao for t in anteriores), default=0) + 1
    for anterior in anteriores:
        anterior.ativo = False

    template = TemplateTaxonomia(
        plataforma_id=plataforma_id,
        nivel=nivel,
        separador=dados.separador,
        tokens=dados.tokens,
        marcador_ausencia=dados.marcador_ausencia,
        versao=proxima_versao,
        ativo=True,
    )
    session.add(template)
    session.commit()
    return template
