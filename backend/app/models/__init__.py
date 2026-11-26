"""Modelos SQLAlchemy.

Todo modelo novo precisa ser importado aqui para que o Alembic o enxergue
no autogenerate.
"""

from app.models.acesso import (
    EventoAcesso,
    EventoErro,
    Papel,
    Sessao,
    TipoEventoAcesso,
    Usuario,
)
from app.models.plano_midia import (
    Metrica,
    PlanoMidia,
    PlanoMidiaAnuncio,
    PlanoMidiaCampanha,
    PlanoMidiaGrupo,
)
from app.models.taxonomia import (
    Anuncio,
    Campanha,
    DicionarioAbreviacao,
    GrupoAnuncio,
    LimitePlataforma,
    Nivel,
    Plataforma,
    TaxonomiaGerada,
    TemplateTaxonomia,
)

__all__ = [
    "Anuncio",
    "Campanha",
    "DicionarioAbreviacao",
    "EventoAcesso",
    "EventoErro",
    "GrupoAnuncio",
    "LimitePlataforma",
    "Metrica",
    "Nivel",
    "Papel",
    "PlanoMidia",
    "PlanoMidiaAnuncio",
    "PlanoMidiaCampanha",
    "PlanoMidiaGrupo",
    "Plataforma",
    "Sessao",
    "TaxonomiaGerada",
    "TemplateTaxonomia",
    "TipoEventoAcesso",
    "Usuario",
]
