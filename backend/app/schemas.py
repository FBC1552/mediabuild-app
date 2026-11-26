"""Schemas Pydantic da API.

Separados dos modelos SQLAlchemy de propósito: o que entra e sai pela HTTP
não é o mesmo que o que está no banco. `match_id`, por exemplo, é sempre
gerado pelo servidor e nunca aceito do cliente.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import Nivel, Papel, TipoEventoAcesso

Campos = dict[str, str]


class CampoGeradoLer(BaseModel):
    """Um campo do nome, nas duas formas que interessam ao analista.

    `bruto` é o que ele digitou ('Conversão'); `final` é o pedaço que
    entrou no nome ('CV') — que é o que a planilha de performance contém.
    `bruto` vem nulo quando o campo é opcional e ficou em branco, e também
    nas linhas retroativas, cujo valor final não era reconstituível.
    """

    bruto: str | None = None
    final: str | None = None
    ordem: int | None = None


CamposGerados = dict[str, CampoGeradoLer]


# --------------------------------------------------------------------------
# erros
# --------------------------------------------------------------------------

class ErroResposta(BaseModel):
    """Corpo padrão de erro. `campo` e `opcoes` alimentam a UI da Fase 4."""

    erro: str = Field(description="Código estável do erro, para tratamento no cliente")
    mensagem: str = Field(description="Texto pronto para exibir ao analista")
    campo: str | None = Field(default=None, description="Campo que causou a falha")
    opcoes: list[str] | None = Field(default=None, description="Valores aceitos, quando aplicável")


# --------------------------------------------------------------------------
# plataformas
# --------------------------------------------------------------------------

class PlataformaCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    sigla: str = Field(min_length=1, max_length=10)
    limites: int | dict[Nivel, int] = Field(
        default=255, description="Um valor para todos os níveis, ou um por nível"
    )
    campos_extras: dict[Nivel, list[str]] | None = Field(
        default=None, description="Campos dinâmicos adicionais por nível"
    )
    separador: str = Field(default="_", min_length=1, max_length=1)


class PlataformaAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=60)
    sigla: str | None = Field(default=None, min_length=1, max_length=10)
    ativo: bool | None = None


class PlataformaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    sigla: str
    ativo: bool


# --------------------------------------------------------------------------
# limites e templates
# --------------------------------------------------------------------------

class LimiteLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plataforma_id: UUID
    nivel: Nivel
    limite_caracteres: int


class LimiteAtualizar(BaseModel):
    limite_caracteres: int = Field(gt=0)


class TemplateLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plataforma_id: UUID
    nivel: Nivel
    separador: str
    tokens: list[dict]
    marcador_ausencia: str
    versao: int
    ativo: bool


class TemplateCriar(BaseModel):
    """Cria uma nova versão do template. Versões antigas não são alteradas,
    para que o histórico continue explicável (ver `template_versao`)."""

    tokens: list[dict] = Field(min_length=1)
    separador: str = Field(default="_", min_length=1, max_length=1)
    marcador_ausencia: str = Field(
        default="NA",
        max_length=10,
        description="Ocupa o lugar de um campo opcional em branco, para que "
        "todo nome do nível tenha a mesma quantidade de partes. String vazia "
        "faz o token sumir do nome, como antes desta regra",
    )


# --------------------------------------------------------------------------
# dicionário
# --------------------------------------------------------------------------

class AbreviacaoCriar(BaseModel):
    categoria: str = Field(min_length=1, max_length=40)
    termo: str = Field(min_length=1, max_length=120)
    abreviacao: str = Field(min_length=1, max_length=20)
    plataforma_id: UUID | None = Field(
        default=None, description="Nulo = vale para todas as plataformas"
    )


class AbreviacaoAtualizar(BaseModel):
    abreviacao: str = Field(min_length=1, max_length=20)


class AbreviacaoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plataforma_id: UUID | None
    categoria: str
    termo: str
    abreviacao: str


# --------------------------------------------------------------------------
# hierarquia
# --------------------------------------------------------------------------

class CampanhaCriar(BaseModel):
    plataforma_id: UUID
    nome_interno: str = Field(min_length=1, max_length=200)
    campos: Campos = Field(default_factory=dict)


class GrupoCriar(BaseModel):
    campanha_id: UUID
    nome_interno: str = Field(min_length=1, max_length=200)
    campos: Campos = Field(default_factory=dict)


class AnuncioCriar(BaseModel):
    grupo_anuncio_id: UUID
    nome_interno: str = Field(min_length=1, max_length=200)
    campos: Campos = Field(default_factory=dict)


class EntidadeAtualizar(BaseModel):
    nome_interno: str | None = Field(default=None, min_length=1, max_length=200)
    campos: Campos | None = None


class CampanhaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plataforma_id: UUID
    nome_interno: str
    match_id: str
    campos: Campos
    criado_em: datetime


class GrupoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campanha_id: UUID
    nome_interno: str
    match_id: str
    campos: Campos
    criado_em: datetime


class AnuncioLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grupo_anuncio_id: UUID
    nome_interno: str
    match_id: str
    campos: Campos
    criado_em: datetime


class NoDaArvore(BaseModel):
    """Filho de uma campanha ou de um grupo, para a árvore da hierarquia.

    Traz a nomenclatura **mais recente** da entidade, e não todas: a árvore
    mostra o estado atual. O histórico completo continua sendo assunto de
    `GET /taxonomias/historico`, e nenhuma das duas rotas edita ou apaga
    nomenclatura (D-004).

    `nomenclatura` é nula enquanto a entidade existe mas ainda não teve
    nome gerado — o que é um estado normal, não um erro.
    """

    id: UUID
    pai_id: UUID
    nome_interno: str
    match_id: str
    nomenclatura: str | None = None
    taxonomia_id: UUID | None = None
    gerado_em: datetime | None = None
    criado_em: datetime


# --------------------------------------------------------------------------
# taxonomias
# --------------------------------------------------------------------------

class PreviewPedido(BaseModel):
    """Gera sem persistir. Alimenta o preview ao vivo do formulário."""

    plataforma_id: UUID
    nivel: Nivel
    campos: Campos = Field(default_factory=dict)
    match_id: str | None = Field(
        default=None,
        description="Se omitido, usa um placeholder de mesmo tamanho — o nome "
        "ainda não é definitivo, mas o cálculo de limite fica correto",
    )


class PreviewResposta(BaseModel):
    nomenclatura: str
    match_id_provisorio: bool
    template_versao: int
    limite_caracteres: int | None
    caracteres: int


class TaxonomiaCriar(BaseModel):
    """Persiste a nomenclatura de uma entidade já existente.

    Usa o `match_id` da própria entidade — estável desde a criação dela.
    """

    nivel: Nivel
    entidade_id: UUID
    lote_id: UUID | None = Field(
        default=None, description="Agrupa taxonomias de uma mesma sessão de trabalho"
    )


class TaxonomiaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nivel: Nivel
    entidade_id: UUID
    plataforma_id: UUID | None = None
    campanha_id: UUID | None = None
    nomenclatura_final: str
    campos_gerados: CamposGerados | None = None
    template_versao: int
    lote_id: UUID | None
    criado_em: datetime


class UtmValidarPedido(BaseModel):
    """Confere uma URL contra uma taxonomia já gerada. Nada é persistido."""

    url: str = Field(min_length=1, max_length=2048, description="A URL de destino, colada")
    taxonomia_id: UUID = Field(description="Taxonomia gerada que serve de referência")


class AchadoUtm(BaseModel):
    """Um item do laudo. `codigo` é estável, como nos erros da API."""

    codigo: str
    parametro: str | None = None
    mensagem: str
    encontrado: str | None = None
    esperado: str | None = None


class UtmResposta(BaseModel):
    """Laudo da URL. Sempre 200: URL problemática é o resultado do pedido,
    não pedido malformado."""

    valido: bool
    erros: list[AchadoUtm]
    avisos: list[AchadoUtm]
    parametros: dict[str, str]
    sugestao: dict[str, str]
    url_sugerida: str


class TaxonomiaHistoricoLer(BaseModel):
    """Linha do histórico com as entidades já resolvidas.

    Existe separado de `TaxonomiaLer` porque a tela precisa do nome da
    plataforma e da campanha — não dos ids — e buscar isso linha a linha
    seria uma requisição por registro.
    """

    id: UUID
    nivel: Nivel
    nomenclatura_final: str
    plataforma: str
    campanha: str
    nome_interno: str
    match_id: str
    caracteres: int
    template_versao: int
    campos: Campos
    campos_gerados: CamposGerados | None = None
    lote_id: UUID | None
    criado_em: datetime


# --------------------------------------------------------------------------
# plano de mídia
# --------------------------------------------------------------------------

# Metas de métrica, código -> quantidade. Inteiro porque nenhuma métrica da
# lista de trabalho (impressões, cliques, conversões, ...) é monetária —
# ver `app/models/plano_midia.py::PlanoMidiaAnuncio.metas`.
Metas = dict[str, int]

# Duas casas: reais e centavos. Ver decisão de moeda em
# `app/models/plano_midia.py::_valor`.
_Valor = Decimal
_CASAS_VALOR = {"max_digits": 14, "decimal_places": 2}
_CASAS_PERCENTUAL = {"max_digits": 6, "decimal_places": 3}


class MetricaCriar(BaseModel):
    codigo: str = Field(
        min_length=1,
        max_length=40,
        pattern=r"^[a-z0-9_]+$",
        description="Identificador estável usado como chave em 'metas'. "
        "minúsculo e sem espaço, para poder virar cabeçalho de planilha sem ambiguidade.",
    )
    rotulo: str = Field(min_length=1, max_length=80)
    ordem: int = Field(default=0, ge=0)


class MetricaAtualizar(BaseModel):
    """`codigo` não é editável: é a chave gravada em 'metas' de todo plano
    que já a usa, e trocá-la desconectaria essas metas silenciosamente.
    Para renomear o que o analista lê, edite `rotulo` — o código pode
    continuar feio por baixo."""

    rotulo: str | None = Field(default=None, min_length=1, max_length=80)
    ordem: int | None = Field(default=None, ge=0)
    ativo: bool | None = None


class MetricaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str
    rotulo: str
    ordem: int
    ativo: bool


class PlanoMidiaCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    verba_total: _Valor = Field(ge=0, **_CASAS_VALOR)
    observacoes: str | None = None


class PlanoMidiaAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    verba_total: _Valor | None = Field(default=None, ge=0, **_CASAS_VALOR)
    observacoes: str | None = None


class _LinhaPedido(BaseModel):
    """Base comum às três linhas do plano (campanha, grupo, anúncio).

    Aceita `valor` em reais OU `percentual` do orçamento do pai — nunca os
    dois, nunca nenhum. Quando vem `percentual`, o servidor calcula o
    `valor` uma única vez, no momento da escrita (D-A/D-B): o valor
    persistido é sempre a fonte da verdade; a porcentagem é forma de
    entrada e, na leitura, forma de exibição derivada de volta.
    """

    valor: _Valor | None = Field(default=None, ge=0, **_CASAS_VALOR)
    percentual: _Valor | None = Field(default=None, ge=0, le=100, **_CASAS_PERCENTUAL)

    @model_validator(mode="after")
    def _exatamente_um(self) -> "_LinhaPedido":
        if (self.valor is None) == (self.percentual is None):
            raise ValueError(
                "Informe 'valor' (em reais) OU 'percentual' (do orçamento do nível acima), "
                "nunca os dois nem nenhum."
            )
        return self


class _FlightEKpiPedido(BaseModel):
    """Mixin dos campos exclusivos da linha de CAMPANHA do plano (D-4/§5.1
    e §5.2 de docs/PLANO-DE-MIDIA.md). Todos opcionais: um rascunho pode
    não ter flight nem KPI definidos ainda.
    """

    flight_inicio: date | None = None
    flight_fim: date | None = None
    # Referência ao catálogo (`GET /metricas`), nunca texto livre — ver
    # `app/erros_plano.py::KpiPrimarioInvalido`. `None` explicitamente
    # limpa o KPI já escolhido (mesmo padrão de `exclude_unset` do resto
    # da API: omitir o campo no PATCH não mexe nele).
    kpi_primario_id: UUID | None = None

    @model_validator(mode="after")
    def _flight_ordenado(self) -> "_FlightEKpiPedido":
        if (
            self.flight_inicio is not None
            and self.flight_fim is not None
            and self.flight_fim < self.flight_inicio
        ):
            raise ValueError("'flight_fim' não pode ser anterior a 'flight_inicio'.")
        return self


class _SincronizarNomenclaturaPedido(BaseModel):
    """Mixin exclusivo dos PATCH de linha do plano (campanha/grupo/anúncio) —
    o verbo único que o analista usa para aceitar um nome regerado (§4.4 de
    `docs/PLANO-DE-MIDIA-UI.md`, "nomenclatura defasada").

    Quando `true`, a linha recopia `nomenclatura` a partir da nomenclatura
    MAIS RECENTE da entidade — a mesma fonte que a leitura já usa para
    calcular `nomenclatura_atual`/`nomenclatura_divergente`
    (`_ultima_nomenclatura` em `app/routers/planos.py`), para os dois nunca
    discordarem depois do PATCH. `match_id` e `nome_interno` não são
    tocados por este verbo: `match_id` é estável pela vida inteira da
    entidade (D-006, nunca muda ao regerar um nome) e `nome_interno` não
    tem campo de divergência calculado na leitura, então não há um "atual"
    para recopiar dele.

    `False` por padrão e só tem efeito quando vem explícito no corpo do
    PATCH — como o resto da API, `exclude_unset`/`model_fields_set` no
    router faz a omissão não acionar nada, mesmo com o default `False`
    presente no schema.
    """

    sincronizar_nomenclatura: bool = False


class CampanhaDoPlanoCriar(_LinhaPedido, _FlightEKpiPedido):
    campanha_id: UUID


class CampanhaDoPlanoAtualizar(_LinhaPedido, _FlightEKpiPedido, _SincronizarNomenclaturaPedido):
    """Reajusta valor/percentual, flight e KPI de uma linha de campanha já
    existente. Como o resto do PATCH da API, campos omitidos não são
    tocados (`exclude_unset` no router) — só `flight_inicio`/`flight_fim`/
    `kpi_primario_id` explicitamente enviados como `null` são limpos.
    `valor`/`percentual` continuam obrigatórios (um dos dois, nunca os
    dois) em todo PATCH — ver `_LinhaPedido` — então pedir sincronização de
    nomenclatura na mesma chamada que reajusta o valor é o caso comum, não
    uma combinação especial: os dois efeitos são aplicados juntos."""


class _CustoUnitarioPedido(BaseModel):
    """Mixin do campo exclusivo da linha de GRUPO do plano (§5.3): custo
    unitário negociado (CPM/CPV, conforme `tipo_compra` do anúncio).
    Informativo — não alimenta cálculo nenhum (ver docstring de
    `PlanoMidiaGrupo.custo_unitario_negociado`)."""

    custo_unitario_negociado: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4
    )


class GrupoDoPlanoCriar(_LinhaPedido, _CustoUnitarioPedido):
    grupo_id: UUID


class GrupoDoPlanoAtualizar(_LinhaPedido, _CustoUnitarioPedido, _SincronizarNomenclaturaPedido):
    """Reajusta valor/percentual e custo unitário negociado de uma linha
    de grupo já existente. `sincronizar_nomenclatura`: ver
    `_SincronizarNomenclaturaPedido`."""


class AnuncioDoPlanoCriar(_LinhaPedido):
    anuncio_id: UUID
    metas: Metas = Field(default_factory=dict)


class AnuncioDoPlanoAtualizar(_LinhaPedido, _SincronizarNomenclaturaPedido):
    """`sincronizar_nomenclatura`: ver `_SincronizarNomenclaturaPedido`."""

    metas: Metas | None = None


class AnuncioDoPlanoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    anuncio_id: UUID
    nome_interno: str
    match_id: str
    nomenclatura: str | None
    # `nomenclatura` acima é o snapshot gravado quando a linha entrou no
    # plano (D-004: não é atualizado sozinho). `nomenclatura_atual` é a
    # nomenclatura mais recente do anúncio agora, resolvida em lote na
    # leitura (ver `_carregar_nomenclaturas_atuais` em `app/routers/planos.py`
    # — sem N+1); `nomenclatura_divergente` compara os dois. A interface
    # decide o que fazer com a divergência (regerar snapshot, avisar,
    # ignorar) — o backend só informa.
    nomenclatura_atual: str | None
    nomenclatura_divergente: bool
    valor: _Valor
    # Derivado de `valor / (valor do grupo pai)`, nunca persistido (D-B).
    # Nulo quando o grupo pai tem valor zero — a divisão não tem sentido.
    percentual: _Valor | None
    metas: Metas
    criado_em: datetime
    atualizado_em: datetime


class GrupoDoPlanoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grupo_id: UUID
    nome_interno: str
    match_id: str
    nomenclatura: str | None
    nomenclatura_atual: str | None
    nomenclatura_divergente: bool
    valor: _Valor
    percentual: _Valor | None
    # Informativo, não alimenta cálculo (ver docstring do modelo).
    custo_unitario_negociado: Decimal | None
    # Soma dos valores dos anúncios filhos e a diferença para `valor`.
    # D-B: desbalanço é estado válido de rascunho — o servidor só informa,
    # nunca redistribui nem rejeita.
    soma_anuncios: _Valor
    diferenca: _Valor
    anuncios: list[AnuncioDoPlanoLer]


class CampanhaDoPlanoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campanha_id: UUID
    plataforma_id: UUID | None
    nome_interno: str
    match_id: str
    nomenclatura: str | None
    nomenclatura_atual: str | None
    nomenclatura_divergente: bool
    valor: _Valor
    percentual: _Valor | None
    flight_inicio: date | None
    flight_fim: date | None
    kpi_primario_id: UUID | None
    kpi_primario_codigo: str | None
    kpi_primario_rotulo: str | None
    # `None` quando não há KPI escolhido; `True`/`False` quando há, conforme
    # a métrica referenciada ainda existir e estiver ativa no catálogo
    # agora — resolvido em lote na leitura, não persistido (mesma lógica de
    # `nomenclatura_divergente`).
    kpi_primario_ativo: bool | None
    soma_grupos: _Valor
    diferenca: _Valor
    grupos: list[GrupoDoPlanoLer]


class PlanoMidiaLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    verba_total: _Valor
    observacoes: str | None
    soma_campanhas: _Valor
    diferenca: _Valor
    campanhas: list[CampanhaDoPlanoLer]
    criado_em: datetime
    atualizado_em: datetime


class PlanoMidiaResumoLer(BaseModel):
    """Linha da listagem — sem a árvore inteira, para não pagar o custo de
    montar todo plano só para exibir um índice."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    verba_total: _Valor
    soma_campanhas: _Valor
    diferenca: _Valor
    quantidade_campanhas: int
    criado_em: datetime
    atualizado_em: datetime


