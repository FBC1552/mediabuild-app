"""Plano de mídia: cascata de rateio (D-A), desbalanço aceito (D-B),
arredondamento, sobrevivência à exclusão da entidade referenciada, e
exportação.

Como `tests/test_api.py`, usa o banco real — o valor destes testes está na
integração rota -> cascata -> banco, não só na aritmética isolada.
"""

import io
import uuid
from decimal import Decimal

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.models import Plataforma
from tests.conftest import CAMPOS_ANUNCIO, CAMPOS_CAMPANHA, CAMPOS_GRUPO


@pytest.fixture
def meta_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "Meta")))


def _sufixo() -> str:
    return uuid.uuid4().hex[:6].upper()


def _d(valor) -> Decimal:
    """As respostas trazem Decimal como string JSON ('33.333', não 33.333),
    para não perder precisão na volta — este helper é só o parse simétrico
    nos testes."""
    return Decimal(str(valor))


@pytest.fixture
def hierarquia(cliente, meta_id):
    """Campanha -> grupo -> anúncio reais, para as linhas do plano
    referenciarem. Não gera nomenclatura: os testes de plano dependem só do
    match_id/nome_interno atribuídos na criação da entidade, não de
    `taxonomias_geradas` — cobrir os dois juntos é assunto de
    `test_plano_com_nomenclatura_ja_gerada`."""
    campanha = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": meta_id,
            "nome_interno": f"Camp {_sufixo()}",
            "campos": CAMPOS_CAMPANHA,
        },
    ).json()
    grupo = cliente.post(
        "/grupos",
        json={
            "campanha_id": campanha["id"],
            "nome_interno": f"Grupo {_sufixo()}",
            "campos": CAMPOS_GRUPO,
        },
    ).json()
    anuncio = cliente.post(
        "/anuncios",
        json={
            "grupo_anuncio_id": grupo["id"],
            "nome_interno": f"Anuncio {_sufixo()}",
            "campos": CAMPOS_ANUNCIO,
        },
    ).json()
    return {"campanha": campanha, "grupo": grupo, "anuncio": anuncio}


@pytest.fixture
def plano(cliente):
    r = cliente.post("/planos", json={"nome": f"Plano {_sufixo()}", "verba_total": "10000.00"})
    assert r.status_code == 201, r.text
    return r.json()


def _linha_campanha(cliente, plano_id, campanha_id, **corpo):
    r = cliente.post(f"/planos/{plano_id}/campanhas", json={"campanha_id": campanha_id, **corpo})
    assert r.status_code == 201, r.text
    return r.json()


def _linha_grupo(cliente, plano_id, linha_campanha_id, grupo_id, **corpo):
    r = cliente.post(
        f"/planos/{plano_id}/campanhas/{linha_campanha_id}/grupos",
        json={"grupo_id": grupo_id, **corpo},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _linha_anuncio(cliente, plano_id, linha_campanha_id, linha_grupo_id, anuncio_id, **corpo):
    r = cliente.post(
        f"/planos/{plano_id}/campanhas/{linha_campanha_id}/grupos/{linha_grupo_id}/anuncios",
        json={"anuncio_id": anuncio_id, **corpo},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------
# plano: criação, leitura, edição, remoção
# --------------------------------------------------------------------------


def test_criar_plano_basico(plano):
    assert _d(plano["verba_total"]) == Decimal("10000.00")
    assert _d(plano["soma_campanhas"]) == Decimal("0")
    assert _d(plano["diferenca"]) == Decimal("10000.00")
    assert plano["campanhas"] == []


def test_atualizar_plano(cliente, plano):
    r = cliente.patch(f"/planos/{plano['id']}", json={"nome": "Novo nome", "verba_total": "5000"})
    assert r.status_code == 200
    assert r.json()["nome"] == "Novo nome"
    assert _d(r.json()["verba_total"]) == Decimal("5000")


def test_remover_plano(cliente, plano):
    assert cliente.delete(f"/planos/{plano['id']}").status_code == 204
    assert cliente.get(f"/planos/{plano['id']}").status_code == 404


def test_plano_inexistente_da_404(cliente):
    assert cliente.get(f"/planos/{uuid.uuid4()}").status_code == 404


def test_listagem_traz_resumo_com_soma_e_diferenca(cliente, plano, hierarquia):
    _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="4000.00")

    r = cliente.get("/planos")
    assert r.status_code == 200
    linha = next(p for p in r.json() if p["id"] == plano["id"])
    assert linha["quantidade_campanhas"] == 1
    assert _d(linha["soma_campanhas"]) == Decimal("4000.00")
    assert _d(linha["diferenca"]) == Decimal("6000.00")


# --------------------------------------------------------------------------
# D-A: cascata de rateio
# --------------------------------------------------------------------------


def test_cascata_de_rateio_por_percentual(cliente, plano, hierarquia):
    """Verba total -> % para a campanha -> % para o grupo -> valor direto
    para o anúncio, com a porcentagem de cada nível calculada de volta a
    partir do valor do pai imediato."""
    linha_c = _linha_campanha(
        cliente, plano["id"], hierarquia["campanha"]["id"], percentual="50"
    )
    assert _d(linha_c["valor"]) == Decimal("5000.00")
    assert _d(linha_c["percentual"]) == Decimal("50.000")

    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], percentual="40"
    )
    assert _d(linha_g["valor"]) == Decimal("2000.00")  # 40% de 5000
    assert _d(linha_g["percentual"]) == Decimal("40.000")

    linha_a = _linha_anuncio(
        cliente,
        plano["id"],
        linha_c["id"],
        linha_g["id"],
        hierarquia["anuncio"]["id"],
        valor="500.00",
    )
    assert _d(linha_a["valor"]) == Decimal("500.00")
    # 500 / 2000 = 25%
    assert _d(linha_a["percentual"]) == Decimal("25.000")

    # A leitura do plano inteiro reflete a mesma cascata, com soma/diferença
    # em cada nível.
    completo = cliente.get(f"/planos/{plano['id']}").json()
    campanha_lida = completo["campanhas"][0]
    assert _d(campanha_lida["soma_grupos"]) == Decimal("2000.00")
    assert _d(campanha_lida["diferenca"]) == Decimal("3000.00")  # 5000 - 2000
    grupo_lido = campanha_lida["grupos"][0]
    assert _d(grupo_lido["soma_anuncios"]) == Decimal("500.00")
    assert _d(grupo_lido["diferenca"]) == Decimal("1500.00")  # 2000 - 500


