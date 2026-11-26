"""Criação de plataformas e a estrutura padrão de campos por nível.

Invariante do sistema: **toda plataforma tem template e limite para todos
os três níveis** (D-007). Uma plataforma sem template num nível é
inutilizável ali — o motor não teria como montar o nome — e a falha só
apareceria quando o analista tentasse gerar.

Por isso a criação é atômica: passa por aqui, ou nasce quebrada. A API
deve usar esta função, nunca instanciar `Plataforma` direto.

A estrutura de campos (`ESTRUTURA_PADRAO`) é a transcrição da aba
"Taxonomia" da planilha de referência. Ela é só o **ponto de partida**: uma
vez criada a plataforma, o padrão vive em `templates_taxonomia` e muda por
UPDATE, sem passar por aqui.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import LimitePlataforma, Nivel, Plataforma, TemplateTaxonomia


@dataclass(frozen=True)
class CampoSpec:
    """Um campo do formulário, na linguagem da planilha.

    `abreviar=True` é "Drop list" (valor precisa existir no dicionário);
    `abreviar=False` com `max_caracteres` é "Campo livre N caracteres".
    """

    chave: str
    rotulo: str
    abreviar: bool = True
    max_caracteres: int | None = None
    opcional: bool = False
    # Quando dois campos compartilham vocabulário ('interesse_1' e
    # 'interesse_2' consultam a categoria 'interesse').
    categoria: str | None = None

    def token(self) -> dict:
        token: dict = {"tipo": "campo", "chave": self.chave, "rotulo": self.rotulo}
        if not self.abreviar:
            token["abreviar"] = False
        if self.max_caracteres is not None:
            token["max_caracteres"] = self.max_caracteres
        if self.opcional:
            token["opcional"] = True
        if self.categoria:
            token["categoria"] = self.categoria
        return token


class _Sigla:
    """Marcador para a posição da sigla da plataforma dentro do nome.

    Na planilha existe uma coluna "Plataforma" no nível de campanha. Aqui
    ela não vira um campo do formulário: o analista já escolheu a
    plataforma no topo da tela, e pedir de novo seria digitar duas vezes.
    Vira um token literal com a sigla (D-008).
    """

    __slots__ = ()


SIGLA = _Sigla()

Item = CampoSpec | _Sigla

# Marcador que ocupa o lugar de um campo opcional em branco, para que todos
# os nomes de um nível tenham a mesma quantidade de partes. Este valor é só
# o **ponto de partida**: quem manda em tempo de execução é a coluna
# `templates_taxonomia.marcador_ausencia`, e trocá-lo é um UPDATE.
MARCADOR_AUSENCIA_PADRAO = "NA"

# Transcrição da aba "Taxonomia" da a planilha de taxonomia de referência, na ordem das colunas.
ESTRUTURA_PADRAO: dict[Nivel, list[Item]] = {
    Nivel.CAMPANHA: [
        CampoSpec("nome_campanha", "Nome da campanha", abreviar=False, max_caracteres=5),
        CampoSpec("empresa", "Empresa"),
        SIGLA,
        CampoSpec("canal", "Canal"),
        CampoSpec("objetivo", "Objetivo"),
        CampoSpec("mes", "Mês"),
        # Acréscimo nosso: etapa de funil é padrão de mercado e barata de
        # cadastrar. Opcional para não obrigar quem não usa.
        CampoSpec("funil", "Etapa do funil", opcional=True),
    ],
    Nivel.GRUPO: [
        CampoSpec("sexo", "Sexo"),
        CampoSpec("idade", "Idade"),
        CampoSpec("interesse_1", "Interesse 1", categoria="interesse"),
        # Opcional: exigir dois interesses forçaria o analista a inventar um.
        CampoSpec("interesse_2", "Interesse 2", categoria="interesse", opcional=True),
        CampoSpec("regiao", "Região"),
        CampoSpec("cidade", "Cidade"),
        CampoSpec("segmentacao", "Segmentação"),
    ],
    Nivel.ANUNCIO: [
        CampoSpec("formato", "Formato"),
        CampoSpec("dimensao", "Dimensão do criativo"),
        CampoSpec("tipo_compra", "Tipo de compra"),
        CampoSpec("nome_criativo", "Nome do criativo", abreviar=False, max_caracteres=10),
        # Opcional: só se aplica a criativo em vídeo.
        CampoSpec("secundagem", "Secundagem", opcional=True),
        CampoSpec("versao", "Versão"),
    ],
}


def montar_tokens(
    sigla: str, itens: list[Item], extras: list[CampoSpec] | None = None
) -> list[dict]:
    """Converte a estrutura declarativa na lista JSONB de tokens.

    O match ID entra sempre no fim — é o `_A1` que a planilha de referência
    escrevia à mão, aqui gerado por sequence (D-006).
    """
    tokens: list[dict] = []
    for item in itens:
        if isinstance(item, _Sigla):
            tokens.append({"tipo": "literal", "valor": sigla})
        else:
            tokens.append(item.token())

    for extra in extras or []:
        tokens.append(extra.token())

    tokens.append({"tipo": "match_id"})
    return tokens


def _normalizar_extras(extras: list[CampoSpec | str] | None) -> list[CampoSpec]:
    """Aceita `CampoSpec` ou só a chave, para não quebrar chamadas antigas."""
    saida: list[CampoSpec] = []
    for extra in extras or []:
        if isinstance(extra, CampoSpec):
            saida.append(extra)
        else:
            saida.append(CampoSpec(chave=extra, rotulo=extra.replace("_", " ").capitalize()))
    return saida


def criar_plataforma(
    session: Session,
    *,
    nome: str,
    sigla: str,
    limites: int | dict[Nivel, int],
    campos_extras: dict[Nivel, list[CampoSpec | str]] | None = None,
    separador: str = "_",
    estrutura: dict[Nivel, list[Item]] | None = None,
    marcador_ausencia: str = MARCADOR_AUSENCIA_PADRAO,
) -> Plataforma:
    """Cria a plataforma com limite e template para os três níveis.

    `limites` aceita um int (mesmo valor para todos os níveis) ou um dict
    por nível. `campos_extras` acrescenta campos específicos da plataforma
    ao fim do nível — por exemplo posicionamento no Meta.
    """
    plataforma = Plataforma(nome=nome, sigla=sigla, ativo=True)
    session.add(plataforma)
    session.flush()

    base = estrutura or ESTRUTURA_PADRAO
    extras = campos_extras or {}

    for nivel in Nivel:
        limite = limites[nivel] if isinstance(limites, dict) else limites
        session.add(
            LimitePlataforma(
                plataforma_id=plataforma.id, nivel=nivel, limite_caracteres=limite
            )
        )
        session.add(
            TemplateTaxonomia(
                plataforma_id=plataforma.id,
                nivel=nivel,
                separador=separador,
                tokens=montar_tokens(
                    sigla, base[nivel], _normalizar_extras(extras.get(nivel))
                ),
                marcador_ausencia=marcador_ausencia,
                versao=1,
                ativo=True,
            )
        )

    session.flush()
    return plataforma


def niveis_faltando(session: Session, plataforma: Plataforma) -> dict[str, list[Nivel]]:
    """Diagnóstico do invariante. Dicionário vazio significa plataforma íntegra."""
    from sqlalchemy import select

    com_template = set(
        session.scalars(
            select(TemplateTaxonomia.nivel).where(
                TemplateTaxonomia.plataforma_id == plataforma.id,
                TemplateTaxonomia.ativo.is_(True),
            )
        )
    )
    com_limite = set(
        session.scalars(
            select(LimitePlataforma.nivel).where(
                LimitePlataforma.plataforma_id == plataforma.id
            )
        )
    )

    faltando: dict[str, list[Nivel]] = {}
    if ausentes := [n for n in Nivel if n not in com_template]:
        faltando["templates"] = ausentes
    if ausentes := [n for n in Nivel if n not in com_limite]:
        faltando["limites"] = ausentes
    return faltando
