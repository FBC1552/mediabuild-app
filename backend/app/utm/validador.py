"""Validador de UTM (D-012) — o app **confere**, não gera.

Função pura, na mesma disciplina do motor de taxonomia: recebe a URL e um
contexto já carregado, devolve o laudo. Sem SQLAlchemy, sem HTTP. É o que
torna as 31 regras testáveis uma a uma e permitirá conferir uma planilha
inteira de URLs depois, sem passar pela API.

O item mais caro que este laudo pega é a URL copiada de outra campanha: o
link funciona, o site abre, e o custo é atribuído no lugar errado por
semanas. Por isso match ID divergente é **erro**, e não aviso.

Duas regras de fundo atravessam o módulo:

- **Conter, não ser igual.** O match ID é a chave do cruzamento; o nome é
  só rótulo. Exigir a nomenclatura inteira reprovaria quem encurta o
  rótulo, sem ganhar nada no cruzamento — a igualdade vira aviso.
- **Regra que depende de nível ausente do contexto é pulada.** Uma
  taxonomia de campanha não sabe nada de anúncio, e o histórico sobrevive
  à entidade (D-004/D-009): faltar dado nosso não pode virar reprovação do
  analista.
"""

import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlencode, urlsplit

from app.taxonomia.normalizacao import remover_acentos
from app.utm.mensagens import ESTE, OUTRO, texto
from app.utm.tipos import Achado, ContextoUtm, ResultadoUtm

# Os seis que o MediaBuild confere. Os demais parâmetros oficiais do GA4
# são reconhecidos, mas o conteúdo não é conferido — dizer isso em voz alta
# é melhor que silêncio, que o analista leria como aprovação.
CONFERIDOS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id")
OBRIGATORIOS = ("utm_source", "utm_medium", "utm_campaign")
OUTROS_GA4 = ("utm_source_platform", "utm_creative_format", "utm_marketing_tactic")

# %20 é erro nestes quatro. Em utm_term não: palavra-chave de Search tem
# espaço legitimamente.
SEM_ESPACO = ("utm_source", "utm_medium", "utm_campaign", "utm_content")

# Nada quebra acima disso; só fica ilegível no relatório.
LIMITE_CAMPAIGN_LONGA = 100

# Distância de edição máxima para tratar um nome como erro de digitação de
# um dos conferidos. 'utm_campaing' e 'utm_mediun' são o caso real: o GA4
# os ignora em silêncio, que é o pior desfecho possível.
DISTANCIA_MAXIMA = 2

ORDEM_SUGESTAO = ("utm_source", "utm_medium", "utm_campaign", "utm_id", "utm_term", "utm_content")

NIVEL_POR_LETRA = {"c": "campanha", "g": "grupo", "a": "anúncio"}

_ESQUEMA = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_HOSPEDEIRO = re.compile(r"^[a-z0-9_][a-z0-9._\-]*$")
# {lpurl}, {{campaign.name}}, %%DEST_URL%%
_MACRO = re.compile(r"\{\{?[^{}]+\}?\}|%%[^%]+%%")
_ESCAPE_INVALIDO = re.compile(r"%(?![0-9A-Fa-f]{2})")
_ESCAPE_DUPLO = re.compile(r"%25[0-9A-Fa-f]{2}")
# Match ID em qualquer posição do valor, já em minúsculas. O lookaround é o
# que impede 'c0001' de casar dentro de 'c00010'.
_MATCH_ID = re.compile(r"(?<![a-z0-9])([cga])(\d{4,})(?![a-z0-9])")
_PERMITIDO = re.compile(r"[A-Za-z0-9._~+\-]")


# --------------------------------------------------------------------------
# apoio
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Par:
    """Um parâmetro da query, nas duas formas que interessam.

    `bruto` é como está escrito na URL (é nele que se enxerga `%20`, `+` e
    escape inválido); `valor` é o texto decodificado, que é o que o GA4 vai
    de fato registrar.
    """

    nome: str
    bruto: str
    valor: str


