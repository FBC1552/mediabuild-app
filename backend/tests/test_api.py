"""Testes da API.

Usam o banco real (com rollback ao fim de cada teste), porque o valor aqui
está justamente na integração: rota → motor → banco → código HTTP correto.
"""

import re
import uuid

import pytest
from sqlalchemy import select

from app.models import DicionarioAbreviacao, Plataforma
from app.taxonomia import normalizar
from app.taxonomia.repositorio import carregar_marcadores_ausencia
from tests.conftest import (
    CAMPOS_ANUNCIO,
    CAMPOS_CAMPANHA,
    CAMPOS_GRUPO,
    NOME_ANUNCIO,
    NOME_CAMPANHA,
    NOME_GRUPO,
)


@pytest.fixture
def meta_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "Meta")))


def _sufixo() -> str:
    return uuid.uuid4().hex[:6].upper()


# --------------------------------------------------------------------------
# plataformas
# --------------------------------------------------------------------------

def test_listar_plataformas(cliente):
    r = cliente.get("/plataformas")
    assert r.status_code == 200
    assert {p["nome"] for p in r.json()} >= {"Meta", "Google", "TikTok"}


def test_criar_plataforma_ja_nasce_com_os_tres_niveis(cliente):
    """D-007 exposto pela API."""
    r = cliente.post(
        "/plataformas", json={"nome": f"Plat {_sufixo()}", "sigla": _sufixo()[:4], "limites": 300}
    )
    assert r.status_code == 201
    plataforma_id = r.json()["id"]

    integridade = cliente.get(f"/plataformas/{plataforma_id}/integridade").json()
    assert integridade["completa"] is True

    limites = cliente.get(f"/plataformas/{plataforma_id}/limites").json()
    assert len(limites) == 3

    templates = cliente.get(f"/plataformas/{plataforma_id}/templates").json()
    assert len(templates) == 3


def test_nome_de_plataforma_duplicado_da_409(cliente):
    r = cliente.post("/plataformas", json={"nome": "Meta", "sigla": f"X{_sufixo()[:3]}"})
    assert r.status_code == 409
    assert r.json()["erro"] == "conflito"


def test_plataforma_inexistente_da_404(cliente):
    assert cliente.get(f"/plataformas/{uuid.uuid4()}").status_code == 404


def test_atualizar_limite(cliente, meta_id):
    r = cliente.put(f"/plataformas/{meta_id}/limites/CAMPANHA", json={"limite_caracteres": 120})
    assert r.status_code == 200
    assert r.json()["limite_caracteres"] == 120


def test_limite_precisa_ser_positivo(cliente, meta_id):
    r = cliente.put(f"/plataformas/{meta_id}/limites/CAMPANHA", json={"limite_caracteres": 0})
    assert r.status_code == 422


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------

def test_preview_nao_persiste_nem_consome_match_id(cliente, meta_id):
    corpo = {"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": CAMPOS_CAMPANHA}

    # Contagem relativa: o banco de desenvolvimento pode já ter taxonomias.
    antes = len(cliente.get("/taxonomias", params={"limite": 1000}).json())

    primeiro = cliente.post("/taxonomias/preview", json=corpo).json()
    segundo = cliente.post("/taxonomias/preview", json=corpo).json()

    assert primeiro["nomenclatura"] == segundo["nomenclatura"] == f"{NOME_CAMPANHA}_C0000"
    assert primeiro["match_id_provisorio"] is True
    assert len(cliente.get("/taxonomias", params={"limite": 1000}).json()) == antes


def test_preview_informa_tamanho_e_limite(cliente, meta_id):
    r = cliente.post(
        "/taxonomias/preview",
        json={"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": CAMPOS_CAMPANHA},
    )
    corpo = r.json()
    assert corpo["caracteres"] == len(corpo["nomenclatura"])
    assert corpo["limite_caracteres"] == 400


def test_preview_com_match_id_real(cliente, meta_id):
    r = cliente.post(
        "/taxonomias/preview",
        json={
            "plataforma_id": meta_id,
            "nivel": "CAMPANHA",
            "campos": CAMPOS_CAMPANHA,
            "match_id": "C0042",
        },
    )
    assert r.json()["nomenclatura"] == f"{NOME_CAMPANHA}_C0042"
    assert r.json()["match_id_provisorio"] is False


