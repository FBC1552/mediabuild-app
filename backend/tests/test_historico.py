"""Testes do histórico — `GET /taxonomias/historico`.

O que a tela precisa e a listagem crua não dá: nome da plataforma e da
campanha resolvidos, e filtros por data de criação, plataforma e campanha.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Nivel, Plataforma, TaxonomiaGerada
from tests.conftest import CAMPOS_ANUNCIO, CAMPOS_CAMPANHA, CAMPOS_GRUPO


@pytest.fixture
def meta_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "Meta")))


@pytest.fixture
def tiktok_id(session):
    return str(session.scalar(select(Plataforma.id).where(Plataforma.nome == "TikTok")))


def _hierarquia(cliente, plataforma_id: str, lote: str, nome_campanha: str = "Black Friday"):
    campanha = cliente.post(
        "/campanhas",
        json={
            "plataforma_id": plataforma_id,
            "nome_interno": nome_campanha,
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
            "nome_interno": "Fivela 15s",
            "campos": CAMPOS_ANUNCIO,
        },
    ).json()

    for nivel, entidade in (("CAMPANHA", campanha), ("GRUPO", grupo), ("ANUNCIO", anuncio)):
        r = cliente.post(
            "/taxonomias",
            json={"nivel": nivel, "entidade_id": entidade["id"], "lote_id": lote},
        )
        assert r.status_code == 201, r.text

    return campanha, grupo, anuncio


def _do_lote(cliente, lote: str, **filtros):
    return cliente.get("/taxonomias/historico", params={"lote_id": lote, **filtros}).json()


# --------------------------------------------------------------------------

def test_historico_resolve_plataforma_e_campanha(cliente, meta_id):
    lote = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote)

    linhas = _do_lote(cliente, lote)
    assert len(linhas) == 3

    assert {l["plataforma"] for l in linhas} == {"Meta"}
    # A campanha aparece nas três linhas, inclusive nas de grupo e anúncio.
    assert {l["campanha"] for l in linhas} == {"Black Friday"}
    assert {l["nivel"] for l in linhas} == {"CAMPANHA", "GRUPO", "ANUNCIO"}


def test_historico_traz_os_campos_da_entidade(cliente, meta_id):
    lote = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote)

    campanha = next(l for l in _do_lote(cliente, lote) if l["nivel"] == "CAMPANHA")
    assert campanha["campos"]["objetivo"] == "Conversão"
    assert campanha["caracteres"] == len(campanha["nomenclatura_final"])
    assert campanha["match_id"].startswith("C")


def test_filtro_por_plataforma(cliente, meta_id, tiktok_id):
    lote_meta = str(uuid.uuid4())
    lote_tiktok = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote_meta)
    _hierarquia(cliente, tiktok_id, lote_tiktok, nome_campanha="Natal")

    so_meta = cliente.get(
        "/taxonomias/historico", params={"plataforma_id": meta_id, "limite": 500}
    ).json()
    assert so_meta, "esperava pelo menos as três do lote do Meta"
    assert {l["plataforma"] for l in so_meta} == {"Meta"}

    ids_tiktok = {l["id"] for l in _do_lote(cliente, lote_tiktok)}
    assert ids_tiktok.isdisjoint({l["id"] for l in so_meta})


def test_filtro_por_campanha(cliente, meta_id):
    """Filtrar pela campanha traz os três níveis dela, não só a campanha."""
    lote_a = str(uuid.uuid4())
    lote_b = str(uuid.uuid4())
    campanha_a, _, _ = _hierarquia(cliente, meta_id, lote_a, nome_campanha="Campanha A")
    _hierarquia(cliente, meta_id, lote_b, nome_campanha="Campanha B")

    linhas = cliente.get(
        "/taxonomias/historico", params={"campanha_id": campanha_a["id"], "limite": 500}
    ).json()

    assert len(linhas) == 3
    assert {l["campanha"] for l in linhas} == {"Campanha A"}


def test_filtro_por_data_de_criacao_inclui_o_dia_de_hoje(cliente, meta_id):
    """`ate` vem da tela como data pura; sem o ajuste de fim de dia, o que
    foi gerado hoje ficaria de fora."""
    lote = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote)

    hoje = date.today().isoformat()
    assert len(_do_lote(cliente, lote, desde=hoje, ate=hoje)) == 3


def test_filtro_por_data_usa_o_fuso_da_aplicacao(cliente, session, meta_id):
    """Regressão do bug de fuso, independente da hora em que a suíte roda.

    `criado_em` é UTC; o analista pensa em data local. Com a máquina em
    UTC-3, o que é gerado às 22h locais é gravado como 01h do dia seguinte
    em UTC — e o filtro `ate=<hoje>`, comparado em UTC, escondia do analista
    o que ele tinha acabado de gerar.

    Em vez de esperar as 21h, o teste grava `criado_em` nos dois instantes
    que cercam a virada do dia local e cobra os dois lados: o de hoje entra,
    o de ontem não.
    """
    lote = str(uuid.uuid4())
    campanha, _, _ = _hierarquia(cliente, meta_id, lote)

    hoje_local = datetime.now(settings.zona).date()
    ontem_local = hoje_local - timedelta(days=1)

    def _gravar(nome: str, momento_local: datetime) -> uuid.UUID:
        registro = TaxonomiaGerada(
            nivel=Nivel.CAMPANHA,
            entidade_id=uuid.UUID(campanha["id"]),
            plataforma_id=uuid.UUID(meta_id),
            campanha_id=uuid.UUID(campanha["id"]),
            nomenclatura_final=nome,
            template_versao=1,
            lote_id=uuid.UUID(lote),
            criado_em=momento_local.astimezone(UTC),
        )
        session.add(registro)
        session.flush()
        return registro.id

    # 23:30 de hoje no fuso do analista = 02:30 de amanhã em UTC.
    tarde_da_noite = _gravar(
        f"FIM_DO_DIA_{lote[:8].upper()}",
        datetime.combine(hoje_local, time(23, 30), tzinfo=settings.zona),
    )
    # 23:30 de ontem local = 02:30 de hoje em UTC: com a comparação em UTC
    # ingênua, esta linha aparecia como se fosse de hoje.
    noite_anterior = _gravar(
        f"VESPERA_{lote[:8].upper()}",
        datetime.combine(ontem_local, time(23, 30), tzinfo=settings.zona),
    )
    session.commit()

    hoje = hoje_local.isoformat()
    ids = {l["id"] for l in _do_lote(cliente, lote, desde=hoje, ate=hoje)}

    assert str(tarde_da_noite) in ids, "o que foi gerado hoje à noite sumiu do histórico"
    assert str(noite_anterior) not in ids, "linha de ontem vazou para o filtro de hoje"


def test_filtro_por_data_exclui_periodo_antigo(cliente, meta_id):
    lote = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote)

    ontem = (date.today() - timedelta(days=1)).isoformat()
    assert _do_lote(cliente, lote, ate=ontem) == []


def test_filtro_por_nivel_e_busca(cliente, meta_id):
    lote = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote)

    so_campanha = _do_lote(cliente, lote, nivel="CAMPANHA")
    assert len(so_campanha) == 1

    nome = so_campanha[0]["nomenclatura_final"]
    achados = cliente.get(
        "/taxonomias/historico", params={"busca": nome[:12].lower(), "limite": 500}
    ).json()
    assert nome in {l["nomenclatura_final"] for l in achados}


def test_filtro_por_campanha_sobrevive_a_exclusao(cliente, meta_id):
    """A coluna denormalizada existe justamente para isto: apagar a
    campanha não pode sumir com o histórico do filtro (D-004)."""
    lote = str(uuid.uuid4())
    campanha, _, _ = _hierarquia(cliente, meta_id, lote)

    assert cliente.delete(f"/campanhas/{campanha['id']}").status_code == 204

    linhas = cliente.get(
        "/taxonomias/historico", params={"campanha_id": campanha["id"], "limite": 500}
    ).json()
    assert len(linhas) == 3
    # A entidade sumiu, mas a nomenclatura permanece.
    assert all(l["nomenclatura_final"] for l in linhas)


def test_export_aceita_os_mesmos_filtros_do_historico(cliente, meta_id):
    lote = str(uuid.uuid4())
    campanha, _, _ = _hierarquia(cliente, meta_id, lote)

    r = cliente.get(
        "/taxonomias/export",
        params={"campanha_id": campanha["id"], "nivel": "ANUNCIO"},
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_historico_nao_tem_edicao_nem_exclusao(cliente, meta_id):
    """D-004 na superfície da API: o histórico é só leitura."""
    lote = str(uuid.uuid4())
    _hierarquia(cliente, meta_id, lote)
    taxonomia = _do_lote(cliente, lote)[0]

    assert cliente.patch(f"/taxonomias/{taxonomia['id']}", json={}).status_code == 405
    assert cliente.delete(f"/taxonomias/{taxonomia['id']}").status_code == 405
