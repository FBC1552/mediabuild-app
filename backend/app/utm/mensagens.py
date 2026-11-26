"""Texto das mensagens do laudo de UTM.

Transcrição literal do D-012. Ficam num módulo só, e não espalhadas pelas
regras, por dois motivos: dá para conferir o conjunto contra a decisão numa
leitura, e o tom (diz o que está errado **e** o que fazer) fica visível
lado a lado, em vez de se perder aos poucos a cada regra nova.

Não confundir com dado configurável: isto é texto de produto, não padrão de
nomenclatura. Padrão de nomenclatura mora no banco (D-008); mensagem de
erro mora no código, como em `app/taxonomia/erros.py`.
"""

# Artigos por nível, para as mensagens que precisam concordar em gênero
# ("este grupo" / "esta campanha").
ESTE = {"campanha": "esta", "grupo": "este", "anúncio": "este"}
OUTRO = {"campanha": "outra", "grupo": "outro", "anúncio": "outro"}

MENSAGENS: dict[str, str] = {
    "url_sem_esquema": (
        "A URL não começa com http:// ou https://. Sem esquema a plataforma pode montar "
        "o link errado — escreva a URL completa."
    ),
    "url_invalida": (
        "Não consegui ler esta URL. Confira se ela está completa, com domínio e sem espaços."
    ),
    "query_dentro_da_ancora": (
        "Os parâmetros estão depois do '#', dentro da âncora. O navegador não envia essa "
        "parte e as UTMs se perdem. Mova a query para antes do '#'."
    ),
    "sem_utm": (
        "A URL não tem nenhum parâmetro utm_. Sem eles não há como cruzar o dado do GA4 "
        "com o da plataforma."
    ),
    "utm_obrigatoria_ausente": (
        "Falta o parâmetro '{p}'. utm_source, utm_medium e utm_campaign são obrigatórios."
    ),
    "utm_vazia": "O parâmetro '{p}' está na URL mas sem valor. Preencha ou remova.",
    "parametro_duplicado": (
        "O parâmetro '{p}' aparece {n} vezes na URL. Qual valor vale fica indefinido — "
        "deixe só um."
    ),
    "utm_desconhecida": (
        "'{p}' não é um parâmetro válido; você quis dizer '{sugestao}'? Escrito assim ele "
        "é ignorado em silêncio e o dado se perde."
    ),
    "match_id_ausente": (
        "O '{p}' não traz o match ID '{esperado}'. Sem ele não dá para juntar {este} "
        "{nivel} com a planilha de performance."
    ),
    "match_id_divergente": (
        "O '{p}' aponta para '{encontrado}', mas {este} {nivel} é '{esperado}'. "
        "Provavelmente a URL foi copiada de {outro} {nivel} — o custo vai ser atribuído "
        "no lugar errado."
    ),
    "match_id_nivel_trocado": (
        "O '{p}' traz '{encontrado}', que é match ID de {nivel_encontrado}. Neste "
        "parâmetro entra o de {nivel_esperado} ('{esperado}')."
    ),
    "utm_id_ausente": (
        "Sem utm_id. É por ele que o GA4 junta o custo importado com a sessão — inclua "
        "'utm_id={c}'."
    ),
    "utm_id_divergente": (
        "O utm_id é '{encontrado}' e a campanha é '{esperado}'. O custo importado vai "
        "casar com a campanha errada."
    ),
    "utm_source_invalida": (
        "'{v}' não está cadastrado em 'utm_source' para {plataforma}. Use uma das opções: "
        "{opcoes}. Ou cadastre '{v}' no dicionário."
    ),
    "utm_medium_invalida": (
        "'{v}' não está cadastrado em 'utm_medium' para {plataforma}. Use uma das opções: "
        "{opcoes}. Ou cadastre '{v}' no dicionário."
    ),
    "utm_source_fora_da_convencao": (
        "'{v}' não corresponde à plataforma escolhida ({sigla}). Se for proposital, "
        "cadastre em 'utm_source' no dicionário para parar de avisar."
    ),
    "utm_medium_fora_da_convencao": (
        "'{v}' não corresponde ao tipo de compra do anúncio ({tipo_compra}). utm_medium é "
        "o que separa CPC de CPM no relatório."
    ),
    "grupo_sem_rastreio": (
        "Nem utm_term nem utm_content trazem o match ID do grupo ('{g}'). Você não vai "
        "conseguir separar conjunto de anúncios no GA4."
    ),
    "nomenclatura_divergente": (
        "O '{p}' tem o match ID certo, mas não é a nomenclatura gerada. Esperado: "
        "'{esperado}'. Encontrado: '{encontrado}'. O cruzamento funciona; a leitura do "
        "relatório fica pior."
    ),
    "caixa_mista": (
        "O '{p}' está como '{v}'. O GA4 diferencia maiúscula de minúscula: '{v}' e "
        "'{minusculo}' viram duas linhas no relatório. Sugestão: '{minusculo}'."
    ),
    "espaco_no_valor": (
        "O '{p}' tem espaço no valor ('{v}'). Espaço quebra o link e vira duas linhas "
        "diferentes no relatório. Troque por '-'."
    ),
    "acento_no_valor": (
        "O '{p}' tem acento no valor ('{v}'). Use '{sugestao}' — acento em UTM vira "
        "codificação diferente em cada ferramenta e o cruzamento não fecha."
    ),
    "caractere_invalido_no_valor": (
        "O '{p}' tem o caractere '{c}' no valor ('{v}'). Em UTM use só letras, números, "
        "'.', '_' e '-'."
    ),
    "encoding_invalido": (
        "O '{p}' tem uma sequência de escape inválida ('{trecho}'). A URL não vai ser "
        "lida como você espera."
    ),
    "encoding_duplo": (
        "O valor de '{p}' parece codificado duas vezes ('{v}'). Confira se a ferramenta "
        "que montou o link não escapou o que já estava escapado."
    ),
    "mais_e_espaco": (
        "O '+' em '{p}' é lido como espaço pelo GA4. Se a intenção era juntar palavras, "
        "use '-'."
    ),
    "sem_https": (
        "A URL usa http://. Se o site redirecionar para https, alguns servidores "
        "descartam a query e as UTMs somem."
    ),
    "macro_na_url": (
        "A URL contém a macro '{m}', que só é resolvida pela plataforma. Não dá para "
        "conferir o valor final aqui."
    ),
    "parametro_utm_nao_conferido": (
        "'{p}' é um parâmetro válido do GA4, mas o MediaBuild não confere o conteúdo dele."
    ),
    "ancora_com_utm": (
        "A âncora depois da query contém 'utm_'. Ela não é enviada como parâmetro — "
        "confira se não é um link montado errado."
    ),
    "utm_campaign_longa": (
        "utm_campaign tem {n} caracteres. Nada quebra, mas relatório com nome desse "
        "tamanho é difícil de ler."
    ),
}


def texto(codigo: str, **dados: object) -> str:
    """Mensagem pronta do código, com os dados interpolados."""
    return MENSAGENS[codigo].format(**dados)
