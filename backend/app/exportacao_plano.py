"""Exportação de um plano de mídia para `.xlsx`.

Replica o layout achatado da planilha de referência
(uma planilha de plano de mídia de referência): uma linha por **anúncio**, com
as três taxonomias (campanha, grupo, anúncio) lado a lado, o investimento
do anúncio e uma coluna por métrica — seguidos de uma linha TOTAL no pé,
somando investimento e cada métrica. Segue o mesmo padrão visual de
`app/exportacao.py` (cabeçalho em negrito, painel congelado, autofiltro,
largura ajustada por coluna).
"""

import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exportacao import neutralizar_formulas
from app.models import Metrica, PlanoMidia

# --------------------------------------------------------------------------
# nota de desbalanço (docs/PLANO-DE-MIDIA.md §4, item 4: "Levar o aviso
# para o Excel exportado")
#
# Tolerância aceita SEM aviso, em termos RELATIVOS à verba total do plano
# — nunca um valor absoluto de reais. 2% de R$ 50.000 são R$ 1.000: essa
# é folga de planejamento deliberada (rateio manual de última hora, ajuste
# fino entre campanhas), não margem de arredondamento residual do rateio
# em cascata — o resíduo de arredondamento já fica na casa dos centavos
# por linha (ver `_calcular_valor` em `app/routers/planos.py`) e nunca
# chegaria perto de 2% sozinho. Constante nomeada e comentada de propósito:
# é um número de negócio que será questionado depois, não um detalhe de
# implementação para esconder dentro de um `if`.
TOLERANCIA_DESBALANCO_RELATIVA = Decimal("0.02")

# As três colunas novas (docs/PLANO-DE-MIDIA.md §5) entram coladas na
# taxonomia do nível a que pertencem — flight e KPI são atributos da
# CAMPANHA, custo unitário negociado é atributo do GRUPO — para que quem lê
# a planilha associe a coluna ao nível certo sem precisar de legenda.
#
# "Investimento (R$)" virou "Investimento previsto (R$)": esta coluna,
# nesta exportação achatada, é sempre o `valor` do ANÚNCIO (uma linha por
# anúncio) — e não existe orçamento configurável por anúncio em nenhuma
# plataforma de mídia (docs/PLANO-DE-MIDIA.md §4). Ver docstring de
# `PlanoMidiaAnuncio.valor`.
COLUNAS_FIXAS = [
    "Taxonomia Campanha",
    "Flight — início",
    "Flight — fim",
    "KPI primário",
    "Taxonomia Grupo de Anúncios",
    "Custo unitário negociado (R$)",
    "Taxonomia Anúncio",
    "Investimento previsto (R$)",
]


@dataclass
class _LinhaExportacao:
    taxonomia_campanha: str
    taxonomia_grupo: str
    taxonomia_anuncio: str
    investimento: Decimal
    flight_inicio: date | None = None
    flight_fim: date | None = None
    kpi_primario_rotulo: str | None = None
    custo_unitario_negociado: Decimal | None = None
    metas: dict[str, int] = field(default_factory=dict)


def _rotulo_de_fallback(codigo: str) -> str:
    """Cabeçalho para uma métrica cujo código já não existe no catálogo —
    plano antigo com métrica desde então removida. Continua legível em vez
    de sumir da planilha ou quebrar a exportação."""
    return codigo.replace("_", " ").capitalize()


def _colunas_de_metrica(
    session: Session, linhas: Sequence[_LinhaExportacao]
) -> tuple[list[str], list[str]]:
    """Códigos e rótulos das métricas presentes nas linhas, na ordem do
    catálogo (`Metrica.ordem`). Assim como `_ordenar_campos` em
    `app/exportacao.py`, a coluna nasce do que está **nos dados**, não de
    uma lista fixa no código — inclui métricas já desativadas, se alguma
    linha ainda carregar meta para elas."""
    presentes = {codigo for linha in linhas for codigo in linha.metas}
    if not presentes:
        return [], []

    catalogo = {
        m.codigo: m
        for m in session.scalars(select(Metrica).where(Metrica.codigo.in_(presentes)))
    }
    ordenados = sorted(
        presentes,
        key=lambda c: (catalogo[c].ordem, c) if c in catalogo else (10_000, c),
    )
    rotulos = [catalogo[c].rotulo if c in catalogo else _rotulo_de_fallback(c) for c in ordenados]
    return ordenados, rotulos


