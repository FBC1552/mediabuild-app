"""Popula o banco com dados de partida.

Idempotente: rodar várias vezes não duplica nada.

    python -m app.seed            # popula o que faltar
    python -m app.seed --reset    # apaga tudo e popula do zero

Os dados vêm da planilha a planilha de taxonomia de referência do cliente (abas "Dicionario" e
"Taxonomia"). Onde ela deixou a lista em branco — objetivo, mês — o valor
aqui é um ponto de partida plausível; o analista ajusta pela tela do
dicionário, sem desenvolvedor.

Os limites de caracteres são valores iniciais plausíveis, **não** conferidos
contra a documentação atual de cada plataforma. Confirmar antes de confiar
neles em produção — o ponto é que ficam em dados, não em código, então
corrigir é um UPDATE.

Quando a estrutura de campos muda (`ESTRUTURA_PADRAO`) — ou o marcador de
ausência (`MARCADOR_AUSENCIA_PADRAO`) — o seed **não** sobrescreve o
template existente: cria a versão seguinte e desativa a anterior.
Nomenclaturas já geradas continuam explicáveis pelo `template_versao` que
guardaram (D-004). Rodar o seed depois da migration `c3f81a6b47d9` é o que
promove os templates de marcador vazio para 'NA'.

O seed também cria o **primeiro administrador** (D-014), a partir de
`ADMIN_LOGIN_INICIAL` / `ADMIN_SENHA_INICIAL`. Como todo o resto daqui, ele
não sobrescreve o que já existe: se o login já está no banco, nada acontece
— nem a senha, nem o papel, nem o `ativo`. Sem essa regra, qualquer `python
-m app.seed` (operação corriqueira) devolveria o acesso a quem conhecesse o
valor antigo da variável de ambiente.
"""

import sys

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.autorizacao import hash_senha, normalizar_login
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Anuncio,
    Campanha,
    DicionarioAbreviacao,
    EventoAcesso,
    EventoErro,
    GrupoAnuncio,
    LimitePlataforma,
    Metrica,
    Nivel,
    Papel,
    PlanoMidia,
    Plataforma,
    TaxonomiaGerada,
    TemplateTaxonomia,
    Usuario,
)
from app.plataformas import (
    ESTRUTURA_PADRAO,
    MARCADOR_AUSENCIA_PADRAO,
    CampoSpec,
    criar_plataforma,
    montar_tokens,
)

# Siglas conforme a coluna "Plataforma" da aba Dicionario (De → Para).
PLATAFORMAS = [
    ("Meta", "METAA", 400),
    ("TikTok", "TIKTOK", 512),
    ("DV360", "DV360", 255),
    ("Google", "GOOGLE", 255),
]

# Campos específicos de uma plataforma, acrescentados ao fim do nível.
# Opcionais de propósito: são refinamentos, não parte do padrão da planilha.
CAMPOS_EXTRAS: dict[str, dict[Nivel, list[CampoSpec]]] = {
    "Meta": {
        Nivel.GRUPO: [CampoSpec("posicionamento", "Posicionamento", opcional=True)],
    },
    "Google": {
        Nivel.GRUPO: [
            CampoSpec("correspondencia", "Tipo de correspondência", opcional=True)
        ],
    },
}

