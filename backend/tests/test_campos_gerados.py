"""Campos separados no histórico — `taxonomias_geradas.campos_gerados`.

O analista cruza a planilha de performance com o nome gerado. A planilha só
conhece o nome, então ele precisa das partes já separadas e na forma em que
entraram no nome ('CV'), não só na forma que digitou ('Conversão').
"""

import io
import uuid

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.models import Plataforma, TaxonomiaGerada
from tests.conftest import CAMPOS_ANUNCIO, CAMPOS_CAMPANHA, CAMPOS_GRUPO


@pytest.fixture
def meta_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "Meta")))


def _campanha_com_taxonomia(cliente, meta_id: str, lote: str, campos=None):
    campanha = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": meta_id,
            "nome_interno": "Black Friday",
            "campos": campos or CAMPOS_CAMPANHA,
        },
    ).json()
    r = cliente.post(
        "/taxonomias",
        json={"nivel": "CAMPANHA", "entidade_id": campanha["id"], "lote_id": lote},
    )
    assert r.status_code == 201, r.text
    return campanha, r.json()


# --------------------------------------------------------------------------
# persistência
# --------------------------------------------------------------------------

def test_geracao_grava_bruto_e_final_por_campo(cliente, meta_id, session):
    lote = str(uuid.uuid4())
    _, taxonomia = _campanha_com_taxonomia(cliente, meta_id, lote)

    registro = session.get(TaxonomiaGerada, uuid.UUID(taxonomia["id"]))
    campos = registro.campos_gerados

    assert campos["objetivo"]["bruto"] == "Conversão"
    assert campos["objetivo"]["final"] == "CV"
    assert campos["empresa"]["final"] == "ALF"
    # Campo livre: o final é só a forma normalizada do que foi digitado.
    assert campos["nome_campanha"]["bruto"] == "ALV27"
    assert campos["nome_campanha"]["final"] == "ALV27"


def test_todo_final_gravado_aparece_no_nome(cliente, meta_id, session):
    """É a garantia que sustenta o cruzamento: o que está na coluna é
    literalmente o pedaço que está no nome."""
    lote = str(uuid.uuid4())
    _, taxonomia = _campanha_com_taxonomia(cliente, meta_id, lote)

    registro = session.get(TaxonomiaGerada, uuid.UUID(taxonomia["id"]))
    partes = registro.nomenclatura_final.split("_")
    for chave, dados in registro.campos_gerados.items():
        assert dados["final"] in partes, chave


def test_ordem_gravada_segue_a_posicao_no_nome(cliente, meta_id, session):
    """JSONB não preserva a ordem das chaves; `ordem` é o que devolve a
    sequência do template ao registro salvo."""
    lote = str(uuid.uuid4())
    _, taxonomia = _campanha_com_taxonomia(cliente, meta_id, lote)

    registro = session.get(TaxonomiaGerada, uuid.UUID(taxonomia["id"]))
    por_ordem = sorted(registro.campos_gerados.items(), key=lambda par: par[1]["ordem"])
    assert [chave for chave, _ in por_ordem][:3] == ["nome_campanha", "empresa", "canal"]


def test_opcional_em_branco_grava_marcador_com_bruto_nulo(cliente, meta_id, session):
    lote = str(uuid.uuid4())
    _, taxonomia = _campanha_com_taxonomia(cliente, meta_id, lote)

    registro = session.get(TaxonomiaGerada, uuid.UUID(taxonomia["id"]))
    assert registro.campos_gerados["funil"] == {"bruto": None, "final": "NA", "ordem": 6}


def test_historico_devolve_os_campos_gerados(cliente, meta_id):
    lote = str(uuid.uuid4())
    _campanha_com_taxonomia(cliente, meta_id, lote)

    linha = cliente.get("/taxonomias/historico", params={"lote_id": lote}).json()[0]
    assert linha["campos_gerados"]["objetivo"] == {
        "bruto": "Conversão",
        "final": "CV",
        "ordem": 4,
    }


# --------------------------------------------------------------------------
# exportação
# --------------------------------------------------------------------------

