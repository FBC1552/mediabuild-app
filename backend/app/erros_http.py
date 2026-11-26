"""Tradução de erros de domínio para respostas HTTP.

Objetivo: o cliente nunca receber 500 por uma falha previsível. Erro do
motor vira 422 com o campo culpado e as opções aceitas; violação de
unicidade vira 409.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.erros_acesso import ErroAcesso, ErroAutenticacao
from app.erros_plano import (
    EntidadeForaDaHierarquia,
    ErroPlano,
    KpiPrimarioInvalido,
    MetricaDesconhecida,
)
from app.taxonomia import (
    AbreviacaoReservada,
    CampoAusente,
    CampoLongoDemais,
    ErroTaxonomia,
    LimiteExcedido,
    NomeInvalido,
    TemplateInvalido,
    TermoDesconhecido,
)

# Código estável por tipo de erro, para o cliente tratar sem parsear texto.
_CODIGOS: dict[type[ErroTaxonomia], str] = {
    TermoDesconhecido: "termo_desconhecido",
    AbreviacaoReservada: "abreviacao_reservada",
    CampoAusente: "campo_ausente",
    CampoLongoDemais: "campo_longo_demais",
    NomeInvalido: "nome_invalido",
    LimiteExcedido: "limite_excedido",
    TemplateInvalido: "template_invalido",
}

_CODIGOS_PLANO: dict[type[ErroPlano], str] = {
    MetricaDesconhecida: "metrica_desconhecida",
    EntidadeForaDaHierarquia: "entidade_fora_da_hierarquia",
    KpiPrimarioInvalido: "kpi_primario_invalido",
}

logger = logging.getLogger("mediabuild.erros")


def corpo_do_erro(exc: ErroTaxonomia) -> dict:
    corpo: dict = {
        "erro": _CODIGOS.get(type(exc), "erro_taxonomia"),
        "mensagem": str(exc),
    }
    if isinstance(exc, TermoDesconhecido):
        corpo["campo"] = exc.chave
        corpo["opcoes"] = exc.opcoes
    elif isinstance(exc, CampoAusente | CampoLongoDemais | AbreviacaoReservada):
        corpo["campo"] = exc.chave
    return corpo


def corpo_do_erro_plano(exc: ErroPlano) -> dict:
    corpo: dict = {
        "erro": _CODIGOS_PLANO.get(type(exc), "erro_plano"),
        "mensagem": str(exc),
    }
    if isinstance(exc, MetricaDesconhecida | KpiPrimarioInvalido):
        corpo["campo"] = exc.chave
        corpo["opcoes"] = exc.opcoes
    elif isinstance(exc, EntidadeForaDaHierarquia):
        corpo["campo"] = exc.chave
    return corpo


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroTaxonomia)
    async def _erro_taxonomia(_: Request, exc: ErroTaxonomia) -> JSONResponse:
        corpo = corpo_do_erro(exc)
        # INFO, não ERROR: 422 aqui é o caminho previsto do D-005, não falha
        # do sistema. Fica registrado porque a frequência por categoria diz
        # quais termos faltam no dicionário.
        logger.info(
            "erro de taxonomia",
            extra={"codigo": corpo["erro"], "campo": corpo.get("campo")},
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=corpo)

    @app.exception_handler(ErroPlano)
    async def _erro_plano(_: Request, exc: ErroPlano) -> JSONResponse:
        corpo = corpo_do_erro_plano(exc)
        logger.info(
            "erro de plano de midia",
            extra={"codigo": corpo["erro"], "campo": corpo.get("campo")},
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=corpo)

    @app.exception_handler(ErroAutenticacao)
    async def _erro_autenticacao(_: Request, exc: ErroAutenticacao) -> JSONResponse:
        # 401 e 403 saem no mesmo formato de todos os outros erros do
        # projeto — `erro` estável mais `mensagem` pronta para exibir —, e
        # não no `{"detail"}` do FastAPI. A tela escolhe o que fazer pelo
        # código: `sessao_expirada` abre diálogo sobre o formulário
        # preenchido; `nao_autenticado` manda para o login.
        corpo = {"erro": exc.codigo, "mensagem": str(exc)}
        logger.info("acesso recusado", extra={"codigo": exc.codigo, "status": exc.status})
        cabecalhos = (
            # 401 sem WWW-Authenticate é tecnicamente incompleto; `Cookie`
            # não é um esquema registrado, mas dizer isso é mais honesto que
            # anunciar `Basic`, que faria o navegador abrir a caixa de
            # usuário/senha dele por cima da nossa tela de login.
            {"WWW-Authenticate": 'Cookie realm="MediaBuild"'} if exc.status == 401 else None
        )
        return JSONResponse(status_code=exc.status, content=corpo, headers=cabecalhos)

    @app.exception_handler(ErroAcesso)
    async def _erro_acesso(_: Request, exc: ErroAcesso) -> JSONResponse:
        # 409 e não 422: o corpo enviado está correto, o que impede a
        # operação é o estado atual do banco (o último admin, a própria
        # conta). Nunca 500 — são desfechos previstos, com texto acionável.
        corpo = {"erro": exc.codigo, "mensagem": str(exc)}
        logger.warning("operacao de acesso bloqueada", extra={"codigo": exc.codigo})
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=corpo)

    @app.exception_handler(IntegrityError)
    async def _integridade(_: Request, exc: IntegrityError) -> JSONResponse:
        original = str(getattr(exc, "orig", exc))
        logger.warning("violacao de integridade", extra={"detalhe": original[:200]})

        if "duplicate key" in original or "already exists" in original:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "erro": "conflito",
                    "mensagem": "Já existe um registro com esse valor único. "
                    "Se for uma nomenclatura, ela já foi gerada antes.",
                },
            )

        if "violates foreign key" in original:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "erro": "referencia_invalida",
                    "mensagem": "O registro referenciado não existe ou não pode ser removido "
                    "porque há dados dependentes.",
                },
            )

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"erro": "conflito", "mensagem": "A operação violou uma restrição do banco."},
        )
