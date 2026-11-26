"""Testes de geração de match ID (D-006). Precisam de Postgres."""

import re

from app.models import Nivel
from app.taxonomia.match_id import gerar_match_id


def test_formato_por_nivel(session):
    assert re.fullmatch(r"C\d{4,}", gerar_match_id(session, Nivel.CAMPANHA))
    assert re.fullmatch(r"G\d{4,}", gerar_match_id(session, Nivel.GRUPO))
    assert re.fullmatch(r"A\d{4,}", gerar_match_id(session, Nivel.ANUNCIO))


def test_ids_consecutivos_nao_se_repetem(session):
    gerados = [gerar_match_id(session, Nivel.CAMPANHA) for _ in range(50)]
    assert len(set(gerados)) == 50


def test_sequences_dos_niveis_sao_independentes(session):
    """Um match ID de campanha não deve consumir a numeração de grupo."""
    campanha = gerar_match_id(session, Nivel.CAMPANHA)
    grupo = gerar_match_id(session, Nivel.GRUPO)
    assert campanha[1:] != "" and grupo[1:] != ""
    assert campanha[0] == "C" and grupo[0] == "G"


def test_id_serve_como_token_de_nomenclatura(session):
    """Precisa passar na RegEx de validação sem transformação."""
    from app.taxonomia.normalizacao import PADRAO_VALIDO

    assert PADRAO_VALIDO.match(gerar_match_id(session, Nivel.CAMPANHA))