# --------------------------------------------------------------------------
# acesso, usuários e observabilidade (D-014)
# --------------------------------------------------------------------------
# Nenhum schema desta seção expõe `senha_hash` ou `senha_salt`. A garantia
# é estrutural: `UsuarioLer` lista os campos um a um em vez de herdar do
# modelo, então uma coluna nova só aparece na resposta se alguém a escrever
# aqui de propósito.

# Login é identificador, não texto livre: minúsculas, dígitos, ponto, hífen
# e underscore. Espaço e arroba ficam de fora — arroba porque induziria a
# tratar o campo como e-mail, que ele deliberadamente não é (D-014).
# O padrão aceita maiúscula porque o `pattern` do Pydantic é conferido
# **antes** do `to_lower`: recusar aqui faria 'GIL.MATOS' virar 422 em vez
# de ser normalizado para 'gil.matos'. O que a regra existe para barrar —
# espaço e arroba — continua barrado.
PADRAO_LOGIN = r"^[A-Za-z0-9._-]+$"

Login = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=60,
        pattern=PADRAO_LOGIN,
    ),
]


class LoginPedido(BaseModel):
    """Corpo de `POST /auth/login`.

    O formato do login é validado aqui (422). Isso não fura a regra da
    mensagem genérica: o que não pode vazar é *se aquele login existe*, e
    saber que 'a b@c' não é um login válido não diz nada sobre a base.
    """

    login: Login
    senha: str = Field(min_length=1, max_length=200)


class UsuarioLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    login: str
    papel: Papel
    ativo: bool
    criado_em: datetime
    ultimo_acesso_em: datetime | None = None


class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    login: Login
    senha: str = Field(min_length=6, max_length=200)
    papel: Papel


class UsuarioAtualizar(BaseModel):
    """Todos opcionais. `login` não está aqui de propósito: ele é a
    identidade que aparece na trilha de acesso, e renomeá-lo tornaria os
    eventos antigos difíceis de ler. Trocar de dono é criar outro usuário."""

    nome: str | None = Field(default=None, min_length=1, max_length=120)
    papel: Papel | None = None
    senha: str | None = Field(default=None, min_length=6, max_length=200)
    ativo: bool | None = None


class SenhaProvisoriaLer(BaseModel):
    """Resposta de `POST /usuarios/{id}/senha`.

    A senha em claro aparece **uma vez**, aqui, e nunca mais: o banco guarda
    só o hash scrypt, então nem o servidor consegue recuperá-la depois. Isso
    é propriedade do desenho, não limitação — e a tela precisa deixar
    explícito que fechar o diálogo perde o valor.
    """

    usuario_id: UUID
    login: str
    senha_provisoria: str


class EventoAcessoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ocorrido_em: datetime
    tipo: TipoEventoAcesso
    login_tentado: str | None
    usuario_id: UUID | None
    # Resolvido na leitura por junção; vem nulo quando o usuário já foi
    # excluído — o evento sobrevive a ele de propósito (D-014).
    usuario_login: str | None = None
    ip: str | None
    agente: str | None
    detalhe: str | None


class EventoErroLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ocorrido_em: datetime
    request_id: str | None
    metodo: str
    caminho: str
    status: int
    codigo_erro: str | None
    mensagem: str | None
    usuario_id: UUID | None
    usuario_login: str | None = None
    duracao_ms: int | None


class LoginsDoDia(BaseModel):
    dia: date
    ok: int
    falha: int


class CaminhoComErro(BaseModel):
    caminho: str
    total: int


class ResumoAdmin(BaseModel):
    """Agregados prontos para a tela de administração.

    Tudo é calculado em SQL — a tela existe justamente para quando a tabela
    de eventos ficou grande demais para ser lida linha a linha.
    """

    dias: int
    desde: datetime
    logins_por_dia: list[LoginsDoDia]
    # Proporção de tentativas que falharam na janela, entre 0 e 1. `0.0`
    # quando não houve nenhuma tentativa — ausência de dado não é sucesso,
    # mas também não é falha, e nulo complicaria a tela sem ganho.
    taxa_falha_login: float
    total_logins_ok: int
    total_logins_falha: int
    top_caminhos_com_erro: list[CaminhoComErro]
    erros_4xx: int
    erros_5xx: int
    sessoes_ativas: int
    usuarios_por_papel: dict[str, int]
