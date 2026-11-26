"""Testes do motor de taxonomia.

Sem banco: o motor é puro. Um bug aqui vira nome errado em campanha real,
então a cobertura é deliberadamente exaustiva.
"""

import pytest

from app.taxonomia import (
    CampoAusente,
    CampoLongoDemais,
    Dicionario,
    LimiteExcedido,
    NomeInvalido,
    ParteResolvida,
    Template,
    TemplateInvalido,
    TermoDesconhecido,
    TokenCampo,
    TokenLiteral,
    TokenMatchId,
    gerar_detalhado,
    gerar_nomenclatura,
    normalizar,
    parse_tokens,
    remover_acentos,
    resolver_token,
)

DICIONARIO = Dicionario(
    [
        ("objetivo", "Conversão", "CV"),
        ("objetivo", "Tráfego", "TRF"),
        ("objetivo", "Geração de Leads", "LEAD"),
        ("publico", "Remarketing", "RMKT"),
        ("publico", "Lookalike", "LAL"),
        ("formato", "Stories", "ST"),
    ]
)

TEMPLATE = Template(
    separador="_",
    tokens=(
        TokenLiteral("FB"),
        TokenCampo("objetivo"),
        TokenCampo("publico"),
        TokenMatchId(),
    ),
)


# --------------------------------------------------------------------------
# normalização
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Conversão", "Conversao"),
        ("Tráfego", "Trafego"),
        ("Promoção", "Promocao"),
        ("ação", "acao"),
        ("Ünïcödé", "Unicode"),
        ("sem acento", "sem acento"),
        ("", ""),
    ],
)
def test_remover_acentos(entrada, esperado):
    assert remover_acentos(entrada) == esperado


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Conversão", "CONVERSAO"),
        ("Black Friday", "BLACK_FRIDAY"),
        ("  espaços   múltiplos  ", "ESPACOS_MULTIPLOS"),
        ("já-com-hifen", "JA-COM-HIFEN"),
        ("MiXeD", "MIXED"),
    ],
)
def test_normalizar(entrada, esperado):
    assert normalizar(entrada, "_") == esperado


def test_normalizar_respeita_o_separador_configurado():
    assert normalizar("Black Friday", "-") == "BLACK-FRIDAY"


# --------------------------------------------------------------------------
# caminho feliz
# --------------------------------------------------------------------------

def test_gera_nome_completo():
    nome = gerar_nomenclatura(
        TEMPLATE,
        {"objetivo": "Conversão", "publico": "Remarketing"},
        DICIONARIO,
        "C0001",
    )
    assert nome == "FB_CV_RMKT_C0001"


def test_separador_hifen():
    template = Template(
        separador="-",
        tokens=(TokenLiteral("GO"), TokenCampo("objetivo"), TokenMatchId()),
    )
    nome = gerar_nomenclatura(template, {"objetivo": "Tráfego"}, DICIONARIO, "C0009")
    assert nome == "GO-TRF-C0009"


def test_busca_no_dicionario_ignora_acento_e_caixa():
    """O analista não deveria precisar acertar a grafia exata do cadastro."""
    for variacao in ("Conversão", "conversao", "CONVERSÃO", "  Conversao  "):
        nome = gerar_nomenclatura(
            TEMPLATE, {"objetivo": variacao, "publico": "Lookalike"}, DICIONARIO, "C0002"
        )
        assert nome == "FB_CV_LAL_C0002"


def test_abreviacao_com_espaco_usa_o_separador():
    template = Template(separador="_", tokens=(TokenCampo("objetivo"), TokenMatchId()))
    dicionario = Dicionario([("objetivo", "Black Friday", "Black Friday")])
    assert gerar_nomenclatura(template, {"objetivo": "Black Friday"}, dicionario, "C1") == (
        "BLACK_FRIDAY_C1"
    )


def test_campo_livre_dispensa_o_dicionario():
    """D-005, exceção: `abreviar=False` para textos sem De → Para."""
    template = Template(
        separador="_",
        tokens=(TokenLiteral("FB"), TokenCampo("produto", abreviar=False), TokenMatchId()),
    )
    nome = gerar_nomenclatura(template, {"produto": "Tênis Corrida"}, DICIONARIO, "C0003")
    assert nome == "FB_TENIS_CORRIDA_C0003"


# --------------------------------------------------------------------------
# D-005 — termo fora do dicionário é erro
# --------------------------------------------------------------------------

