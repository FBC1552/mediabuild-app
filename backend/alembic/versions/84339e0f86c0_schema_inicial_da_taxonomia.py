"""schema inicial da taxonomia

Revision ID: 84339e0f86c0
Revises:
Create Date: 2026-08-01 22:07:29.623718

Ajustes manuais sobre o autogenerate:
- O enum `nivel` é criado uma única vez no início (o autogenerate emitiria
  um CREATE TYPE por tabela que o usa, falhando na segunda).
- O downgrade remove o tipo, sem o que um novo upgrade falharia.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '84339e0f86c0'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False: o ciclo de vida do tipo é controlado explicitamente abaixo.
nivel = postgresql.ENUM('CAMPANHA', 'GRUPO', 'ANUNCIO', name='nivel', create_type=False)


def upgrade() -> None:
    nivel.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'plataformas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('nome', sa.String(length=60), nullable=False),
        sa.Column('sigla', sa.String(length=10), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome'),
        sa.UniqueConstraint('sigla'),
    )

    op.create_table(
        'taxonomias_geradas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('nivel', nivel, nullable=False),
        sa.Column('entidade_id', sa.UUID(), nullable=False),
        sa.Column('nomenclatura_final', sa.Text(), nullable=False),
        sa.Column('template_versao', sa.Integer(), nullable=False),
        sa.Column('lote_id', sa.UUID(), nullable=True),
        sa.Column('usuario_id', sa.UUID(), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nomenclatura_final'),
    )
    op.create_index('ix_taxonomia_entidade', 'taxonomias_geradas', ['nivel', 'entidade_id'], unique=False)
    op.create_index('ix_taxonomia_lote', 'taxonomias_geradas', ['lote_id'], unique=False)

    op.create_table(
        'campanhas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plataforma_id', sa.UUID(), nullable=False),
        sa.Column('nome_interno', sa.String(length=200), nullable=False),
        sa.Column('match_id', sa.String(length=20), nullable=False),
        sa.Column('campos', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plataforma_id'], ['plataformas.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id'),
    )

    op.create_table(
        'dicionario_abreviacoes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plataforma_id', sa.UUID(), nullable=True),
        sa.Column('categoria', sa.String(length=40), nullable=False),
        sa.Column('termo', sa.String(length=120), nullable=False),
        sa.Column('abreviacao', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['plataforma_id'], ['plataformas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Dois índices parciais em vez de uma UNIQUE comum: no Postgres NULLs são
    # distintos entre si, então UNIQUE(plataforma_id, categoria, termo)
    # deixaria passar duas linhas globais idênticas.
    op.create_index(
        'uq_abreviacao_global', 'dicionario_abreviacoes', ['categoria', 'termo'],
        unique=True, postgresql_where=sa.text('plataforma_id IS NULL'),
    )
    op.create_index(
        'uq_abreviacao_por_plataforma', 'dicionario_abreviacoes', ['plataforma_id', 'categoria', 'termo'],
        unique=True, postgresql_where=sa.text('plataforma_id IS NOT NULL'),
    )

    op.create_table(
        'limites_plataforma',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plataforma_id', sa.UUID(), nullable=False),
        sa.Column('nivel', nivel, nullable=False),
        sa.Column('limite_caracteres', sa.Integer(), nullable=False),
        sa.CheckConstraint('limite_caracteres > 0', name='ck_limite_positivo'),
        sa.ForeignKeyConstraint(['plataforma_id'], ['plataformas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plataforma_id', 'nivel', name='uq_limite_plataforma_nivel'),
    )

    op.create_table(
        'templates_taxonomia',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plataforma_id', sa.UUID(), nullable=False),
        sa.Column('nivel', nivel, nullable=False),
        sa.Column('separador', sa.String(length=1), server_default='_', nullable=False),
        sa.Column('tokens', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('versao', sa.Integer(), server_default='1', nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.CheckConstraint('length(separador) = 1', name='ck_separador_um_caractere'),
        sa.CheckConstraint('versao > 0', name='ck_versao_positiva'),
        sa.ForeignKeyConstraint(['plataforma_id'], ['plataformas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plataforma_id', 'nivel', 'versao', name='uq_template_plataforma_nivel_versao'),
    )

    op.create_table(
        'grupos_anuncio',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('campanha_id', sa.UUID(), nullable=False),
        sa.Column('nome_interno', sa.String(length=200), nullable=False),
        sa.Column('match_id', sa.String(length=20), nullable=False),
        sa.Column('campos', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campanha_id'], ['campanhas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id'),
    )

    op.create_table(
        'anuncios',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('grupo_anuncio_id', sa.UUID(), nullable=False),
        sa.Column('nome_interno', sa.String(length=200), nullable=False),
        sa.Column('match_id', sa.String(length=20), nullable=False),
        sa.Column('campos', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['grupo_anuncio_id'], ['grupos_anuncio.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id'),
    )


def downgrade() -> None:
    op.drop_table('anuncios')
    op.drop_table('grupos_anuncio')
    op.drop_table('templates_taxonomia')
    op.drop_table('limites_plataforma')
    op.drop_index('uq_abreviacao_por_plataforma', table_name='dicionario_abreviacoes',
                  postgresql_where=sa.text('plataforma_id IS NOT NULL'))
    op.drop_index('uq_abreviacao_global', table_name='dicionario_abreviacoes',
                  postgresql_where=sa.text('plataforma_id IS NULL'))
    op.drop_table('dicionario_abreviacoes')
    op.drop_table('campanhas')
    op.drop_index('ix_taxonomia_lote', table_name='taxonomias_geradas')
    op.drop_index('ix_taxonomia_entidade', table_name='taxonomias_geradas')
    op.drop_table('taxonomias_geradas')
    op.drop_table('plataformas')

    nivel.drop(op.get_bind(), checkfirst=True)
