"""Conversão de data de calendário para instante UTC (`app/tempo.py`).

Testes puros: não dependem de banco nem da hora em que a suíte roda. Um
teste que só quebra depois das 21h não serve para um bug que só aparece
depois das 21h.
"""

from datetime import UTC, datetime

import pytest

from app.config import settings
from app.tempo import fim_do_intervalo, inicio_do_intervalo


@pytest.fixture(autouse=True)
def _fuso_de_sao_paulo(monkeypatch):
    """Fixa o fuso da aplicação: o teste verifica a regra, não a config."""
    monkeypatch.setattr(settings, "fuso_horario", "America/Sao_Paulo")


def test_data_pura_vira_meia_noite_local_em_utc():
    # 04/08 00:00 em São Paulo (UTC-3) é 04/08 03:00 UTC.
    assert inicio_do_intervalo(datetime(2026, 8, 4)) == datetime(2026, 8, 4, 3, tzinfo=UTC)


def test_ate_estica_ate_o_fim_do_dia_local():
    # 04/08 23:59:59.999999 local é 05/08 02:59:59.999999 UTC — e é por isso
    # que uma taxonomia gerada às 22h locais (01:00 UTC do dia seguinte)
    # continua dentro de 'ate=2026-08-04'.
    fim = fim_do_intervalo(datetime(2026, 8, 4))
    assert fim == datetime(2026, 8, 5, 2, 59, 59, 999999, tzinfo=UTC)
    assert datetime(2026, 8, 5, 1, 0, tzinfo=UTC) <= fim


def test_hora_explicita_nao_e_esticada():
    assert fim_do_intervalo(datetime(2026, 8, 4, 12, 30)) == datetime(
        2026, 8, 4, 15, 30, tzinfo=UTC
    )


def test_fuso_explicito_do_cliente_e_respeitado():
    """Quem manda offset sabe o que quis — não reinterpretamos."""
    com_fuso = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)
    assert inicio_do_intervalo(com_fuso) == com_fuso
    # Meia-noite UTC também é meia-noite: continua esticando, mas em UTC.
    assert fim_do_intervalo(com_fuso) == datetime(2026, 8, 4, 23, 59, 59, 999999, tzinfo=UTC)


def test_fuso_utc_configurado_nao_desloca(monkeypatch):
    """Servidor e usuário em UTC: a conversão vira identidade."""
    monkeypatch.setattr(settings, "fuso_horario", "UTC")
    assert inicio_do_intervalo(datetime(2026, 8, 4)) == datetime(2026, 8, 4, tzinfo=UTC)


def test_fuso_invalido_e_recusado_na_configuracao():
    from app.config import Settings

    with pytest.raises(ValueError, match="não é um fuso IANA conhecido"):
        Settings(debug=True, fuso_horario="America/Nao_Existe")