class _Laudo:
    """Acumulador de erros e avisos. Existe para que cada regra seja uma
    linha legível, em vez de manipulação de duas listas."""

    def __init__(self) -> None:
        self.erros: list[Achado] = []
        self.avisos: list[Achado] = []

    def erro(self, codigo: str, parametro: str | None = None, **dados: object) -> None:
        self.erros.append(self._achado(codigo, parametro, dados))

    def aviso(self, codigo: str, parametro: str | None = None, **dados: object) -> None:
        self.avisos.append(self._achado(codigo, parametro, dados))

    @staticmethod
    def _achado(codigo: str, parametro: str | None, dados: dict) -> Achado:
        encontrado = dados.pop("_encontrado", None)
        esperado = dados.pop("_esperado", None)
        return Achado(
            codigo=codigo,
            parametro=parametro,
            mensagem=texto(codigo, **dados),
            encontrado=None if encontrado is None else str(encontrado),
            esperado=None if esperado is None else str(esperado),
        )


def canonico(valor: str) -> str:
    """Forma usada em toda comparação: sem acento, minúscula, sem bordas.

    Comparar assim é o que garante a promessa do D-012 de que o match ID
    **nunca** falha por caixa — maiúscula é aviso, não erro, porque o motor
    gera nome maiúsculo e reprovar a própria saída do produto seria absurdo.
    """
    return remover_acentos(valor).strip().lower()


def contem_match_id(valor: str, match_id: str) -> bool:
    """O match ID aparece delimitado dentro do valor?"""
    alvo = re.escape(canonico(match_id))
    return re.search(rf"(?<![a-z0-9]){alvo}(?![a-z0-9])", canonico(valor)) is not None


def match_ids_no_valor(valor: str) -> list[str]:
    """Todos os match IDs reconhecíveis no valor, na ordem em que aparecem."""
    return [f"{letra}{numero}" for letra, numero in _MATCH_ID.findall(canonico(valor))]


def _distancia(a: str, b: str) -> int:
    """Levenshtein. Pequeno o bastante para não valer uma dependência."""
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i]
        for j, cb in enumerate(b, start=1):
            atual.append(
                min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb))
            )
        anterior = atual
    return anterior[-1]


def _mais_parecido(nome: str) -> str | None:
    candidatos = sorted((_distancia(nome, c), c) for c in CONFERIDOS)
    distancia, melhor = candidatos[0]
    return melhor if distancia <= DISTANCIA_MAXIMA else None


def _para_valor_de_url(texto_bruto: str) -> str:
    """Forma que a sugestão usa: canônica, com espaço virando '-'."""
    return re.sub(r"\s+", "-", canonico(texto_bruto))


def _decodificar(bruto: str) -> str:
    # '+' vira espaço, que é justamente o que o GA4 faz — e o motivo do
    # aviso `mais_e_espaco`.
    return unquote(bruto.replace("+", " "))


# --------------------------------------------------------------------------
# entrada: a URL em si
# --------------------------------------------------------------------------

def _conferir_url(bruta: str, laudo: _Laudo):
    """Analisa a URL e devolve (partes, query) ou None se não dá para seguir."""
    completa = bruta
    if not _ESQUEMA.match(bruta):
        laudo.erro("url_sem_esquema", None, _encontrado=bruta)
        # Segue analisando mesmo assim: o pedido é um laudo, e parar no
        # primeiro erro devolveria uma linha onde cabem quinze.
        completa = f"https://{bruta}"

    try:
        partes = urlsplit(completa)
    except ValueError:
        laudo.erro("url_invalida", None, _encontrado=bruta)
        return None

    hospedeiro = partes.hostname
    if not hospedeiro or not _HOSPEDEIRO.match(hospedeiro):
        laudo.erro("url_invalida", None, _encontrado=bruta)
        return None

    if partes.scheme == "http":
        laudo.aviso("sem_https", None, _encontrado=bruta)

    for macro in dict.fromkeys(_MACRO.findall(completa)):
        laudo.aviso("macro_na_url", None, m=macro, _encontrado=macro)

    consulta = partes.query
    fragmento = partes.fragment
    hash_antes_da_query = "#" in completa and (
        "?" not in completa or completa.index("#") < completa.index("?")
    )

    if "utm_" in canonico(fragmento):
        if hash_antes_da_query:
            # Armadilha clássica de SPA: a query caiu dentro do fragmento,
            # o navegador não a envia e as UTMs somem. O laudo continua
            # sobre os parâmetros que estão lá — errados de lugar, mas
            # ainda dizem se o resto está certo.
            laudo.erro("query_dentro_da_ancora", None, _encontrado=fragmento)
            consulta = fragmento.split("?", 1)[1] if "?" in fragmento else fragmento
        else:
            laudo.aviso("ancora_com_utm", None, _encontrado=fragmento)

    return partes, consulta, hash_antes_da_query