def _planilha(cliente, lote: str):
    ws = load_workbook(
        io.BytesIO(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    ).active
    cabecalho = [c.value for c in ws[1]]
    return cabecalho, list(ws.iter_rows(min_row=2, values_only=True))


def test_export_tem_uma_coluna_por_token_com_o_valor_do_nome(cliente, meta_id):
    """É a coluna que faz o PROCV fechar: a planilha de performance traz
    'CV', não 'Conversão'."""
    lote = str(uuid.uuid4())
    _campanha_com_taxonomia(cliente, meta_id, lote)

    cabecalho, linhas = _planilha(cliente, lote)
    assert "Objetivo (nome)" in cabecalho
    assert linhas[0][cabecalho.index("Objetivo (nome)")] == "CV"
    # A coluna com o valor digitado continua existindo, ao lado.
    assert linhas[0][cabecalho.index("Objetivo")] == "Conversão"


def test_colunas_do_nome_seguem_a_ordem_do_template(cliente, meta_id):
    lote = str(uuid.uuid4())
    _campanha_com_taxonomia(cliente, meta_id, lote)

    cabecalho, _ = _planilha(cliente, lote)
    posicoes = [
        cabecalho.index(rotulo)
        for rotulo in ("Nome da campanha (nome)", "Empresa (nome)", "Canal (nome)",
                       "Objetivo (nome)", "Mês (nome)")
    ]
    assert posicoes == sorted(posicoes)


def test_export_traz_o_marcador_do_opcional_em_branco(cliente, meta_id):
    """A coluna existe mesmo quando o campo ficou vazio — se ela sumisse, o
    deslocamento voltaria pela planilha."""
    lote = str(uuid.uuid4())
    _campanha_com_taxonomia(cliente, meta_id, lote)

    cabecalho, linhas = _planilha(cliente, lote)
    assert linhas[0][cabecalho.index("Etapa do funil (nome)")] == "NA"


def test_export_de_niveis_diferentes_nao_embaralha_as_colunas(cliente, meta_id):
    """Campanha, grupo e anúncio na mesma planilha: cada linha preenche as
    suas colunas e deixa as demais em branco, sem deslocar."""
    lote = str(uuid.uuid4())
    campanha = cliente.post(
        "/campanhas",
        json={"plataforma_id": meta_id, "nome_interno": "BF", "campos": CAMPOS_CAMPANHA},
    ).json()
    grupo = cliente.post(
        "/grupos",
        json={"campanha_id": campanha["id"], "nome_interno": "RMK", "campos": CAMPOS_GRUPO},
    ).json()
    anuncio = cliente.post(
        "/anuncios",
        json={
            "grupo_anuncio_id": grupo["id"],
            "nome_interno": "Fivela",
            "campos": CAMPOS_ANUNCIO,
        },
    ).json()
    for nivel, entidade in (("CAMPANHA", campanha), ("GRUPO", grupo), ("ANUNCIO", anuncio)):
        cliente.post(
            "/taxonomias",
            json={"nivel": nivel, "entidade_id": entidade["id"], "lote_id": lote},
        )

    cabecalho, linhas = _planilha(cliente, lote)
    coluna_objetivo = cabecalho.index("Objetivo (nome)")
    coluna_formato = cabecalho.index("Formato (nome)")

    # Célula vazia volta como None do openpyxl.
    valores_objetivo = {l[coluna_objetivo] for l in linhas}
    valores_formato = {l[coluna_formato] for l in linhas}
    # A campanha preenche objetivo e deixa formato vazio; o anúncio, o contrário.
    assert valores_objetivo == {"CV", None}
    assert valores_formato == {"VID", None}


def test_planilha_sem_campos_gerados_nao_quebra(session):
    """Linhas retroativas têm `campos_gerados` nulo (o backfill só recuperou
    o bruto). A exportação precisa continuar abrindo."""
    from datetime import datetime, timezone

    from app.exportacao import Linha, gerar_planilha
    from app.models import Nivel

    linha = Linha(
        id=uuid.uuid4(),
        nomenclatura="X_C0001",
        plataforma="Meta",
        nivel=Nivel.CAMPANHA,
        campanha="BF",
        nome_interno="BF",
        match_id="C0001",
        template_versao=1,
        criado_em=datetime.now(timezone.utc),
        lote_id=None,
    )
    ws = load_workbook(io.BytesIO(gerar_planilha([linha]))).active
    assert [c.value for c in ws[1]][0] == "Nomenclatura"
