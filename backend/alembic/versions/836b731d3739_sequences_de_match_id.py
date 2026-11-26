"""sequences de match id

Revision ID: 836b731d3739
Revises: 84339e0f86c0
Create Date: 2026-08-01 22:20:10.917209

D-006: match ID sequencial por nível (C0001, G0001, A0001). Uma sequence
por nível garante unicidade sem race condition, ao contrário de um
SELECT max()+1 concorrente.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '836b731d3739'
down_revision: str | None = '84339e0f86c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEQUENCES = ("seq_match_campanha", "seq_match_grupo", "seq_match_anuncio")


def upgrade() -> None:
    for nome in SEQUENCES:
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {nome} START WITH 1 INCREMENT BY 1")


def downgrade() -> None:
    for nome in SEQUENCES:
        op.execute(f"DROP SEQUENCE IF EXISTS {nome}")
