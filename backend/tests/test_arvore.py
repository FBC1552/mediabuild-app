"""Listagem da hierarquia — o que a tela precisa para montar a árvore.

O schema já tinha `Campanha 1→N GrupoAnuncio 1→N Anuncio`; faltava a API
expor os filhos junto com a nomenclatura mais recente de cada um, sem
obrigar a tela a uma requisição por filho.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Plataforma
from tests.conftest import CAMPOS_ANUNCIO, CAMPOS_CAMPANHA, CAMPOS_GRUPO


@pytest.fixture
def meta_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "Meta")))


@pytest.fixture
def tiktok_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "TikTok")))


def _campanha(cliente, plataforma_id: str, nome: str = "Black Friday"):
    return cliente.post(
        "/campanhas",
        json={"plataforma_id": plataforma_id, "nome_interno": nome, "campos": CAMPOS_CAMPANHA},
    ).json()


def _grupo(cliente, campanha_id: str, nome: str = "Remarketing 30d"):
    return cliente.post(
        "/grupos",
        json={"campanha_id": campanha_id, "nome_interno": nome, "campos": CAMPOS_GRUPO},
    ).json()


def _anuncio(cliente, grupo_id: str, nome: str = "Fivela 15s"):
    return cliente.post(
        "/anuncios",
        json={"grupo_anuncio_id": grupo_id, "nome_interno": nome, "campos": CAMPOS_ANUNCIO},
    ).json()


def _gerar(cliente, nivel: str, entidade_id: str):
    r = cliente.post("/taxonomias", json={"nivel": nivel, "entidade_id": entidade_id})
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------
# filhos de uma campanha
# --------------------------------------------------------------------------

def test_grupos_da_campanha_trazem_identificacao_e_nomenclatura(cliente, meta_id):
    campanha = _campanha(cliente, meta_id)
    grupo = _grupo(cliente, campanha["id"])
    taxonomia = _gerar(cliente, "GRUPO", grupo["id"])

    r = cliente.get(f"/campanhas/{campanha['id']}/grupos")
    assert r.status_code == 200
    (no,) = r.json()

    assert no["id"] == grupo["id"]
    assert no["pai_id"] == campanha["id"]
    assert no["nome_interno"] == "Remarketing 30d"
    assert no["match_id"] == grupo["match_id"]
    assert no["nomenclatura"] == taxonomia["nomenclatura_final"]
    assert no["criado_em"]


def test_grupo_sem_nomenclatura_vem_com_nulo(cliente, meta_id):
    """Entidade criada e ainda não gerada é estado normal, não erro."""
    campanha = _campanha(cliente, meta_id)
    _grupo(cliente, campanha["id"])

    (no,) = cliente.get(f"/campanhas/{campanha['id']}/grupos").json()
    assert no["nomenclatura"] is None
    assert no["taxonomia_id"] is None


def test_traz_a_nomenclatura_mais_recente(cliente, meta_id, session):
    """Gerar de novo cria um registro novo (D-004); a árvore mostra o
    último, e o anterior continua no histórico."""
    from datetime import timedelta

    from sqlalchemy import update

    from app.models import TaxonomiaGerada

    campanha = _campanha(cliente, meta_id)
    grupo = _grupo(cliente, campanha["id"])
    primeira = _gerar(cliente, "GRUPO", grupo["id"])

    # `criado_em` vem de `now()`, que no Postgres é o instante de início da
    # transação — e o conftest põe o teste inteiro numa só. Sem recuar o
    # relógio da primeira, as duas nasceriam com o mesmo carimbo e o teste
    # não estaria checando 'mais recente' coisa nenhuma.
    session.execute(
        update(TaxonomiaGerada)
        .where(TaxonomiaGerada.id == uuid.UUID(primeira["id"]))
        .values(criado_em=TaxonomiaGerada.criado_em - timedelta(hours=1))
    )

    cliente.patch(f"/grupos/{grupo['id']}", json={"campos": {**CAMPOS_GRUPO, "cidade": "Recife"}})
    segunda = _gerar(cliente, "GRUPO", grupo["id"])

    (no,) = cliente.get(f"/campanhas/{campanha['id']}/grupos").json()
    assert no["nomenclatura"] == segunda["nomenclatura_final"]
    assert no["nomenclatura"] != primeira["nomenclatura_final"]

    # A anterior continua acessível pelo histórico.
    historico = cliente.get(
        "/taxonomias", params={"entidade_id": grupo["id"], "limite": 10}
    ).json()
    assert {t["id"] for t in historico} == {primeira["id"], segunda["id"]}


def test_grupos_de_outra_campanha_nao_vazam(cliente, meta_id):
    campanha_a = _campanha(cliente, meta_id, "Campanha A")
    campanha_b = _campanha(cliente, meta_id, "Campanha B")
    _grupo(cliente, campanha_a["id"], "Grupo A")
    _grupo(cliente, campanha_b["id"], "Grupo B")

    nomes = {g["nome_interno"] for g in cliente.get(f"/campanhas/{campanha_a['id']}/grupos").json()}
    assert nomes == {"Grupo A"}


def test_campanha_sem_grupos_devolve_lista_vazia(cliente, meta_id):
    campanha = _campanha(cliente, meta_id)
    r = cliente.get(f"/campanhas/{campanha['id']}/grupos")
    assert r.status_code == 200
    assert r.json() == []


def test_campanha_inexistente_da_404_e_nao_lista_vazia(cliente):
    """Distinguir 'não existe' de 'existe e está vazia' é o que permite à
    tela mostrar erro em vez de uma árvore silenciosamente vazia."""
    r = cliente.get(f"/campanhas/{uuid.uuid4()}/grupos")
    assert r.status_code == 404
    assert "não encontrad" in r.json()["detail"].lower()


# --------------------------------------------------------------------------
# filhos de um grupo
# --------------------------------------------------------------------------

def test_anuncios_do_grupo(cliente, meta_id):
    campanha = _campanha(cliente, meta_id)
    grupo = _grupo(cliente, campanha["id"])
    anuncio = _anuncio(cliente, grupo["id"])
    taxonomia = _gerar(cliente, "ANUNCIO", anuncio["id"])

    (no,) = cliente.get(f"/grupos/{grupo['id']}/anuncios").json()
    assert no["id"] == anuncio["id"]
    assert no["pai_id"] == grupo["id"]
    assert no["match_id"] == anuncio["match_id"]
    assert no["nomenclatura"] == taxonomia["nomenclatura_final"]


def test_grupo_inexistente_da_404(cliente):
    assert cliente.get(f"/grupos/{uuid.uuid4()}/anuncios").status_code == 404


def test_rota_de_filhos_nao_colide_com_a_rota_de_detalhe(cliente, meta_id):
    """`/grupos/{id}` e `/grupos/{id}/anuncios` convivem: a primeira devolve
    a entidade, a segunda a lista."""
    campanha = _campanha(cliente, meta_id)
    grupo = _grupo(cliente, campanha["id"])

    detalhe = cliente.get(f"/grupos/{grupo['id']}").json()
    filhos = cliente.get(f"/grupos/{grupo['id']}/anuncios").json()

    assert detalhe["id"] == grupo["id"]
    assert filhos == []


def test_arvore_nao_expoe_edicao_nem_exclusao_de_taxonomia(cliente, meta_id):
    """D-004 na superfície da API: nem a árvore abre essa porta."""
    campanha = _campanha(cliente, meta_id)
    grupo = _grupo(cliente, campanha["id"])
    taxonomia = _gerar(cliente, "GRUPO", grupo["id"])

    assert cliente.patch(f"/taxonomias/{taxonomia['id']}", json={}).status_code == 405
    assert cliente.delete(f"/taxonomias/{taxonomia['id']}").status_code == 405


def test_custo_da_listagem_nao_cresce_com_o_numero_de_filhos(cliente, meta_id, session):
    """Guarda contra N+1: a tela existe justamente para listar muitos filhos.

    O que importa não é o número absoluto de consultas — é ele não variar
    com a quantidade de filhos.
    """
    from sqlalchemy import event

    def montar(quantos: int) -> tuple[int, int]:
        campanha = _campanha(cliente, meta_id, f"Campanha {uuid.uuid4().hex[:6]}")
        for i in range(quantos):
            grupo = _grupo(cliente, campanha["id"], f"Grupo {i}")
            _gerar(cliente, "GRUPO", grupo["id"])

        consultas = 0

        def contar(*_args, **_kwargs):
            nonlocal consultas
            consultas += 1

        event.listen(session.bind, "before_cursor_execute", contar)
        try:
            nos = cliente.get(f"/campanhas/{campanha['id']}/grupos").json()
        finally:
            event.remove(session.bind, "before_cursor_execute", contar)

        assert len(nos) == quantos
        assert all(n["nomenclatura"] for n in nos)
        return consultas

    dois, oito = montar(2), montar(8)
    assert dois == oito, (dois, oito)


# --------------------------------------------------------------------------
# filtro por plataforma na raiz
# --------------------------------------------------------------------------

def test_campanhas_filtram_por_plataforma(cliente, meta_id, tiktok_id):
    """A raiz da árvore. O filtro já existia; este teste é que ele não some."""
    do_meta = _campanha(cliente, meta_id, f"Meta {uuid.uuid4().hex[:6]}")
    do_tiktok = _campanha(cliente, tiktok_id, f"TikTok {uuid.uuid4().hex[:6]}")

    ids = {c["id"] for c in cliente.get("/campanhas", params={"plataforma_id": meta_id}).json()}
    assert do_meta["id"] in ids
    assert do_tiktok["id"] not in ids
