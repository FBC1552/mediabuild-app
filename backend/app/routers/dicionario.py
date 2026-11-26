"""Dicionário De → Para das abreviações.

Existe como CRUD para que adicionar um termo não exija desenvolvedor —
é a saída que a mensagem de erro do D-005 oferece ao analista.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import DicionarioAbreviacao
from app.schemas import AbreviacaoAtualizar, AbreviacaoCriar, AbreviacaoLer
from app.taxonomia import AbreviacaoReservada, normalizar
from app.taxonomia.repositorio import carregar_marcadores_ausencia

router = APIRouter(prefix="/dicionario", tags=["dicionário"])

# O separador é irrelevante aqui — abreviação não tem espaço. Serve só para
# chamar `normalizar` na mesma forma que o motor usa ao montar o nome, que é
# o que torna a comparação fiel ao que sairia gravado.
_SEPARADOR = "_"


def _recusar_marcador(session: Session, abreviacao: str) -> None:
    """D-011: uma abreviação não pode **ser** um marcador de ausência.

    Igualdade exata sobre a forma normalizada, nunca 'contém': o marcador
    ocupa a posição de um campo em branco, então só o texto idêntico cria a
    ambiguidade. 'NOR' e 'NOV' passam; 'na', 'Na' e ' NA ' não, porque
    todos os três chegariam ao nome como 'NA'.
    """
    marcadores = carregar_marcadores_ausencia(session)
    if normalizar(abreviacao, _SEPARADOR) in marcadores:
        raise AbreviacaoReservada(abreviacao, marcadores)


@router.get("", response_model=list[AbreviacaoLer])
def listar(
    categoria: str | None = None,
    plataforma_id: UUID | None = None,
    incluir_globais: bool = True,
    session: Session = Depends(get_session),
):
    """Filtrando por plataforma, traz também as globais por padrão — que é
    o conjunto que o motor enxerga ao gerar um nome."""
    consulta = select(DicionarioAbreviacao)

    if categoria is not None:
        consulta = consulta.where(DicionarioAbreviacao.categoria == categoria)

    if plataforma_id is not None:
        if incluir_globais:
            consulta = consulta.where(
                or_(
                    DicionarioAbreviacao.plataforma_id == plataforma_id,
                    DicionarioAbreviacao.plataforma_id.is_(None),
                )
            )
        else:
            consulta = consulta.where(DicionarioAbreviacao.plataforma_id == plataforma_id)

    return session.scalars(
        consulta.order_by(DicionarioAbreviacao.categoria, DicionarioAbreviacao.termo)
    ).all()


@router.get("/categorias", response_model=list[str])
def listar_categorias(session: Session = Depends(get_session)):
    return list(
        session.scalars(
            select(DicionarioAbreviacao.categoria)
            .distinct()
            .order_by(DicionarioAbreviacao.categoria)
        ).all()
    )


@router.post("", response_model=AbreviacaoLer, status_code=status.HTTP_201_CREATED)
def criar(dados: AbreviacaoCriar, session: Session = Depends(get_session)):
    _recusar_marcador(session, dados.abreviacao)
    abreviacao = DicionarioAbreviacao(**dados.model_dump())
    session.add(abreviacao)
    session.commit()
    return abreviacao


@router.patch("/{abreviacao_id}", response_model=AbreviacaoLer)
def atualizar(
    abreviacao_id: UUID, dados: AbreviacaoAtualizar, session: Session = Depends(get_session)
):
    registro = session.get(DicionarioAbreviacao, abreviacao_id)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Abreviação não encontrada.")
    # A trava vale também na edição: cadastrar 'NAC' e depois corrigir para
    # 'NA' chegaria ao mesmo nome ambíguo pela porta dos fundos.
    _recusar_marcador(session, dados.abreviacao)
    registro.abreviacao = dados.abreviacao
    session.commit()
    return registro


@router.delete("/{abreviacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(abreviacao_id: UUID, session: Session = Depends(get_session)):
    registro = session.get(DicionarioAbreviacao, abreviacao_id)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Abreviação não encontrada.")
    session.delete(registro)
    session.commit()
