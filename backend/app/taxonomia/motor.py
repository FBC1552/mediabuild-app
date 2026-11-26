"""Motor de taxonomia — o núcleo do MediaBuild.

Função **pura**: recebe template, campos, dicionário e match ID; devolve o
nome. Não acessa banco nem HTTP. É o que permite testá-lo de forma
exaustiva e reaproveitá-lo depois num importador em lote.

Pipeline (AVALIACAO.md):
    campos brutos
      -> percorre os tokens ordenados do template
      -> abrevia via dicionário (ou marcador de ausência, se opcional vazio)
      -> normaliza (NFD, sem acento, maiúsculo, espaço -> separador)
      -> monta (join com separador)
      -> valida (RegEx + limite de caracteres)
      -> nomenclatura_final

A checagem de colisão **não** está aqui: depende do banco e é feita na
camada de persistência, pela UNIQUE em `taxonomias_geradas`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.taxonomia.erros import (
    CampoAusente,
    CampoLongoDemais,
    LimiteExcedido,
    NomeInvalido,
    TermoDesconhecido,
)
from app.taxonomia.normalizacao import (
    PADRAO_VALIDO,
    caracteres_invalidos,
    normalizar,
)
from app.taxonomia.tipos import (
    CampoGerado,
    Dicionario,
    Resultado,
    Template,
    TokenCampo,
    TokenLiteral,
    TokenMatchId,
)


@dataclass(frozen=True)
class ParteResolvida:
    """Um pedaço do nome mais o rastro de onde ele veio.

    Só tokens de campo têm `chave`; literal e match ID entram no nome mas
    não são campos do formulário, então não vão para `campos_gerados`.
    """

    texto: str
    chave: str | None = None
    bruto: str | None = None


def resolver_token(
    token: TokenLiteral | TokenCampo | TokenMatchId,
    campos: Mapping[str, str],
    dicionario: Dicionario,
    match_id: str,
    separador: str,
    marcador_ausencia: str = "",
) -> ParteResolvida:
    """Resolve um token para o pedaço de texto já normalizado."""
    if isinstance(token, TokenLiteral):
        return ParteResolvida(normalizar(token.valor, separador))

    if isinstance(token, TokenMatchId):
        return ParteResolvida(normalizar(match_id, separador))

    # TokenCampo
    bruto = campos.get(token.chave)
    if bruto is None or not str(bruto).strip():
        if token.opcional:
            # Marcador em vez de sumir: nomes do mesmo nível precisam ter a
            # mesma quantidade de partes, senão as colunas da planilha de
            # performance deslocam de uma linha para a outra. Marcador vazio
            # ('' no template) mantém o comportamento antigo, de omitir.
            return ParteResolvida(
                normalizar(marcador_ausencia, separador), chave=token.chave, bruto=None
            )
        raise CampoAusente(token.chave)
    bruto = str(bruto).strip()

    # O limite do campo vale sobre o que o analista digitou, não sobre a
    # forma normalizada — é o texto dele que precisa caber na regra.
    if token.max_caracteres is not None and len(bruto) > token.max_caracteres:
        raise CampoLongoDemais(token.chave, bruto, token.max_caracteres)

    if not token.abreviar:
        return ParteResolvida(normalizar(bruto, separador), chave=token.chave, bruto=bruto)

    categoria = token.categoria_dicionario
    abreviacao = dicionario.buscar(categoria, bruto)
    if abreviacao is None:
        # D-005: erro explícito, listando as opções cadastradas.
        raise TermoDesconhecido(categoria, bruto, dicionario.opcoes(categoria), chave=token.chave)

    return ParteResolvida(normalizar(abreviacao, separador), chave=token.chave, bruto=bruto)


def validar(nome: str, limite_caracteres: int | None) -> None:
    """Rede de segurança: RegEx e limite da plataforma."""
    if not PADRAO_VALIDO.match(nome):
        raise NomeInvalido(nome, caracteres_invalidos(nome))

    if limite_caracteres is not None and len(nome) > limite_caracteres:
        raise LimiteExcedido(nome, limite_caracteres)


def gerar_detalhado(
    template: Template,
    campos: Mapping[str, str],
    dicionario: Dicionario,
    match_id: str,
    limite_caracteres: int | None = None,
) -> Resultado:
    """Gera a nomenclatura final **e** o rastro de cada campo.

    Levanta `ErroTaxonomia` (ou subclasse) quando a entrada não permite
    produzir um nome válido — nunca devolve um nome aproximado.

    O rastro (`Resultado.campos`) é o que vai para
    `taxonomias_geradas.campos_gerados`: para cada campo, o que o analista
    digitou e o pedaço que entrou no nome. É o que permite cruzar o nome
    com a planilha de performance campo a campo, sem tentar fatiar o nome
    de volta pelo separador — fatiar seria ambíguo assim que um valor
    contivesse o separador.
    """
    resolvidas = [
        resolver_token(
            token,
            campos,
            dicionario,
            match_id,
            template.separador,
            template.marcador_ausencia,
        )
        for token in template.tokens
    ]

    nome = template.separador.join(p.texto for p in resolvidas if p.texto)
    validar(nome, limite_caracteres)

    gerados: dict[str, CampoGerado] = {}
    for ordem, parte in enumerate(resolvidas):
        if parte.chave is not None:
            gerados[parte.chave] = CampoGerado(
                final=parte.texto, bruto=parte.bruto, ordem=ordem
            )

    return Resultado(nomenclatura=nome, campos=gerados)


def gerar_nomenclatura(
    template: Template,
    campos: Mapping[str, str],
    dicionario: Dicionario,
    match_id: str,
    limite_caracteres: int | None = None,
) -> str:
    """Só o nome. Atalho para quem não precisa do rastro por campo."""
    return gerar_detalhado(
        template, campos, dicionario, match_id, limite_caracteres
    ).nomenclatura