def _extrair_pares(consulta: str) -> list[_Par]:
    pares: list[_Par] = []
    for pedaco in consulta.split("&"):
        if not pedaco:
            continue
        nome_bruto, _, valor_bruto = pedaco.partition("=")
        nome = canonico(unquote(nome_bruto))
        if not nome:
            continue
        pares.append(_Par(nome=nome, bruto=valor_bruto, valor=_decodificar(valor_bruto)))
    return pares


# --------------------------------------------------------------------------
# regras por parâmetro
# --------------------------------------------------------------------------

def _conferir_nome(laudo: _Laudo, nome: str) -> None:
    if nome in CONFERIDOS:
        return
    if nome in OUTROS_GA4:
        laudo.aviso("parametro_utm_nao_conferido", nome, p=nome, _encontrado=nome)
        return
    parecido = _mais_parecido(nome)
    if parecido is not None:
        laudo.erro(
            "utm_desconhecida", nome, p=nome, sugestao=parecido,
            _encontrado=nome, _esperado=parecido,
        )


def _conferir_valor(laudo: _Laudo, par: _Par) -> None:
    nome, bruto, valor = par.nome, par.bruto, par.valor

    if not valor.strip():
        laudo.erro("utm_vazia", nome, p=nome, _encontrado=valor)
        return

    if _MACRO.search(bruto):
        # O valor final só existe depois de a plataforma resolver a macro;
        # conferir caixa e caractere aqui seria reclamar do que ainda não é.
        return

    if (escape := _ESCAPE_INVALIDO.search(bruto)) is not None:
        trecho = bruto[escape.start() : escape.start() + 3]
        laudo.erro("encoding_invalido", nome, p=nome, trecho=trecho, _encontrado=trecho)
    if _ESCAPE_DUPLO.search(bruto):
        laudo.aviso("encoding_duplo", nome, p=nome, v=valor, _encontrado=valor)
    if "+" in bruto:
        laudo.aviso("mais_e_espaco", nome, p=nome, _encontrado=valor)

    espaco_literal = " " in bruto
    espaco_escapado = "%20" in bruto.lower()
    if espaco_literal or (espaco_escapado and nome in SEM_ESPACO):
        # Espaço em utm_term é aviso: palavra-chave de Search tem espaço.
        registrar = laudo.erro if nome != "utm_term" else laudo.aviso
        registrar("espaco_no_valor", nome, p=nome, v=valor, _encontrado=valor)

    if any(ord(c) > 127 for c in valor):
        sugestao = _para_valor_de_url(valor)
        laudo.erro(
            "acento_no_valor", nome, p=nome, v=valor, sugestao=sugestao,
            _encontrado=valor, _esperado=sugestao,
        )

    for c in valor:
        if ord(c) > 127 or c == " ":
            continue  # já reportado como acento ou espaço
        if not _PERMITIDO.match(c):
            laudo.erro(
                "caractere_invalido_no_valor", nome, p=nome, c=c, v=valor, _encontrado=c
            )
            break

    if valor != valor.lower():
        laudo.aviso(
            "caixa_mista", nome, p=nome, v=valor, minusculo=valor.lower(),
            _encontrado=valor, _esperado=valor.lower(),
        )


# --------------------------------------------------------------------------
# regras de match ID
# --------------------------------------------------------------------------

def _conferir_match(laudo: _Laudo, parametro: str, valor: str, esperado: str, nivel: str) -> bool:
    """Confere um slot que precisa **conter** o match ID. Devolve se casou."""
    alvo = canonico(esperado)
    if contem_match_id(valor, alvo):
        return True

    encontrados = match_ids_no_valor(valor)
    do_mesmo_nivel = [m for m in encontrados if m[0] == alvo[0]]

    if do_mesmo_nivel:
        laudo.erro(
            "match_id_divergente", parametro,
            p=parametro, encontrado=do_mesmo_nivel[0], esperado=alvo,
            este=ESTE[nivel], outro=OUTRO[nivel], nivel=nivel,
            _encontrado=do_mesmo_nivel[0], _esperado=alvo,
        )
    elif encontrados:
        # Níveis invertidos: o dado de anúncio seria somado como campanha.
        laudo.erro(
            "match_id_nivel_trocado", parametro,
            p=parametro, encontrado=encontrados[0], esperado=alvo,
            nivel_encontrado=NIVEL_POR_LETRA[encontrados[0][0]], nivel_esperado=nivel,
            _encontrado=encontrados[0], _esperado=alvo,
        )
    else:
        laudo.erro(
            "match_id_ausente", parametro,
            p=parametro, esperado=alvo, este=ESTE[nivel], nivel=nivel,
            _encontrado=valor, _esperado=alvo,
        )
    return False


