"""Catálogo de métricas que podem receber meta num anúncio do plano.

CRUD simples, no mesmo espírito de `app/routers/dicionario.py`: acrescentar,
renomear ou desativar uma métrica não pode exigir um desenvolvedor nem uma
migration (ver docstring de `app/models/plano_midia.py::Metrica`).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Metrica
from app.schemas import MetricaAtualizar, MetricaCriar, MetricaLer

router = APIRouter(prefix="/metricas", tags=["métricas"])


@router.get("", response_model=list[MetricaLer])
def listar(incluir_inativas: bool = False, session: Session = Depends(get_session)):
    consulta = select(Metrica).order_by(Metrica.ordem, Metrica.codigo)
    if not incluir_inativas:
        consulta = consulta.where(Metrica.ativo.is_(True))
    return session.scalars(consulta).all()


@router.post("", response_model=MetricaLer, status_code=status.HTTP_201_CREATED)
def criar(dados: MetricaCriar, session: Session = Depends(get_session)):
    metrica = Metrica(**dados.model_dump())
    session.add(metrica)
    session.commit()
    return metrica


@router.patch("/{metrica_id}", response_model=MetricaLer)
def atualizar(metrica_id: UUID, dados: MetricaAtualizar, session: Session = Depends(get_session)):
    metrica = session.get(Metrica, metrica_id)
    if metrica is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Métrica não encontrada.")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(metrica, campo, valor)
    session.commit()
    return metrica


@router.delete("/{metrica_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(metrica_id: UUID, session: Session = Depends(get_session)):
    """Remoção definitiva do catálogo. Planos que já gravaram metas com este
    código continuam com o valor no JSONB — não há foreign key para
    apagar em cascata (ver docstring de `Metrica`). Para só parar de
    oferecer a métrica em metas novas sem perder o histórico do rótulo,
    prefira `PATCH` com `ativo=false`."""
    metrica = session.get(Metrica, metrica_id)
    if metrica is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Métrica não encontrada.")
    session.delete(metrica)
    session.commit()