def test_percentual_e_valor_juntos_e_nenhum_dos_dois_sao_rejeitados(
    cliente, plano, hierarquia
):
    r = cliente.post(
        f"/planos/{plano['id']}/campanhas",
        json={"campanha_id": hierarquia["campanha"]["id"], "valor": "10", "percentual": "10"},
    )
    assert r.status_code == 422

    r = cliente.post(
        f"/planos/{plano['id']}/campanhas", json={"campanha_id": hierarquia["campanha"]["id"]}
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------
# D-B: desbalanço é aceito e só reportado
# --------------------------------------------------------------------------


def test_plano_desbalanceado_e_aceito_e_a_diferenca_e_reportada(cliente, plano, hierarquia):
    """A soma dos filhos pode não bater com o valor do pai. Nada é
    redistribuído, e a linha não é rejeitada — só a diferença aparece na
    resposta, para a UI sinalizar."""
    linha_c = _linha_campanha(
        cliente, plano["id"], hierarquia["campanha"]["id"], valor="9999.00"
    )
    # 9999 de um plano de 10000 -> sobram 1, não é erro.
    completo = cliente.get(f"/planos/{plano['id']}").json()
    assert _d(completo["soma_campanhas"]) == Decimal("9999.00")
    assert _d(completo["diferenca"]) == Decimal("1.00")

    # E o grupo pode estourar o valor da campanha (>100% do pai) — também
    # não é rejeitado, o desbalanço é que fica visível.
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="20000.00"
    )
    campanha_lida = cliente.get(f"/planos/{plano['id']}").json()["campanhas"][0]
    assert _d(campanha_lida["soma_grupos"]) == Decimal("20000.00")
    assert _d(campanha_lida["diferenca"]) == Decimal("-10001.00")
    assert linha_g  # linha foi criada normalmente, sem 422/409


# --------------------------------------------------------------------------
# arredondamento
# --------------------------------------------------------------------------


def test_arredondamento_da_divisao_percentual(cliente, plano, hierarquia):
    """1/3 de 100 não fecha em centavos exatos: 33.33 x 3 = 99.99, não 100.
    O valor gravado é o arredondado (metade para cima, duas casas); a
    diferença de 1 centavo no nível acima é esperada e reportada, não é bug
    nem é escondida por um ajuste automático (D-B)."""
    r = cliente.patch(f"/planos/{plano['id']}", json={"verba_total": "100.00"})
    assert r.status_code == 200

    linha = _linha_campanha(
        cliente, plano["id"], hierarquia["campanha"]["id"], percentual="33.333"
    )
    assert _d(linha["valor"]) == Decimal("33.33")

    completo = cliente.get(f"/planos/{plano['id']}").json()
    assert _d(completo["soma_campanhas"]) == Decimal("33.33")
    assert _d(completo["diferenca"]) == Decimal("66.67")


def test_percentual_e_null_quando_pai_e_zero(cliente, hierarquia):
    r = cliente.post("/planos", json={"nome": f"Plano zero {_sufixo()}", "verba_total": "0"})
    plano_zero = r.json()
    linha = _linha_campanha(
        cliente, plano_zero["id"], hierarquia["campanha"]["id"], valor="0"
    )
    assert linha["percentual"] is None