def _montar_linhas(plano: PlanoMidia) -> list[_LinhaExportacao]:
    """Achata a árvore campanha → grupo → anúncio numa linha por anúncio,
    igual à planilha de referência. Usa a nomenclatura gerada quando existe;
    cai para o nome interno quando a entidade ainda não tem nome gerado —
    estado normal de um plano em rascunho, não um erro."""
    linhas: list[_LinhaExportacao] = []
    for campanha in plano.campanhas:
        for grupo in campanha.grupos:
            for anuncio in grupo.anuncios:
                linhas.append(
                    _LinhaExportacao(
                        taxonomia_campanha=campanha.nomenclatura or campanha.nome_interno,
                        taxonomia_grupo=grupo.nomenclatura or grupo.nome_interno,
                        taxonomia_anuncio=anuncio.nomenclatura or anuncio.nome_interno,
                        investimento=anuncio.valor,
                        flight_inicio=campanha.flight_inicio,
                        flight_fim=campanha.flight_fim,
                        kpi_primario_rotulo=campanha.kpi_primario_rotulo,
                        custo_unitario_negociado=grupo.custo_unitario_negociado,
                        metas=anuncio.metas or {},
                    )
                )
    return linhas


def _dentro_da_tolerancia(diferenca: Decimal, verba_total: Decimal) -> bool:
    """`True` quando `diferenca` não precisa virar aviso na planilha.

    A razão é sempre `abs(diferenca) / verba_total` — a verba TOTAL do
    plano, não o valor local do nó (campanha ou grupo) sendo checado. Duas
    razões para isso, não uma: (1) faz o mesmo desvio em reais pesar igual
    em qualquer nível da árvore, em vez de um grupo pequeno "estourar" a
    100 pontos percentuais com uma diferença de R$ 5; (2) evita dividir por
    um valor local que é zero com frequência bem maior que a verba total
    (campanha/grupo recém-criado, ainda sem rateio) — sem precisar de um
    tratamento de exceção por nó.

    Verba total zero é o único caso em que a razão relativa não tem
    sentido nenhum (0/0): aí qualquer `diferenca` diferente de zero é
    desbalanço, sem meio-termo.
    """
    if verba_total == 0:
        return diferenca == 0
    return abs(diferenca) / verba_total <= TOLERANCIA_DESBALANCO_RELATIVA


def _formatar_valor(valor: Decimal) -> str:
    return f"R$ {valor:,.2f}"


def _notas_desbalanco(plano: PlanoMidia) -> list[str]:
    """Uma linha de aviso por nó (plano, campanha, grupo) cuja soma dos
    filhos não fecha com o valor do pai além de `TOLERANCIA_DESBALANCO_RELATIVA`.

    Reporta o topo E os níveis internos, não só o topo. Mesmo raciocínio
    de `docs/PLANO-DE-MIDIA-UI.md` §4.2 (o analista precisa ver o saldo em
    todo nó com filhos, não só no topo da árvore) aplicado ao arquivo: um
    grupo pode estourar sozinho sem que a campanha OU o plano acusem nada,
    porque o resto da verba está perfeitamente alocado em outro ramo da
    árvore — dois desvios de sinais opostos em ramos diferentes se cancelam
    na soma do topo. Quem só abre o Excel, sem a árvore navegável da tela,
    perderia esse sinal por completo se só o topo fosse reportado; é
    exatamente o cenário "múltiplos editores em ramos diferentes" descrito
    no domínio (`docs/PLANO-DE-MIDIA.md` §4). Anúncio é folha — não tem
    soma de filhos — então não entra aqui.

    Cada nível usa a MESMA tolerância relativa à verba total do plano (ver
    `_dentro_da_tolerancia`), não uma tolerância própria por nó.
    """
    verba_total = plano.verba_total
    notas: list[str] = []

    soma_campanhas = sum((c.valor for c in plano.campanhas), Decimal("0"))
    diferenca_topo = verba_total - soma_campanhas
    if not _dentro_da_tolerancia(diferenca_topo, verba_total):
        rotulo = "sem alocar" if diferenca_topo > 0 else "alocado acima da verba total"
        notas.append(
            f"Plano '{plano.nome}': campanhas somam {_formatar_valor(soma_campanhas)} de "
            f"{_formatar_valor(verba_total)} de verba total — "
            f"{_formatar_valor(abs(diferenca_topo))} {rotulo}."
        )

    for campanha in plano.campanhas:
        soma_grupos = sum((g.valor for g in campanha.grupos), Decimal("0"))
        diferenca_campanha = campanha.valor - soma_grupos
        if not _dentro_da_tolerancia(diferenca_campanha, verba_total):
            rotulo = "sem alocar" if diferenca_campanha > 0 else "alocado acima do valor da campanha"
            notas.append(
                f"Campanha '{campanha.nome_interno}' ({campanha.match_id}): grupos somam "
                f"{_formatar_valor(soma_grupos)} de {_formatar_valor(campanha.valor)} "
                f"alocados à campanha — {_formatar_valor(abs(diferenca_campanha))} {rotulo}."
            )
        for grupo in campanha.grupos:
            soma_anuncios = sum((a.valor for a in grupo.anuncios), Decimal("0"))
            diferenca_grupo = grupo.valor - soma_anuncios
            if not _dentro_da_tolerancia(diferenca_grupo, verba_total):
                rotulo = "sem alocar" if diferenca_grupo > 0 else "alocado acima do valor do grupo"
                notas.append(
                    f"Grupo '{grupo.nome_interno}' ({grupo.match_id}): anúncios somam "
                    f"{_formatar_valor(soma_anuncios)} de {_formatar_valor(grupo.valor)} "
                    f"alocados ao grupo — {_formatar_valor(abs(diferenca_grupo))} {rotulo}."
                )
    return notas


