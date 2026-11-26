"""Motor rodando com os dados reais do seed, não com fixtures.

É o que prova que template, dicionário e limites cadastrados no banco
produzem de fato as nomenclaturas esperadas — e que a estrutura de campos
da planilha de referência (a planilha de taxonomia de referência) fecha ponta a ponta.
"""

import re
import uuid

import pytest
from sqlalchemy import select

from app.models import Nivel, Plataforma
from app.plataformas import CampoSpec, criar_plataforma, niveis_faltando
from app.taxonomia import (
    CampoAusente,
    CampoLongoDemais,
    TermoDesconhecido,
    gerar_nomenclatura,
)
from app.taxonomia.match_id import gerar_match_id
from app.taxonomia.repositorio import (
    carregar_dicionario,
    carregar_limite,
    carregar_template,
)

# Conjuntos completos por nível, na forma que o analista preenche a tela.
CAMPANHA = {
    "nome_campanha": "ALV27",
    "empresa": "Loja Alfa",
    "canal": "Instagram",
    "objetivo": "Conversão",
    "mes": "Agosto",
}
GRUPO = {
    "sexo": "Feminino",
    "idade": "25-34",
    "interesse_1": "Bolsas",
    "interesse_2": "Moda",
    "regiao": "Sudeste",
    "cidade": "Rio de Janeiro",
    "segmentacao": "Remarketing",
}
ANUNCIO = {
    "formato": "Vídeo",
    "dimensao": "1200x600",
    "tipo_compra": "CPC",
    "nome_criativo": "fivela",
    "secundagem": "15s",
    "versao": "C",
}


def _plataforma(session, nome: str) -> Plataforma:
    return session.scalar(select(Plataforma).where(Plataforma.nome == nome))


def _gerar(session, nome_plataforma: str, nivel: Nivel, campos: dict) -> str:
    plataforma = _plataforma(session, nome_plataforma)
    template = carregar_template(session, plataforma.id, nivel)
    dicionario = carregar_dicionario(session, plataforma.id)
    limite = carregar_limite(session, plataforma.id, nivel)
    match_id = gerar_match_id(session, nivel)
    return gerar_nomenclatura(template, campos, dicionario, match_id, limite)


# --------------------------------------------------------------------------
# a estrutura da planilha, ponta a ponta
# --------------------------------------------------------------------------

def test_campanha_no_meta(session):
    """O exemplo da aba Taxonomia: nome, empresa, plataforma, canal,
    objetivo, mês — e o match ID no lugar do '_A1' escrito à mão.

    O 'NA' antes do match ID é o marcador do 'funil', opcional e em branco
    aqui: opcional vazio ocupa a posição em vez de sumir com ela."""
    nome = _gerar(session, "Meta", Nivel.CAMPANHA, CAMPANHA)
    assert re.fullmatch(r"ALV27_ALF_METAA_INSTA_CV_AGO_NA_C\d{4,}", nome), nome


def test_grupo_no_meta(session):
    """O 'NA' final é o 'posicionamento', extra opcional do Meta."""
    nome = _gerar(session, "Meta", Nivel.GRUPO, GRUPO)
    assert re.fullmatch(r"F_25-34_BOLSA_MODA_SUD_RJ_RMKT_NA_G\d{4,}", nome), nome


def test_anuncio_no_tiktok(session):
    nome = _gerar(session, "TikTok", Nivel.ANUNCIO, ANUNCIO)
    assert re.fullmatch(r"VID_1200X600_CPC_FIVELA_15S_C_A\d{4,}", nome), nome


def test_campo_livre_respeita_o_proprio_limite(session):
    """'Nome da campanha' é campo livre de 5 caracteres na planilha."""
    with pytest.raises(CampoLongoDemais) as erro:
        _gerar(session, "Meta", Nivel.CAMPANHA, {**CAMPANHA, "nome_campanha": "ALV27X"})

    assert erro.value.chave == "nome_campanha"
    assert erro.value.maximo == 5


def test_campo_livre_nao_precisa_estar_no_dicionario(session):
    """Campo livre é o contraponto do D-005: aceita qualquer texto."""
    nome = _gerar(session, "Meta", Nivel.CAMPANHA, {**CAMPANHA, "nome_campanha": "ZZZZZ"})
    assert nome.startswith("ZZZZZ_")


