"""Validador de UTM do MediaBuild (D-012).

O app **confere** a URL de destino; não a monta. Montar exigiria conhecer
regra de landing page, redirecionador e macro de cada plataforma — e o
produto gera nomes.

`validador` é puro (sem SQLAlchemy, sem HTTP), como o motor de taxonomia;
`repositorio` é quem toca o banco.
"""

from app.utm.tipos import Achado, ContextoUtm, ResultadoUtm
from app.utm.validador import contem_match_id, match_ids_no_valor, validar_utm

__all__ = [
    "Achado",
    "ContextoUtm",
    "ResultadoUtm",
    "contem_match_id",
    "match_ids_no_valor",
    "validar_utm",
]