def test_termo_fora_do_dicionario_da_422_com_opcoes(cliente, meta_id):
    """D-005 chegando ao cliente de forma acionável."""
    r = cliente.post(
        "/taxonomias/preview",
        json={"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": {**CAMPOS_CAMPANHA, "objetivo": "Awareness"}},
    )
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["erro"] == "termo_desconhecido"
    assert corpo["campo"] == "objetivo"
    assert "Conversão" in corpo["opcoes"]


def test_campo_ausente_da_422_dizendo_qual(cliente, meta_id):
    r = cliente.post(
        "/taxonomias/preview", json={"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": {}}
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "campo_ausente"
    # Aponta o primeiro campo faltante na ordem do template, não um genérico.
    assert r.json()["campo"] == "nome_campanha"


def test_campo_livre_longo_demais_da_422(cliente, meta_id):
    """'Nome da campanha' é campo livre de 5 caracteres na planilha."""
    r = cliente.post(
        "/taxonomias/preview",
        json={
            "plataforma_id": meta_id,
            "nivel": "CAMPANHA",
            "campos": {**CAMPOS_CAMPANHA, "nome_campanha": "LONGO DEMAIS"},
        },
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "campo_longo_demais"
    assert r.json()["campo"] == "nome_campanha"


def test_campo_opcional_em_branco_nao_da_erro(cliente, meta_id):
    """Interesse 2 vazio vira marcador em vez de `campo_ausente`.

    O marcador ocupa a posição em vez de sumir com ela: o nome com e sem o
    interesse 2 precisa ter a mesma quantidade de partes, senão as colunas
    da planilha de performance deslocam.
    """
    r = cliente.post(
        "/taxonomias/preview",
        json={
            "plataforma_id": meta_id,
            "nivel": "GRUPO",
            "campos": {**CAMPOS_GRUPO, "interesse_2": ""},
        },
    )
    assert r.status_code == 200, r.text
    # 'posicionamento' (extra opcional do Meta) também está em branco.
    assert r.json()["nomenclatura"] == "F_25-34_BOLSA_NA_SUD_RJ_RMKT_NA_G0000"


def test_opcional_vazio_e_preenchido_tem_a_mesma_quantidade_de_partes(cliente, meta_id):
    """Regressão do deslocamento de coluna, agora pela API."""

    def partes(campos: dict) -> int:
        r = cliente.post(
            "/taxonomias/preview",
            json={"plataforma_id": meta_id, "nivel": "GRUPO", "campos": campos},
        )
        assert r.status_code == 200, r.text
        return len(r.json()["nomenclatura"].split("_"))

    assert partes({**CAMPOS_GRUPO, "interesse_2": ""}) == partes(CAMPOS_GRUPO)


def test_limite_excedido_da_422(cliente, meta_id):
    cliente.put(f"/plataformas/{meta_id}/limites/CAMPANHA", json={"limite_caracteres": 5})
    r = cliente.post(
        "/taxonomias/preview",
        json={"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": CAMPOS_CAMPANHA},
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "limite_excedido"


# --------------------------------------------------------------------------
# fluxo completo
# --------------------------------------------------------------------------

def test_fluxo_completo_campanha_grupo_anuncio(cliente, meta_id):
    """Critério de saída da Fase 3: o fluxo inteiro pela API."""
    campanha = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": meta_id,
            "nome_interno": "Black Friday",
            "campos": CAMPOS_CAMPANHA,
        },
    ).json()
    assert re.fullmatch(r"C\d{4,}", campanha["match_id"])

    grupo = cliente.post(
        "/grupos",
        json={
            "campanha_id": campanha["id"],
            "nome_interno": "Remarketing 30d",
            "campos": CAMPOS_GRUPO,
        },
    ).json()

    anuncio = cliente.post(
        "/anuncios",
        json={
            "grupo_anuncio_id": grupo["id"],
            "nome_interno": "Stories vertical",
            "campos": CAMPOS_ANUNCIO,
        },
    ).json()

    lote = str(uuid.uuid4())
    nomes = []
    for nivel, entidade in (
        ("CAMPANHA", campanha),
        ("GRUPO", grupo),
        ("ANUNCIO", anuncio),
    ):
        r = cliente.post(
            "/taxonomias",
            json={"nivel": nivel, "entidade_id": entidade["id"], "lote_id": lote},
        )
        assert r.status_code == 201, r.text
        nomes.append(r.json()["nomenclatura_final"])

    assert re.fullmatch(rf"{NOME_CAMPANHA}_C\d{{4,}}", nomes[0])
    assert re.fullmatch(rf"{NOME_GRUPO}_G\d{{4,}}", nomes[1])
    assert re.fullmatch(rf"{NOME_ANUNCIO}_A\d{{4,}}", nomes[2])

    do_lote = cliente.get("/taxonomias", params={"lote_id": lote}).json()
    assert len(do_lote) == 3


def test_taxonomia_usa_o_match_id_da_entidade(cliente, meta_id):
    campanha = cliente.post(
        "/campanhas",
        json={"plataforma_id": meta_id, "nome_interno": "x", "campos": {**CAMPOS_CAMPANHA, "objetivo": "Tráfego"}},
    ).json()
    r = cliente.post("/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]})
    assert r.json()["nomenclatura_final"].endswith(campanha["match_id"])


def test_gerar_a_mesma_taxonomia_duas_vezes_da_409(cliente, meta_id):
    """A UNIQUE em nomenclatura_final protege o cruzamento com performance."""
    campanha = cliente.post(
        "/campanhas",
        json={"plataforma_id": meta_id, "nome_interno": "x", "campos": CAMPOS_CAMPANHA},
    ).json()
    corpo = {"nivel": "CAMPANHA", "entidade_id": campanha["id"]}

    assert cliente.post("/taxonomias", json=corpo).status_code == 201
    repetida = cliente.post("/taxonomias", json=corpo)
    assert repetida.status_code == 409
    assert repetida.json()["erro"] == "conflito"


def test_taxonomia_de_entidade_inexistente_da_404(cliente):
    r = cliente.post(
        "/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404


def test_taxonomia_nao_tem_delete_nem_patch(cliente, meta_id):
    """D-004: imutabilidade garantida pela ausência das rotas."""
    campanha = cliente.post(
        "/campanhas",
        json={"plataforma_id": meta_id, "nome_interno": "x", "campos": CAMPOS_CAMPANHA},
    ).json()
    taxonomia = cliente.post(
        "/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]}
    ).json()

    assert cliente.delete(f"/taxonomias/{taxonomia['id']}").status_code == 405
    assert cliente.patch(f"/taxonomias/{taxonomia['id']}", json={}).status_code == 405


# --------------------------------------------------------------------------
# dicionário
# --------------------------------------------------------------------------

def test_cadastrar_termo_destrava_a_geracao(cliente, meta_id):
    """O caminho que a mensagem de erro do D-005 sugere ao analista."""
    corpo = {"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": {**CAMPOS_CAMPANHA, "objetivo": "Awareness"}}
    assert cliente.post("/taxonomias/preview", json=corpo).status_code == 422

    cliente.post(
        "/dicionario",
        json={"categoria": "objetivo", "termo": "Awareness", "abreviacao": "AWR"},
    )

    r = cliente.post("/taxonomias/preview", json=corpo)
    assert r.status_code == 200
    # '_NA_' é o marcador do 'funil', opcional e em branco neste conjunto.
    assert r.json()["nomenclatura"].endswith("_AWR_AGO_NA_C0000")


def test_abreviacao_global_duplicada_da_409(cliente):
    termo = f"Termo {_sufixo()}"
    corpo = {"categoria": "objetivo", "termo": termo, "abreviacao": "XX"}
    assert cliente.post("/dicionario", json=corpo).status_code == 201
    assert cliente.post("/dicionario", json=corpo).status_code == 409


@pytest.mark.parametrize("reservada", ["NA", "na", "Na", " na "])
def test_abreviacao_igual_ao_marcador_e_recusada(cliente, reservada):
    """D-011: 'Nacional' → 'NA' tornaria o nome ambíguo, porque 'NA' é o
    que ocupa a posição de um campo opcional em branco."""
    r = cliente.post(
        "/dicionario",
        json={"categoria": "regiao", "termo": f"Nacional {_sufixo()}", "abreviacao": reservada},
    )
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["erro"] == "abreviacao_reservada"
    assert corpo["campo"] == "abreviacao"
    # Mensagem acionável: diz por que é proibido e o que fazer.
    assert "campo opcional" in corpo["mensagem"]


@pytest.mark.parametrize("livre", ["NAC", "NOR", "NOV", "NATAL", "ANA"])
def test_abreviacao_que_apenas_contem_o_marcador_passa(cliente, livre):
    """A reserva é igualdade exata, não lista negra: conter 'NA' é comum."""
    r = cliente.post(
        "/dicionario",
        json={"categoria": "regiao", "termo": f"Regiao {_sufixo()}", "abreviacao": livre},
    )
    assert r.status_code == 201, r.text


def test_editar_abreviacao_para_o_marcador_e_recusado(cliente):
    """A porta dos fundos: cadastrar 'NAC' e corrigir depois para 'NA'."""
    criada = cliente.post(
        "/dicionario",
        json={"categoria": "regiao", "termo": f"Nacional {_sufixo()}", "abreviacao": "NAC"},
    ).json()

    r = cliente.patch(f"/dicionario/{criada['id']}", json={"abreviacao": "NA"})
    assert r.status_code == 422
    assert r.json()["erro"] == "abreviacao_reservada"

    # E o registro continua como estava: a recusa é antes da escrita.
    assert cliente.get("/dicionario", params={"categoria": "regiao"}).json()
    atual = next(
        i for i in cliente.get("/dicionario", params={"categoria": "regiao"}).json()
        if i["id"] == criada["id"]
    )
    assert atual["abreviacao"] == "NAC"


def test_dicionario_nao_colide_com_marcador_de_ausencia(session):
    """Percorre a tabela **inteira**, no padrão do D-007: a garantia é de
    código e de teste, não de constraint — então uma linha cadastrada por
    fora da API (seed, UPDATE manual) precisa quebrar a suíte."""
    marcadores = set(carregar_marcadores_ausencia(session))
    colisoes = [
        (r.categoria, r.termo, r.abreviacao)
        for r in session.scalars(select(DicionarioAbreviacao))
        if normalizar(r.abreviacao, "_") in marcadores
    ]
    assert colisoes == [], (
        f"abreviações idênticas a um marcador de ausência ({sorted(marcadores)}): {colisoes}"
    )


def test_filtrar_dicionario_por_plataforma_inclui_globais(cliente, meta_id):
    itens = cliente.get("/dicionario", params={"plataforma_id": meta_id}).json()
    categorias = {i["categoria"] for i in itens}
    assert "posicionamento" in categorias  # específica do Meta
    assert "objetivo" in categorias  # global


def test_listar_categorias(cliente):
    categorias = cliente.get("/dicionario/categorias").json()
    assert {"objetivo", "empresa", "canal", "interesse", "formato"} <= set(categorias)


# --------------------------------------------------------------------------
# templates
# --------------------------------------------------------------------------

def test_nova_versao_de_template_desativa_a_anterior(cliente, meta_id):
    # Relativo à versão corrente: o seed cria versões novas quando a
    # estrutura de campos muda, então fixar "2" quebraria a cada mudança.
    antes = cliente.get(
        f"/plataformas/{meta_id}/templates", params={"nivel": "CAMPANHA"}
    ).json()
    versao_atual = max(t["versao"] for t in antes)

    r = cliente.post(
        f"/plataformas/{meta_id}/templates/CAMPANHA",
        json={
            "tokens": [
                {"tipo": "literal", "valor": "FB"},
                {"tipo": "literal", "valor": "V2"},
                {"tipo": "campo", "chave": "objetivo"},
                {"tipo": "match_id"},
            ]
        },
    )
    assert r.status_code == 201
    assert r.json()["versao"] == versao_atual + 1

    todos = cliente.get(f"/plataformas/{meta_id}/templates", params={"nivel": "CAMPANHA"}).json()
    ativos = [t for t in todos if t["ativo"]]
    assert len(ativos) == 1 and ativos[0]["versao"] == versao_atual + 1

    preview = cliente.post(
        "/taxonomias/preview",
        json={"plataforma_id": meta_id, "nivel": "CAMPANHA", "campos": CAMPOS_CAMPANHA},
    ).json()
    assert preview["nomenclatura"] == "FB_V2_CV_C0000"
    assert preview["template_versao"] == versao_atual + 1


def test_template_com_token_invalido_da_422(cliente, meta_id):
    r = cliente.post(
        f"/plataformas/{meta_id}/templates/CAMPANHA",
        json={"tokens": [{"tipo": "inexistente"}]},
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "template_invalido"


# --------------------------------------------------------------------------
# OpenAPI
# --------------------------------------------------------------------------

def test_openapi_publica_as_rotas(cliente):
    caminhos = cliente.get("/openapi.json").json()["paths"]
    for esperado in (
        "/plataformas",
        "/campanhas",
        "/grupos",
        "/anuncios",
        "/dicionario",
        "/taxonomias",
        "/taxonomias/preview",
    ):
        assert esperado in caminhos, esperado