def test_campo_opcional_em_branco_vira_marcador(session):
    """Interesse 2 vazio não vira erro nem separador duplicado — e não some,
    porque sumir mudaria a quantidade de partes do nome."""
    sem_segundo = {**GRUPO, "interesse_2": ""}
    nome = _gerar(session, "Meta", Nivel.GRUPO, sem_segundo)

    assert re.fullmatch(r"F_25-34_BOLSA_NA_SUD_RJ_RMKT_NA_G\d{4,}", nome), nome
    assert "__" not in nome


def test_opcional_vazio_e_preenchido_tem_a_mesma_quantidade_de_partes(session):
    """A regressão que o marcador existe para impedir: com o interesse 2 em
    branco, o nome tinha uma parte a menos e as colunas da planilha de
    performance deslocavam de uma linha para a outra."""
    com = _gerar(session, "Meta", Nivel.GRUPO, GRUPO)
    sem = _gerar(session, "Meta", Nivel.GRUPO, {**GRUPO, "interesse_2": ""})

    assert len(com.split("_")) == len(sem.split("_"))


def test_marcador_e_configuravel_por_update_no_template(session):
    """Padrão de nomenclatura vive em dado: trocar o marcador é UPDATE."""
    from app.models import TemplateTaxonomia

    plataforma = _plataforma(session, "Meta")
    registro = session.scalar(
        select(TemplateTaxonomia).where(
            TemplateTaxonomia.plataforma_id == plataforma.id,
            TemplateTaxonomia.nivel == Nivel.GRUPO,
            TemplateTaxonomia.ativo.is_(True),
        )
    )
    registro.marcador_ausencia = "ZZ"
    session.flush()

    nome = _gerar(session, "Meta", Nivel.GRUPO, {**GRUPO, "interesse_2": ""})
    assert "_ZZ_" in nome and "_NA_" not in nome


def test_campo_obrigatorio_em_branco_continua_sendo_erro(session):
    with pytest.raises(CampoAusente) as erro:
        _gerar(session, "Meta", Nivel.GRUPO, {**GRUPO, "cidade": ""})
    assert erro.value.chave == "cidade"


def test_interesses_compartilham_o_mesmo_vocabulario(session):
    """interesse_1 e interesse_2 são posições distintas no nome, mas o
    analista cadastra a lista de interesses uma vez só."""
    trocado = {**GRUPO, "interesse_1": "Moda", "interesse_2": "Bolsas"}
    nome = _gerar(session, "Meta", Nivel.GRUPO, trocado)
    assert "_MODA_BOLSA_" in nome


def test_termo_fora_do_dicionario_lista_as_opcoes_da_categoria(session):
    """D-005, agora apontando a chave do campo e não a categoria."""
    with pytest.raises(TermoDesconhecido) as erro:
        _gerar(session, "Meta", Nivel.GRUPO, {**GRUPO, "interesse_2": "Astronomia"})

    assert erro.value.chave == "interesse_2"
    assert erro.value.categoria == "interesse"
    assert "Bolsas" in erro.value.opcoes


def test_campo_extra_da_plataforma_e_opcional(session):
    """`posicionamento` só existe no Meta e não trava quem não usa."""
    com_extra = _gerar(
        session, "Meta", Nivel.GRUPO, {**GRUPO, "posicionamento": "Instagram Stories"}
    )
    assert "_IGST_" in com_extra

    sem_extra = _gerar(session, "Meta", Nivel.GRUPO, GRUPO)
    assert "_IGST_" not in sem_extra


def test_posicionamento_do_meta_nao_vale_para_o_google(session):
    """Abreviação com escopo de plataforma não deve vazar para outra."""
    with pytest.raises(TermoDesconhecido):
        _gerar(
            session,
            "Google",
            Nivel.GRUPO,
            {**GRUPO, "correspondencia": "Instagram Stories"},
        )


# --------------------------------------------------------------------------
# invariante dos três níveis (D-007)
# --------------------------------------------------------------------------

