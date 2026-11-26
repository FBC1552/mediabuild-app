"""historico: campos_gerados (nome ja fatiado por campo)

Revision ID: b7d2c9114a55
Revises: a1c4f7e29b03
Create Date: 2026-08-05 00:10:00.000000

Até aqui o histórico guardava só `nomenclatura_final`, um texto. O analista
precisa dos pedaços separados para cruzar com a planilha de performance, e
refatiar o nome pelo separador não serve: um valor que contenha o separador
(uma abreviação com espaço, por exemplo) tornaria a fatia ambígua.

`campos_gerados` guarda, por chave de campo, o valor bruto (o que foi
digitado) e o valor final (o que entrou no nome), mais a posição do token
no template — JSONB não preserva a ordem das chaves, então sem `ordem` a
exportação não teria como reconstruir a sequência do nome.

Índice GIN porque a consulta natural sobre esta coluna é de contenção
("quais nomes usaram objetivo=CV"), que é exatamente o que o B-tree não
resolve.

**Backfill parcial, de propósito.** As entidades guardam o valor bruto em
`campanhas.campos` e afins, então o `bruto` é recuperável. O `final` não é:
depende do dicionário e do template **da época**, e o dicionário é editável
pelo analista — reconstruí-lo hoje produziria uma abreviação plausível e
possivelmente errada num registro que deveria ser imutável (D-004). Fica
nulo, e é honesto que fique.

Linhas cuja entidade já foi apagada ficam com a coluna inteira nula: o
histórico sobrevive à entidade (D-004), mas o valor bruto vai embora com
ela. `SELECT count(*) FROM taxonomias_geradas WHERE campos_gerados IS NULL`
depois do upgrade diz quantas são.

Escrita à mão: o autogenerate não infere backfill nem `postgresql_using`.
Não toca o enum `nivel`, então não precisa do conserto de 84339e0f86c0.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2c9114a55"
down_revision: str | None = "a1c4f7e29b03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# O `final` fica nulo de propósito (ver docstring). `ordem` também: a ordem
# dos tokens no template da época não é reconstituível a partir do registro.
_BACKFILL = """
UPDATE taxonomias_geradas t
   SET campos_gerados = (
        SELECT jsonb_object_agg(
                   par.key,
                   jsonb_build_object('bruto', par.value, 'final', NULL, 'ordem', NULL)
               )
          FROM jsonb_each_text({fonte}.campos) AS par
   )
  FROM {tabela}
 WHERE t.nivel = '{nivel}'
   AND t.entidade_id = {fonte}.id
   AND {fonte}.campos <> '{{}}'::jsonb
"""


def upgrade() -> None:
    op.add_column(
        "taxonomias_geradas",
        sa.Column(
            "campos_gerados", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    for nivel, tabela, fonte in (
        ("CAMPANHA", "campanhas c", "c"),
        ("GRUPO", "grupos_anuncio g", "g"),
        ("ANUNCIO", "anuncios a", "a"),
    ):
        op.execute(_BACKFILL.format(nivel=nivel, tabela=tabela, fonte=fonte))

    op.create_index(
        "ix_taxonomia_campos_gerados",
        "taxonomias_geradas",
        ["campos_gerados"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_taxonomia_campos_gerados", table_name="taxonomias_geradas")
    op.drop_column("taxonomias_geradas", "campos_gerados")
