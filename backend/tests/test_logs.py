"""Testes do logging estruturado.

O valor de um log é ser investigável depois. Aqui isso quer dizer: sai
JSON parseável, os campos extras aparecem, e todas as linhas de uma mesma
requisição carregam o mesmo `request_id`.
"""

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import logs
from app.logs import CABECALHO_REQUEST_ID, FormatadorJson, FormatadorTexto, LogDeRequisicoes


def registro(mensagem: str = "oi", **extras) -> logging.LogRecord:
    r = logging.LogRecord("mediabuild.teste", logging.INFO, __file__, 1, mensagem, None, None)
    for chave, valor in extras.items():
        setattr(r, chave, valor)
    return r


# --------------------------------------------------------------------------
# formatadores
# --------------------------------------------------------------------------

def test_json_e_parseavel_e_tem_os_campos_base():
    evento = json.loads(FormatadorJson().format(registro("nome gerado")))
    assert evento["mensagem"] == "nome gerado"
    assert evento["nivel"] == "INFO"
    assert evento["logger"] == "mediabuild.teste"
    assert evento["hora"]


def test_json_inclui_os_campos_passados_em_extra():
    """É o que permite agrupar por categoria depois, sem regex na mensagem."""
    evento = json.loads(
        FormatadorJson().format(registro("erro de taxonomia", codigo="termo_desconhecido"))
    )
    assert evento["codigo"] == "termo_desconhecido"


def test_json_nao_vaza_os_atributos_internos_do_logging():
    evento = json.loads(FormatadorJson().format(registro()))
    assert "msg" not in evento
    assert "args" not in evento
    assert "levelno" not in evento


def test_json_serializa_valor_nao_serializavel_em_vez_de_estourar():
    """Um log não pode derrubar a requisição que ele está descrevendo."""
    evento = json.loads(FormatadorJson().format(registro(objeto=object())))
    assert isinstance(evento["objeto"], str)


def test_json_inclui_o_traceback_quando_ha_excecao():
    try:
        raise ValueError("exemplo")
    except ValueError:
        import sys

        r = registro("falhou")
        r.exc_info = sys.exc_info()
        evento = json.loads(FormatadorJson().format(r))

    assert "ValueError: exemplo" in evento["excecao"]


def test_formato_texto_e_legivel():
    linha = FormatadorTexto().format(registro("nome gerado"))
    assert "nome gerado" in linha
    assert "INFO" in linha
    assert not linha.startswith("{")


# --------------------------------------------------------------------------
# middleware
# --------------------------------------------------------------------------

def app_de_teste() -> FastAPI:
    app = FastAPI()
    app.add_middleware(LogDeRequisicoes)

    @app.get("/ok")
    def ok():
        logging.getLogger("mediabuild.teste").info("durante a requisicao")
        return {"request_id": logs.request_id_atual()}

    @app.get("/explode")
    def explode():
        raise RuntimeError("falha proposital")

    return app


def test_devolve_o_request_id_no_cabecalho():
    r = TestClient(app_de_teste()).get("/ok")
    assert r.status_code == 200
    assert r.headers[CABECALHO_REQUEST_ID]


def test_o_id_do_cabecalho_e_o_visto_pelo_codigo_da_rota():
    """O rastro só serve se o log da rota e o do acesso baterem."""
    r = TestClient(app_de_teste()).get("/ok")
    assert r.json()["request_id"] == r.headers[CABECALHO_REQUEST_ID]


def test_respeita_um_request_id_vindo_de_fora():
    """Para o rastro atravessar a fronteira de um proxy ou outro serviço."""
    r = TestClient(app_de_teste()).get("/ok", headers={CABECALHO_REQUEST_ID: "abc-123"})
    assert r.headers[CABECALHO_REQUEST_ID] == "abc-123"
    assert r.json()["request_id"] == "abc-123"


def test_cada_requisicao_recebe_um_id_diferente():
    cliente = TestClient(app_de_teste())
    ids = {cliente.get("/ok").headers[CABECALHO_REQUEST_ID] for _ in range(5)}
    assert len(ids) == 5


def test_o_id_nao_vaza_de_uma_requisicao_para_a_proxima():
    """ContextVar mal resetada faria um log aparecer sob o id errado."""
    cliente = TestClient(app_de_teste())
    cliente.get("/ok")
    assert logs.request_id_atual() is None


def test_registra_metodo_rota_status_e_duracao(caplog):
    with caplog.at_level(logging.INFO, logger="mediabuild.acesso"):
        TestClient(app_de_teste()).get("/ok")

    acesso = next(r for r in caplog.records if r.name == "mediabuild.acesso")
    assert acesso.metodo == "GET"
    assert acesso.rota == "/ok"
    assert acesso.status == 200
    assert acesso.duracao_ms >= 0


def test_erro_nao_tratado_e_registrado_com_traceback(caplog):
    cliente = TestClient(app_de_teste(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="mediabuild.acesso"):
        resposta = cliente.get("/explode")

    assert resposta.status_code == 500
    erro = next(r for r in caplog.records if r.levelno >= logging.ERROR)
    assert erro.exc_info is not None
    assert erro.rota == "/explode"


def test_o_id_e_resetado_mesmo_quando_a_rota_estoura():
    cliente = TestClient(app_de_teste(), raise_server_exceptions=False)
    cliente.get("/explode")
    assert logs.request_id_atual() is None