def test_plataforma_sem_template_devolve_none(session):
    """A API precisa distinguir 'sem template' de erro, para pedir cadastro."""
    assert carregar_template(session, uuid.uuid4(), Nivel.CAMPANHA) is None


def test_toda_plataforma_do_banco_tem_os_tres_niveis(session):
    """Invariante: nenhuma plataforma pode existir sem template e limite
    em todos os níveis. Vale para qualquer plataforma cadastrada, não só
    as do seed — é isso que faz o teste pegar uma inclusão incompleta."""
    plataformas = session.scalars(select(Plataforma)).all()
    assert plataformas, "banco sem plataformas: rode `python -m app.seed`"

    for plataforma in plataformas:
        assert niveis_faltando(session, plataforma) == {}, (
            f"plataforma '{plataforma.nome}' está incompleta"
        )
        for nivel in Nivel:
            assert carregar_template(session, plataforma.id, nivel) is not None
            assert carregar_limite(session, plataforma.id, nivel) > 0


def test_criar_plataforma_gera_os_tres_niveis(session):
    nova = criar_plataforma(session, nome="Pinterest", sigla="PIN", limites=300)

    assert niveis_faltando(session, nova) == {}
    for nivel in Nivel:
        assert carregar_template(session, nova.id, nivel) is not None
        assert carregar_limite(session, nova.id, nivel) == 300


def test_criar_plataforma_com_campos_extras(session):
    """Campos específicos da plataforma entram no template já na criação."""
    criar_plataforma(
        session,
        nome="Pinterest",
        sigla="PIN",
        limites=300,
        campos_extras={
            Nivel.GRUPO: [CampoSpec("posicionamento", "Posicionamento", opcional=True)]
        },
    )
    # 'Instagram Stories' tem escopo Meta, então aqui é preciso um termo
    # global — o extra existe no template, mas o dicionário não vaza. Em
    # branco, o extra vira o marcador 'NA' no fim.
    nome = _gerar(session, "Pinterest", Nivel.GRUPO, GRUPO)
    assert re.fullmatch(r"F_25-34_BOLSA_MODA_SUD_RJ_RMKT_NA_G\d{4,}", nome), nome


def test_criar_plataforma_aceita_limite_diferente_por_nivel(session):
    """O motivo de `limites_plataforma` existir: no Meta, nome de campanha
    e nome de anúncio têm limites diferentes."""
    nova = criar_plataforma(
        session,
        nome="Linkedin",
        sigla="LI",
        limites={Nivel.CAMPANHA: 100, Nivel.GRUPO: 200, Nivel.ANUNCIO: 255},
    )
    assert carregar_limite(session, nova.id, Nivel.CAMPANHA) == 100
    assert carregar_limite(session, nova.id, Nivel.GRUPO) == 200
    assert carregar_limite(session, nova.id, Nivel.ANUNCIO) == 255


def test_plataforma_nova_ja_gera_nome_em_todos_os_niveis(session):
    """Prova prática do invariante: a plataforma nasce utilizável."""
    criar_plataforma(session, nome="Pinterest", sigla="PIN", limites=300)

    esperados = {
        Nivel.CAMPANHA: (CAMPANHA, r"ALV27_ALF_PIN_INSTA_CV_AGO_NA_C\d{4,}"),
        Nivel.GRUPO: (GRUPO, r"F_25-34_BOLSA_MODA_SUD_RJ_RMKT_G\d{4,}"),
        Nivel.ANUNCIO: (ANUNCIO, r"VID_1200X600_CPC_FIVELA_15S_C_A\d{4,}"),
    }
    for nivel, (campos, padrao) in esperados.items():
        nome = _gerar(session, "Pinterest", nivel, campos)
        assert re.fullmatch(padrao, nome), nome


def test_niveis_faltando_detecta_plataforma_incompleta(session):
    """Uma plataforma criada por fora, sem passar por criar_plataforma."""
    quebrada = Plataforma(nome="Incompleta", sigla="INC", ativo=True)
    session.add(quebrada)
    session.flush()

    faltando = niveis_faltando(session, quebrada)
    assert set(faltando["templates"]) == set(Nivel)
    assert set(faltando["limites"]) == set(Nivel)