def test_termo_desconhecido_levanta_erro():
    with pytest.raises(TermoDesconhecido) as exc:
        gerar_nomenclatura(
            TEMPLATE,
            {"objetivo": "Awareness", "publico": "Remarketing"},
            DICIONARIO,
            "C0004",
        )
    assert exc.value.termo == "Awareness"
    assert exc.value.categoria == "objetivo"


def test_erro_de_termo_lista_as_opcoes_cadastradas():
    """A mensagem precisa ser acionável: cadastrar ou escolher uma existente."""
    with pytest.raises(TermoDesconhecido) as exc:
        gerar_nomenclatura(
            TEMPLATE, {"objetivo": "Awareness", "publico": "Remarketing"}, DICIONARIO, "C1"
        )
    assert exc.value.opcoes == ["Conversão", "Geração de Leads", "Tráfego"]
    mensagem = str(exc.value)
    assert "Conversão" in mensagem
    assert "dicionário" in mensagem


def test_erro_de_termo_quando_a_categoria_esta_vazia():
    template = Template(separador="_", tokens=(TokenCampo("inexistente"), TokenMatchId()))
    with pytest.raises(TermoDesconhecido) as exc:
        gerar_nomenclatura(template, {"inexistente": "X"}, DICIONARIO, "C1")
    assert exc.value.opcoes == []
    assert "Não há nenhum termo cadastrado" in str(exc.value)


def test_nunca_deixa_passar_o_termo_normalizado():
    """A regressão mais cara possível: 'CONVERSAO' no lugar de 'CV'."""
    with pytest.raises(TermoDesconhecido):
        gerar_nomenclatura(
            TEMPLATE, {"objetivo": "Alcance", "publico": "Remarketing"}, DICIONARIO, "C1"
        )


# --------------------------------------------------------------------------
# campos ausentes
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [None, "", "   "])
def test_campo_vazio_ou_ausente(valor):
    campos = {"objetivo": "Conversão", "publico": valor}
    if valor is None:
        campos.pop("publico")
    with pytest.raises(CampoAusente) as exc:
        gerar_nomenclatura(TEMPLATE, campos, DICIONARIO, "C0005")
    assert exc.value.chave == "publico"


# --------------------------------------------------------------------------
# validação do nome final
# --------------------------------------------------------------------------

def test_caractere_especial_e_rejeitado():
    template = Template(
        separador="_", tokens=(TokenCampo("produto", abreviar=False), TokenMatchId())
    )
    with pytest.raises(NomeInvalido) as exc:
        gerar_nomenclatura(template, {"produto": "Promo@100%"}, DICIONARIO, "C1")
    assert "@" in exc.value.invalidos
    assert "%" in exc.value.invalidos


def test_limite_de_caracteres_excedido():
    with pytest.raises(LimiteExcedido) as exc:
        gerar_nomenclatura(
            TEMPLATE,
            {"objetivo": "Conversão", "publico": "Remarketing"},
            DICIONARIO,
            "C0001",
            limite_caracteres=10,
        )
    assert exc.value.limite == 10
    assert exc.value.tamanho == len("FB_CV_RMKT_C0001")


def test_nome_exatamente_no_limite_passa():
    nome = gerar_nomenclatura(
        TEMPLATE,
        {"objetivo": "Conversão", "publico": "Remarketing"},
        DICIONARIO,
        "C0001",
        limite_caracteres=16,
    )
    assert len(nome) == 16


def test_sem_limite_nao_valida_tamanho():
    template = Template(separador="_", tokens=(TokenCampo("produto", abreviar=False),))
    nome = gerar_nomenclatura(template, {"produto": "A" * 500}, DICIONARIO, "C1")
    assert len(nome) == 500


# --------------------------------------------------------------------------
# templates
# --------------------------------------------------------------------------

def test_parse_tokens_do_formato_jsonb():
    tokens = parse_tokens(
        [
            {"tipo": "literal", "valor": "FB"},
            {"tipo": "campo", "chave": "objetivo"},
            {"tipo": "campo", "chave": "produto", "abreviar": False},
            {"tipo": "match_id"},
        ]
    )
    assert tokens == (
        TokenLiteral("FB"),
        TokenCampo("objetivo", abreviar=True),
        TokenCampo("produto", abreviar=False),
        TokenMatchId(),
    )


@pytest.mark.parametrize(
    "brutos",
    [
        [],
        "não é lista",
        [{"valor": "FB"}],
        [{"tipo": "desconhecido"}],
        [{"tipo": "literal"}],
        [{"tipo": "campo"}],
    ],
)
def test_template_invalido(brutos):
    with pytest.raises(TemplateInvalido):
        parse_tokens(brutos)