# Abreviações globais (valem para qualquer plataforma).
# A chave é a categoria consultada pelo motor — ver `TokenCampo.categoria_dicionario`.
ABREVIACOES_GLOBAIS: dict[str, list[tuple[str, str]]] = {
    # --- campanha -------------------------------------------------------
    "empresa": [
        ("Loja Alfa", "ALF"),
        ("Loja Beta", "BET"),
    ],
    "canal": [
        ("Instagram", "INSTA"),
        ("Facebook", "FACEB"),
        ("Messenger", "MESSEG"),
        ("Audience Network", "AUDNET"),
        ("YouTube", "YT"),
        ("Search", "SEARCH"),
        ("Display", "DISPLAY"),
        ("Shopping", "SHOPPING"),
    ],
    "objetivo": [
        ("Conversão", "CV"),
        ("Tráfego", "TRF"),
        ("Alcance", "ALC"),
        ("Reconhecimento", "RCN"),
        ("Engajamento", "ENG"),
        ("Geração de Leads", "LEAD"),
        ("Vendas do Catálogo", "CAT"),
        ("Instalações do App", "APP"),
        ("Visualizações de Vídeo", "VV"),
    ],
    "mes": [
        ("Janeiro", "JAN"),
        ("Fevereiro", "FEV"),
        ("Março", "MAR"),
        ("Abril", "ABR"),
        ("Maio", "MAI"),
        ("Junho", "JUN"),
        ("Julho", "JUL"),
        ("Agosto", "AGO"),
        ("Setembro", "SET"),
        ("Outubro", "OUT"),
        ("Novembro", "NOV"),
        ("Dezembro", "DEZ"),
    ],
    "funil": [
        ("Topo", "TOF"),
        ("Meio", "MOF"),
        ("Fundo", "BOF"),
    ],
    # --- grupo de anúncio ------------------------------------------------
    "sexo": [
        ("Feminino", "F"),
        ("Masculino", "M"),
        ("Todos", "ALL"),
    ],
    "idade": [
        ("18-24", "18-24"),
        ("25-34", "25-34"),
        ("35-44", "35-44"),
        ("45-54", "45-54"),
        ("55+", "55MAIS"),
        ("Todas", "ALL"),
    ],
    # Compartilhada por interesse_1 e interesse_2.
    "interesse": [
        ("Moda", "MODA"),
        ("Bolsas", "BOLSA"),
        ("Calçados", "CALC"),
        ("Beleza", "BELEZA"),
        ("Luxo", "LUXO"),
        ("Viagem", "VIAGEM"),
        ("Fitness", "FITNESS"),
        ("Decoração", "DECOR"),
    ],
    "regiao": [
        ("Sudeste", "SUD"),
        ("Sul", "SUL"),
        ("Nordeste", "NOR"),
        ("Norte", "NRT"),
        ("Centro-Oeste", "CO"),
        ("Brasil", "BR"),
    ],
    "cidade": [
        ("São Paulo", "SP"),
        ("Rio de Janeiro", "RJ"),
        ("Belo Horizonte", "BH"),
        ("Porto Alegre", "POA"),
        ("Curitiba", "CWB"),
        ("Brasília", "BSB"),
        ("Recife", "REC"),
        ("Salvador", "SSA"),
        ("Fortaleza", "FOR"),
        ("Todas", "ALL"),
    ],
    "segmentacao": [
        ("Remarketing", "RMKT"),
        ("Lookalike", "LAL"),
        ("Interesses", "INT"),
        ("Retargeting", "RTG"),
        ("Base de Clientes", "BASE"),
        ("Público Frio", "FRIO"),
        ("Aberto", "OPEN"),
    ],
    # --- anúncio ----------------------------------------------------------
    "formato": [
        ("Vídeo", "VID"),
        ("Imagem Única", "IMG"),
        ("Carrossel", "CAR"),
        ("Coleção", "COL"),
        ("Stories", "ST"),
        ("Reels", "RLS"),
        ("Feed", "FD"),
        ("Banner", "BNR"),
    ],
    "dimensao": [
        ("1080x1080", "1080X1080"),
        ("1080x1920", "1080X1920"),
        ("1200x628", "1200X628"),
        ("1200x600", "1200X600"),
        ("1080x1350", "1080X1350"),
        ("300x250", "300X250"),
    ],
    "tipo_compra": [
        ("CPC", "CPC"),
        ("CPM", "CPM"),
        ("CPV", "CPV"),
        ("CPA", "CPA"),
        ("oCPM", "OCPM"),
    ],
    "secundagem": [
        ("6s", "6S"),
        ("15s", "15S"),
        ("30s", "30S"),
        ("60s", "60S"),
    ],
    "versao": [
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
    ],
}

# Abreviações específicas de uma plataforma.
ABREVIACOES_POR_PLATAFORMA: dict[str, dict[str, list[tuple[str, str]]]] = {
    "Meta": {
        "posicionamento": [
            ("Facebook Feed", "FBFEED"),
            ("Instagram Feed", "IGFEED"),
            ("Instagram Stories", "IGST"),
            ("Audience Network", "AN"),
            ("Automático", "AUTO"),
        ],
    },
    "Google": {
        "correspondencia": [
            ("Ampla", "BRD"),
            ("Frase", "PHR"),
            ("Exata", "EXT"),
        ],
    },
}