def _conferir_nomenclatura(
    laudo: _Laudo, parametro: str, valor: str, nomenclatura: str | None
) -> None:
    """Match ID certo mas rótulo diferente: aviso, nunca erro (D-012)."""
    if not nomenclatura:
        return
    esperado = canonico(nomenclatura)
    if canonico(valor) != esperado:
        laudo.aviso(
            "nomenclatura_divergente", parametro,
            p=parametro, esperado=esperado, encontrado=valor,
            _encontrado=valor, _esperado=esperado,
        )


def _conferir_campanha(laudo: _Laudo, primeiros: dict[str, _Par], contexto: ContextoUtm) -> None:
    campanha = contexto.match_id_campanha
    if not campanha:
        return
    alvo = canonico(campanha)

    par = primeiros.get("utm_campaign")
    if par is not None and par.valor.strip():
        if _conferir_match(laudo, "utm_campaign", par.valor, alvo, "campanha"):
            _conferir_nomenclatura(
                laudo, "utm_campaign", par.valor, contexto.nomenclatura_campanha
            )
        if len(par.valor) > LIMITE_CAMPAIGN_LONGA:
            laudo.aviso(
                "utm_campaign_longa", "utm_campaign", n=len(par.valor), _encontrado=par.valor
            )

    identificador = primeiros.get("utm_id")
    if identificador is None:
        # Ausência é aviso ativo: é pelo utm_id que o GA4 junta o custo
        # importado com a sessão. Sem ele o ROAS não fecha, mesmo com as
        # outras cinco UTMs perfeitas.
        laudo.aviso("utm_id_ausente", "utm_id", c=alvo, _esperado=alvo)
    elif identificador.valor.strip() and not contem_match_id(identificador.valor, alvo):
        laudo.erro(
            "utm_id_divergente", "utm_id",
            encontrado=identificador.valor, esperado=alvo,
            _encontrado=identificador.valor, _esperado=alvo,
        )


def _conferir_anuncio(laudo: _Laudo, primeiros: dict[str, _Par], contexto: ContextoUtm) -> None:
    anuncio = contexto.match_id_anuncio
    if not anuncio:
        return
    alvo = canonico(anuncio)

    par = primeiros.get("utm_content")
    if par is None:
        laudo.erro(
            "match_id_ausente", "utm_content",
            p="utm_content", esperado=alvo, este=ESTE["anúncio"], nivel="anúncio",
            _esperado=alvo,
        )
        return
    if not par.valor.strip():
        return  # já reportado como utm_vazia

    if _conferir_match(laudo, "utm_content", par.valor, alvo, "anúncio"):
        _conferir_nomenclatura(laudo, "utm_content", par.valor, contexto.nomenclatura_anuncio)


def _conferir_grupo(laudo: _Laudo, primeiros: dict[str, _Par], contexto: ContextoUtm) -> None:
    """O grupo aceita dois endereços: utm_term **ou** utm_content.

    utm_term é o slot sem consenso — em Search ele é a palavra-chave
    (`{keyword}`), e disputar essa posição quebraria uma convenção que
    funciona. Então: em nenhum dos dois = aviso; presente com o 'g' errado
    = erro.
    """
    grupo = contexto.match_id_grupo
    if not grupo:
        return
    alvo = canonico(grupo)

    candidatos = [
        par
        for par in (primeiros.get("utm_term"), primeiros.get("utm_content"))
        if par is not None and par.valor.strip()
    ]
    if any(contem_match_id(par.valor, alvo) for par in candidatos):
        return

    for par in candidatos:
        errados = [m for m in match_ids_no_valor(par.valor) if m[0] == "g"]
        if errados:
            laudo.erro(
                "match_id_divergente", par.nome,
                p=par.nome, encontrado=errados[0], esperado=alvo,
                este=ESTE["grupo"], outro=OUTRO["grupo"], nivel="grupo",
                _encontrado=errados[0], _esperado=alvo,
            )
            return

    laudo.aviso("grupo_sem_rastreio", "utm_term", g=alvo, _esperado=alvo)


