"""templates: marcador de ausencia para campo opcional

Revision ID: c3f81a6b47d9
Revises: b7d2c9114a55
Create Date: 2026-08-05 00:20:00.000000

Um campo opcional deixado em branco desaparecia do nome. Consequência: dois
anúncios do mesmo nível saíam com quantidade de partes diferente, e as
colunas da planilha de performance deslocavam de uma linha para a outra —
o cruzamento que este produto existe para proteger.

Agora o lugar é ocupado por um marcador. Ele vive no template, e não no
código, porque é padrão de nomenclatura: trocar 'NA' por outra coisa
precisa ser um UPDATE (D-008).

**O default aqui é `''`, não `'NA'`, e isso é deliberado.** As linhas
existentes descrevem templates sob os quais nomes já foram gerados sem
marcador; escrever 'NA' nelas mudaria retroativamente o significado de uma
versão de template e tornaria os nomes antigos inexplicáveis pelo
`template_versao` que guardaram (D-004). `''` preserva o comportamento
antigo. Quem promove o padrão para 'NA' é `app/seed.py::sincronizar_templates()`,
criando a **versão seguinte** e desativando a anterior — rode
`python -m app.seed` depois deste upgrade.

O default da coluna passa a 'NA' logo em seguida, para que template criado
daqui em diante já nasça com marcador.

Não toca o enum `nivel`, então dispensa o conserto de 84339e0f86c0.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f81a6b47d9"
down_revision: str | None = "b7d2c9114a55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Passo 1: nasce com '' para que as versões já existentes continuem
    # significando o que significavam.
    op.add_column(
        "templates_taxonomia",
        sa.Column(
            "marcador_ausencia",
            sa.String(length=10),
            nullable=False,
            server_default="",
        ),
    )
    # Passo 2: o default para os próximos INSERTs é o marcador de verdade.
    op.alter_column("templates_taxonomia", "marcador_ausencia", server_default="NA")


def downgrade() -> None:
    op.drop_column("templates_taxonomia", "marcador_ausencia")
