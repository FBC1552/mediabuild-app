import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import logs
from app.autorizacao import exige_acesso_ao_produto, exige_dicionario
from app.config import settings
from app.db import get_session
from app.erros_http import registrar_handlers
from app.routers import (
    auth,
    dicionario,
    hierarquia,
    metricas,
    monitoramento,
    planos,
    plataformas,
    taxonomias,
    usuarios,
    utm,
)

logs.configurar()
logger = logging.getLogger("mediabuild")

@asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "aplicacao iniciada",
        extra={"debug": settings.debug, "log_json": settings.log_em_json},
    )
    yield
    logger.info("aplicacao encerrada")


app = FastAPI(
    title="MediaBuild API",
    description="Gerador de taxonomias para campanhas de mídia paga.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)

# Ordem importa: o log de requisições fica por fora para medir o tempo
# total, inclusive o que o CORS gasta.
app.add_middleware(logs.LogDeRequisicoes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origens_permitidas,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[logs.CABECALHO_REQUEST_ID],
)

registrar_handlers(app)

# Autorização pendurada aqui, no ponto de montagem, e não rota a rota
# (D-014). O motivo é de manutenção: uma rota nova dentro de qualquer um
# destes routers já nasce protegida, sem depender de alguém lembrar do
# decorator. `exige_acesso_ao_produto` exige sessão válida e recusa DELETE
# para o papel `basico` — por método HTTP, então a próxima rota de remoção
# que for escrita também nasce fora do alcance dele.
PRODUTO = [Depends(exige_acesso_ao_produto)]

app.include_router(auth.router)
app.include_router(plataformas.router, dependencies=PRODUTO)
app.include_router(hierarquia.router, dependencies=PRODUTO)
# O dicionário inteiro, inclusive o GET, some para o papel `basico`: a aba
# não aparece para ele, e uma aba que abre vazia por 403 seria pior do que
# uma que não existe.
app.include_router(dicionario.router, dependencies=[Depends(exige_dicionario)])
app.include_router(taxonomias.router, dependencies=PRODUTO)
app.include_router(utm.router, dependencies=PRODUTO)
app.include_router(metricas.router, dependencies=PRODUTO)
app.include_router(planos.router, dependencies=PRODUTO)
# Estes dois já trazem `Depends(exige_admin)` no próprio APIRouter.
app.include_router(usuarios.router)
app.include_router(monitoramento.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    """Liveness: o processo está de pé. Não depende do banco de propósito —
    o container não deve ser reiniciado só porque o Postgres piscou."""
    return {"status": "ok", "app": settings.app_name}


@app.get("/health/ready", tags=["infra"])
def ready(response: Response, session: Session = Depends(get_session)) -> dict[str, str]:
    """Readiness: a API consegue de fato falar com o Postgres."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - queremos reportar qualquer falha de conexão
        # A exceção do psycopg cita host, porta e usuário. Vai para o log,
        # não para a resposta: /health/ready não tem autenticação.
        logger.exception("banco indisponivel no readiness")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        corpo = {"status": "erro", "database": "indisponivel"}
        if settings.debug:
            corpo["detalhe"] = str(exc)
        return corpo

    return {"status": "ok", "database": "conectado"}
