"""Logging estruturado.

Em produção sai uma linha JSON por evento, que qualquer agregador consome
sem regex. Em desenvolvimento sai texto legível, porque ninguém quer ler
JSON no terminal enquanto programa.

Todo log dentro de uma requisição carrega o mesmo `request_id`, o que
permite juntar "requisição chegou", "erro do motor" e "requisição
respondeu 422" numa investigação só.
"""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

# ContextVar e não parâmetro: o id precisa chegar a código que não conhece
# HTTP — o motor de taxonomia, por exemplo, que é puro de propósito.
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

CABECALHO_REQUEST_ID = "X-Request-ID"
_ID_VALIDO = re.compile(r"[A-Za-z0-9._-]{1,64}")

# Atributos que o logging já traz e não devem virar campo extra do JSON.
_PADRAO = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"asctime", "message", "taskName"}


def request_id_atual() -> str | None:
    return _request_id.get()


class FormatadorJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "hora": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }

        if (rid := request_id_atual()) is not None:
            evento["request_id"] = rid

        # Campos passados via `logger.info(..., extra={...})`.
        for chave, valor in record.__dict__.items():
            if chave not in _PADRAO and not chave.startswith("_"):
                evento[chave] = valor

        if record.exc_info:
            evento["excecao"] = self.formatException(record.exc_info)

        return json.dumps(evento, ensure_ascii=False, default=str)


class FormatadorTexto(logging.Formatter):
    """Formato de desenvolvimento: curto, com o request id abreviado."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<7} {record.name:<24} {record.getMessage()}"
        if (rid := request_id_atual()) is not None:
            base = f"[{rid[:8]}] {base}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configurar() -> None:
    """Reconfigura o logging raiz e os loggers do uvicorn.

    O uvicorn instala handlers próprios; sem tirá-los, cada linha sairia
    duas vezes — uma no formato dele, outra no nosso.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJson() if settings.log_em_json else FormatadorTexto())

    raiz = logging.getLogger()
    raiz.handlers = [handler]
    raiz.setLevel(settings.log_level.upper())

    for nome in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(nome)
        logger.handlers = []
        logger.propagate = True

    # O log de acesso do uvicorn duplicaria o nosso middleware, que já
    # registra método, rota, status e duração — com o request id junto.
    logging.getLogger("uvicorn.access").disabled = True


def _erro_do_corpo(corpo: bytes) -> tuple[str | None, str | None]:
    """Extrai `(codigo_erro, mensagem)` de um corpo de erro da API.

    Lê o contrato de `app/erros_http.py` (`{"erro": ..., "mensagem": ...}`)
    e cai para o `detail` do FastAPI quando a resposta não seguiu esse
    contrato — um 404 de rota inexistente, por exemplo. Corpo ilegível vira
    `(None, None)`: registro de erro não pode gerar erro.
    """
    if not corpo:
        return None, None
    try:
        dados = json.loads(corpo)
    except (ValueError, UnicodeDecodeError):
        return None, None
    if not isinstance(dados, dict):
        return None, None

    codigo = dados.get("erro")
    mensagem = dados.get("mensagem") or dados.get("detail")
    return (
        codigo if isinstance(codigo, str) else None,
        mensagem if isinstance(mensagem, str) else (json.dumps(mensagem, default=str) if mensagem else None),
    )


class LogDeRequisicoes(BaseHTTPMiddleware):
    """Atribui um request id, registra uma linha por requisição e persiste
    as respostas de erro em `eventos_erro` (D-014).

    A persistência mora aqui, e não num middleware separado, porque depende
    de dois valores que só este ponto tem juntos: o `request_id` que ele
    mesmo criou e a duração medida de ponta a ponta. Um irmão teria que
    recalcular os dois e correria o risco de discordar do log.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("mediabuild.acesso")

    async def dispatch(self, request: Request, call_next):
        # Importados aqui e não no topo para manter `app.logs` sem
        # dependência de banco no import — ele é configurado antes de tudo
        # em `app/main.py`.
        from app.observabilidade import registrar_evento_de_erro

        def usuario_id_atual():
            """Quem fez o pedido, se a rota exigiu sessão.

            Lido de `scope["state"]` e **não** de um ContextVar: o
            `call_next` do BaseHTTPMiddleware roda o resto da aplicação numa
            task filha, e o que ela escreve num ContextVar não volta para
            cá. O `scope` é o mesmo dicionário nas duas pontas, então é ele
            que atravessa. `app/autorizacao.py::usuario_atual` grava lá.
            """
            return request.scope.get("state", {}).get("usuario_id")

        # Respeita um id vindo de fora (proxy, outro serviço) para que o
        # rastro atravesse a fronteira.
        # Só no formato esperado: o valor vai para o log, para o banco e volta
        # no cabeçalho, e um id longo demais faria o registro do erro falhar.
        recebido = request.headers.get(CABECALHO_REQUEST_ID, "")
        rid = recebido if _ID_VALIDO.fullmatch(recebido) else uuid.uuid4().hex
        token = _request_id.set(rid)
        inicio = time.perf_counter()

        try:
            resposta = await call_next(request)
        except Exception as exc:
            duracao = round((time.perf_counter() - inicio) * 1000, 1)
            self.logger.exception(
                "falha nao tratada",
                extra={
                    "metodo": request.method,
                    "rota": request.url.path,
                    "duracao_ms": duracao,
                },
            )
            # Exceção que escapou vira 500 para o cliente; a tela de
            # monitoramento precisa justamente destas.
            registrar_evento_de_erro(
                request_id=rid,
                metodo=request.method,
                caminho=request.url.path,
                status=500,
                codigo_erro="excecao_nao_tratada",
                mensagem=f"{type(exc).__name__}: {exc}",
                usuario_id=usuario_id_atual(),
                duracao_ms=duracao,
            )
            _request_id.reset(token)
            raise

        if resposta.status_code >= 400:
            # O corpo do BaseHTTPMiddleware é um stream de uso único:
            # consumi-lo obriga a remontar a resposta, senão o cliente
            # receberia corpo vazio. Só vale a pena em erro — em 200 o corpo
            # pode ser uma planilha inteira.
            corpo = b"".join([pedaco async for pedaco in resposta.body_iterator])
            codigo_erro, mensagem = _erro_do_corpo(corpo)
            cabecalhos = resposta.headers.raw
            resposta = Response(
                content=corpo,
                status_code=resposta.status_code,
                media_type=resposta.media_type,
            )
            # `raw_headers` e não um dict: preserva cabeçalhos repetidos,
            # como o `set-cookie` que o logout emite.
            resposta.raw_headers = cabecalhos

            registrar_evento_de_erro(
                request_id=rid,
                metodo=request.method,
                caminho=request.url.path,
                status=resposta.status_code,
                codigo_erro=codigo_erro,
                mensagem=mensagem,
                usuario_id=usuario_id_atual(),
                duracao_ms=round((time.perf_counter() - inicio) * 1000, 1),
            )

        duracao = round((time.perf_counter() - inicio) * 1000, 1)
        # Erro de servidor merece WARNING; 4xx é uso normal da API (o 422 do
        # D-005 é o caminho previsto quando falta termo no dicionário).
        nivel = logging.WARNING if resposta.status_code >= 500 else logging.INFO
        self.logger.log(
            nivel,
            f"{request.method} {request.url.path} {resposta.status_code}",
            extra={
                "metodo": request.method,
                "rota": request.url.path,
                "status": resposta.status_code,
                "duracao_ms": duracao,
            },
        )

        resposta.headers[CABECALHO_REQUEST_ID] = rid
        _request_id.reset(token)
        return resposta