# --------------------------------------------------------------------------
# o plano sobrevive à entidade referenciada
# --------------------------------------------------------------------------


def test_plano_sobrevive_a_remocao_da_campanha(cliente, plano, hierarquia):
    """Denormalização de nome/match id/nomenclatura (D-009 aplicado ao
    plano): apagar a campanha original não pode apagar nem corromper a
    linha do plano que já a referenciava."""
    campanha = hierarquia["campanha"]
    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")

    assert cliente.delete(f"/campanhas/{campanha['id']}").status_code == 204

    completo = cliente.get(f"/planos/{plano['id']}")
    assert completo.status_code == 200
    campanha_lida = completo.json()["campanhas"][0]
    assert campanha_lida["id"] == linha["id"]
    assert campanha_lida["nome_interno"] == campanha["nome_interno"]
    assert campanha_lida["match_id"] == campanha["match_id"]
    assert _d(campanha_lida["valor"]) == Decimal("1000.00")


def test_plano_com_nomenclatura_ja_gerada_denormaliza_o_nome(cliente, plano, hierarquia):
    campanha = hierarquia["campanha"]
    gerada = cliente.post("/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]})
    assert gerada.status_code == 201
    nomenclatura = gerada.json()["nomenclatura_final"]

    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")
    assert linha["nomenclatura"] == nomenclatura
    # Snapshot gravado igual à nomenclatura atual -> sem divergência.
    assert linha["nomenclatura_atual"] == nomenclatura
    assert linha["nomenclatura_divergente"] is False


# --------------------------------------------------------------------------
# decisão 4: divergência de nomenclatura (snapshot vs. atual)
# --------------------------------------------------------------------------


def test_nomenclatura_diverge_quando_gerada_depois_da_linha_do_plano(cliente, plano, hierarquia):
    """A linha do plano é criada antes de a campanha ter nomenclatura
    gerada (snapshot None); gerando a nomenclatura depois, a leitura do
    plano precisa sinalizar a divergência sem que o snapshot mude sozinho
    (D-004: refresh automático não é implementado, só a sinalização)."""
    campanha = hierarquia["campanha"]
    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")
    assert linha["nomenclatura"] is None
    assert linha["nomenclatura_atual"] is None
    assert linha["nomenclatura_divergente"] is False

    gerada = cliente.post("/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]})
    assert gerada.status_code == 201
    nomenclatura = gerada.json()["nomenclatura_final"]

    completo = cliente.get(f"/planos/{plano['id']}").json()
    campanha_lida = completo["campanhas"][0]
    # O snapshot gravado na criação da linha continua None (D-004) — só a
    # leitura aponta que a nomenclatura atual já existe e diverge dele.
    assert campanha_lida["nomenclatura"] is None
    assert campanha_lida["nomenclatura_atual"] == nomenclatura
    assert campanha_lida["nomenclatura_divergente"] is True


def test_nomenclatura_divergente_tambem_aparece_em_grupo_e_anuncio(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    linha_a = _linha_anuncio(
        cliente, plano["id"], linha_c["id"], linha_g["id"], hierarquia["anuncio"]["id"], valor="10"
    )
    assert linha_g["nomenclatura_divergente"] is False
    assert linha_a["nomenclatura_divergente"] is False

    gerada_g = cliente.post(
        "/taxonomias", json={"nivel": "GRUPO", "entidade_id": hierarquia["grupo"]["id"]}
    )
    assert gerada_g.status_code == 201

    completo = cliente.get(f"/planos/{plano['id']}").json()
    grupo_lido = completo["campanhas"][0]["grupos"][0]
    assert grupo_lido["nomenclatura_divergente"] is True
    assert grupo_lido["nomenclatura_atual"] == gerada_g.json()["nomenclatura_final"]
    # Anúncio não teve nomenclatura gerada -> continua sem divergência.
    assert grupo_lido["anuncios"][0]["nomenclatura_divergente"] is False


# --------------------------------------------------------------------------
# sincronizar_nomenclatura: o verbo que aceita o nome regerado (adendo)
# --------------------------------------------------------------------------


def test_sincronizar_nomenclatura_na_campanha(cliente, plano, hierarquia):
    campanha = hierarquia["campanha"]
    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")
    assert linha["nomenclatura"] is None

    gerada = cliente.post("/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]})
    nomenclatura = gerada.json()["nomenclatura_final"]

    completo = cliente.get(f"/planos/{plano['id']}").json()
    assert completo["campanhas"][0]["nomenclatura_divergente"] is True

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}",
        json={"valor": "1000.00", "sincronizar_nomenclatura": True},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nomenclatura"] == nomenclatura
    assert corpo["nomenclatura_atual"] == nomenclatura
    assert corpo["nomenclatura_divergente"] is False
    # match_id e nome_interno não são tocados pelo verbo de sincronização.
    assert corpo["nome_interno"] == campanha["nome_interno"]
    assert corpo["match_id"] == campanha["match_id"]


def test_sincronizar_nomenclatura_no_grupo(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    gerada = cliente.post(
        "/taxonomias", json={"nivel": "GRUPO", "entidade_id": hierarquia["grupo"]["id"]}
    )
    nomenclatura = gerada.json()["nomenclatura_final"]

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}/grupos/{linha_g['id']}",
        json={"valor": "50", "sincronizar_nomenclatura": True},
    )
    assert r.status_code == 200
    assert r.json()["nomenclatura"] == nomenclatura
    assert r.json()["nomenclatura_divergente"] is False


def test_sincronizar_nomenclatura_no_anuncio(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    linha_a = _linha_anuncio(
        cliente, plano["id"], linha_c["id"], linha_g["id"], hierarquia["anuncio"]["id"], valor="10"
    )
    gerada = cliente.post(
        "/taxonomias", json={"nivel": "ANUNCIO", "entidade_id": hierarquia["anuncio"]["id"]}
    )
    nomenclatura = gerada.json()["nomenclatura_final"]

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}/grupos/{linha_g['id']}"
        f"/anuncios/{linha_a['id']}",
        json={"valor": "10", "sincronizar_nomenclatura": True},
    )
    assert r.status_code == 200
    assert r.json()["nomenclatura"] == nomenclatura
    assert r.json()["nomenclatura_divergente"] is False


def test_sincronizar_nomenclatura_sem_nomenclatura_atual_e_no_op(cliente, plano, hierarquia):
    """Entidade sem nomenclatura gerada nenhuma (`nomenclatura_atual` é
    `None`): pedir sincronização não zera o snapshot (que já era `None`
    aqui) nem quebra o PATCH — no-op silencioso, sem 422. O resto do PATCH
    (o `valor`, sempre obrigatório) é aplicado normalmente."""
    campanha = hierarquia["campanha"]
    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")
    assert linha["nomenclatura"] is None
    assert linha["nomenclatura_atual"] is None

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}",
        json={"valor": "2000.00", "sincronizar_nomenclatura": True},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nomenclatura"] is None
    assert corpo["nomenclatura_atual"] is None
    assert _d(corpo["valor"]) == Decimal("2000.00")