def gerar_planilha_plano(session: Session, plano: PlanoMidia) -> bytes:
    """Monta o `.xlsx` do plano em memória e devolve os bytes."""
    linhas = _montar_linhas(plano)
    colunas_metricas, rotulos_metricas = _colunas_de_metrica(session, linhas)
    cabecalho = [*COLUNAS_FIXAS, *rotulos_metricas]

    wb = Workbook()
    ws = wb.active
    ws.title = "Plano de Mídia"

    ws.append(cabecalho)
    fundo = PatternFill("solid", fgColor="F8F9FA")
    for celula in ws[1]:
        celula.font = Font(bold=True)
        celula.fill = fundo
        celula.alignment = Alignment(vertical="center")

    total_investimento = Decimal("0")
    totais_metrica = dict.fromkeys(colunas_metricas, 0)

    for linha in linhas:
        ws.append(
            [
                linha.taxonomia_campanha,
                linha.flight_inicio,
                linha.flight_fim,
                linha.kpi_primario_rotulo or "",
                linha.taxonomia_grupo,
                float(linha.custo_unitario_negociado)
                if linha.custo_unitario_negociado is not None
                else "",
                linha.taxonomia_anuncio,
                float(linha.investimento),
                *(linha.metas.get(c, "") for c in colunas_metricas),
            ]
        )
        total_investimento += linha.investimento
        for coluna in colunas_metricas:
            totais_metrica[coluna] += linha.metas.get(coluna, 0) or 0

    # Linha TOTAL no pé, como na planilha de referência. Flight/KPI/custo
    # unitário não somam (não são grandezas aditivas — datas e um KPI
    # nominal por campanha, preço unitário por grupo), então ficam em
    # branco na linha de totais, só o investimento e as métricas somam.
    ws.append(
        [
            "TOTAL",
            "",
            "",
            "",
            "",
            "",
            "",
            float(total_investimento),
            *(totais_metrica[c] for c in colunas_metricas),
        ]
    )
    for celula in ws[ws.max_row]:
        celula.font = Font(bold=True)
        celula.fill = fundo

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # Largura por coluna calculada agora, só a partir dos dados tabulares —
    # antes de anexar a nota de desbalanço abaixo, cujo texto corrido é bem
    # mais longo que qualquer taxonomia e distorceria a coluna A se entrasse
    # nesta conta.
    for i, titulo in enumerate(cabecalho, start=1):
        maior = max(
            [len(str(titulo))] + [len(str(c.value or "")) for c in ws[get_column_letter(i)][1:]]
        )
        ws.column_dimensions[get_column_letter(i)].width = min(max(maior + 2, 12), 60)

    # Nota de desbalanço logo abaixo do TOTAL — mesma aba, leitura
    # sequencial de cima para baixo, sem exigir que quem abre o arquivo
    # descubra uma aba separada. É a mesma linha de raciocínio da linha
    # TOTAL da planilha de referência: o resumo mora colado aos dados que ele
    # resume, não num lugar à parte. `auto_filter`/`freeze_panes` já foram
    # fixados nas linhas de dados acima e não incluem essas linhas extras.
    notas = _notas_desbalanco(plano)
    if notas:
        largura = len(cabecalho)
        aviso_fundo = PatternFill("solid", fgColor="FFEB9C")
        aviso_fonte = Font(bold=True, color="9C5700")

        ws.append([])
        ws.append(["Aviso de desbalanço — o mesmo aviso aparece na tela do MediaBuild"])
        linha_titulo = ws.max_row
        ws.merge_cells(start_row=linha_titulo, start_column=1, end_row=linha_titulo, end_column=largura)
        celula_titulo = ws.cell(row=linha_titulo, column=1)
        celula_titulo.font = aviso_fonte
        celula_titulo.fill = aviso_fundo

        for nota in notas:
            ws.append([nota])
            linha = ws.max_row
            ws.merge_cells(start_row=linha, start_column=1, end_row=linha, end_column=largura)
            celula = ws.cell(row=linha, column=1)
            celula.fill = aviso_fundo

    neutralizar_formulas(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
