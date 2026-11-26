"""Exportação das taxonomias para `.xlsx`.

O arquivo é feito para o analista **copiar e colar** na plataforma de
anúncios: cada campo em sua coluna, e uma coluna com a nomenclatura final
pronta. Por isso a nomenclatura vem logo no início, antes dos campos que a
compõem — é a coluna que ele mais usa.

Cada campo aparece **duas vezes**: na forma que o analista digitou
('Conversão') e, sufixada com '(nome)', na forma que entrou no nome
('CV'). A segunda é a que fecha o PROCV contra a planilha de performance,
que só conhece o nome; a primeira é a que ele consegue ler.
"""

import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Anuncio, Campanha, GrupoAnuncio, Nivel, TaxonomiaGerada

# Colunas fixas, na ordem em que aparecem na planilha.
COLUNAS_FIXAS = [
    "Nomenclatura",
    "Plataforma",
    "Nível",
    "Campanha",
    "Nome interno",
    "Match ID",
    "Caracteres",
]
COLUNAS_FINAIS = ["Criado em", "Lote"]

_ROTULO_NIVEL = {
    Nivel.CAMPANHA: "Campanha",
    Nivel.GRUPO: "Grupo de anúncio",
    Nivel.ANUNCIO: "Anúncio",
}

# Ordem preferida das colunas dinâmicas; o resto entra em ordem alfabética.
# Segue a ordem em que os campos aparecem no nome (ver ESTRUTURA_PADRAO).
_PRIORIDADE_CAMPOS = [
    "nome_campanha",
    "empresa",
    "canal",
    "objetivo",
    "mes",
    "funil",
    "sexo",
    "idade",
    "interesse_1",
    "interesse_2",
    "regiao",
    "cidade",
    "segmentacao",
    "formato",
    "dimensao",
    "tipo_compra",
    "nome_criativo",
    "secundagem",
    "versao",
    "posicionamento",
    "correspondencia",
]

# Rótulos legíveis das colunas dinâmicas; o resto vira 'chave_composta' -> 'Chave composta'.
_ROTULO_CAMPO = {
    "nome_campanha": "Nome da campanha",
    "mes": "Mês",
    "funil": "Etapa do funil",
    "regiao": "Região",
    "segmentacao": "Segmentação",
    "dimensao": "Dimensão do criativo",
    "tipo_compra": "Tipo de compra",
    "nome_criativo": "Nome do criativo",
    "versao": "Versão",
    "correspondencia": "Tipo de correspondência",
}


@dataclass
class Linha:
    id: UUID
    nomenclatura: str
    plataforma: str
    nivel: Nivel
    campanha: str
    nome_interno: str
    match_id: str
    template_versao: int
    criado_em: datetime
    lote_id: UUID | None
    campos: dict[str, str] = field(default_factory=dict)
    # {"objetivo": {"bruto": "Conversão", "final": "CV", "ordem": 4}}
    campos_gerados: dict[str, dict] = field(default_factory=dict)


def montar_linhas(session: Session, taxonomias: Sequence[TaxonomiaGerada]) -> list[Linha]:
    """Resolve as entidades polimórficas em lote, evitando N+1.

    `taxonomias_geradas.entidade_id` não tem foreign key (é polimórfico e o
    histórico precisa sobreviver à exclusão da entidade), então a junção é
    feita aqui, por nível.
    """
    por_nivel: dict[Nivel, list[UUID]] = {}
    for t in taxonomias:
        por_nivel.setdefault(t.nivel, []).append(t.entidade_id)

    # (plataforma, campanha, nome_interno, campos)
    entidades: dict[tuple[Nivel, UUID], tuple[str, str, str, dict]] = {}

    if ids := por_nivel.get(Nivel.CAMPANHA):
        for c in session.scalars(
            select(Campanha).options(joinedload(Campanha.plataforma)).where(Campanha.id.in_(ids))
        ):
            entidades[(Nivel.CAMPANHA, c.id)] = (
                c.plataforma.nome,
                c.nome_interno,
                c.nome_interno,
                c.campos,
            )

    if ids := por_nivel.get(Nivel.GRUPO):
        for g in session.scalars(
            select(GrupoAnuncio)
            .options(joinedload(GrupoAnuncio.campanha).joinedload(Campanha.plataforma))
            .where(GrupoAnuncio.id.in_(ids))
        ):
            entidades[(Nivel.GRUPO, g.id)] = (
                g.campanha.plataforma.nome,
                g.campanha.nome_interno,
                g.nome_interno,
                g.campos,
            )

    if ids := por_nivel.get(Nivel.ANUNCIO):
        for a in session.scalars(
            select(Anuncio)
            .options(
                joinedload(Anuncio.grupo)
                .joinedload(GrupoAnuncio.campanha)
                .joinedload(Campanha.plataforma)
            )
            .where(Anuncio.id.in_(ids))
        ):
            entidades[(Nivel.ANUNCIO, a.id)] = (
                a.grupo.campanha.plataforma.nome,
                a.grupo.campanha.nome_interno,
                a.nome_interno,
                a.campos,
            )

    linhas: list[Linha] = []
    for t in taxonomias:
        # A entidade pode ter sido apagada — o histórico sobrevive a ela (D-004).
        plataforma, campanha, nome_interno, campos = entidades.get(
            (t.nivel, t.entidade_id), ("(entidade removida)", "", "", {})
        )
        # O match ID está embutido no fim da nomenclatura.
        match_id = t.nomenclatura_final.rsplit("_", 1)[-1].rsplit("-", 1)[-1]
        linhas.append(
            Linha(
                id=t.id,
                nomenclatura=t.nomenclatura_final,
                plataforma=plataforma,
                nivel=t.nivel,
                campanha=campanha,
                nome_interno=nome_interno,
                match_id=match_id,
                template_versao=t.template_versao,
                criado_em=t.criado_em,
                lote_id=t.lote_id,
                campos=campos or {},
                campos_gerados=t.campos_gerados or {},
            )
        )
    return linhas