def test_separador_precisa_ter_um_caractere():
    with pytest.raises(TemplateInvalido):
        Template(separador="__", tokens=(TokenLiteral("FB"),))


def test_template_de_registro():
    template = Template.de_registro(
        separador="_", tokens=[{"tipo": "literal", "valor": "TT"}, {"tipo": "match_id"}], versao=2
    )
    assert template.versao == 2
    assert gerar_nomenclatura(template, {}, DICIONARIO, "C0007") == "TT_C0007"


# --------------------------------------------------------------------------
# determinismo
# --------------------------------------------------------------------------

def test_mesma_entrada_gera_sempre_o_mesmo_nome():
    campos = {"objetivo": "Conversão", "publico": "Remarketing"}
    nomes = {gerar_nomenclatura(TEMPLATE, campos, DICIONARIO, "C0001") for _ in range(20)}
    assert len(nomes) == 1


# --------------------------------------------------------------------------
# tipos de campo: drop list, campo livre e opcional
# --------------------------------------------------------------------------

CAMPO_LIVRE = Template(
    separador="_",
    tokens=(
        TokenCampo("nome_campanha", abreviar=False, max_caracteres=5),
        TokenCampo("objetivo"),
        TokenCampo("extra", opcional=True),
        TokenMatchId(),
    ),
)


def test_campo_livre_dentro_do_limite():
    nome = gerar_nomenclatura(
        CAMPO_LIVRE, {"nome_campanha": "ALV27", "objetivo": "Conversão"}, DICIONARIO, "C0001"
    )
    assert nome == "ALV27_CV_NA_C0001"


def test_campo_livre_acima_do_limite():
    with pytest.raises(CampoLongoDemais) as erro:
        gerar_nomenclatura(
            CAMPO_LIVRE,
            {"nome_campanha": "ALV27X", "objetivo": "Conversão"},
            DICIONARIO,
            "C0001",
        )
    assert erro.value.chave == "nome_campanha"
    assert erro.value.tamanho == 6
    assert erro.value.maximo == 5


def test_campo_livre_ignora_espacos_das_bordas_ao_medir():
    """'  ALV27  ' tem 9 caracteres mas 5 de conteúdo — medir o bruto
    rejeitaria um valor que o analista digitou certo."""
    nome = gerar_nomenclatura(
        CAMPO_LIVRE, {"nome_campanha": "  ALV27  ", "objetivo": "Conversão"}, DICIONARIO, "C0001"
    )
    assert nome == "ALV27_CV_NA_C0001"


def test_campo_opcional_ausente_vira_marcador_sem_separador_duplicado():
    nome = gerar_nomenclatura(
        CAMPO_LIVRE, {"nome_campanha": "ABC", "objetivo": "Conversão"}, DICIONARIO, "C0001"
    )
    assert nome == "ABC_CV_NA_C0001"
    assert "__" not in nome


def test_campo_opcional_preenchido_entra_no_nome():
    template = Template(
        separador="_",
        tokens=(TokenCampo("objetivo"), TokenCampo("formato", opcional=True), TokenMatchId()),
    )
    nome = gerar_nomenclatura(
        template, {"objetivo": "Conversão", "formato": "Stories"}, DICIONARIO, "C0001"
    )
    assert nome == "CV_ST_C0001"


def test_categoria_permite_dois_campos_com_o_mesmo_vocabulario():
    template = Template(
        separador="_",
        tokens=(
            TokenCampo("objetivo_1", categoria="objetivo"),
            TokenCampo("objetivo_2", categoria="objetivo"),
            TokenMatchId(),
        ),
    )
    nome = gerar_nomenclatura(
        template, {"objetivo_1": "Conversão", "objetivo_2": "Tráfego"}, DICIONARIO, "C0001"
    )
    assert nome == "CV_TRF_C0001"


def test_termo_desconhecido_aponta_a_chave_e_a_categoria():
    """A UI destaca a chave ('objetivo_2'); as opções vêm da categoria."""
    template = Template(
        separador="_", tokens=(TokenCampo("objetivo_2", categoria="objetivo"), TokenMatchId())
    )
    with pytest.raises(TermoDesconhecido) as erro:
        gerar_nomenclatura(template, {"objetivo_2": "Inexistente"}, DICIONARIO, "C0001")

    assert erro.value.chave == "objetivo_2"
    assert erro.value.categoria == "objetivo"
    assert "Conversão" in erro.value.opcoes


