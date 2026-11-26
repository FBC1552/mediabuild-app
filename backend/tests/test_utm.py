"""Testes do validador de UTM (D-012).

Puros: sem banco, sem HTTP. É a mesma disciplina do `test_motor.py` — as
regras que decidem se um custo de mídia vai ser atribuído à campanha certa
precisam ser exercitáveis uma a uma, rápido e sem infraestrutura.

Convenções destes testes:
- `codigos(...)` compara conjuntos de códigos, não texto de mensagem;
- o contexto padrão é uma taxonomia de **anúncio**, que é o caso com os
  três níveis presentes. Contextos parciais têm testes próprios, porque
  "regra que depende de nível ausente é pulada" é regra do D-012.
"""

import pytest

from app.utm import ContextoUtm, contem_match_id, validar_utm
from app.utm.mensagens import MENSAGENS

NOME_CAMPANHA = "ALV27_ALF_METAA_INSTA_CV_AGO_NA_C0001"
NOME_GRUPO = "F_25-34_BOLSA_MODA_SUD_RJ_RMKT_NA_G0001"
NOME_ANUNCIO = "VID_1200X600_CPC_FIVELA_15S_C_A0001"

URL_LIMPA = (
    "https://loja.com.br/promo"
    "?utm_source=metaa"
    "&utm_medium=cpc"
    "&utm_campaign=alv27_alf_metaa_insta_cv_ago_na_c0001"
    "&utm_id=c0001"
    "&utm_term=g0001"
    "&utm_content=vid_1200x600_cpc_fivela_15s_c_a0001"
)


@pytest.fixture
def contexto() -> ContextoUtm:
    """Taxonomia de anúncio no Meta, com os três níveis conhecidos."""
    return ContextoUtm(
        nivel="ANUNCIO",
        sigla_plataforma="METAA",
        nome_plataforma="Meta",
        match_id_campanha="C0001",
        match_id_grupo="G0001",
        match_id_anuncio="A0001",
        nomenclatura_campanha=NOME_CAMPANHA,
        nomenclatura_grupo=NOME_GRUPO,
        nomenclatura_anuncio=NOME_ANUNCIO,
        tipo_compra="CPC",
        canal="Instagram",
    )


def codigos(achados) -> set[str]:
    return {a.codigo for a in achados}


def trocar(url: str, de: str, para: str) -> str:
    assert de in url, f"o trecho '{de}' não está na URL do teste"
    return url.replace(de, para)


# --------------------------------------------------------------------------
# o caso que precisa passar limpo
# --------------------------------------------------------------------------

def test_url_correta_nao_tem_erro_nem_aviso(contexto):
    resultado = validar_utm(URL_LIMPA, contexto)
    assert resultado.valido
    assert resultado.erros == []
    assert resultado.avisos == []


def test_valido_e_derivado_dos_erros_e_ignora_avisos(contexto):
    """Aviso é o que funciona mas envelhece mal — não reprova."""
    resultado = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=MetaA"), contexto)
    assert codigos(resultado.avisos) == {"caixa_mista"}
    assert resultado.valido


def test_seguir_a_sugestao_do_app_limpa_o_laudo(contexto):
    """A sugestão vem em minúsculas justamente para isto: aplicá-la não
    pode deixar um aviso para trás."""
    sujo = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=Meta%20A"), contexto)
    assert sujo.erros

    limpo = validar_utm(sujo.url_sugerida, contexto)
    assert limpo.erros == []
    assert limpo.avisos == []


# --------------------------------------------------------------------------
# a URL em si
# --------------------------------------------------------------------------

def test_url_sem_esquema_e_erro_mas_o_laudo_continua(contexto):
    resultado = validar_utm(URL_LIMPA.removeprefix("https://"), contexto)
    assert "url_sem_esquema" in codigos(resultado.erros)
    # O resto foi conferido mesmo assim: o pedido é um laudo, não um
    # 'pare no primeiro erro'.
    assert resultado.parametros["utm_campaign"].endswith("c0001")
    assert codigos(resultado.erros) == {"url_sem_esquema"}


