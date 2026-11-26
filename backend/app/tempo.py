"""Tradução entre a data que o analista digita e o instante que o banco guarda.

O banco grava `criado_em` como `timestamptz`, ou seja, **em UTC**. A tela
manda `2026-08-04`, que é uma data de calendário — e data de calendário não
é um instante: ela só vira um intervalo depois de dizer *em que fuso*.

O bug que isto conserta: com a máquina em UTC-3, uma taxonomia gerada às
22h de 04/08 é gravada como 05/08 01:00 UTC. Interpretando `ate=2026-08-04`
como UTC, o intervalo terminava às 04/08 23:59:59 UTC — e o analista perdia
do próprio histórico o que tinha acabado de gerar. Entre 21h e meia-noite,
todo dia.

A decisão é: **comparar sempre em UTC**, e interpretar a data recebida no
fuso da aplicação (`settings.fuso_horario`), nunca no fuso do servidor.
Ler o relógio da máquina funcionaria hoje, com o servidor no mesmo fuso do
usuário, e quebraria silenciosamente na migração para a nuvem, onde o
servidor estará em UTC (docs/NUVEM.md) — a pior forma de quebrar, porque a
suíte continuaria verde na máquina de quem desenvolve.

Datas já com fuso explícito (`2026-08-04T21:00:00-03:00`) são respeitadas
como vieram: quem foi específico sabe o que quis.
"""

from datetime import UTC, datetime, timedelta

from app.config import settings

_MEIA_NOITE = (0, 0, 0, 0)


def _aware(valor: datetime) -> datetime:
    """Amarra o fuso da aplicação a um datetime ingênuo."""
    if valor.tzinfo is not None:
        return valor
    return valor.replace(tzinfo=settings.zona)


def inicio_do_intervalo(desde: datetime) -> datetime:
    """Limite inferior do filtro, em UTC.

    `2026-08-04` vira 04/08 00:00 no fuso local, e não 04/08 00:00 UTC —
    senão as três primeiras horas do dia local (em UTC-3) ficariam de fora.
    """
    return _aware(desde).astimezone(UTC)


def fim_do_intervalo(ate: datetime) -> datetime:
    """Limite superior do filtro, em UTC, inclusivo quando vem só a data.

    O FastAPI converte `2026-08-04` para meia-noite; sem esticar até o fim
    do dia, "até hoje" esconderia tudo o que foi gerado hoje. Quem manda
    hora explícita não é esticado.
    """
    local = _aware(ate)
    if (local.hour, local.minute, local.second, local.microsecond) == _MEIA_NOITE:
        local = local + timedelta(days=1) - timedelta(microseconds=1)
    return local.astimezone(UTC)
