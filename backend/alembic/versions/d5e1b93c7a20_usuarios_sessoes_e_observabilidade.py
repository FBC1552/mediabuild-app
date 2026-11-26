"""usuarios, sessoes e observabilidade de acesso (D-014)

Revision ID: d5e1b93c7a20
Revises: 83b359645ea6
Create Date: 2026-08-07

Resolve o D-003, que estava aberto desde o início do projeto: passa a
existir tabela `usuarios`, e com ela sessão, papel e trilha de acesso.

**Escrita à mão, não autogerada, por causa dos dois enums.** O autogenerate
do Alembic emite um `CREATE TYPE` por *tabela* que usa um enum — então
`papel_usuario` sairia duas vezes se duas tabelas o referenciassem — e
nunca emite o `DROP TYPE` no downgrade, o que faz o `upgrade` seguinte
falhar com "type already exists". É a mesma armadilha documentada em
`84339e0f86c0`, e o conserto é o mesmo: declarar o tipo com
`create_type=False`, criá-lo uma única vez com `checkfirst=True` no início
do upgrade, e dropá-lo no fim do downgrade.

Sobre o que NÃO tem foreign key aqui, e é de propósito:

- `eventos_acesso.usuario_id` — a trilha de quem entrou onde sobrevive à
  exclusão da conta. Com FK CASCADE, apagar o usuário apagaria o rastro
  dele junto, que é o oposto do que uma trilha de acesso serve.
- `eventos_erro.usuario_id` — mesma coisa.
- `sessoes.usuario_id` **tem** FK CASCADE, e a diferença é intencional:
  sessão não é histórico, é credencial viva. Excluir o usuário precisa
  derrubá-la no mesmo instante.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e1b93c7a20"
down_revision: str | None = "83b359645ea6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False nos dois: o ciclo de vida é controlado explicitamente
# abaixo, e não pelo primeiro CREATE TABLE que por acaso os mencionar.
papel_usuario = postgresql.ENUM(
    "basico", "pleno", "admin", name="papel_usuario", create_type=False
)
tipo_evento_acesso = postgresql.ENUM(
    "login_ok",
    "login_falha",
    "logout",
    "sessao_expirada",
    name="tipo_evento_acesso",
    create_type=False,
)


def upgrade() -> None:
    papel_usuario.create(op.get_bind(), checkfirst=True)
    tipo_evento_acesso.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("login", sa.String(length=60), nullable=False),
        sa.Column("senha_hash", sa.String(length=256), nullable=False),
        sa.Column("senha_salt", sa.String(length=64), nullable=False),
        sa.Column("papel", papel_usuario, nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ultimo_acesso_em", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login"),
    )

    op.create_table(
        "sessoes",
        sa.Column("id", sa.UUID(), nullable=False),
        # SHA-256 hexadecimal do token do cookie. O token em claro nunca
        # toca o banco: dump vazado não vira sessão viva.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("agente", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessao_usuario", "sessoes", ["usuario_id"], unique=False)
    op.create_index(
        "ix_sessao_expiracao", "sessoes", ["expira_em", "revogada_em"], unique=False
    )

    op.create_table(
        "eventos_acesso",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "ocorrido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("tipo", tipo_evento_acesso, nullable=False),
        sa.Column("login_tentado", sa.String(length=60), nullable=True),
        # Sem FK: ver docstring do módulo.
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("agente", sa.String(length=300), nullable=True),
        sa.Column("detalhe", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evento_acesso_ocorrido", "eventos_acesso", ["ocorrido_em"])
    op.create_index("ix_evento_acesso_tipo", "eventos_acesso", ["tipo", "ocorrido_em"])
    op.create_index("ix_evento_acesso_usuario", "eventos_acesso", ["usuario_id"])

    op.create_table(
        "eventos_erro",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "ocorrido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("metodo", sa.String(length=10), nullable=False),
        sa.Column("caminho", sa.String(length=400), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("codigo_erro", sa.String(length=60), nullable=True),
        sa.Column("mensagem", sa.Text(), nullable=True),
        # Sem FK: ver docstring do módulo.
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("duracao_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evento_erro_ocorrido", "eventos_erro", ["ocorrido_em"])
    op.create_index("ix_evento_erro_status", "eventos_erro", ["status", "ocorrido_em"])
    op.create_index("ix_evento_erro_request", "eventos_erro", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_evento_erro_request", table_name="eventos_erro")
    op.drop_index("ix_evento_erro_status", table_name="eventos_erro")
    op.drop_index("ix_evento_erro_ocorrido", table_name="eventos_erro")
    op.drop_table("eventos_erro")

    op.drop_index("ix_evento_acesso_usuario", table_name="eventos_acesso")
    op.drop_index("ix_evento_acesso_tipo", table_name="eventos_acesso")
    op.drop_index("ix_evento_acesso_ocorrido", table_name="eventos_acesso")
    op.drop_table("eventos_acesso")

    op.drop_index("ix_sessao_expiracao", table_name="sessoes")
    op.drop_index("ix_sessao_usuario", table_name="sessoes")
    op.drop_table("sessoes")

    op.drop_table("usuarios")

    # Os DROP TYPE são o conserto que o autogenerate não escreve. Sem eles,
    # `downgrade` seguido de `upgrade` falha com "type already exists" — e a
    # falha aparece só na segunda vez, o que a torna difícil de atribuir.
    tipo_evento_acesso.drop(op.get_bind(), checkfirst=True)
    papel_usuario.drop(op.get_bind(), checkfirst=True)
