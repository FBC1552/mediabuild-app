"""Ponte entre o banco e o motor puro.

O motor não conhece SQLAlchemy. Estas funções leem as tabelas e devolvem
as estruturas simples que ele espera — é aqui que a Fase 3 vai plugar a API.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    DicionarioAbreviacao,
    LimitePlataforma,
    Nivel,
    TemplateTaxonomia,
)
from app.plataformas import MARCADOR_AUSENCIA_PADRAO
from app.taxonomia.tipos import Dicionario, Template


def carregar_template(session: Session, plataforma_id: uuid.UUID, nivel: Nivel) -> Template | None:
    """Template ativo de maior versão para (plataforma, nível)."""
    registro = session.scalar(
        select(TemplateTaxonomia)
        .where(
            TemplateTaxonomia.plataforma_id == plataforma_id,
            TemplateTaxonomia.nivel == nivel,
            TemplateTaxonomia.ativo.is_(True),
        )
        .order_by(TemplateTaxonomia.versao.desc())
        .limit(1)
    )
    if registro is None:
        return None
    return Template.de_registro(
        separador=registro.separador,
        tokens=registro.tokens,
        versao=registro.versao,
        marcador_ausencia=registro.marcador_ausencia,
    )


def carregar_dicionario(session: Session, plataforma_id: uuid.UUID) -> Dicionario:
    """Abreviações globais somadas às da plataforma.

    As da plataforma são carregadas por último de propósito: sobrescrevem
    a global quando o mesmo (categoria, termo) existe nos dois escopos.
    """
    registros = session.scalars(
        select(DicionarioAbreviacao)
        .where(
            or_(
                DicionarioAbreviacao.plataforma_id.is_(None),
                DicionarioAbreviacao.plataforma_id == plataforma_id,
            )
        )
        .order_by(DicionarioAbreviacao.plataforma_id.is_(None).desc())
    )
    return Dicionario((r.categoria, r.termo, r.abreviacao) for r in registros)


def carregar_marcadores_ausencia(session: Session) -> list[str]:
    """Marcadores de ausência em uso, mais o padrão do produto (D-011).

    O padrão entra mesmo que nenhum template ativo o use: um template pode
    ser promovido para `NA` a qualquer `UPDATE` ou pelo próximo seed, e uma
    abreviação `NA` cadastrada na janela entre as duas coisas tornaria o
    nome ambíguo sem que ninguém tivesse errado nada.

    Marcador vazio é descartado: `''` significa 'o token some do nome', o
    comportamento anterior ao D-011, e não reserva texto nenhum.
    """
    em_uso = session.scalars(
        select(TemplateTaxonomia.marcador_ausencia)
        .where(TemplateTaxonomia.ativo.is_(True))
        .distinct()
    ).all()

    marcadores = {MARCADOR_AUSENCIA_PADRAO}
    marcadores.update(m for m in em_uso if m)
    return sorted(marcadores)


def carregar_limite(session: Session, plataforma_id: uuid.UUID, nivel: Nivel) -> int | None:
    return session.scalar(
        select(LimitePlataforma.limite_caracteres).where(
            LimitePlataforma.plataforma_id == plataforma_id,
            LimitePlataforma.nivel == nivel,
        )
    )
