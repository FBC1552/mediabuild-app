"""Persistência dos eventos de acesso e de erro (D-014).

O log estruturado de `app/logs.py` continua sendo a fonte para investigação
profunda. Esta camada existe para outra pergunta: a tela de administração
precisa responder "quem entrou hoje" e "o que está falhando" sem que alguém
tenha acesso ao stdout do container.

Duas regras duras aqui:

1. **Gravar evento nunca pode derrubar a requisição do usuário.** Se a
   tabela sumir, se o banco engasgar, se o schema estiver atrasado — o
   usuário recebe a resposta dele e o problema vira uma linha de log. O
   inverso (falhar a requisição porque a auditoria falhou) transformaria a
   observabilidade em ponto único de falha do produto inteiro.

2. **O evento de erro usa sessão própria.** A sessão da requisição pode
   estar exatamente em estado de rollback *por causa* do erro que estamos
   tentando registrar; reaproveitá-la significaria perder o registro
   justamente nos casos mais interessantes.
"""

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import EventoAcesso, EventoErro, TipoEventoAcesso

logger = logging.getLogger("mediabuild.observabilidade")

# Fábrica da sessão usada só para gravar evento de erro. É variável de
# módulo, e não `SessionLocal` chamado direto, para que a suíte possa
# amarrá-la à conexão transacional do teste (senão cada 404 testado deixaria
# uma linha no banco de desenvolvimento) e para que o teste de resiliência
# possa injetar uma fábrica que explode.
fabrica_de_sessao: Callable[[], Session] = SessionLocal


def registrar_evento_acesso(
    session: Session,
    *,
    tipo: str,
    usuario_id: UUID | None = None,
    login_tentado: str | None = None,
    ip: str | None = None,
    agente: str | None = None,
    detalhe: str | None = None,
) -> None:
    """Enfileira um evento de acesso na sessão recebida (sem commit).

    Recebe a sessão da requisição de propósito: login e logout são operações
    que já estão escrevendo (sessão criada, sessão revogada) e o evento tem
    que ser atômico com elas. Um logout que revoga mas não registra, ou o
    contrário, é pior que nenhum dos dois.
    """
    try:
        session.add(
            EventoAcesso(
                tipo=TipoEventoAcesso(tipo),
                usuario_id=usuario_id,
                login_tentado=login_tentado,
                ip=ip,
                agente=agente,
                detalhe=detalhe,
            )
        )
    except Exception:  # noqa: BLE001 - auditoria nunca derruba o fluxo
        logger.exception("falha ao registrar evento de acesso", extra={"tipo": tipo})


def registrar_evento_de_erro(
    *,
    request_id: str | None,
    metodo: str,
    caminho: str,
    status: int,
    codigo_erro: str | None,
    mensagem: str | None,
    usuario_id: UUID | None,
    duracao_ms: float | None,
) -> None:
    """Grava uma resposta com status >= 400, em sessão própria.

    Silencioso por contrato: qualquer falha aqui vira log e nada mais.
    """
    try:
        with fabrica_de_sessao() as session:
            session.add(
                EventoErro(
                    request_id=request_id,
                    metodo=metodo[:10],
                    caminho=caminho[:400],
                    status=status,
                    codigo_erro=codigo_erro[:60] if codigo_erro else None,
                    mensagem=mensagem[:2000] if mensagem else None,
                    usuario_id=usuario_id,
                    duracao_ms=int(duracao_ms) if duracao_ms is not None else None,
                )
            )
            session.commit()
    except Exception:  # noqa: BLE001 - ver docstring do módulo
        logger.exception(
            "falha ao registrar evento de erro",
            extra={"caminho": caminho, "status": status},
        )