# --------------------------------------------------------------------------
# regras de vocabulário
# --------------------------------------------------------------------------

def _conferir_vocabulario(
    laudo: _Laudo,
    par: _Par | None,
    vocabulario: tuple[str, ...],
    padrao: str | None,
    codigo_erro: str,
    codigo_aviso: str,
    **dados_do_aviso: object,
) -> None:
    """Vocabulário cadastrado manda; sem ele, a divergência é só aviso.

    É a decisão do D-012 que mantém isto em dados: o time que usa
    `paid_social` cadastra `paid_social` e para de ser avisado. Tratar como
    autoridade um vocabulário que ninguém registrou seria inventar regra.
    """
    if par is None or not par.valor.strip():
        return
    valor = canonico(par.valor)

    if vocabulario:
        if valor not in {canonico(o) for o in vocabulario}:
            laudo.erro(
                codigo_erro, par.nome,
                v=par.valor, opcoes=", ".join(sorted(vocabulario)),
                plataforma=dados_do_aviso.get("plataforma", "esta plataforma"),
                _encontrado=par.valor,
            )
        return

    if padrao and valor != canonico(padrao):
        laudo.aviso(
            codigo_aviso, par.nome,
            v=par.valor,
            **{k: v for k, v in dados_do_aviso.items() if k != "plataforma"},
            _encontrado=par.valor, _esperado=canonico(padrao),
        )


# --------------------------------------------------------------------------
# sugestão
# --------------------------------------------------------------------------

def _escolher(par: _Par | None, vocabulario: tuple[str, ...], padrao: str | None) -> str | None:
    """Valor sugerido para source/medium: mantém o que já serve."""
    atual = _para_valor_de_url(par.valor) if par is not None and par.valor.strip() else None
    opcoes = [_para_valor_de_url(o) for o in vocabulario]
    if opcoes:
        if atual in opcoes:
            return atual
        if padrao and _para_valor_de_url(padrao) in opcoes:
            return _para_valor_de_url(padrao)
        return opcoes[0]
    if padrao:
        return _para_valor_de_url(padrao)
    return atual


def _montar_sugestao(primeiros: dict[str, _Par], contexto: ContextoUtm) -> dict[str, str]:
    """Os valores que o MediaBuild montaria. Sempre em minúsculas — seguir
    a sugestão do próprio app limpa o aviso `caixa_mista`."""
    sugestao: dict[str, str] = {}

    origem = _escolher(
        primeiros.get("utm_source"), contexto.vocabulario_source, contexto.sigla_plataforma
    )
    if origem:
        sugestao["utm_source"] = origem

    meio = _escolher(
        primeiros.get("utm_medium"), contexto.vocabulario_medium, contexto.tipo_compra
    )
    if meio:
        sugestao["utm_medium"] = meio

    campanha = contexto.match_id_campanha
    if contexto.nomenclatura_campanha:
        sugestao["utm_campaign"] = _para_valor_de_url(contexto.nomenclatura_campanha)
    elif campanha:
        atual = primeiros.get("utm_campaign")
        sugestao["utm_campaign"] = (
            _para_valor_de_url(atual.valor)
            if atual is not None and contem_match_id(atual.valor, campanha)
            else canonico(campanha)
        )

    if campanha:
        sugestao["utm_id"] = canonico(campanha)

    if contexto.nomenclatura_anuncio:
        sugestao["utm_content"] = _para_valor_de_url(contexto.nomenclatura_anuncio)
    elif contexto.match_id_anuncio:
        sugestao["utm_content"] = canonico(contexto.match_id_anuncio)

    grupo = contexto.match_id_grupo
    if grupo:
        alvo = canonico(grupo)
        conteudo = sugestao.get("utm_content", "")
        atual = primeiros.get("utm_term")
        if contem_match_id(conteudo, alvo):
            pass  # o grupo já viaja no utm_content; não ocupa o utm_term
        elif atual is not None and contem_match_id(atual.valor, alvo):
            sugestao["utm_term"] = _para_valor_de_url(atual.valor)
        else:
            # Sugestão canônica. Quem usa {keyword} em Search ignora esta
            # linha de propósito e convive com o aviso `grupo_sem_rastreio`
            # — que é exatamente o desenho do D-012 para este slot.
            sugestao["utm_term"] = alvo

    return sugestao