# Lista canônica fechada pelo especialista de domínio em
# `docs/PLANO-DE-MIDIA.md` §1 — essa versão substitui a lista de trabalho
# que este seed continha antes (códigos `visualizacoes_*` e ordem com os
# quartis junto de Curtidas/Seguidores/Compartilhamentos estavam errados).
# A partir daqui, acrescentar, renomear ou desativar uma métrica é um
# `PATCH /metricas`, nunca uma edição neste arquivo — a lista vive em
# `metricas` (ver `app/models/plano_midia.py::Metrica`), não em código.
#
# Ordem de funil (docs/PLANO-DE-MIDIA.md §1): Impressões → Cliques →
# quartis de vídeo (atenção/exposição, mesma família de Impressões/
# Cliques) → Conversões → Curtidas/Seguidores/Compartilhamentos
# (engajamento social, família separada). "Investimento (R$)" também está
# na tabela do documento (linha 1), mas não entra neste catálogo: já existe
# como coluna dedicada (`valor`) em cada linha do plano, não como meta em
# `PlanoMidiaAnuncio.metas` — duplicá-lo aqui criaria duas formas de
# guardar o mesmo dado.
#
# Códigos dos quartis (atenção, ver docs/PLANO-DE-MIDIA.md §2): `video_inicio`
# é início de reprodução (Meta `video_play_actions` / DV360 "Starts"), NÃO
# o "Views"/"TrueView views" de destaque da plataforma; `video_completo` é
# quartil 100%, NÃO o ThruPlay da Meta. Ver o documento para a tabela de
# mapeamento por plataforma.
METRICAS = [
    ("impressoes", "Impressões", 10),
    ("cliques", "Cliques", 20),
    ("video_inicio", "Vídeo — início", 30),
    ("video_25", "Vídeo — 25%", 40),
    ("video_50", "Vídeo — 50%", 50),
    ("video_75", "Vídeo — 75%", 60),
    ("video_completo", "Vídeo — final (100%)", 70),
    ("conversoes", "Conversões", 80),
    ("curtidas", "Curtidas", 90),
    ("seguidores", "Seguidores", 100),
    ("compartilhamentos", "Compartilhamentos", 110),
]


def garantir_admin_inicial(session: Session) -> bool:
    """Cria o primeiro administrador. Idempotente.

    **Nunca sobrescreve a senha de um usuário que já existe** — mesmo
    princípio do dicionário, que não desfaz o ajuste do analista. Aqui o
    motivo é mais forte: rodar o seed é operação corriqueira (todo pull com
    template novo pede um), e se ele redefinisse a senha, qualquer `python
    -m app.seed` devolveria silenciosamente o acesso a quem conhecesse o
    valor antigo da variável de ambiente.

    Também não promove nem reativa: se o admin inicial foi rebaixado ou
    desativado de propósito, o seed não é o lugar para desfazer isso.

    Devolve `True` se criou.
    """
    login = normalizar_login(settings.admin_login_inicial)
    if session.scalar(select(Usuario).where(Usuario.login == login)) is not None:
        return False

    senha_hash, senha_salt = hash_senha(settings.admin_senha_inicial)
    session.add(
        Usuario(
            nome="Administrador",
            login=login,
            senha_hash=senha_hash,
            senha_salt=senha_salt,
            papel=Papel.ADMIN,
            ativo=True,
        )
    )
    return True


def resetar(session: Session) -> None:
    """Apaga os dados na ordem que respeita as foreign keys."""
    for modelo in (
        # `sessoes` cai por CASCADE junto de `usuarios`. Os eventos são
        # apagados explicitamente: `--reset` é "banco do zero", e o
        # histórico de acesso de um banco que não existe mais não explica
        # nada. Isso é diferente de DELETE /usuarios, onde os eventos ficam.
        EventoAcesso,
        EventoErro,
        Usuario,
        PlanoMidia,  # planos_midia_* cascateiam por FK no banco
        Metrica,
        TaxonomiaGerada,
        Anuncio,
        GrupoAnuncio,
        Campanha,
        TemplateTaxonomia,
        DicionarioAbreviacao,
        LimitePlataforma,
        Plataforma,
    ):
        session.execute(delete(modelo))
    session.commit()


def _garantir_metrica(session: Session, codigo: str, rotulo: str, ordem: int) -> bool:
    """Insere se não existir. Não sobrescreve `rotulo`/`ordem`: o analista
    pode ter ajustado pela tela — mesmo contrato de `_garantir_abreviacao`."""
    if session.scalar(select(Metrica).where(Metrica.codigo == codigo)) is not None:
        return False
    session.add(Metrica(codigo=codigo, rotulo=rotulo, ordem=ordem))
    return True


