"""Schema do MediaBuild.

Implementa o modelo corrigido de docs/AVALIACAO.md — que difere da spec
original em três pontos deliberados:

1. O dicionário de abreviações é uma tabela, não constantes no código.
2. O padrão de nomenclatura vive em `templates_taxonomia` (tokens ordenados
   em JSONB), não em colunas fixas. Mudar o padrão é UPDATE, não migration.
3. `limite_caracteres` é por (plataforma, nível), não por plataforma.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Nivel(enum.Enum):
    """Níveis da hierarquia que recebem nomenclatura."""

    CAMPANHA = "CAMPANHA"
    GRUPO = "GRUPO"
    ANUNCIO = "ANUNCIO"


# Um único tipo enum nativo no Postgres, reaproveitado por todas as tabelas.
nivel_enum = Enum(
    Nivel,
    name="nivel",
    values_callable=lambda e: [m.value for m in e],
    create_type=True,
)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _criado_em() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Plataforma(Base):
    __tablename__ = "plataformas"

    id: Mapped[uuid.UUID] = _pk()
    nome: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    sigla: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    limites: Mapped[list["LimitePlataforma"]] = relationship(
        back_populates="plataforma", cascade="all, delete-orphan"
    )
    templates: Mapped[list["TemplateTaxonomia"]] = relationship(
        back_populates="plataforma", cascade="all, delete-orphan"
    )


class LimitePlataforma(Base):
    """Limite de caracteres por nível.

    Fica aqui e não em `plataformas` porque o limite varia por nível:
    no Meta, nome de campanha e nome de anúncio têm limites diferentes.
    """

    __tablename__ = "limites_plataforma"
    __table_args__ = (
        UniqueConstraint("plataforma_id", "nivel", name="uq_limite_plataforma_nivel"),
        CheckConstraint("limite_caracteres > 0", name="ck_limite_positivo"),
    )

    id: Mapped[uuid.UUID] = _pk()
    plataforma_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plataformas.id", ondelete="CASCADE"), nullable=False
    )
    nivel: Mapped[Nivel] = mapped_column(nivel_enum, nullable=False)
    limite_caracteres: Mapped[int] = mapped_column(Integer, nullable=False)

    plataforma: Mapped[Plataforma] = relationship(back_populates="limites")


class TemplateTaxonomia(Base):
    """Define a sequência ordenada de tokens que forma o nome.

    `tokens` é uma lista JSONB, por exemplo:
        [{"tipo": "literal",  "valor": "FB"},
         {"tipo": "campo",    "chave": "objetivo"},
         {"tipo": "match_id"}]

    Versionado: `taxonomias_geradas.template_versao` registra qual versão
    gerou cada nome, para que o histórico continue explicável depois de o
    padrão mudar.
    """

    __tablename__ = "templates_taxonomia"
    __table_args__ = (
        UniqueConstraint("plataforma_id", "nivel", "versao", name="uq_template_plataforma_nivel_versao"),
        CheckConstraint("versao > 0", name="ck_versao_positiva"),
        CheckConstraint("length(separador) = 1", name="ck_separador_um_caractere"),
    )

    id: Mapped[uuid.UUID] = _pk()
    plataforma_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plataformas.id", ondelete="CASCADE"), nullable=False
    )
    nivel: Mapped[Nivel] = mapped_column(nivel_enum, nullable=False)
    separador: Mapped[str] = mapped_column(String(1), nullable=False, server_default="_")
    tokens: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Texto que ocupa o lugar de um campo opcional em branco. Fica aqui e
    # não no código porque é padrão de nomenclatura: trocar 'NA' por outra
    # coisa é UPDATE. String vazia = o token some do nome, que é o
    # comportamento das versões anteriores a esta regra.
    marcador_ausencia: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="NA"
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    plataforma: Mapped[Plataforma] = relationship(back_populates="templates")


class DicionarioAbreviacao(Base):
    """De → Para das abreviações. `plataforma_id` nulo significa global.

    A unicidade é feita com dois índices parciais em vez de uma UNIQUE
    comum: no Postgres, NULLs são distintos entre si, então uma
    UNIQUE(plataforma_id, categoria, termo) deixaria passar duas linhas
    globais idênticas.
    """

    __tablename__ = "dicionario_abreviacoes"
    __table_args__ = (
        Index(
            "uq_abreviacao_por_plataforma",
            "plataforma_id",
            "categoria",
            "termo",
            unique=True,
            postgresql_where=text("plataforma_id IS NOT NULL"),
        ),
        Index(
            "uq_abreviacao_global",
            "categoria",
            "termo",
            unique=True,
            postgresql_where=text("plataforma_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    plataforma_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plataformas.id", ondelete="CASCADE"), nullable=True
    )
    categoria: Mapped[str] = mapped_column(String(40), nullable=False)
    termo: Mapped[str] = mapped_column(String(120), nullable=False)
    abreviacao: Mapped[str] = mapped_column(String(20), nullable=False)


class Campanha(Base):
    __tablename__ = "campanhas"

    id: Mapped[uuid.UUID] = _pk()
    plataforma_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plataformas.id", ondelete="RESTRICT"), nullable=False
    )
    nome_interno: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    campos: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    criado_em: Mapped[datetime] = _criado_em()

    plataforma: Mapped[Plataforma] = relationship()
    grupos: Mapped[list["GrupoAnuncio"]] = relationship(
        back_populates="campanha", cascade="all, delete-orphan"
    )


class GrupoAnuncio(Base):
    __tablename__ = "grupos_anuncio"

    id: Mapped[uuid.UUID] = _pk()
    campanha_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campanhas.id", ondelete="CASCADE"), nullable=False
    )
    nome_interno: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    campos: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    criado_em: Mapped[datetime] = _criado_em()

    campanha: Mapped[Campanha] = relationship(back_populates="grupos")
    anuncios: Mapped[list["Anuncio"]] = relationship(
        back_populates="grupo", cascade="all, delete-orphan"
    )


class Anuncio(Base):
    __tablename__ = "anuncios"

    id: Mapped[uuid.UUID] = _pk()
    grupo_anuncio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grupos_anuncio.id", ondelete="CASCADE"), nullable=False
    )
    nome_interno: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    campos: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    criado_em: Mapped[datetime] = _criado_em()

    grupo: Mapped[GrupoAnuncio] = relationship(back_populates="anuncios")


class TaxonomiaGerada(Base):
    """Histórico imutável de nomenclaturas geradas (D-004).

    `entidade_id` é polimórfico (aponta para campanha, grupo ou anúncio
    conforme `nivel`) e de propósito **não** tem foreign key: apagar a
    entidade não pode apagar o histórico, porque o nome já pode ter subido
    numa plataforma de anúncios e estar amarrado a dados de performance.

    `plataforma_id` e `campanha_id` são cópias denormalizadas, gravadas na
    geração e também sem FK. Existem por dois motivos: a tela de histórico
    filtra por elas o tempo todo e não deveria pagar três subconsultas
    polimórficas, e o filtro precisa continuar funcionando depois que a
    entidade for apagada.
    """

    __tablename__ = "taxonomias_geradas"
    __table_args__ = (
        Index("ix_taxonomia_entidade", "nivel", "entidade_id"),
        Index("ix_taxonomia_lote", "lote_id"),
        Index("ix_taxonomia_plataforma", "plataforma_id", "criado_em"),
        Index("ix_taxonomia_campanha", "campanha_id"),
        Index("ix_taxonomia_campos_gerados", "campos_gerados", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = _pk()
    nivel: Mapped[Nivel] = mapped_column(nivel_enum, nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plataforma_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    campanha_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    nomenclatura_final: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Nome já fatiado, por chave de campo: {"objetivo": {"bruto": "Conversão",
    # "final": "CV", "ordem": 4}}. O analista cruza a planilha de performance
    # por aqui, sem tentar refatiar o nome pelo separador — o que seria
    # ambíguo assim que um valor contivesse o separador. Nulo nas linhas
    # anteriores à coluna e naquelas cuja entidade já havia sido apagada.
    campos_gerados: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    template_versao: Mapped[int] = mapped_column(Integer, nullable=False)
    lote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Sem FK e nullable de propósito: não há tabela `usuarios` no MVP (D-003).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    criado_em: Mapped[datetime] = _criado_em()