def test_sincronizar_nomenclatura_omitido_nao_sincroniza(cliente, plano, hierarquia):
    """`exclude_unset`: omitir o campo (não mandar `sincronizar_nomenclatura`
    no corpo) tem que ter o mesmo efeito de não pedir nada — mesmo com
    default `False` presente no schema."""
    campanha = hierarquia["campanha"]
    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")
    cliente.post("/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]})

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}", json={"valor": "1500.00"}
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nomenclatura"] is None
    assert corpo["nomenclatura_divergente"] is True

    # Mandar 'false' explícito também não sincroniza.
    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}",
        json={"valor": "1500.00", "sincronizar_nomenclatura": False},
    )
    assert r.status_code == 200
    assert r.json()["nomenclatura"] is None


def test_sincronizar_nomenclatura_combinada_com_edicao_de_valor(cliente, plano, hierarquia):
    """`sincronizar_nomenclatura=true` na MESMA chamada que reajusta o
    valor: permitido, e os dois efeitos são aplicados juntos — não é uma
    combinação especial, é o caso comum (valor é sempre obrigatório em
    todo PATCH de linha, ver `_LinhaPedido`)."""
    campanha = hierarquia["campanha"]
    linha = _linha_campanha(cliente, plano["id"], campanha["id"], valor="1000.00")
    gerada = cliente.post("/taxonomias", json={"nivel": "CAMPANHA", "entidade_id": campanha["id"]})
    nomenclatura = gerada.json()["nomenclatura_final"]

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}",
        json={"valor": "3333.33", "sincronizar_nomenclatura": True},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert _d(corpo["valor"]) == Decimal("3333.33")
    assert corpo["nomenclatura"] == nomenclatura
    assert corpo["nomenclatura_divergente"] is False


# --------------------------------------------------------------------------
# decisão 3: flight, KPI primário e custo unitário negociado
# --------------------------------------------------------------------------


