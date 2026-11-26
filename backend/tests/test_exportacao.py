"""Testes da exportação Excel.

O critério de saída da Fase 5 é o arquivo abrir sem aviso de corrupção,
então os testes reabrem o `.xlsx` com openpyxl e conferem o conteúdo.
"""

import io
import uuid

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.exportacao import COLUNAS_FIXAS, gerar_planilha, montar_linhas
from app.models import Nivel, Plataforma, TaxonomiaGerada
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


def _abrir(conteudo: bytes):
    return load_workbook(io.BytesIO(conteudo)).active


def _linhas(ws):
    return list(ws.iter_rows(min_row=2, values_only=True))


def _cabecalho(ws):
    return [c.value for c in ws[1]]


def _montar_hierarquia(cliente, meta_id: str, lote: str):
    """Cria campanha + grupo + anúncio e gera as três taxonomias."""
    campanha = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": meta_id,
            "nome_interno": "Black Friday",
            "campos": CAMPOS_CAMPANHA,
        },
    ).json()
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

    for nivel, entidade in (("CAMPANHA", campanha), ("GRUPO", grupo), ("ANUNCIO", anuncio)):
        cliente.post(
            "/taxonomias",
            json={"nivel": nivel, "entidade_id": entidade["id"], "lote_id": lote},
        )
    return campanha, grupo, anuncio


# --------------------------------------------------------------------------

def test_planilha_vazia_ainda_e_valida(session):
    """Exportar sem resultado não pode gerar arquivo corrompido."""
    ws = _abrir(gerar_planilha([]))
    assert _cabecalho(ws)[: len(COLUNAS_FIXAS)] == COLUNAS_FIXAS
    assert _linhas(ws) == []


def test_export_devolve_xlsx_com_content_disposition(cliente, meta_id):
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    r = cliente.get("/taxonomias/export", params={"lote_id": lote})
    assert r.status_code == 200
    assert (
        r.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert ".xlsx" in r.headers["content-disposition"]
    # Assinatura de arquivo ZIP — todo .xlsx é um zip.
    assert r.content[:2] == b"PK"


def test_arquivo_reabre_e_tem_as_tres_linhas(cliente, meta_id):
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    assert len(_linhas(ws)) == 3


def test_nomenclatura_e_a_primeira_coluna(cliente, meta_id):
    """É a coluna que o analista cola na plataforma; tem que estar à mão."""
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    assert _cabecalho(ws)[0] == "Nomenclatura"

    nomes = {linha[0] for linha in _linhas(ws)}
    assert any(n.startswith(f"{NOME_CAMPANHA}_C") for n in nomes)
    assert any(n.startswith(f"{NOME_GRUPO}_G") for n in nomes)
    assert any(n.startswith(f"{NOME_ANUNCIO}_A") for n in nomes)


def test_campos_dinamicos_viram_colunas_separadas(cliente, meta_id):
    """O objetivo do arquivo é permitir copiar e colar campo a campo."""
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    cabecalho = _cabecalho(ws)
    for esperado in ("Nome da campanha", "Empresa", "Objetivo", "Mês", "Formato"):
        assert esperado in cabecalho, cabecalho

    coluna_objetivo = cabecalho.index("Objetivo")
    valores = {linha[coluna_objetivo] for linha in _linhas(ws)}
    assert "Conversão" in valores


def test_colunas_de_contexto_preenchidas(cliente, meta_id):
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    cabecalho = _cabecalho(ws)
    linhas = _linhas(ws)

    plataformas = {l[cabecalho.index("Plataforma")] for l in linhas}
    niveis = {l[cabecalho.index("Nível")] for l in linhas}
    internos = {l[cabecalho.index("Nome interno")] for l in linhas}

    assert plataformas == {"Meta"}
    assert niveis == {"Campanha", "Grupo de anúncio", "Anúncio"}
    assert "Black Friday" in internos


def test_contagem_de_caracteres_bate_com_a_nomenclatura(cliente, meta_id):
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    cabecalho = _cabecalho(ws)
    for linha in _linhas(ws):
        assert linha[cabecalho.index("Caracteres")] == len(linha[0])


def test_cabecalho_congelado_e_com_filtro(cliente, meta_id):
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref is not None


def test_filtro_por_lote_isola_a_sessao(cliente, meta_id):
    lote_a = str(uuid.uuid4())
    lote_b = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote_a)
    _montar_hierarquia(cliente, meta_id, lote_b)

    so_a = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote_a}).content)
    assert len(_linhas(so_a)) == 3

    tudo = _abrir(cliente.get("/taxonomias/export").content)
    assert len(_linhas(tudo)) >= 6


def test_filtro_por_nivel(cliente, meta_id):
    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    ws = _abrir(
        cliente.get("/taxonomias/export", params={"lote_id": lote, "nivel": "CAMPANHA"}).content
    )
    linhas = _linhas(ws)
    assert len(linhas) == 1
    assert linhas[0][_cabecalho(ws).index("Nível")] == "Campanha"


def test_historico_sobrevive_a_exclusao_da_entidade(cliente, meta_id, session):
    """D-004: apagar a campanha não pode quebrar a exportação."""
    lote = str(uuid.uuid4())
    campanha, _, _ = _montar_hierarquia(cliente, meta_id, lote)

    assert cliente.delete(f"/campanhas/{campanha['id']}").status_code == 204

    ws = _abrir(cliente.get("/taxonomias/export", params={"lote_id": lote}).content)
    linhas = _linhas(ws)
    assert len(linhas) == 3
    plataformas = {l[_cabecalho(ws).index("Plataforma")] for l in linhas}
    assert plataformas == {"(entidade removida)"}


def test_montar_linhas_nao_faz_consulta_por_taxonomia(cliente, meta_id, session):
    """Guarda contra N+1: as entidades são resolvidas em lote por nível."""
    from sqlalchemy import event

    lote = str(uuid.uuid4())
    _montar_hierarquia(cliente, meta_id, lote)

    registros = session.scalars(
        select(TaxonomiaGerada).where(TaxonomiaGerada.lote_id == lote)
    ).all()
    assert len(registros) == 3

    consultas = 0

    def contar(*_args, **_kwargs):
        nonlocal consultas
        consultas += 1

    event.listen(session.bind, "before_cursor_execute", contar)
    try:
        linhas = montar_linhas(session, registros)
    finally:
        event.remove(session.bind, "before_cursor_execute", contar)

    assert len(linhas) == 3
    # Uma consulta por nível presente, não uma por taxonomia.
    assert consultas <= len(Nivel)