def _ordenar_campos(linhas: Sequence[Linha]) -> list[str]:
    presentes = {chave for linha in linhas for chave in linha.campos}
    prioritarios = [c for c in _PRIORIDADE_CAMPOS if c in presentes]
    resto = sorted(presentes - set(prioritarios))
    return prioritarios + resto


def _rotulo(chave: str) -> str:
    return _ROTULO_CAMPO.get(chave, chave.replace("_", " ").capitalize())


def _ordenar_campos_gerados(linhas: Sequence[Linha]) -> list[str]:
    """Chaves de `campos_gerados` na ordem em que aparecem no nome.

    A ordem vem do próprio registro (`ordem`, gravada pelo motor a partir
    do template) e **não** de uma lista no código: JSONB não preserva a
    ordem das chaves, e o padrão de nomenclatura vive em dado. Quando a
    exportação mistura níveis ou plataformas, a menor posição vista vence,
    o que mantém campanha antes de grupo antes de anúncio.

    Linhas retroativas não têm `ordem`; caem no fim, em ordem alfabética.
    """
    menor_posicao: dict[str, int] = {}
    for linha in linhas:
        for chave, dados in linha.campos_gerados.items():
            ordem = dados.get("ordem") if isinstance(dados, dict) else None
            atual = menor_posicao.get(chave)
            if ordem is None:
                menor_posicao.setdefault(chave, 10_000)
            elif atual is None or ordem < atual:
                menor_posicao[chave] = ordem
    return sorted(menor_posicao, key=lambda c: (menor_posicao[c], c))


def neutralizar_formulas(ws) -> None:
    """Grava como texto todo valor que o Excel executaria como fórmula.

    O openpyxl trata string iniciada por '=' como fórmula, e vários valores
    exportados são digitados por usuário (nome interno, campos, nome do
    plano). A exportação nunca escreve fórmula de propósito, então qualquer
    célula do tipo 'f' é texto disfarçado.
    """
    for linha in ws.iter_rows():
        for celula in linha:
            if celula.data_type == "f":
                celula.data_type = "s"


def gerar_planilha(linhas: Sequence[Linha]) -> bytes:
    """Monta o `.xlsx` em memória e devolve os bytes."""
    colunas_campos = _ordenar_campos(linhas)
    # Uma coluna por token de campo, com o valor **como aparece no nome**.
    # É o que faz o PROCV do analista fechar: a planilha de performance traz
    # 'CV', não 'Conversão'.
    colunas_geradas = _ordenar_campos_gerados(linhas)
    cabecalho = [
        *COLUNAS_FIXAS,
        *(_rotulo(c) for c in colunas_campos),
        *(f"{_rotulo(c)} (nome)" for c in colunas_geradas),
        *COLUNAS_FINAIS,
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Taxonomias"

    ws.append(cabecalho)
    fundo = PatternFill("solid", fgColor="F8F9FA")
    for celula in ws[1]:
        celula.font = Font(bold=True)
        celula.fill = fundo
        celula.alignment = Alignment(vertical="center")

    for linha in linhas:
        ws.append(
            [
                linha.nomenclatura,
                linha.plataforma,
                _ROTULO_NIVEL[linha.nivel],
                linha.campanha,
                linha.nome_interno,
                linha.match_id,
                len(linha.nomenclatura),
                *(linha.campos.get(c, "") for c in colunas_campos),
                *(
                    (linha.campos_gerados.get(c) or {}).get("final") or ""
                    for c in colunas_geradas
                ),
                # Excel não aceita datetime com timezone.
                linha.criado_em.replace(tzinfo=None) if linha.criado_em else None,
                str(linha.lote_id) if linha.lote_id else "",
            ]
        )

    # Cabeçalho congelado e filtro, para trabalhar com listas longas.
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for i, titulo in enumerate(cabecalho, start=1):
        maior = max(
            [len(str(titulo))] + [len(str(c.value or "")) for c in ws[get_column_letter(i)][1:]]
        )
        ws.column_dimensions[get_column_letter(i)].width = min(max(maior + 2, 12), 60)

    neutralizar_formulas(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