@pytest.mark.parametrize("url", ["", "   ", "https://", "https:// espaço no host/", "não é url"])
def test_url_impossivel_de_ler_e_url_invalida(url, contexto):
    resultado = validar_utm(url, contexto)
    assert "url_invalida" in codigos(resultado.erros)
    assert resultado.url_sugerida == ""


def test_http_puro_e_aviso(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "https://", "http://"), contexto)
    assert "sem_https" in codigos(resultado.avisos)
    assert resultado.valido
    # A sugestão sobe para https.
    assert resultado.url_sugerida.startswith("https://")


def test_query_dentro_da_ancora_e_erro(contexto):
    """Armadilha de SPA: com o '#' antes do '?', o navegador não envia a
    query e as UTMs somem — mas o laudo do resto continua valendo."""
    url = trocar(URL_LIMPA, "/promo?", "/promo#/pagina?")
    resultado = validar_utm(url, contexto)
    assert "query_dentro_da_ancora" in codigos(resultado.erros)
    assert resultado.parametros["utm_id"] == "c0001"
    assert "#" not in resultado.url_sugerida


def test_ancora_depois_da_query_com_utm_e_so_aviso(contexto):
    resultado = validar_utm(f"{URL_LIMPA}#utm_source=outro", contexto)
    assert codigos(resultado.avisos) == {"ancora_com_utm"}
    assert resultado.valido


def test_ancora_comum_depois_da_query_nao_reclama(contexto):
    assert validar_utm(f"{URL_LIMPA}#secao-precos", contexto).avisos == []


def test_macro_de_plataforma_e_aviso_e_nao_reprova_o_valor(contexto):
    url = trocar(URL_LIMPA, "utm_content=vid_1200x600_cpc_fivela_15s_c_a0001", "utm_content={{ad.name}}")
    resultado = validar_utm(url, contexto)
    assert "macro_na_url" in codigos(resultado.avisos)
    # O valor final só existe depois de a plataforma resolver: nada de
    # caixa_mista nem caractere inválido sobre '{{ad.name}}'.
    assert "caractere_invalido_no_valor" not in codigos(resultado.erros)


def test_sem_nenhum_parametro_utm(contexto):
    resultado = validar_utm("https://loja.com.br/promo?gclid=abc", contexto)
    assert codigos(resultado.erros) == {"sem_utm"}
    # Mesmo assim entrega a URL pronta — que é o que o analista precisa.
    assert "utm_campaign=" in resultado.url_sugerida
    assert "gclid=abc" in resultado.url_sugerida


# --------------------------------------------------------------------------
# parâmetros: nome, presença, forma
# --------------------------------------------------------------------------

