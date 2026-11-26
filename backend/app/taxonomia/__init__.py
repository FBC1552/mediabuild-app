"""Motor de taxonomia do MediaBuild.

Núcleo puro: `gerar_nomenclatura` não toca banco nem HTTP.
A geração de match ID (`app.taxonomia.match_id`) é separada justamente
por depender do banco.
"""

from app.taxonomia.erros import (
    AbreviacaoReservada,
    CampoAusente,
    CampoLongoDemais,
    ErroTaxonomia,
    LimiteExcedido,
    NomeInvalido,
    TemplateInvalido,
    TermoDesconhecido,
)
from app.taxonomia.motor import (
    ParteResolvida,
    gerar_detalhado,
    gerar_nomenclatura,
    resolver_token,
    validar,
)
from app.taxonomia.normalizacao import normalizar, remover_acentos
from app.taxonomia.tipos import (
    CampoGerado,
    Dicionario,
    Resultado,
    Template,
    TokenCampo,
    TokenLiteral,
    TokenMatchId,
    parse_tokens,
)

__all__ = [
    "AbreviacaoReservada",
    "CampoAusente",
    "CampoGerado",
    "CampoLongoDemais",
    "Dicionario",
    "ErroTaxonomia",
    "LimiteExcedido",
    "NomeInvalido",
    "ParteResolvida",
    "Resultado",
    "Template",
    "TemplateInvalido",
    "TermoDesconhecido",
    "TokenCampo",
    "TokenLiteral",
    "TokenMatchId",
    "gerar_detalhado",
    "gerar_nomenclatura",
    "normalizar",
    "parse_tokens",
    "remover_acentos",
    "resolver_token",
    "validar",
]
