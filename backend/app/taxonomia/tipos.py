"""Estruturas de entrada do motor.

Deliberadamente desacopladas do SQLAlchemy: o motor recebe dados simples,
não modelos. É o que permite testá-lo sem banco e reaproveitá-lo depois
num importador em lote.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.taxonomia.erros import TemplateInvalido
from app.taxonomia.normalizacao import chave_de_busca


@dataclass(frozen=True)
class TokenLiteral:
    """Texto fixo, como a sigla da plataforma."""

    valor: str


@dataclass(frozen=True)
class TokenCampo:
    """Valor vindo dos campos preenchidos pelo analista.

    Dois tipos, na linguagem da planilha do cliente:

    - **Drop list** (`abreviar=True`): o valor precisa existir no dicionário
      De → Para. É o padrão.
    - **Campo livre** (`abreviar=False`): texto digitado, sem dicionário,
      limitado por `max_caracteres`.

    `rotulo` é o nome que o analista lê no formulário ('dimensão do
    criativo'); `chave` é o identificador técnico ('dimensao'). Guardar os
    dois aqui mantém a regra de que o padrão de nomenclatura vive em dados
    — a UI não precisa de uma tabela de rótulos hardcoded.

    `opcional=True` permite deixar em branco: o token some do nome em vez
    de virar erro. Serve para campos que só se aplicam a alguns casos, como
    a secundagem de um criativo que não é vídeo.
    """

    chave: str
    abreviar: bool = True
    rotulo: str | None = None
    max_caracteres: int | None = None
    opcional: bool = False
    categoria: str | None = None

    @property
    def categoria_dicionario(self) -> str:
        """Categoria consultada no dicionário. Por padrão é a própria chave.

        Separar as duas permite que campos diferentes compartilhem
        vocabulário: 'interesse_1' e 'interesse_2' são posições distintas no
        nome, mas o analista cadastra a lista de interesses uma vez só.
        """
        return self.categoria or self.chave


@dataclass(frozen=True)
class TokenMatchId:
    """Posição onde entra o match ID da entidade."""


Token = TokenLiteral | TokenCampo | TokenMatchId


def parse_tokens(brutos: object) -> tuple[Token, ...]:
    """Converte a lista JSONB de `templates_taxonomia.tokens` em tokens tipados."""
    if not isinstance(brutos, list) or not brutos:
        raise TemplateInvalido("a lista de tokens está vazia ou não é uma lista")

    tokens: list[Token] = []
    for i, bruto in enumerate(brutos):
        if not isinstance(bruto, Mapping) or "tipo" not in bruto:
            raise TemplateInvalido(f"token {i} não tem a chave 'tipo'")

        tipo = bruto["tipo"]
        if tipo == "literal":
            valor = bruto.get("valor")
            if not valor:
                raise TemplateInvalido(f"token {i} do tipo 'literal' não tem 'valor'")
            tokens.append(TokenLiteral(valor=str(valor)))
        elif tipo == "campo":
            chave = bruto.get("chave")
            if not chave:
                raise TemplateInvalido(f"token {i} do tipo 'campo' não tem 'chave'")

            maximo = bruto.get("max_caracteres")
            if maximo is not None:
                try:
                    maximo = int(maximo)
                except (TypeError, ValueError):
                    raise TemplateInvalido(
                        f"token {i}: 'max_caracteres' precisa ser um número inteiro"
                    ) from None
                if maximo < 1:
                    raise TemplateInvalido(
                        f"token {i}: 'max_caracteres' precisa ser maior que zero"
                    )

            rotulo = bruto.get("rotulo")
            categoria = bruto.get("categoria")
            tokens.append(
                TokenCampo(
                    chave=str(chave),
                    abreviar=bool(bruto.get("abreviar", True)),
                    rotulo=str(rotulo) if rotulo else None,
                    max_caracteres=maximo,
                    opcional=bool(bruto.get("opcional", False)),
                    categoria=str(categoria) if categoria else None,
                )
            )
        elif tipo == "match_id":
            tokens.append(TokenMatchId())
        else:
            raise TemplateInvalido(f"token {i} tem tipo desconhecido: '{tipo}'")

    return tuple(tokens)


@dataclass(frozen=True)
class Template:
    """Padrão de nomenclatura de um (plataforma, nível).

    `marcador_ausencia` é o texto que ocupa o lugar de um campo opcional
    deixado em branco. Existe para que todos os nomes de um mesmo nível
    tenham a **mesma quantidade de partes**: sem ele, o join descartava a
    parte vazia e as colunas da planilha de performance deslocavam de uma
    linha para a outra, que é justamente o cruzamento que o produto
    protege.

    Mora no template e não no código porque é padrão de nomenclatura —
    trocar 'NA' por outra coisa precisa ser um UPDATE. `""` restaura o
    comportamento antigo (o token some do nome), e é o que as versões de
    template anteriores a esta regra guardam.
    """

    separador: str
    tokens: tuple[Token, ...]
    versao: int = 1
    marcador_ausencia: str = "NA"

    def __post_init__(self) -> None:
        if len(self.separador) != 1:
            raise TemplateInvalido(
                f"o separador precisa ter exatamente 1 caractere, recebido: '{self.separador}'"
            )
        if self.separador in self.marcador_ausencia:
            # Marcador contendo o separador partiria o nome numa parte a
            # mais, desfazendo exatamente a contagem fixa que ele garante.
            raise TemplateInvalido(
                f"o marcador de ausência '{self.marcador_ausencia}' não pode conter "
                f"o separador '{self.separador}'"
            )

    @classmethod
    def de_registro(
        cls,
        separador: str,
        tokens: object,
        versao: int = 1,
        marcador_ausencia: str = "NA",
    ) -> "Template":
        """Constrói a partir das colunas de `templates_taxonomia`."""
        return cls(
            separador=separador,
            tokens=parse_tokens(tokens),
            versao=versao,
            marcador_ausencia=marcador_ausencia or "",
        )


class Dicionario:
    """Índice De → Para das abreviações.

    A busca ignora acentos, caixa e espaços nas bordas, para que
    'conversao' encontre o termo cadastrado como 'Conversão'.
    """

    def __init__(self, entradas: Iterable[tuple[str, str, str]]) -> None:
        """`entradas` são triplas (categoria, termo, abreviacao)."""
        self._por_chave: dict[tuple[str, str], str] = {}
        self._termos_por_categoria: dict[str, list[str]] = {}

        for categoria, termo, abreviacao in entradas:
            cat = categoria.strip().lower()
            self._por_chave[(cat, chave_de_busca(termo))] = abreviacao
            self._termos_por_categoria.setdefault(cat, []).append(termo)

    def buscar(self, categoria: str, termo: str) -> str | None:
        return self._por_chave.get((categoria.strip().lower(), chave_de_busca(termo)))

    def opcoes(self, categoria: str) -> list[str]:
        """Termos cadastrados na categoria, para orientar o analista no erro."""
        return sorted(self._termos_por_categoria.get(categoria.strip().lower(), []))


@dataclass(frozen=True)
class CampoGerado:
    """O que aconteceu com um campo durante a geração.

    `bruto` é o que o analista digitou; `final` é o pedaço que de fato
    entrou no nome, já abreviado e normalizado. Guardar os dois é o que
    permite ao analista cruzar a planilha de performance — que só tem o
    nome, ou seja, o `final` — com o valor legível que ele escolheu.

    `ordem` é a posição do token no template. Vai junto porque JSONB **não
    preserva a ordem das chaves**: sem ela, a exportação não teria como
    reconstruir a sequência do nome a partir do registro salvo.
    """

    final: str
    bruto: str | None
    ordem: int

    def para_json(self) -> dict:
        return {"bruto": self.bruto, "final": self.final, "ordem": self.ordem}


@dataclass(frozen=True)
class Resultado:
    """Nome pronto mais o rastro de cada campo que o compôs."""

    nomenclatura: str
    campos: dict[str, CampoGerado]

    def campos_para_json(self) -> dict[str, dict]:
        """Forma persistida em `taxonomias_geradas.campos_gerados`."""
        return {chave: campo.para_json() for chave, campo in self.campos.items()}