def test_obrigatoria_ausente(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc&", ""), contexto)
    assert "utm_obrigatoria_ausente" in codigos(resultado.erros)
    assert [a.parametro for a in resultado.erros if a.codigo == "utm_obrigatoria_ausente"] == [
        "utm_medium"
    ]


def test_parametro_vazio(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium="), contexto)
    assert "utm_vazia" in codigos(resultado.erros)


def test_parametro_duplicado(contexto):
    resultado = validar_utm(f"{URL_LIMPA}&utm_source=outro", contexto)
    duplicado = next(a for a in resultado.erros if a.codigo == "parametro_duplicado")
    assert duplicado.parametro == "utm_source"
    assert "2 vezes" in duplicado.mensagem


@pytest.mark.parametrize(
    ("errado", "esperado"),
    [("utm_campaing", "utm_campaign"), ("utm_mediun", "utm_medium"), ("utmsource", "utm_source")],
)
def test_nome_a_um_erro_de_digitacao_e_erro(errado, esperado, contexto):
    """O GA4 ignora em silêncio, que é o pior desfecho possível."""
    resultado = validar_utm(f"https://loja.com.br/?{errado}=x", contexto)
    achado = next(a for a in resultado.erros if a.codigo == "utm_desconhecida")
    assert achado.esperado == esperado


def test_parametro_ga4_que_nao_conferimos_e_aviso(contexto):
    resultado = validar_utm(f"{URL_LIMPA}&utm_source_platform=manager", contexto)
    assert "parametro_utm_nao_conferido" in codigos(resultado.avisos)
    assert resultado.valido


def test_parametro_alheio_nao_e_conferido_nem_reclamado(contexto):
    resultado = validar_utm(f"{URL_LIMPA}&gclid=Cj0KC&fbclid=IwAR", contexto)
    assert resultado.valido
    assert resultado.avisos == []
    # E é preservado na sugestão: a URL sugerida não pode quebrar o link.
    assert "gclid=Cj0KC" in resultado.url_sugerida


# --------------------------------------------------------------------------
# forma do valor
# --------------------------------------------------------------------------

def test_espaco_literal_e_erro_fora_do_utm_term(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=meta ads"), contexto)
    assert "espaco_no_valor" in codigos(resultado.erros)


def test_espaco_em_utm_term_e_apenas_aviso(contexto):
    """Palavra-chave de Search tem espaço legitimamente."""
    resultado = validar_utm(trocar(URL_LIMPA, "utm_term=g0001", "utm_term=bolsa de couro"), contexto)
    assert "espaco_no_valor" in codigos(resultado.avisos)
    assert "espaco_no_valor" not in codigos(resultado.erros)


def test_espaco_escapado_e_erro_nos_quatro(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=meta%20ads"), contexto)
    assert "espaco_no_valor" in codigos(resultado.erros)


def test_espaco_escapado_em_utm_term_passa(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_term=g0001", "utm_term=bolsa%20g0001"), contexto
    )
    assert "espaco_no_valor" not in codigos(resultado.erros)


def test_acento_no_valor(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium=promoção"), contexto)
    achado = next(a for a in resultado.erros if a.codigo == "acento_no_valor")
    assert achado.esperado == "promocao"


def test_caractere_invalido_no_valor(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium=cpc|display"), contexto)
    achado = next(a for a in resultado.erros if a.codigo == "caractere_invalido_no_valor")
    assert achado.encontrado == "|"


def test_encoding_invalido(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium=cpc%zz"), contexto)
    assert "encoding_invalido" in codigos(resultado.erros)


def test_encoding_duplo_e_aviso(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_campaign=", "utm_campaign=black%252Dfriday%2D"), contexto
    )
    assert "encoding_duplo" in codigos(resultado.avisos)


def test_mais_lido_como_espaco_e_aviso(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_content=vid_1200x600", "utm_content=vid+1200x600"), contexto
    )
    assert "mais_e_espaco" in codigos(resultado.avisos)


def test_caixa_mista_e_aviso_e_nunca_erro(contexto):
    """O motor gera nome MAIÚSCULO: reprovar a própria saída do produto
    seria absurdo. A comparação de match ID é case-insensitive."""
    maiuscula = URL_LIMPA.replace("utm_campaign=alv27", "utm_campaign=ALV27").replace(
        "_insta_cv_ago_na_c0001", "_INSTA_CV_AGO_NA_C0001"
    )
    resultado = validar_utm(maiuscula, contexto)
    assert codigos(resultado.avisos) == {"caixa_mista"}
    assert resultado.valido


# --------------------------------------------------------------------------
# match ID — o coração do D-012
# --------------------------------------------------------------------------

def test_match_id_precisa_estar_delimitado():
    """`c0001` não pode casar dentro de `c00010`. Sem o lookaround, a URL
    de outra campanha passaria como se fosse desta."""
    assert contem_match_id("promo_c0001_bf", "C0001")
    assert contem_match_id("C0001", "c0001")
    assert not contem_match_id("promo_c00010_bf", "C0001")
    assert not contem_match_id("xc0001", "C0001")


def test_utm_campaign_com_match_id_de_outra_campanha_e_erro(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "_ago_na_c0001", "_ago_na_c0042"), contexto
    )
    achado = next(a for a in resultado.erros if a.codigo == "match_id_divergente")
    assert (achado.parametro, achado.encontrado, achado.esperado) == (
        "utm_campaign", "c0042", "c0001",
    )


def test_utm_campaign_vizinho_no_prefixo_nao_passa(contexto):
    """`c00010` contém `c0001` como texto; delimitado, não casa."""
    resultado = validar_utm(trocar(URL_LIMPA, "_ago_na_c0001", "_ago_na_c00010"), contexto)
    assert "match_id_divergente" in codigos(resultado.erros)


def test_utm_campaign_sem_nenhum_match_id_e_erro(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_campaign=alv27_alf_metaa_insta_cv_ago_na_c0001", "utm_campaign=black-friday"),
        contexto,
    )
    assert "match_id_ausente" in codigos(resultado.erros)


def test_nivel_trocado_e_erro(contexto):
    """`a0001` em utm_campaign: o dado do anúncio seria somado como campanha."""
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_campaign=alv27_alf_metaa_insta_cv_ago_na_c0001", "utm_campaign=a0001"),
        contexto,
    )
    achado = next(a for a in resultado.erros if a.codigo == "match_id_nivel_trocado")
    assert achado.encontrado == "a0001"
    assert "anúncio" in achado.mensagem and "campanha" in achado.mensagem


def test_campanha_no_utm_content_tambem_e_nivel_trocado(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_content=vid_1200x600_cpc_fivela_15s_c_a0001", "utm_content=c0001"),
        contexto,
    )
    assert "match_id_nivel_trocado" in codigos(resultado.erros)


def test_match_id_certo_com_rotulo_diferente_e_apenas_aviso(contexto):
    """Conter, não ser igual: o match ID é a chave, o nome é rótulo."""
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_campaign=alv27_alf_metaa_insta_cv_ago_na_c0001", "utm_campaign=black-friday-c0001"),
        contexto,
    )
    assert resultado.valido
    achado = next(a for a in resultado.avisos if a.codigo == "nomenclatura_divergente")
    assert achado.esperado == NOME_CAMPANHA.lower()


def test_utm_campaign_muito_longa_e_aviso(contexto):
    longa = "black-friday-" + "x" * 120 + "-c0001"
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_campaign=alv27_alf_metaa_insta_cv_ago_na_c0001", f"utm_campaign={longa}"),
        contexto,
    )
    assert "utm_campaign_longa" in codigos(resultado.avisos)


# --- utm_id ---------------------------------------------------------------

def test_utm_id_ausente_e_aviso_com_a_sugestao_pronta(contexto):
    """Sem utm_id o GA4 não junta o custo importado com a sessão."""
    resultado = validar_utm(trocar(URL_LIMPA, "&utm_id=c0001", ""), contexto)
    achado = next(a for a in resultado.avisos if a.codigo == "utm_id_ausente")
    assert achado.esperado == "c0001"
    assert "utm_id=c0001" in achado.mensagem
    assert resultado.sugestao["utm_id"] == "c0001"
    assert resultado.valido


def test_utm_id_de_outra_campanha_e_erro(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_id=c0001", "utm_id=c0042"), contexto)
    achado = next(a for a in resultado.erros if a.codigo == "utm_id_divergente")
    assert (achado.encontrado, achado.esperado) == ("c0042", "c0001")


# --- grupo: utm_term OU utm_content --------------------------------------

def test_grupo_pode_viajar_no_utm_content(contexto):
    """O slot do utm_term é disputado com a palavra-chave de Search."""
    url = URL_LIMPA.replace("utm_term=g0001", "utm_term={keyword}").replace(
        "utm_content=vid_1200x600_cpc_fivela_15s_c_a0001",
        "utm_content=g0001_vid_1200x600_cpc_fivela_15s_c_a0001",
    )
    resultado = validar_utm(url, contexto)
    assert "grupo_sem_rastreio" not in codigos(resultado.avisos)


def test_grupo_em_lugar_nenhum_e_aviso(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_term=g0001", "utm_term=bolsa-couro"), contexto)
    assert "grupo_sem_rastreio" in codigos(resultado.avisos)
    assert resultado.valido


def test_grupo_errado_e_erro(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_term=g0001", "utm_term=g0042"), contexto)
    achado = next(a for a in resultado.erros if a.codigo == "match_id_divergente")
    assert (achado.parametro, achado.encontrado) == ("utm_term", "g0042")


def test_palavra_chave_de_search_no_utm_term_passa_sem_reclamacao(contexto):
    """Macro de keyword ocupa o utm_term; o grupo vai no utm_content."""
    url = URL_LIMPA.replace("utm_term=g0001", "utm_term={keyword}").replace(
        "utm_content=vid_", "utm_content=g0001_vid_"
    )
    resultado = validar_utm(url, contexto)
    assert resultado.valido
    assert codigos(resultado.avisos) <= {"macro_na_url", "nomenclatura_divergente"}


def test_utm_content_ausente_com_anuncio_no_contexto_e_erro(contexto):
    resultado = validar_utm(
        trocar(URL_LIMPA, "&utm_content=vid_1200x600_cpc_fivela_15s_c_a0001", ""), contexto
    )
    achado = next(a for a in resultado.erros if a.codigo == "match_id_ausente")
    assert achado.parametro == "utm_content"


# --------------------------------------------------------------------------
# contexto parcial: regra sem dado é pulada, nunca reprovada
# --------------------------------------------------------------------------

def test_taxonomia_de_campanha_nao_cobra_anuncio_nem_grupo():
    contexto = ContextoUtm(
        nivel="CAMPANHA",
        sigla_plataforma="METAA",
        match_id_campanha="C0001",
        nomenclatura_campanha=NOME_CAMPANHA,
    )
    url = (
        "https://loja.com.br/?utm_source=metaa&utm_medium=cpc"
        "&utm_campaign=alv27_alf_metaa_insta_cv_ago_na_c0001&utm_id=c0001"
    )
    resultado = validar_utm(url, contexto)
    assert resultado.valido
    assert "grupo_sem_rastreio" not in codigos(resultado.avisos)
    assert "utm_term" not in resultado.sugestao


def test_contexto_vazio_ainda_confere_a_forma_da_url():
    """Sem contexto nenhum, as regras de forma continuam valendo — e
    nenhuma regra de match ID reprova por falta de dado nosso."""
    resultado = validar_utm("https://loja.com.br/?utm_source=Meta Ads", ContextoUtm())
    assert codigos(resultado.erros) == {"espaco_no_valor", "utm_obrigatoria_ausente"}
    assert not any(c.startswith("match_id") for c in codigos(resultado.erros))


def test_taxonomia_de_grupo_confere_o_grupo_e_ignora_o_anuncio():
    contexto = ContextoUtm(
        nivel="GRUPO",
        sigla_plataforma="METAA",
        match_id_campanha="C0001",
        match_id_grupo="G0001",
        nomenclatura_grupo=NOME_GRUPO,
    )
    url = (
        "https://loja.com.br/?utm_source=metaa&utm_medium=cpc"
        "&utm_campaign=c0001&utm_id=c0001&utm_term=g0042"
    )
    resultado = validar_utm(url, contexto)
    assert "match_id_divergente" in codigos(resultado.erros)
    # Nada sobre utm_content: não há anúncio no contexto.
    assert all(a.parametro != "utm_content" for a in resultado.erros)


# --------------------------------------------------------------------------
# vocabulário de source e medium
# --------------------------------------------------------------------------

def test_source_fora_do_vocabulario_cadastrado_e_erro(contexto):
    com_vocabulario = ContextoUtm(
        **{**contexto.__dict__, "vocabulario_source": ("facebook", "instagram")}
    )
    resultado = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=fb"), com_vocabulario)
    achado = next(a for a in resultado.erros if a.codigo == "utm_source_invalida")
    # Mesma saída dupla do D-005: escolha uma destas, ou cadastre a sua.
    assert "facebook, instagram" in achado.mensagem
    assert "cadastre 'fb'" in achado.mensagem


def test_source_dentro_do_vocabulario_passa(contexto):
    com_vocabulario = ContextoUtm(
        **{**contexto.__dict__, "vocabulario_source": ("facebook", "instagram")}
    )
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_source=metaa", "utm_source=instagram"), com_vocabulario
    )
    assert resultado.valido
    assert codigos(resultado.avisos) == set()


def test_sem_vocabulario_a_divergencia_de_source_e_so_aviso(contexto):
    """Não dá para tratar como autoridade um vocabulário que ninguém
    cadastrou."""
    resultado = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=facebook"), contexto)
    assert codigos(resultado.avisos) == {"utm_source_fora_da_convencao"}
    assert resultado.valido


def test_medium_fora_do_vocabulario_cadastrado_e_erro(contexto):
    com_vocabulario = ContextoUtm(**{**contexto.__dict__, "vocabulario_medium": ("cpc", "cpm")})
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium=paid_social"), com_vocabulario
    )
    assert "utm_medium_invalida" in codigos(resultado.erros)


def test_sem_vocabulario_o_medium_e_comparado_ao_tipo_de_compra(contexto):
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium=cpm"), contexto)
    achado = next(a for a in resultado.avisos if a.codigo == "utm_medium_fora_da_convencao")
    assert "CPC" in achado.mensagem
    assert resultado.valido


def test_sem_tipo_de_compra_no_contexto_o_medium_nao_e_cobrado(contexto):
    sem_tipo = ContextoUtm(**{**contexto.__dict__, "tipo_compra": None})
    resultado = validar_utm(trocar(URL_LIMPA, "utm_medium=cpc", "utm_medium=paid_social"), sem_tipo)
    assert "utm_medium_fora_da_convencao" not in codigos(resultado.avisos)


# --------------------------------------------------------------------------
# sugestão e URL sugerida
# --------------------------------------------------------------------------

def test_sugestao_vem_toda_em_minusculas(contexto):
    sugestao = validar_utm(URL_LIMPA, contexto).sugestao
    assert sugestao == {v.lower(): s.lower() for v, s in sugestao.items()}
    assert sugestao["utm_campaign"] == NOME_CAMPANHA.lower()
    assert sugestao["utm_content"] == NOME_ANUNCIO.lower()


def test_sugestao_usa_o_vocabulario_quando_ele_existe(contexto):
    com_vocabulario = ContextoUtm(
        **{**contexto.__dict__, "vocabulario_source": ("facebook", "instagram")}
    )
    resultado = validar_utm(trocar(URL_LIMPA, "utm_source=metaa", "utm_source=fb"), com_vocabulario)
    assert resultado.sugestao["utm_source"] in ("facebook", "instagram")


def test_url_sugerida_preserva_caminho_e_parametros_alheios(contexto):
    resultado = validar_utm(f"{URL_LIMPA}&gclid=abc123", contexto)
    assert resultado.url_sugerida.startswith("https://loja.com.br/promo?")
    assert "gclid=abc123" in resultado.url_sugerida
    # E as UTMs saem em ordem canônica.
    assert resultado.url_sugerida.index("utm_source=") < resultado.url_sugerida.index("utm_medium=")


def test_url_sugerida_mantem_ancora_legitima(contexto):
    resultado = validar_utm(f"{URL_LIMPA}#precos", contexto)
    assert resultado.url_sugerida.endswith("#precos")


def test_url_sem_query_alguma_ainda_recebe_sugestao(contexto):
    resultado = validar_utm("https://loja.com.br/promo", contexto)
    assert "sem_utm" in codigos(resultado.erros)
    assert resultado.url_sugerida.startswith("https://loja.com.br/promo?utm_source=")


def test_url_sem_query_e_sem_contexto_nao_inventa_sugestao():
    resultado = validar_utm("https://loja.com.br/", ContextoUtm())
    assert resultado.url_sugerida == ""
    assert resultado.sugestao == {}


def test_sugestao_nao_repete_o_grupo_quando_ele_ja_esta_no_conteudo(contexto):
    """Se a nomenclatura do anúncio já carrega o g, o utm_term fica livre
    para a palavra-chave."""
    com_grupo_no_nome = ContextoUtm(
        **{**contexto.__dict__, "nomenclatura_anuncio": f"G0001_{NOME_ANUNCIO}"}
    )
    resultado = validar_utm(URL_LIMPA, com_grupo_no_nome)
    assert "utm_term" not in resultado.sugestao
    assert "g0001" in resultado.sugestao["utm_content"]


def test_sugestao_de_conteudo_cai_no_match_id_sem_nomenclatura(contexto):
    """Anúncio existe mas nunca teve nome gerado: sugere o match ID puro,
    que é o mínimo que faz o cruzamento funcionar."""
    sem_nome = ContextoUtm(**{**contexto.__dict__, "nomenclatura_anuncio": None})
    assert validar_utm(URL_LIMPA, sem_nome).sugestao["utm_content"] == "a0001"


def test_utm_content_vazio_reporta_uma_coisa_so(contexto):
    """Vazio já é `utm_vazia`; cobrar o match ID em cima seria repetir a
    mesma queixa com outro nome."""
    resultado = validar_utm(
        trocar(URL_LIMPA, "utm_content=vid_1200x600_cpc_fivela_15s_c_a0001", "utm_content="),
        contexto,
    )
    assert "utm_vazia" in codigos(resultado.erros)
    assert "match_id_ausente" not in codigos(resultado.erros)


def test_parametro_sem_nome_e_ignorado(contexto):
    """'?=x' não é parâmetro; ignorar é melhor que inventar um achado."""
    resultado = validar_utm(URL_LIMPA.replace("?utm_source", "?=x&utm_source"), contexto)
    assert resultado.valido
    assert "" not in resultado.parametros


def test_url_que_nem_o_parser_do_python_le(contexto):
    """IPv6 malformado levanta ValueError no `urlsplit` — vira laudo, não 500."""
    resultado = validar_utm("https://[::1oops/?utm_source=metaa", contexto)
    assert "url_invalida" in codigos(resultado.erros)


# --------------------------------------------------------------------------
# contrato do laudo
# --------------------------------------------------------------------------

def test_todo_achado_tem_codigo_registrado_em_mensagens(contexto):
    """Rede de segurança: um código novo sem texto em pt-BR quebraria a
    tela sem quebrar teste nenhum."""
    urls = [
        URL_LIMPA,
        "loja.com.br/?utm_source=Meta Ads&utm_medium=cpc%zz&utm_campaign=a0001&utm_term=g0042",
        "http://loja.com.br/#/x?utm_source=metaa&utm_campaing=x&utm_source_platform=y",
        "https://loja.com.br/?utm_source=metaa&utm_source=outro&utm_medium=&utm_campaign=x%252Dy+z",
    ]
    for url in urls:
        resultado = validar_utm(url, contexto)
        for achado in resultado.erros + resultado.avisos:
            assert achado.codigo in MENSAGENS, achado.codigo
            assert achado.mensagem and "{" not in achado.mensagem


def test_json_do_laudo_tem_as_seis_chaves_do_contrato(contexto):
    corpo = validar_utm(URL_LIMPA, contexto).para_json()
    assert set(corpo) == {"valido", "erros", "avisos", "parametros", "sugestao", "url_sugerida"}

    sujo = validar_utm("loja.com.br/?utm_source=Meta Ads", contexto).para_json()
    for item in sujo["erros"] + sujo["avisos"]:
        assert set(item) == {"codigo", "parametro", "mensagem", "encontrado", "esperado"}