def test_flight_e_kpi_primario_na_linha_de_campanha(cliente, plano, hierarquia):
    metricas = cliente.get("/metricas").json()
    impressoes = next(m for m in metricas if m["codigo"] == "impressoes")

    linha = _linha_campanha(
        cliente,
        plano["id"],
        hierarquia["campanha"]["id"],
        valor="1000.00",
        flight_inicio="2026-08-01",
        flight_fim="2026-08-31",
        kpi_primario_id=impressoes["id"],
    )
    assert linha["flight_inicio"] == "2026-08-01"
    assert linha["flight_fim"] == "2026-08-31"
    assert linha["kpi_primario_id"] == impressoes["id"]
    assert linha["kpi_primario_codigo"] == "impressoes"
    assert linha["kpi_primario_rotulo"] == impressoes["rotulo"]
    assert linha["kpi_primario_ativo"] is True


def test_flight_invertido_e_rejeitado(cliente, plano, hierarquia):
    r = cliente.post(
        f"/planos/{plano['id']}/campanhas",
        json={
            "campanha_id": hierarquia["campanha"]["id"],
            "valor": "10",
            "flight_inicio": "2026-08-31",
            "flight_fim": "2026-08-01",
        },
    )
    assert r.status_code == 422


def test_kpi_primario_desconhecido_da_422(cliente, plano, hierarquia):
    r = cliente.post(
        f"/planos/{plano['id']}/campanhas",
        json={
            "campanha_id": hierarquia["campanha"]["id"],
            "valor": "10",
            "kpi_primario_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "kpi_primario_invalido"
    assert r.json()["campo"] == "kpi_primario_id"


def test_kpi_primario_desativado_depois_sinaliza_mas_nao_quebra(cliente, plano, hierarquia):
    """Escolher um KPI válido, desativá-lo depois: o plano continua
    legível (código/rótulo denormalizados) e a leitura sinaliza
    `kpi_primario_ativo=False` em vez de quebrar ou apagar a escolha."""
    codigo = f"teste_{_sufixo().lower()}"
    metrica = cliente.post("/metricas", json={"codigo": codigo, "rotulo": "Métrica de teste"}).json()

    linha = _linha_campanha(
        cliente,
        plano["id"],
        hierarquia["campanha"]["id"],
        valor="10",
        kpi_primario_id=metrica["id"],
    )
    assert linha["kpi_primario_ativo"] is True

    cliente.patch(f"/metricas/{metrica['id']}", json={"ativo": False})

    completo = cliente.get(f"/planos/{plano['id']}").json()
    campanha_lida = completo["campanhas"][0]
    assert campanha_lida["kpi_primario_codigo"] == codigo
    assert campanha_lida["kpi_primario_ativo"] is False


def test_atualizar_flight_e_kpi_de_campanha_respeita_exclude_unset(cliente, plano, hierarquia):
    metricas = cliente.get("/metricas").json()
    cliques = next(m for m in metricas if m["codigo"] == "cliques")

    linha = _linha_campanha(
        cliente,
        plano["id"],
        hierarquia["campanha"]["id"],
        valor="10",
        flight_inicio="2026-08-01",
        kpi_primario_id=cliques["id"],
    )

    # PATCH só com 'valor' não deve tocar flight/KPI já gravados.
    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}", json={"valor": "20"}
    )
    assert r.status_code == 200
    assert r.json()["flight_inicio"] == "2026-08-01"
    assert r.json()["kpi_primario_codigo"] == "cliques"

    # PATCH explicitamente limpando o KPI.
    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha['id']}",
        json={"valor": "20", "kpi_primario_id": None},
    )
    assert r.status_code == 200
    assert r.json()["kpi_primario_id"] is None
    assert r.json()["kpi_primario_codigo"] is None
    assert r.json()["kpi_primario_ativo"] is None


def test_custo_unitario_negociado_na_linha_de_grupo(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente,
        plano["id"],
        linha_c["id"],
        hierarquia["grupo"]["id"],
        valor="50",
        custo_unitario_negociado="15.5000",
    )
    assert Decimal(str(linha_g["custo_unitario_negociado"])) == Decimal("15.5000")

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}/grupos/{linha_g['id']}",
        json={"valor": "50", "custo_unitario_negociado": "9.9"},
    )
    assert r.status_code == 200
    assert Decimal(str(r.json()["custo_unitario_negociado"])) == Decimal("9.9")


# --------------------------------------------------------------------------
# hierarquia e métricas
# --------------------------------------------------------------------------


def test_grupo_de_outra_campanha_e_rejeitado(cliente, plano, hierarquia, meta_id):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")

    outra_campanha = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": meta_id,
            "nome_interno": f"Outra {_sufixo()}",
            "campos": CAMPOS_CAMPANHA,
        },
    ).json()
    outro_grupo = cliente.post(
        "/grupos",
        json={
            "campanha_id": outra_campanha["id"],
            "nome_interno": f"Outro grupo {_sufixo()}",
            "campos": CAMPOS_GRUPO,
        },
    ).json()

    r = cliente.post(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}/grupos",
        json={"grupo_id": outro_grupo["id"], "valor": "10"},
    )
    assert r.status_code == 422
    assert r.json()["erro"] == "entidade_fora_da_hierarquia"


