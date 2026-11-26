"""Plano de mídia: seleção de campanhas existentes com verba rateada em
cascata e metas de métrica por linha (anúncio).

Este módulo não toca `app/taxonomia/motor.py` nem o pipeline de geração de
nome — plano de mídia é um documento **separado** que referencia campanhas,
grupos e anúncios já existentes (e, quando houver, a nomenclatura já gerada
para eles). Ver docstring de `PlanoMidiaCampanha` para a decisão de
denormalização.

Diferença central para `taxonomias_geradas`: **o plano é mutável**. D-004
(imutabilidade) vale para nomenclatura gerada, não para este documento — o
analista adiciona, edita valor/percentual e remove linhas o tempo todo
enquanto monta o plano.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.taxonomia import _criado_em, _pk


def _atualizado_em() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _valor() -> Mapped[Decimal]:
    """Coluna monetária/quantidade em reais, com duas casas decimais.

    `NUMERIC(14, 2)` e não `float`: `NUMERIC` do Postgres é decimal exato —
    não sofre o arredondamento binário que um `float` traria, e o rateio
    percentual em cascata (D-A) já divide o valor várias vezes antes de
    chegar ao anúncio. Também não convertemos para inteiro de centavos:
    como a coluna já é decimal exata, a conversão só trocaria um tipo exato
    por outro, ao custo de multiplicar/dividir por 100 em toda leitura e
    escrita — superfície extra para bug sem ganho de precisão.
    """
    return mapped_column(
        NUMERIC(14, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )


class Metrica(Base):
    """Catálogo de métricas que podem receber meta num anúncio do plano.

    Existe como tabela — e não como `Enum` ou constante em código — pelo
    mesmo motivo de `dicionario_abreviacoes` e `templates_taxonomia`:
    acrescentar, renomear ou desativar uma métrica precisa ser um `UPDATE`,
    nunca uma migration. A lista de trabalho informada pelo domínio
    (impressões, cliques, conversões, ...) é só o **seed** de partida —
    ver `app/seed.py`. `PlanoMidiaAnuncio.metas` guarda as metas por
    `codigo`, em JSONB, sem foreign key: o valor de uma métrica não deixa
    de fazer sentido num plano antigo só porque o catálogo mudou depois.

    `ativo=False` é a forma de "remover" sem quebrar planos que já usam o
    código — a métrica só some das opções oferecidas para metas *novas*
    (ver `app/erros_plano.py::MetricaDesconhecida`), sem apagar o que já
    foi digitado.
    """

    __tablename__ = "metricas"
    __table_args__ = (CheckConstraint("ordem >= 0", name="ck_metrica_ordem_nao_negativa"),)

    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    rotulo: Mapped[str] = mapped_column(String(80), nullable=False)
    # Ordem de exibição/exportação. Não é a ordem alfabética porque a
    # planilha do cliente tem uma sequência própria (Impressões antes de
    # Cliques antes de Conversões, etc.) que faz sentido de funil.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ativo: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")


class PlanoMidia(Base):
    """Cabeçalho do plano: nome, verba total em reais e observações livres.

    A verba é distribuída em cascata para as campanhas selecionadas, delas
    para os grupos, e dos grupos para os anúncios (D-A). O desbalanço entre
    a soma dos filhos e o valor do pai é estado válido de rascunho — ver
    `PlanoMidiaCampanha` — então esta tabela não tem nenhuma constraint que
    tente forçar a soma a fechar.
    """

    __tablename__ = "planos_midia"
    __table_args__ = (
        CheckConstraint("verba_total >= 0", name="ck_plano_verba_nao_negativa"),
    )

    id: Mapped[uuid.UUID] = _pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    verba_total: Mapped[Decimal] = _valor()
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()

    campanhas: Mapped[list["PlanoMidiaCampanha"]] = relationship(
        back_populates="plano",
        cascade="all, delete-orphan",
        order_by="PlanoMidiaCampanha.criado_em",
    )


class PlanoMidiaCampanha(Base):
    """Uma campanha selecionada dentro de um plano, com sua fatia de verba.

    `campanha_id` **não tem foreign key**, de propósito — mesmo raciocínio
    de `taxonomias_geradas.entidade_id` (D-009): apagar a campanha não pode
    apagar nem corromper um plano de mídia já fechado, porque o plano
    continua sendo um documento de referência (o que foi vendido/planejado)
    mesmo depois que a campanha operacional deixa de existir no sistema.

    Por isso `nome_interno`, `match_id` e `nomenclatura` são **cópias
    denormalizadas**, gravadas no momento em que a linha é criada (a partir
    da campanha e da sua última `TaxonomiaGerada`, se houver): é o que
    mantém a linha legível e o `match_id` cruzável com a planilha de
    performance depois que a campanha original some. `plataforma_id`
    também é copiado, sem FK, pelo mesmo motivo de filtro barato que
    justificou a coluna homônima em `taxonomias_geradas`.

    `valor` é a fonte da verdade (D-B); a porcentagem exibida na API é
    sempre **derivada** de `valor` dividido pelo `verba_total` do plano, e
    nunca persistida — persistir as duas criaria uma segunda fonte da
    verdade que poderia divergir da primeira.

    `valor`, neste nível, é rótulo "Investimento (R$)" no export/API — ao
    contrário do mesmo campo em `PlanoMidiaAnuncio`, que é rotulado
    "Investimento previsto (R$)" porque não existe orçamento configurável
    por anúncio em nenhuma plataforma de mídia (ver docstring de
    `PlanoMidiaAnuncio.valor` e `docs/PLANO-DE-MIDIA.md` §4). No nível da
    campanha o valor pode corresponder a orçamento real (CBO no Meta, por
    exemplo), por isso o rótulo não carrega a mesma ressalva.

    `flight_inicio`/`flight_fim` (docs/PLANO-DE-MIDIA.md §5.1) resolvem a
    ambiguidade de mês-sem-ano já registrada em `docs/DECISOES.md`: o nome
    gerado carrega só um mês abreviado (`JUL`), que fica ambíguo depois de
    12 meses de operação. As datas não tocam o token de nome — o nome
    continua como está — só dão ao plano uma noção de calendário. Ambas
    nullable (rascunho pode não ter flight definido ainda) e sem
    constraint de obrigatoriedade cruzada além de fim >= início.

    `kpi_primario_*` (docs/PLANO-DE-MIDIA.md §5.2) aponta qual das métricas
    do catálogo é a que importa para *esta* campanha. Sem foreign key para
    `metricas.id`, de propósito: `Metrica` tem rota de DELETE de verdade
    (`DELETE /metricas/{id}`, ver `app/routers/metricas.py`), então uma FK
    aqui quebraria a exclusão ou exigiria `ON DELETE SET NULL` silencioso —
    nos dois casos, o plano perderia a informação de qual KPI foi escolhido.
    Em vez disso, `kpi_primario_codigo`/`kpi_primario_rotulo` são cópias
    denormalizadas gravadas no momento da escrita (mesma lógica de
    `nome_interno`/`match_id` para a campanha em si), e o `id` fica
    disponível só para a leitura resolver, à parte, se o KPI escolhido
    ainda existe e está ativo no catálogo (`_kpi_primario_ativo` em
    `app/routers/planos.py`) — sem isso a interface não teria como
    distinguir "KPI ainda válido" de "KPI removido/desativado depois".
    """

    __tablename__ = "planos_midia_campanhas"
    __table_args__ = (
        UniqueConstraint("plano_id", "campanha_id", name="uq_plano_campanha"),
        CheckConstraint("valor >= 0", name="ck_plano_campanha_valor_nao_negativo"),
        CheckConstraint(
            "flight_fim IS NULL OR flight_inicio IS NULL OR flight_fim >= flight_inicio",
            name="ck_plano_campanha_flight_ordenado",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    plano_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planos_midia.id", ondelete="CASCADE"), nullable=False
    )
    campanha_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plataforma_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    nome_interno: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False)
    nomenclatura: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor: Mapped[Decimal] = _valor()
    flight_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    flight_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    kpi_primario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kpi_primario_codigo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kpi_primario_rotulo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()

    plano: Mapped[PlanoMidia] = relationship(back_populates="campanhas")
    grupos: Mapped[list["PlanoMidiaGrupo"]] = relationship(
        back_populates="campanha",
        cascade="all, delete-orphan",
        order_by="PlanoMidiaGrupo.criado_em",
    )


class PlanoMidiaGrupo(Base):
    """Um grupo de anúncio selecionado dentro de uma linha de campanha do
    plano. Mesma lógica de denormalização de `PlanoMidiaCampanha`, aplicada
    um nível abaixo: `grupo_id` sem FK, nome/match id/nomenclatura
    copiados no momento da inserção.

    `custo_unitario_negociado` (docs/PLANO-DE-MIDIA.md §5.3) é o preço
    unitário (CPM ou CPV, conforme o `tipo_compra` que a taxonomia do
    anúncio já carrega — `app/plataformas.py`) acordado com o veículo.
    Mora aqui, no GRUPO, e não na campanha nem no anúncio: é no grupo
    (Conjunto de anúncios/ABO no Meta, Grupo de anúncios no Google/TikTok,
    Line Item no DV360) que o orçamento **é** de fato configurável na
    plataforma — o mesmo raciocínio que justifica o rótulo diferente do
    `valor` do anúncio (ver `PlanoMidiaAnuncio.valor`). Guardado só como
    referência informativa do que foi negociado; **nenhum cálculo é feito
    a partir dele** — decisão explícita do usuário de não projetar
    impressões/views automaticamente a partir de verba (metas continuam
    100% digitadas à mão, D-C). Nullable: nem todo grupo tem preço
    negociado quando o rascunho é criado.
    """

    __tablename__ = "planos_midia_grupos"
    __table_args__ = (
        UniqueConstraint(
            "plano_midia_campanha_id", "grupo_id", name="uq_plano_campanha_grupo"
        ),
        CheckConstraint("valor >= 0", name="ck_plano_grupo_valor_nao_negativo"),
        CheckConstraint(
            "custo_unitario_negociado IS NULL OR custo_unitario_negociado >= 0",
            name="ck_plano_grupo_custo_unitario_nao_negativo",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    plano_midia_campanha_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planos_midia_campanhas.id", ondelete="CASCADE"), nullable=False
    )
    grupo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    nome_interno: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False)
    nomenclatura: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor: Mapped[Decimal] = _valor()
    custo_unitario_negociado: Mapped[Decimal | None] = mapped_column(
        NUMERIC(12, 4), nullable=True
    )
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()

    campanha: Mapped[PlanoMidiaCampanha] = relationship(back_populates="grupos")
    anuncios: Mapped[list["PlanoMidiaAnuncio"]] = relationship(
        back_populates="grupo",
        cascade="all, delete-orphan",
        order_by="PlanoMidiaAnuncio.criado_em",
    )


class PlanoMidiaAnuncio(Base):
    """Um anúncio selecionado dentro de uma linha de grupo do plano —
    a folha da cascata de rateio, e onde moram as metas de métrica.

    `metas` é JSONB `{codigo_da_metrica: valor}`, com valores inteiros
    (contagens: impressões, cliques, conversões, ...; nenhuma métrica da
    lista de trabalho é monetária, então não há razão para `Decimal` aqui).
    São metas **digitadas à mão** (D-C): nada aqui projeta a partir de
    CPM/CPV. As chaves são validadas contra `Metrica.ativo` na escrita
    (`app/erros_plano.py::MetricaDesconhecida`), não por foreign key — JSONB
    não suporta isso, e não seria desejável mesmo se suportasse: uma meta
    digitada para uma métrica depois desativada precisa continuar legível.

    `valor`, neste nível, é rotulado **"Investimento previsto (R$)"** no
    export/API — não "Investimento (R$)" como em `PlanoMidiaCampanha` e
    `PlanoMidiaGrupo`. Motivo (docs/PLANO-DE-MIDIA.md §4): não existe
    orçamento configurável por anúncio em nenhuma plataforma de mídia — os
    anúncios de um grupo competem pelo orçamento do grupo via leilão. O
    número aqui é projeção de planejamento (útil para dividir a verba entre
    conceitos criativos e comparar planejado vs. realizado depois, via
    `match_id`), não uma configuração que existe do outro lado. O rótulo
    muda; o campo, a coluna e o tipo continuam os mesmos.
    """

    __tablename__ = "planos_midia_anuncios"
    __table_args__ = (
        UniqueConstraint(
            "plano_midia_grupo_id", "anuncio_id", name="uq_plano_grupo_anuncio"
        ),
        CheckConstraint("valor >= 0", name="ck_plano_anuncio_valor_nao_negativo"),
    )

    id: Mapped[uuid.UUID] = _pk()
    plano_midia_grupo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planos_midia_grupos.id", ondelete="CASCADE"), nullable=False
    )
    anuncio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    nome_interno: Mapped[str] = mapped_column(String(200), nullable=False)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False)
    nomenclatura: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor: Mapped[Decimal] = _valor()
    metas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()

    grupo: Mapped[PlanoMidiaGrupo] = relationship(back_populates="anuncios")