def _garantir_abreviacao(
    session: Session, plataforma_id, categoria: str, termo: str, abreviacao: str
) -> bool:
    """Insere se não existir. Não sobrescreve: o analista pode ter ajustado."""
    consulta = select(DicionarioAbreviacao).where(
        DicionarioAbreviacao.categoria == categoria,
        DicionarioAbreviacao.termo == termo,
    )
    consulta = consulta.where(
        DicionarioAbreviacao.plataforma_id.is_(None)
        if plataforma_id is None
        else DicionarioAbreviacao.plataforma_id == plataforma_id
    )
    if session.scalar(consulta) is not None:
        return False

    session.add(
        DicionarioAbreviacao(
            plataforma_id=plataforma_id,
            categoria=categoria,
            termo=termo,
            abreviacao=abreviacao,
        )
    )
    return True


def sincronizar_templates(session: Session, plataforma: Plataforma) -> int:
    """Alinha os templates da plataforma com `ESTRUTURA_PADRAO`.

    Quando os tokens **ou o marcador de ausência** divergem, cria a
    **versão seguinte** e desativa a anterior, em vez de editar no lugar: o
    histórico guarda o `template_versao` que usou e precisa continuar
    explicável (D-004).

    O marcador entra nessa comparação porque também é padrão de
    nomenclatura: um template com marcador '' e outro com 'NA' produzem
    nomes com quantidade de partes diferente para a mesma entrada. Editar
    o marcador no lugar tornaria os nomes antigos inexplicáveis.

    Devolve quantas versões novas foram criadas.
    """
    extras = CAMPOS_EXTRAS.get(plataforma.nome, {})
    novas = 0

    for nivel in Nivel:
        desejado = montar_tokens(
            plataforma.sigla, ESTRUTURA_PADRAO[nivel], extras.get(nivel)
        )

        atuais = list(
            session.scalars(
                select(TemplateTaxonomia)
                .where(
                    TemplateTaxonomia.plataforma_id == plataforma.id,
                    TemplateTaxonomia.nivel == nivel,
                )
                .order_by(TemplateTaxonomia.versao.desc())
            )
        )

        if (
            atuais
            and atuais[0].tokens == desejado
            and atuais[0].marcador_ausencia == MARCADOR_AUSENCIA_PADRAO
            and atuais[0].ativo
        ):
            continue

        for antigo in atuais:
            antigo.ativo = False

        session.add(
            TemplateTaxonomia(
                plataforma_id=plataforma.id,
                nivel=nivel,
                separador=atuais[0].separador if atuais else "_",
                tokens=desejado,
                marcador_ausencia=MARCADOR_AUSENCIA_PADRAO,
                versao=(atuais[0].versao + 1) if atuais else 1,
                ativo=True,
            )
        )
        novas += 1

    return novas


def popular(session: Session) -> dict[str, int]:
    criados = {
        "plataformas": 0,
        "limites": 0,
        "templates": 0,
        "versoes_novas": 0,
        "abreviacoes": 0,
        "metricas": 0,
        "admin": 0,
    }

    if garantir_admin_inicial(session):
        criados["admin"] += 1

    for nome, sigla, limite in PLATAFORMAS:
        plataforma = session.scalar(select(Plataforma).where(Plataforma.nome == nome))

        if plataforma is None:
            # criar_plataforma garante os três níveis de uma vez (D-007) — o
            # seed não tem uma cópia própria dessa regra.
            plataforma = criar_plataforma(
                session,
                nome=nome,
                sigla=sigla,
                limites=limite,
                campos_extras=CAMPOS_EXTRAS.get(nome),
            )
            criados["plataformas"] += 1
            criados["limites"] += len(Nivel)
            criados["templates"] += len(Nivel)
        else:
            if plataforma.sigla != sigla:
                plataforma.sigla = sigla
                session.flush()
            criados["versoes_novas"] += sincronizar_templates(session, plataforma)

        for categoria, pares in ABREVIACOES_POR_PLATAFORMA.get(nome, {}).items():
            for termo, abreviacao in pares:
                if _garantir_abreviacao(
                    session, plataforma.id, categoria, termo, abreviacao
                ):
                    criados["abreviacoes"] += 1

    for categoria, pares in ABREVIACOES_GLOBAIS.items():
        for termo, abreviacao in pares:
            if _garantir_abreviacao(session, None, categoria, termo, abreviacao):
                criados["abreviacoes"] += 1

    for codigo, rotulo, ordem in METRICAS:
        if _garantir_metrica(session, codigo, rotulo, ordem):
            criados["metricas"] += 1

    session.commit()
    return criados


def main() -> None:
    reset = "--reset" in sys.argv
    with SessionLocal() as session:
        if reset:
            print("apagando dados existentes...")
            resetar(session)
        criados = popular(session)

    print("seed concluido:")
    for chave, valor in criados.items():
        print(f"  {chave}: +{valor}")


if __name__ == "__main__":
    main()
