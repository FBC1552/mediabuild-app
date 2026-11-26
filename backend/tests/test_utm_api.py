"""Validador de UTM na superfície da API — `POST /utm/validar` (D-012).

O que estes testes cobrem e os puros não: o `repositorio.py` montando o
contexto a partir do banco (subindo anúncio → grupo → campanha pelos ids
denormalizados do D-009), o contrato HTTP e a promessa de que **nada é
persistido**.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.models import Plataforma, TaxonomiaGerada
from tests.conftest import CAMPOS_ANUNCIO, CAMPOS_CAMPANHA, CAMPOS_GRUPO


@pytest.fixture
def meta_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "Meta")))


@pytest.fixture
def hierarquia(cliente, meta_id):
    """Campanha → grupo → anúncio, os três com nomenclatura gerada."""
    campanha = cliente.post(
        "/campanhas",
        json={"plataforma_id": meta_id, "nome_interno": "Black Friday", "campos": CAMPOS_CAMPANHA},
    ).json()
    grupo = cliente.post(
        "/grupos",
        json={"campanha_id": campanha["id"], "nome_interno": "Remarketing", "campos": CAMPOS_GRUPO},
    ).json()
    anuncio = cliente.post(
        "/anuncios",
        json={
            "grupo_anuncio_id": grupo["id"],
            "nome_interno": "Fivela 15s",
            "campos": CAMPOS_ANUNCIO,
        },
    ).json()

    taxonomias = {}
    for nivel, entidade in (("CAMPANHA", campanha), ("GRUPO", grupo), ("ANUNCIO", anuncio)):
        r = cliente.post("/taxonomias", json={"nivel": nivel, "entidade_id": entidade["id"]})
        assert r.status_code == 201, r.text
        taxonomias[nivel] = r.json()

    return {"campanha": campanha, "grupo": grupo, "anuncio": anuncio, "taxonomias": taxonomias}


def validar(cliente, url: str, taxonomia_id: str):
    resposta = cliente.post("/utm/validar", json={"url": url, "taxonomia_id": taxonomia_id})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def codigos(itens) -> set[str]:
    return {i["codigo"] for i in itens}


# --------------------------------------------------------------------------

def test_url_montada_pela_sugestao_do_proprio_app_e_valida(cliente, hierarquia):
    """Ida e volta: o contexto vem do banco, a sugestão sai dele, e conferir
    a sugestão não pode acusar nada."""
    taxonomia = hierarquia["taxonomias"]["ANUNCIO"]["id"]

    primeiro = validar(cliente, "https://loja.com.br/promo", taxonomia)
    assert "sem_utm" in codigos(primeiro["erros"])
    assert primeiro["url_sugerida"]

    segundo = validar(cliente, primeiro["url_sugerida"], taxonomia)
    assert segundo["valido"], segundo["erros"]
    assert segundo["erros"] == []


def test_contexto_traz_os_tres_niveis_do_banco(cliente, hierarquia):
    """Os match IDs conferidos são os das entidades, não recalculados."""
    taxonomia = hierarquia["taxonomias"]["ANUNCIO"]["id"]
    sugestao = validar(cliente, "https://loja.com.br/", taxonomia)["sugestao"]

    assert sugestao["utm_id"] == hierarquia["campanha"]["match_id"].lower()
    assert hierarquia["grupo"]["match_id"].lower() in sugestao["utm_term"]
    assert hierarquia["anuncio"]["match_id"].lower() in sugestao["utm_content"]
    # utm_medium sai do `tipo_compra` do anúncio, lido do JSONB de campos.
    assert sugestao["utm_medium"] == CAMPOS_ANUNCIO["tipo_compra"].lower()


def test_url_de_outra_campanha_e_erro_e_nao_500(cliente, hierarquia):
    """O caso mais caro do D-012: o link funciona, o site abre, e o custo é
    atribuído no lugar errado por semanas."""
    taxonomia = hierarquia["taxonomias"]["ANUNCIO"]["id"]
    corpo = validar(
        cliente,
        "https://loja.com.br/?utm_source=metaa&utm_medium=cpc&utm_campaign=natal_c9999"
        "&utm_id=c9999&utm_term=g9999&utm_content=video_a9999",
        taxonomia,
    )
    assert corpo["valido"] is False
    assert "match_id_divergente" in codigos(corpo["erros"])
    assert "utm_id_divergente" in codigos(corpo["erros"])


def test_taxonomia_de_campanha_nao_cobra_os_niveis_de_baixo(cliente, hierarquia):
    taxonomia = hierarquia["taxonomias"]["CAMPANHA"]["id"]
    campanha = hierarquia["campanha"]["match_id"].lower()
    corpo = validar(
        cliente,
        f"https://loja.com.br/?utm_source=metaa&utm_medium=cpc&utm_campaign={campanha}"
        f"&utm_id={campanha}",
        taxonomia,
    )
    assert corpo["valido"], corpo["erros"]
    assert "grupo_sem_rastreio" not in codigos(corpo["avisos"])


def test_taxonomia_de_grupo_confere_campanha_e_grupo(cliente, hierarquia):
    """O nível do meio: sobe até a campanha pelo id denormalizado e cobra o
    grupo, sem inventar exigência de anúncio."""
    taxonomia = hierarquia["taxonomias"]["GRUPO"]["id"]
    campanha = hierarquia["campanha"]["match_id"].lower()
    corpo = validar(
        cliente,
        f"https://loja.com.br/?utm_source=metaa&utm_medium=cpc&utm_campaign={campanha}"
        f"&utm_id={campanha}&utm_term=g9999",
        taxonomia,
    )
    divergente = next(e for e in corpo["erros"] if e["codigo"] == "match_id_divergente")
    assert divergente["parametro"] == "utm_term"
    assert divergente["esperado"] == hierarquia["grupo"]["match_id"].lower()
    assert all(e["parametro"] != "utm_content" for e in corpo["erros"])


def test_linha_de_historico_sem_plataforma_nao_quebra(cliente, session, hierarquia):
    """`plataforma_id` é nulo nas linhas anteriores ao D-009. O laudo cai
    para as regras que não dependem da plataforma, em vez de estourar."""
    linha = session.get(TaxonomiaGerada, uuid.UUID(hierarquia["taxonomias"]["ANUNCIO"]["id"]))
    linha.plataforma_id = None
    session.flush()

    corpo = validar(
        cliente,
        "https://loja.com.br/?utm_source=metaa&utm_medium=cpc&utm_campaign=x",
        str(linha.id),
    )
    assert "utm_source_fora_da_convencao" not in codigos(corpo["avisos"])
    assert corpo["parametros"]["utm_source"] == "metaa"


def test_vocabulario_cadastrado_transforma_aviso_em_erro(cliente, meta_id, hierarquia):
    """Sem vocabulário, divergência é aviso; cadastrado, vira erro — e a
    decisão continua em dados, sem tocar em código (D-012)."""
    taxonomia = hierarquia["taxonomias"]["ANUNCIO"]["id"]
    url = (
        "https://loja.com.br/?utm_source=tiktok&utm_medium=cpc"
        f"&utm_campaign={hierarquia['campanha']['match_id'].lower()}"
        f"&utm_id={hierarquia['campanha']['match_id'].lower()}"
        f"&utm_term={hierarquia['grupo']['match_id'].lower()}"
        f"&utm_content={hierarquia['anuncio']['match_id'].lower()}"
    )

    antes = validar(cliente, url, taxonomia)
    assert "utm_source_fora_da_convencao" in codigos(antes["avisos"])
    assert "utm_source_invalida" not in codigos(antes["erros"])

    r = cliente.post(
        "/dicionario",
        json={
            "categoria": "utm_source",
            "termo": "Facebook",
            "abreviacao": "facebook",
            "plataforma_id": meta_id,
        },
    )
    assert r.status_code == 201, r.text

    depois = validar(cliente, url, taxonomia)
    erro = next(e for e in depois["erros"] if e["codigo"] == "utm_source_invalida")
    assert "facebook" in erro["mensagem"]
    assert depois["valido"] is False


def test_conferir_url_nao_persiste_nada(cliente, session, hierarquia):
    """D-004: conferir URL não gera taxonomia nem altera a existente."""
    antes = session.scalar(select(func.count()).select_from(TaxonomiaGerada))
    validar(cliente, "https://loja.com.br/?utm_source=x", hierarquia["taxonomias"]["ANUNCIO"]["id"])
    assert session.scalar(select(func.count()).select_from(TaxonomiaGerada)) == antes


def test_taxonomia_inexistente_e_404(cliente):
    resposta = cliente.post(
        "/utm/validar", json={"url": "https://loja.com.br/", "taxonomia_id": str(uuid.uuid4())}
    )
    assert resposta.status_code == 404


def test_corpo_invalido_e_422(cliente, hierarquia):
    """URL problemática é 200 com laudo; corpo malformado é que é 422."""
    assert cliente.post("/utm/validar", json={"url": "x"}).status_code == 422
    assert (
        cliente.post(
            "/utm/validar",
            json={"url": "", "taxonomia_id": hierarquia["taxonomias"]["ANUNCIO"]["id"]},
        ).status_code
        == 422
    )


def test_url_ilegivel_ainda_responde_200_com_laudo(cliente, hierarquia):
    corpo = validar(cliente, "isso não é uma url", hierarquia["taxonomias"]["ANUNCIO"]["id"])
    assert corpo["valido"] is False
    assert "url_invalida" in codigos(corpo["erros"])


def test_contexto_sobrevive_a_exclusao_da_campanha(cliente, hierarquia):
    """O histórico sobrevive à entidade (D-004/D-009). Sem a campanha, as
    regras que dependem dela são puladas — não viram erro nem 500."""
    taxonomia = hierarquia["taxonomias"]["ANUNCIO"]["id"]
    assert cliente.delete(f"/campanhas/{hierarquia['campanha']['id']}").status_code == 204

    corpo = validar(
        cliente,
        "https://loja.com.br/?utm_source=metaa&utm_medium=cpc&utm_campaign=qualquer-coisa",
        taxonomia,
    )
    assert not any(c.startswith("match_id") for c in codigos(corpo["erros"]))
    assert "utm_id_ausente" not in codigos(corpo["avisos"])
