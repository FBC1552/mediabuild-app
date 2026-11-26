"""Verifica que o schema da Fase 1 faz o que promete.

Foco nas constraints que protegem regras de negócio — não em CRUD trivial.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import (
    Anuncio,
    Campanha,
    DicionarioAbreviacao,
    GrupoAnuncio,
    LimitePlataforma,
    Nivel,
    Plataforma,
    TaxonomiaGerada,
    TemplateTaxonomia,
)


def _sufixo() -> str:
    return uuid.uuid4().hex[:8].upper()


def _plataforma(session) -> Plataforma:
    p = Plataforma(nome=f"Teste {_sufixo()}", sigla=_sufixo()[:6], ativo=True)
    session.add(p)
    session.flush()
    return p


def _hierarquia(session, plataforma: Plataforma) -> tuple[Campanha, GrupoAnuncio, Anuncio]:
    campanha = Campanha(
        plataforma_id=plataforma.id,
        nome_interno="Black Friday",
        match_id=f"C{_sufixo()}",
        campos={"objetivo": "Conversão"},
    )
    session.add(campanha)
    session.flush()

    grupo = GrupoAnuncio(
        campanha_id=campanha.id,
        nome_interno="Remarketing 30d",
        match_id=f"G{_sufixo()}",
        campos={"publico": "Remarketing"},
    )
    session.add(grupo)
    session.flush()

    anuncio = Anuncio(
        grupo_anuncio_id=grupo.id,
        nome_interno="Stories vertical",
        match_id=f"A{_sufixo()}",
        campos={"formato": "Stories"},
    )
    session.add(anuncio)
    session.flush()
    return campanha, grupo, anuncio


def test_seed_populou_as_tres_plataformas(session):
    nomes = set(session.scalars(select(Plataforma.nome)).all())
    assert {"Meta", "Google", "TikTok"} <= nomes


def test_seed_criou_limite_para_cada_nivel(session):
    meta = session.scalar(select(Plataforma).where(Plataforma.nome == "Meta"))
    niveis = set(
        session.scalars(
            select(LimitePlataforma.nivel).where(LimitePlataforma.plataforma_id == meta.id)
        ).all()
    )
    assert niveis == {Nivel.CAMPANHA, Nivel.GRUPO, Nivel.ANUNCIO}


def test_template_do_meta_tem_campo_dinamico_de_posicionamento(session):
    meta = session.scalar(select(Plataforma).where(Plataforma.nome == "Meta"))
    tpl = session.scalar(
        select(TemplateTaxonomia).where(
            TemplateTaxonomia.plataforma_id == meta.id, TemplateTaxonomia.nivel == Nivel.GRUPO
        )
    )
    chaves = [t.get("chave") for t in tpl.tokens if t["tipo"] == "campo"]
    assert "posicionamento" in chaves
    assert tpl.tokens[-1]["tipo"] == "match_id"


def test_template_ativo_tem_marcador_de_ausencia(session):
    """O marcador vive numa coluna do template, não no código: trocá-lo é UPDATE."""
    meta = session.scalar(select(Plataforma).where(Plataforma.nome == "Meta"))
    ativos = session.scalars(
        select(TemplateTaxonomia).where(
            TemplateTaxonomia.plataforma_id == meta.id,
            TemplateTaxonomia.ativo.is_(True),
        )
    ).all()
    assert ativos
    assert {t.marcador_ausencia for t in ativos} == {"NA"}


def test_seed_versiona_o_marcador_em_vez_de_editar_no_lugar(session):
    """Mudar o marcador muda a quantidade de partes do nome. Editar a versão
    ativa no lugar tornaria os nomes já gerados inexplicáveis pelo
    `template_versao` que guardaram (D-004)."""
    from app.seed import sincronizar_templates

    meta = session.scalar(select(Plataforma).where(Plataforma.nome == "Meta"))
    antes = session.scalar(
        select(TemplateTaxonomia).where(
            TemplateTaxonomia.plataforma_id == meta.id,
            TemplateTaxonomia.nivel == Nivel.CAMPANHA,
            TemplateTaxonomia.ativo.is_(True),
        )
    )
    versao_antiga, tokens_antigos = antes.versao, list(antes.tokens)

    antes.marcador_ausencia = "ZZ"
    session.flush()

    novas = sincronizar_templates(session, meta)
    session.flush()

    assert novas >= 1
    depois = session.scalar(
        select(TemplateTaxonomia).where(
            TemplateTaxonomia.plataforma_id == meta.id,
            TemplateTaxonomia.nivel == Nivel.CAMPANHA,
            TemplateTaxonomia.ativo.is_(True),
        )
    )
    assert depois.versao == versao_antiga + 1
    assert depois.marcador_ausencia == "NA"
    assert depois.tokens == tokens_antigos
    # A versão anterior continua existindo, apenas desativada.
    session.refresh(antes)
    assert antes.ativo is False
    assert antes.marcador_ausencia == "ZZ"


def test_seed_nao_versiona_quando_nada_mudou(session):
    """Idempotência: rodar o seed de novo não pode inflar `template_versao`."""
    from app.seed import sincronizar_templates

    meta = session.scalar(select(Plataforma).where(Plataforma.nome == "Meta"))
    assert sincronizar_templates(session, meta) == 0


def test_consulta_percorre_a_hierarquia_completa(session):
    """Critério de saída da Fase 1: uma consulta SQL atravessa
    plataforma → campanha → grupo → anúncio."""
    plataforma = _plataforma(session)
    campanha, grupo, anuncio = _hierarquia(session, plataforma)

    linha = session.execute(
        text("""
            SELECT p.sigla,
                   c.match_id  AS campanha,
                   g.match_id  AS grupo,
                   a.match_id  AS anuncio,
                   c.campos ->> 'objetivo' AS objetivo
            FROM anuncios a
            JOIN grupos_anuncio g ON g.id = a.grupo_anuncio_id
            JOIN campanhas      c ON c.id = g.campanha_id
            JOIN plataformas    p ON p.id = c.plataforma_id
            WHERE a.id = :anuncio_id
        """),
        {"anuncio_id": anuncio.id},
    ).one()

    assert linha.sigla == plataforma.sigla
    assert linha.campanha == campanha.match_id
    assert linha.grupo == grupo.match_id
    assert linha.anuncio == anuncio.match_id
    assert linha.objetivo == "Conversão"


def test_match_id_duplicado_e_rejeitado(session):
    plataforma = _plataforma(session)
    repetido = f"C{_sufixo()}"
    for _ in range(2):
        session.add(
            Campanha(
                plataforma_id=plataforma.id,
                nome_interno="x",
                match_id=repetido,
                campos={},
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_nomenclatura_final_duplicada_e_rejeitada(session):
    """Colisão de nome quebraria o cruzamento com planilhas de performance,
    que é a razão de existir do match ID."""
    nome = f"FB_CV_RMKT_{_sufixo()}"
    for _ in range(2):
        session.add(
            TaxonomiaGerada(
                nivel=Nivel.CAMPANHA,
                entidade_id=uuid.uuid4(),
                nomenclatura_final=nome,
                template_versao=1,
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_abreviacao_global_duplicada_e_rejeitada(session):
    """No Postgres NULLs são distintos entre si, então uma UNIQUE comum
    deixaria passar dois termos globais iguais. O índice parcial resolve."""
    termo = f"Termo {_sufixo()}"
    for _ in range(2):
        session.add(
            DicionarioAbreviacao(
                plataforma_id=None, categoria="objetivo", termo=termo, abreviacao="XX"
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_mesmo_termo_pode_existir_global_e_por_plataforma(session):
    """O escopo por plataforma precisa poder sobrescrever o global."""
    plataforma = _plataforma(session)
    termo = f"Termo {_sufixo()}"
    session.add(
        DicionarioAbreviacao(plataforma_id=None, categoria="formato", termo=termo, abreviacao="GL")
    )
    session.add(
        DicionarioAbreviacao(
            plataforma_id=plataforma.id, categoria="formato", termo=termo, abreviacao="PL"
        )
    )
    session.flush()  # não deve levantar


def test_limite_de_caracteres_precisa_ser_positivo(session):
    plataforma = _plataforma(session)
    session.add(
        LimitePlataforma(plataforma_id=plataforma.id, nivel=Nivel.CAMPANHA, limite_caracteres=0)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_apagar_campanha_leva_grupos_e_anuncios(session):
    plataforma = _plataforma(session)
    campanha, grupo, anuncio = _hierarquia(session, plataforma)
    grupo_id, anuncio_id = grupo.id, anuncio.id

    session.delete(campanha)
    session.flush()

    assert session.get(GrupoAnuncio, grupo_id) is None
    assert session.get(Anuncio, anuncio_id) is None


def test_historico_sobrevive_a_exclusao_da_entidade(session):
    """D-004: o nome já pode ter subido numa plataforma de anúncios, então
    apagar a campanha não pode apagar o histórico."""
    plataforma = _plataforma(session)
    campanha, _, _ = _hierarquia(session, plataforma)

    taxonomia = TaxonomiaGerada(
        nivel=Nivel.CAMPANHA,
        entidade_id=campanha.id,
        nomenclatura_final=f"FB_CV_{_sufixo()}",
        template_versao=1,
    )
    session.add(taxonomia)
    session.flush()
    taxonomia_id = taxonomia.id

    session.delete(campanha)
    session.flush()

    assert session.get(TaxonomiaGerada, taxonomia_id) is not None