def test_metrica_desconhecida_da_422(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )

    r = cliente.post(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}/grupos/{linha_g['id']}/anuncios",
        json={
            "anuncio_id": hierarquia["anuncio"]["id"],
            "valor": "10",
            "metas": {"nao_existe": 100},
        },
    )
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["erro"] == "metrica_desconhecida"
    assert corpo["campo"] == "metas"


def test_metas_validas_sao_aceitas(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    linha_a = _linha_anuncio(
        cliente,
        plano["id"],
        linha_c["id"],
        linha_g["id"],
        hierarquia["anuncio"]["id"],
        valor="10",
        metas={"impressoes": 4_000_000, "cliques": 17000, "conversoes": 500},
    )
    assert linha_a["metas"] == {"impressoes": 4_000_000, "cliques": 17000, "conversoes": 500}


def test_atualizar_linha_de_campanha_e_de_anuncio(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    linha_a = _linha_anuncio(
        cliente,
        plano["id"],
        linha_c["id"],
        linha_g["id"],
        hierarquia["anuncio"]["id"],
        valor="10",
        metas={"impressoes": 100},
    )

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}", json={"valor": "200"}
    )
    assert r.status_code == 200
    assert _d(r.json()["valor"]) == Decimal("200.00")

    r = cliente.patch(
        f"/planos/{plano['id']}/campanhas/{linha_c['id']}/grupos/{linha_g['id']}"
        f"/anuncios/{linha_a['id']}",
        json={"valor": "15", "metas": {"impressoes": 999, "cliques": 10}},
    )
    assert r.status_code == 200
    assert _d(r.json()["valor"]) == Decimal("15.00")
    assert r.json()["metas"] == {"impressoes": 999, "cliques": 10}


# --------------------------------------------------------------------------
# remoção de linha
# --------------------------------------------------------------------------


def test_remover_linha_de_campanha_remove_grupos_e_anuncios_em_cascata(
    cliente, plano, hierarquia
):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    _linha_anuncio(
        cliente, plano["id"], linha_c["id"], linha_g["id"], hierarquia["anuncio"]["id"], valor="10"
    )

    assert cliente.delete(f"/planos/{plano['id']}/campanhas/{linha_c['id']}").status_code == 204

    completo = cliente.get(f"/planos/{plano['id']}").json()
    assert completo["campanhas"] == []


# --------------------------------------------------------------------------
# exportação
# --------------------------------------------------------------------------