@pytest.mark.parametrize("maximo", ["abc", None if False else "", 0, -3])
def test_max_caracteres_invalido_no_template(maximo):
    with pytest.raises(TemplateInvalido):
        parse_tokens([{"tipo": "campo", "chave": "x", "max_caracteres": maximo}])


def test_parse_tokens_le_os_atributos_novos():
    (token,) = parse_tokens(
        [
            {
                "tipo": "campo",
                "chave": "nome_criativo",
                "rotulo": "Nome do criativo",
                "abreviar": False,
                "max_caracteres": 10,
                "opcional": True,
                "categoria": "criativo",
            }
        ]
    )
    assert token.rotulo == "Nome do criativo"
    assert token.abreviar is False
    assert token.max_caracteres == 10
    assert token.opcional is True
    assert token.categoria_dicionario == "criativo"


def test_categoria_padrao_e_a_propria_chave():
    assert TokenCampo("objetivo").categoria_dicionario == "objetivo"


# --------------------------------------------------------------------------
# marcador de ausência — quantidade fixa de partes por nível
# --------------------------------------------------------------------------

COM_OPCIONAL = Template(
    separador="_",
    tokens=(
        TokenCampo("objetivo"),
        TokenCampo("formato", opcional=True),
        TokenCampo("publico"),
        TokenMatchId(),
    ),
)


def _partes(nome: str) -> list[str]:
    return nome.split("_")


def test_opcional_vazio_e_preenchido_dao_a_mesma_quantidade_de_partes():
    """A razão de existir do marcador: sem ele, o nome sem o opcional tinha
    uma parte a menos e as colunas da planilha de performance deslocavam."""
    preenchido = gerar_nomenclatura(
        COM_OPCIONAL,
        {"objetivo": "Conversão", "formato": "Stories", "publico": "Remarketing"},
        DICIONARIO,
        "C0001",
    )
    vazio = gerar_nomenclatura(
        COM_OPCIONAL,
        {"objetivo": "Conversão", "formato": "", "publico": "Remarketing"},
        DICIONARIO,
        "C0002",
    )
    ausente = gerar_nomenclatura(
        COM_OPCIONAL,
        {"objetivo": "Conversão", "publico": "Remarketing"},
        DICIONARIO,
        "C0003",
    )

    assert preenchido == "CV_ST_RMKT_C0001"
    assert vazio == "CV_NA_RMKT_C0002"
    assert ausente == "CV_NA_RMKT_C0003"
    assert len(_partes(preenchido)) == len(_partes(vazio)) == len(_partes(ausente)) == 4


def test_marcador_ocupa_sempre_a_mesma_posicao():
    """Deslocar a coluna é o mesmo defeito que sumir com ela."""
    vazio = gerar_nomenclatura(
        COM_OPCIONAL,
        {"objetivo": "Conversão", "publico": "Remarketing"},
        DICIONARIO,
        "C0001",
    )
    assert _partes(vazio)[1] == "NA"


def test_marcador_vem_do_template_e_nao_do_codigo():
    """Trocar o marcador precisa ser UPDATE, não deploy."""
    template = Template(
        separador="_",
        tokens=(TokenCampo("objetivo"), TokenCampo("formato", opcional=True), TokenMatchId()),
        marcador_ausencia="SEM",
    )
    assert gerar_nomenclatura(template, {"objetivo": "Conversão"}, DICIONARIO, "C1") == (
        "CV_SEM_C1"
    )


def test_marcador_vazio_mantem_o_comportamento_antigo():
    """As versões de template anteriores à regra guardam '' e precisam
    continuar gerando o nome sem a parte (D-004)."""
    template = Template(
        separador="_",
        tokens=(TokenCampo("objetivo"), TokenCampo("formato", opcional=True), TokenMatchId()),
        marcador_ausencia="",
    )
    nome = gerar_nomenclatura(template, {"objetivo": "Conversão"}, DICIONARIO, "C1")
    assert nome == "CV_C1"
    assert "__" not in nome


def test_marcador_e_normalizado_como_qualquer_outra_parte():
    template = Template(
        separador="_",
        tokens=(TokenCampo("formato", opcional=True), TokenMatchId()),
        marcador_ausencia="não",
    )
    assert gerar_nomenclatura(template, {}, DICIONARIO, "C1") == "NAO_C1"