def _montar_url(partes, pares: list[_Par], sugestao: dict[str, str], query_na_ancora: bool) -> str:
    """URL pronta para colar: https, os parâmetros não-utm preservados e as
    UTMs sugeridas em ordem canônica."""
    preservados = [(par.nome, par.valor) for par in pares if not par.nome.startswith("utm")]
    utms = [(nome, sugestao[nome]) for nome in ORDEM_SUGESTAO if nome in sugestao]
    if not preservados and not utms:
        return ""

    consulta = urlencode(preservados + utms, quote_via=quote, safe="{}%:/")
    base = f"https://{partes.netloc}{partes.path}"
    # Um fragmento que continha a query estava no lugar errado — é o erro
    # `query_dentro_da_ancora`, e recolocá-lo repetiria o problema.
    ancora = "" if query_na_ancora or not partes.fragment else f"#{partes.fragment}"
    return f"{base}?{consulta}{ancora}"


# --------------------------------------------------------------------------
# ponto de entrada
# --------------------------------------------------------------------------

def validar_utm(url: str, contexto: ContextoUtm | None = None) -> ResultadoUtm:
    """Confere a URL contra a taxonomia e devolve o laudo.

    Nunca levanta exceção por URL ruim: URL problemática **é** o laudo, não
    requisição malformada. Nada aqui persiste nada.
    """
    contexto = contexto or ContextoUtm()
    laudo = _Laudo()
    bruta = (url or "").strip()

    if not bruta:
        laudo.erro("url_invalida", None, _encontrado=url)
        return ResultadoUtm(erros=laudo.erros, avisos=laudo.avisos)

    analise = _conferir_url(bruta, laudo)
    if analise is None:
        return ResultadoUtm(erros=laudo.erros, avisos=laudo.avisos)
    partes, consulta, query_na_ancora = analise

    pares = _extrair_pares(consulta)
    primeiros: dict[str, _Par] = {}
    for par in pares:
        primeiros.setdefault(par.nome, par)
    parametros = {nome: par.valor for nome, par in primeiros.items()}

    sugestao = _montar_sugestao(primeiros, contexto)
    url_sugerida = _montar_url(partes, pares, sugestao, query_na_ancora)

    # 'utm' e não 'utm_' de propósito: com só um 'utmsource=fb' na URL, o
    # laudo útil é "você quis dizer utm_source", não "não há nenhuma UTM".
    if not any(nome.startswith("utm") for nome in primeiros):
        laudo.erro("sem_utm", None, _encontrado=consulta)
        return ResultadoUtm(
            erros=laudo.erros, avisos=laudo.avisos, parametros=parametros,
            sugestao=sugestao, url_sugerida=url_sugerida,
        )

    contagem = Counter(par.nome for par in pares)
    for nome, par in primeiros.items():
        if not nome.startswith("utm"):
            continue
        if contagem[nome] > 1:
            laudo.erro(
                "parametro_duplicado", nome, p=nome, n=contagem[nome], _encontrado=par.valor
            )
        _conferir_nome(laudo, nome)
        _conferir_valor(laudo, par)

    for obrigatorio in OBRIGATORIOS:
        if obrigatorio not in primeiros:
            laudo.erro("utm_obrigatoria_ausente", obrigatorio, p=obrigatorio, _esperado=obrigatorio)

    _conferir_campanha(laudo, primeiros, contexto)
    _conferir_anuncio(laudo, primeiros, contexto)
    _conferir_grupo(laudo, primeiros, contexto)

    plataforma = contexto.nome_plataforma or contexto.sigla_plataforma or "esta plataforma"
    _conferir_vocabulario(
        laudo, primeiros.get("utm_source"), contexto.vocabulario_source,
        contexto.sigla_plataforma, "utm_source_invalida", "utm_source_fora_da_convencao",
        plataforma=plataforma, sigla=contexto.sigla_plataforma or "",
    )
    _conferir_vocabulario(
        laudo, primeiros.get("utm_medium"), contexto.vocabulario_medium,
        contexto.tipo_compra, "utm_medium_invalida", "utm_medium_fora_da_convencao",
        plataforma=plataforma, tipo_compra=contexto.tipo_compra or "",
    )

    return ResultadoUtm(
        erros=laudo.erros, avisos=laudo.avisos, parametros=parametros,
        sugestao=sugestao, url_sugerida=url_sugerida,
    )
