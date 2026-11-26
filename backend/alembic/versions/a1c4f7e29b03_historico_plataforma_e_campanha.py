"""historico: plataforma_id e campanha_id denormalizados

Revision ID: a1c4f7e29b03
Revises: 836b731d3739
Create Date: 2026-08-03 23:50:00.000000

A tela de histórico filtra por plataforma e por campanha. Sem estas
colunas, o filtro precisaria de três subconsultas polimórficas por
requisição (uma por nível) e pararia de funcionar assim que a entidade
fosse apagada — e o histórico sobrevive à entidade de propósito (D-004).

Sem foreign key, pelo mesmo motivo que `entidade_id` não tem: apagar uma
campanha não pode apagar o registro do nome que já subiu numa plataforma
de anúncios.

Escrita à mão em vez de autogenerate: o backfill precisa subir a
hierarquia (anúncio -> grupo -> campanha -> plataforma), o que o
autogenerate não infere.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4f7e29b03"
down_revision: str | None = "836b731d3739"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "taxonomias_geradas",
        sa.Column("plataforma_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "taxonomias_geradas",
        sa.Column("campanha_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Backfill por nível, subindo a hierarquia a partir de entidade_id.
    op.execute(
        """
        UPDATE taxonomias_geradas t
           SET campanha_id = c.id, plataforma_id = c.plataforma_id
          FROM campanhas c
         WHERE t.nivel = 'CAMPANHA' AND t.entidade_id = c.id
        """
    )
    op.execute(
        """
        UPDATE taxonomias_geradas t
           SET campanha_id = c.id, plataforma_id = c.plataforma_id
          FROM grupos_anuncio g
          JOIN campanhas c ON c.id = g.campanha_id
         WHERE t.nivel = 'GRUPO' AND t.entidade_id = g.id
        """
    )
    op.execute(
        """
        UPDATE taxonomias_geradas t
           SET campanha_id = c.id, plataforma_id = c.plataforma_id
          FROM anuncios a
          JOIN grupos_anuncio g ON g.id = a.grupo_anuncio_id
          JOIN campanhas c ON c.id = g.campanha_id
         WHERE t.nivel = 'ANUNCIO' AND t.entidade_id = a.id
        """
    )

    op.create_index(
        "ix_taxonomia_plataforma", "taxonomias_geradas", ["plataforma_id", "criado_em"]
    )
    op.create_index("ix_taxonomia_campanha", "taxonomias_geradas", ["campanha_id"])


def downgrade() -> None:
    op.drop_index("ix_taxonomia_campanha", table_name="taxonomias_geradas")
    op.drop_index("ix_taxonomia_plataforma", table_name="taxonomias_geradas")
    op.drop_column("taxonomias_geradas", "campanha_id")
    op.drop_column("taxonomias_geradas", "plataforma_id")
