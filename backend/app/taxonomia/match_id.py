"""Geração de match ID (D-006).

Fica fora de `motor.py` de propósito: depende do banco, e o motor precisa
continuar puro. O motor recebe o match ID já pronto.

Formato: inicial do nível + 4 dígitos (`C0001`, `G0001`, `A0001`).
Passa de 4 dígitos naturalmente quando estourar 9999 (`C10000`) — a coluna
`match_id` tem 20 caracteres, e o zero-padding é só estética.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Nivel

_SEQUENCE_POR_NIVEL = {
    Nivel.CAMPANHA: ("seq_match_campanha", "C"),
    Nivel.GRUPO: ("seq_match_grupo", "G"),
    Nivel.ANUNCIO: ("seq_match_anuncio", "A"),
}


def gerar_match_id(session: Session, nivel: Nivel) -> str:
    """Reserva o próximo match ID do nível.

    Usa `nextval`, que é atômico: dois processos concorrentes nunca recebem
    o mesmo número, e o valor não é devolvido em caso de rollback — o que é
    aceitável, já que buracos na sequência não têm significado.
    """
    sequence, prefixo = _SEQUENCE_POR_NIVEL[nivel]
    proximo = session.execute(text(f"SELECT nextval('{sequence}')")).scalar_one()
    return f"{prefixo}{proximo:04d}"