def test_marcador_nao_pode_conter_o_separador():
    """Conteria uma parte extra e desfaria a contagem fixa que ele garante."""
    with pytest.raises(TemplateInvalido):
        Template(
            separador="_",
            tokens=(TokenCampo("objetivo"), TokenMatchId()),
            marcador_ausencia="N_A",
        )


def test_de_registro_le_o_marcador_da_coluna():
    template = Template.de_registro(
        separador="_",
        tokens=[{"tipo": "campo", "chave": "x", "opcional": True}, {"tipo": "match_id"}],
        versao=3,
        marcador_ausencia="ND",
    )
    assert template.marcador_ausencia == "ND"
    assert gerar_nomenclatura(template, {}, DICIONARIO, "C1") == "ND_C1"


def test_de_registro_trata_marcador_nulo_como_vazio():
    template = Template.de_registro(
        separador="_",
        tokens=[{"tipo": "campo", "chave": "x", "opcional": True}, {"tipo": "match_id"}],
        marcador_ausencia=None,
    )
    assert template.marcador_ausencia == ""


# --------------------------------------------------------------------------
# rastro por campo — o que vai para `taxonomias_geradas.campos_gerados`
# --------------------------------------------------------------------------

def test_gerar_detalhado_devolve_bruto_e_final_por_campo():
    resultado = gerar_detalhado(
        TEMPLATE,
        {"objetivo": "Conversão", "publico": "Remarketing"},
        DICIONARIO,
        "C0001",
    )
    assert resultado.nomenclatura == "FB_CV_RMKT_C0001"
    assert resultado.campos["objetivo"].bruto == "Conversão"
    assert resultado.campos["objetivo"].final == "CV"
    assert resultado.campos["publico"].final == "RMKT"


def test_rastro_ignora_literal_e_match_id():
    """Sigla e match ID entram no nome mas não são campos do formulário."""
    resultado = gerar_detalhado(TEMPLATE, {"objetivo": "Conversão", "publico": "Lookalike"},
                                DICIONARIO, "C0001")
    assert set(resultado.campos) == {"objetivo", "publico"}


def test_rastro_guarda_a_ordem_do_token():
    """JSONB não preserva a ordem das chaves; sem `ordem` a exportação não
    conseguiria reconstruir a sequência do nome."""
    resultado = gerar_detalhado(
        TEMPLATE, {"objetivo": "Conversão", "publico": "Remarketing"}, DICIONARIO, "C1"
    )
    assert resultado.campos["objetivo"].ordem < resultado.campos["publico"].ordem


def test_rastro_do_opcional_vazio_tem_marcador_no_final_e_bruto_nulo():
    resultado = gerar_detalhado(
        COM_OPCIONAL, {"objetivo": "Conversão", "publico": "Lookalike"}, DICIONARIO, "C1"
    )
    assert resultado.campos["formato"].bruto is None
    assert resultado.campos["formato"].final == "NA"


def test_rastro_do_campo_livre_guarda_o_texto_digitado():
    template = Template(
        separador="_",
        tokens=(TokenCampo("produto", abreviar=False, max_caracteres=20), TokenMatchId()),
    )
    resultado = gerar_detalhado(template, {"produto": "Tênis Corrida"}, DICIONARIO, "C1")
    assert resultado.campos["produto"].bruto == "Tênis Corrida"
    assert resultado.campos["produto"].final == "TENIS_CORRIDA"


def test_campos_para_json_tem_a_forma_persistida():
    resultado = gerar_detalhado(
        TEMPLATE, {"objetivo": "Conversão", "publico": "Remarketing"}, DICIONARIO, "C1"
    )
    assert resultado.campos_para_json()["objetivo"] == {
        "bruto": "Conversão",
        "final": "CV",
        "ordem": 1,
    }


def test_gerar_nomenclatura_e_o_mesmo_nome_de_gerar_detalhado():
    campos = {"objetivo": "Conversão", "publico": "Remarketing"}
    assert gerar_nomenclatura(TEMPLATE, campos, DICIONARIO, "C1") == (
        gerar_detalhado(TEMPLATE, campos, DICIONARIO, "C1").nomenclatura
    )


def test_resolver_token_devolve_o_texto_e_a_origem():
    parte = resolver_token(
        TokenCampo("objetivo"), {"objetivo": "Tráfego"}, DICIONARIO, "C1", "_"
    )
    assert parte == ParteResolvida(texto="TRF", chave="objetivo", bruto="Tráfego")

    literal = resolver_token(TokenLiteral("FB"), {}, DICIONARIO, "C1", "_")
    assert literal.texto == "FB" and literal.chave is None