def test_export_replica_o_layout_do_cliente(cliente, plano, hierarquia):
    linha_c = _linha_campanha(cliente, plano["id"], hierarquia["campanha"]["id"], valor="100")
    linha_g = _linha_grupo(
        cliente, plano["id"], linha_c["id"], hierarquia["grupo"]["id"], valor="50"
    )
    _linha_anuncio(
        cliente,
        plano["id"],
        linha_c["id"],
        linha_g["id"],
        hierarquia["anuncio"]["id"],
        valor="20000",
        metas={"impressoes": 4_000_000, "cliques": 17000},
    )

    r = cliente.get(f"/planos/export?plano_id={plano['id']}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    cabecalho = [c.value for c in ws[1]]
    assert cabecalho == [
        "Taxonomia Campanha",
        "Flight — início",
        "Flight — fim",
        "KPI primário",
        "Taxonomia Grupo de Anúncios",
        "Custo unitário negociado (R$)",
        "Taxonomia Anúncio",
        "Investimento previsto (R$)",
        "Impressões",
        "Cliques",
    ]

    linha_dados = [c.value for c in ws[2]]
    assert linha_dados[0] == hierarquia["campanha"]["nome_interno"]
    assert linha_dados[7] == 20000.0

    # Linha TOTAL é a linha 3 (uma única linha de dados na 2). Não usa
    # `ws.max_row`: este plano tem verba de R$ 10.000 com só R$ 100/50/20.000
    # alocados em cascata — um desbalanço real, então a planilha também
    # carrega a nota de aviso depois do TOTAL (ver testes dedicados a ela).
    total = [c.value for c in ws[3]]
    assert total[0] == "TOTAL"
    assert total[7] == 20000.0


def test_export_de_plano_vazio_nao_quebra(cliente):
    """Plano vazio SEM verba (não o fixture `plano`, que tem R$ 10.000 e
    geraria nota de desbalanço — coberto à parte em
    `test_export_nota_de_desbalanco_plano_vazio_com_verba`): só cabeçalho e
    TOTAL zerado, sem nota nenhuma, porque `0 - 0 == 0` está dentro da
    tolerância (`_dentro_da_tolerancia` trata verba total zero à parte)."""
    plano_vazio = cliente.post("/planos", json={"nome": f"Vazio {_sufixo()}", "verba_total": "0"}).json()
    r = cliente.get(f"/planos/export?plano_id={plano_vazio['id']}")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    # Só o cabeçalho e a linha TOTAL (zerada) — sem anúncio nenhum, sem nota.
    assert ws.max_row == 2
    assert [c.value for c in ws[2]][0] == "TOTAL"


# --------------------------------------------------------------------------
# nota de desbalanço no Excel exportado (tolerância de 2% relativos à
# verba total — TOLERANCIA_DESBALANCO_RELATIVA em app/exportacao_plano.py)
# --------------------------------------------------------------------------


def _linhas_de_aviso(ws) -> list[str]:
    """Texto de cada linha da seção de aviso no fim da planilha (depois de
    uma linha em branco que segue o TOTAL) — vazio quando não há nota."""
    linhas = [row[0].value for row in ws.iter_rows(min_row=1)]
    try:
        indice_total = linhas.index("TOTAL")
    except ValueError:
        return []
    # Depois do TOTAL, quando há nota: uma linha em branco, uma linha de
    # título ("Aviso de desbalanço — ..."), e então uma linha por nota (ver
    # `gerar_planilha_plano`). Sem nota, o TOTAL é a última linha da aba.
    return [v for v in linhas[indice_total + 3 :] if v]


def _fechar_niveis_internos(cliente, plano_id, campanha_linha_id, hierarquia, valor: str) -> None:
    """Cria grupo e anúncio com o MESMO valor da linha de campanha, para
    que os níveis internos (campanha->grupo, grupo->anúncio) fechem
    perfeitamente — isolando, nos testes de tolerância abaixo, a variação
    ao nível do TOPO (verba total vs. soma das campanhas), sem o ruído de
    um grupo/anúncio zerado também gerar nota por conta própria."""
    linha_g = _linha_grupo(cliente, plano_id, campanha_linha_id, hierarquia["grupo"]["id"], valor=valor)
    _linha_anuncio(cliente, plano_id, campanha_linha_id, linha_g["id"], hierarquia["anuncio"]["id"], valor=valor)


def test_export_nota_de_desbalanco_no_topo_acima_da_tolerancia(cliente, hierarquia):
    """Plano com verba de R$ 1.000, só R$ 970 alocados (diferença de 3%,
    acima dos 2% de tolerância): a planilha carrega a nota."""
    plano_desbalanceado = cliente.post(
        "/planos", json={"nome": f"Desbal {_sufixo()}", "verba_total": "1000.00"}
    ).json()
    linha_c = _linha_campanha(cliente, plano_desbalanceado["id"], hierarquia["campanha"]["id"], valor="970")
    _fechar_niveis_internos(cliente, plano_desbalanceado["id"], linha_c["id"], hierarquia, "970")

    r = cliente.get(f"/planos/export?plano_id={plano_desbalanceado['id']}")
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    avisos = _linhas_de_aviso(ws)
    assert avisos, "esperava nota de desbalanço no topo"
    assert "Desbal" in avisos[0] or plano_desbalanceado["nome"] in avisos[0]
    assert any("30,00" in a or "30.00" in a for a in avisos)


def test_export_sem_nota_quando_diferenca_e_exatamente_2_por_cento(cliente, hierarquia):
    """Diferença de exatamente 2% da verba total (R$ 20 de R$ 1.000):
    `abs(diferenca) / verba_total <= 0.02` inclui a igualdade — não gera nota."""
    plano_no_limite = cliente.post(
        "/planos", json={"nome": f"Limite {_sufixo()}", "verba_total": "1000.00"}
    ).json()
    linha_c = _linha_campanha(cliente, plano_no_limite["id"], hierarquia["campanha"]["id"], valor="980")
    _fechar_niveis_internos(cliente, plano_no_limite["id"], linha_c["id"], hierarquia, "980")

    r = cliente.get(f"/planos/export?plano_id={plano_no_limite['id']}")
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    assert _linhas_de_aviso(ws) == []


def test_export_nota_de_desbalanco_logo_acima_de_2_por_cento(cliente, hierarquia):
    """Um centavo além dos 2% (R$ 20,01 de diferença numa verba de
    R$ 1.000) já é suficiente para a nota aparecer."""
    plano_logo_acima = cliente.post(
        "/planos", json={"nome": f"LogoAcima {_sufixo()}", "verba_total": "1000.00"}
    ).json()
    linha_c = _linha_campanha(cliente, plano_logo_acima["id"], hierarquia["campanha"]["id"], valor="979.99")
    _fechar_niveis_internos(cliente, plano_logo_acima["id"], linha_c["id"], hierarquia, "979.99")

    r = cliente.get(f"/planos/export?plano_id={plano_logo_acima['id']}")
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    assert _linhas_de_aviso(ws) != []


def test_export_nota_de_nivel_interno_quando_topo_fecha(cliente, hierarquia, meta_id):
    """Duas campanhas de R$ 5.000 cada somam exatamente a verba de
    R$ 10.000 (TOPO fechado, dentro da tolerância por definição). Mas
    dentro de cada uma, o grupo diverge do valor da campanha por R$ 300 —
    3% da verba TOTAL do plano, acima dos 2% — em direções opostas (uma
    sub-aloca, a outra sobre-aloca). O desbalanço de nível interno é real
    e tem que aparecer na nota mesmo com o topo limpo."""
    plano_grande = cliente.post(
        "/planos", json={"nome": f"Interno {_sufixo()}", "verba_total": "10000.00"}
    ).json()

    campanha_b = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": meta_id,
            "nome_interno": f"Camp B {_sufixo()}",
            "campos": CAMPOS_CAMPANHA,
        },
    ).json()
    grupo_b = cliente.post(
        "/grupos",
        json={
            "campanha_id": campanha_b["id"],
            "nome_interno": f"Grupo B {_sufixo()}",
            "campos": CAMPOS_GRUPO,
        },
    ).json()

    # Campanha A: R$ 5000 na linha, mas só R$ 4700 alocados no grupo -> falta R$ 300 (3% da verba total).
    linha_a = _linha_campanha(cliente, plano_grande["id"], hierarquia["campanha"]["id"], valor="5000")
    _linha_grupo(cliente, plano_grande["id"], linha_a["id"], hierarquia["grupo"]["id"], valor="4700")

    # Campanha B: R$ 5000 na linha, mas R$ 5300 alocados no grupo -> sobra R$ 300 (3% da verba total).
    linha_b = _linha_campanha(cliente, plano_grande["id"], campanha_b["id"], valor="5000")
    _linha_grupo(cliente, plano_grande["id"], linha_b["id"], grupo_b["id"], valor="5300")

    completo = cliente.get(f"/planos/{plano_grande['id']}").json()
    assert _d(completo["diferenca"]) == Decimal("0.00")  # topo fecha certinho

    r = cliente.get(f"/planos/export?plano_id={plano_grande['id']}")
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    avisos = _linhas_de_aviso(ws)
    # Nenhuma nota de TOPO (plano fecha), mas duas notas de CAMPANHA.
    assert not any(a.startswith("Plano ") for a in avisos)
    assert sum(1 for a in avisos if a.startswith("Campanha ")) == 2


def test_export_nota_de_desbalanco_plano_vazio_com_verba(cliente, plano):
    """Plano com verba mas nenhuma campanha adicionada ainda (rascunho
    recém-criado): 100% de desbalanço no topo, nota aparece."""
    r = cliente.get(f"/planos/export?plano_id={plano['id']}")
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    avisos = _linhas_de_aviso(ws)
    assert avisos != []
    assert avisos[0].startswith("Plano ")


def test_export_verba_total_zero_nao_divide_por_zero(cliente, hierarquia):
    """Verba total zero e uma linha com valor positivo (estado de rascunho
    válido, D-B não impede) não pode lançar `ZeroDivisionError` — vira
    nota, porque qualquer diferença não-zero contra verba zero é
    desbalanço por definição (ver `_dentro_da_tolerancia`)."""
    plano_zero = cliente.post(
        "/planos", json={"nome": f"Zero {_sufixo()}", "verba_total": "0"}
    ).json()
    _linha_campanha(cliente, plano_zero["id"], hierarquia["campanha"]["id"], valor="50")

    r = cliente.get(f"/planos/export?plano_id={plano_zero['id']}")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    assert _linhas_de_aviso(ws) != []


# --------------------------------------------------------------------------
# métricas: catálogo em dado, não em código
# --------------------------------------------------------------------------


def test_catalogo_de_metricas_seed(cliente):
    r = cliente.get("/metricas")
    assert r.status_code == 200
    codigos = {m["codigo"] for m in r.json()}
    assert {"impressoes", "cliques", "conversoes"} <= codigos


def test_criar_e_desativar_metrica(cliente):
    codigo = f"teste_{_sufixo().lower()}"
    r = cliente.post("/metricas", json={"codigo": codigo, "rotulo": "Métrica de teste"})
    assert r.status_code == 201
    metrica_id = r.json()["id"]

    r = cliente.patch(f"/metricas/{metrica_id}", json={"ativo": False})
    assert r.status_code == 200
    assert r.json()["ativo"] is False

    # Inativa não aparece na listagem padrão...
    assert codigo not in {m["codigo"] for m in cliente.get("/metricas").json()}
    # ...mas aparece pedindo explicitamente.
    assert codigo in {
        m["codigo"] for m in cliente.get("/metricas?incluir_inativas=true").json()
    }
