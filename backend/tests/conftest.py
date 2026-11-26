import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import observabilidade
from app.autorizacao import NOME_COOKIE, agora, hash_senha, hash_token
from app.db import engine, get_session
from app.main import app
from app.models import Papel, Sessao, Usuario

# Conjuntos completos de campos por nível, na estrutura da planilha do
# cliente (a planilha de taxonomia de referência). Ficam aqui porque quase todo teste de banco
# precisa preencher um nível inteiro — repetir sete campos em cada um
# esconderia o que o teste está de fato verificando.
CAMPOS_CAMPANHA = {
    "nome_campanha": "ALV27",
    "empresa": "Loja Alfa",
    "canal": "Instagram",
    "objetivo": "Conversão",
    "mes": "Agosto",
}
CAMPOS_GRUPO = {
    "sexo": "Feminino",
    "idade": "25-34",
    "interesse_1": "Bolsas",
    "interesse_2": "Moda",
    "regiao": "Sudeste",
    "cidade": "Rio de Janeiro",
    "segmentacao": "Remarketing",
}
CAMPOS_ANUNCIO = {
    "formato": "Vídeo",
    "dimensao": "1200x600",
    "tipo_compra": "CPC",
    "nome_criativo": "fivela",
    "secundagem": "15s",
    "versao": "C",
}

# Nomes que esses conjuntos produzem no Meta, sem o match ID do fim.
# O 'NA' final é o marcador dos opcionais que ficaram em branco: 'funil' na
# campanha e 'posicionamento' no grupo (extra do Meta). Ele está aí de
# propósito — é o que mantém a quantidade de partes fixa por nível.
NOME_CAMPANHA = "ALV27_ALF_METAA_INSTA_CV_AGO_NA"
NOME_GRUPO = "F_25-34_BOLSA_MODA_SUD_RJ_RMKT_NA"
NOME_ANUNCIO = "VID_1200X600_CPC_FIVELA_15S_C"

# Senha dos usuários de teste, com o hash calculado UMA VEZ para a suíte
# inteira. scrypt custa ~50 ms de propósito (é o ponto dele), e a suíte cria
# um usuário por teste — recalcular em cada um acrescentaria dezenas de
# segundos sem testar nada além do que os testes de login já cobrem.
SENHA_DE_TESTE = "senha-de-teste"
_HASH_DE_TESTE, _SALT_DE_TESTE = hash_senha(SENHA_DE_TESTE)


@pytest.fixture(scope="session")
def _conexao():
    """Pula os testes de banco se não houver Postgres acessível."""
    try:
        conexao = engine.connect()
        conexao.execute(text("SELECT 1"))
        # O SELECT acima abre uma transação implícita; sem encerrá-la, o
        # begin() de cada teste falharia com "already initialized".
        conexao.rollback()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres indisponivel: {exc}", allow_module_level=True)
    yield conexao
    conexao.close()


@pytest.fixture
def session(_conexao):
    """Sessão dentro de uma transação revertida ao fim de cada teste,
    para que os testes não sujem o banco de desenvolvimento."""
    transacao = _conexao.begin()
    with Session(bind=_conexao, expire_on_commit=False, join_transaction_mode="create_savepoint") as s:
        yield s
    transacao.rollback()


# --------------------------------------------------------------------------
# eventos de erro
# --------------------------------------------------------------------------

class _SessaoDescartavel:
    """Sessão de mentira, que aceita tudo e não guarda nada.

    `app/observabilidade.py` grava evento de erro numa sessão **própria**,
    de propósito: a da requisição pode estar em rollback justamente por
    causa do erro. Só que "sessão própria" significa fora da transação que
    a suíte reverte — então, sem isto, cada 404 testado deixaria uma linha
    permanente no banco de desenvolvimento, e são muitos.

    Quem precisa de fato conferir o que foi gravado usa a fixture
    `eventos_erro_no_banco`, que troca isto por uma sessão real presa à
    transação do teste.
    """

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def add(self, _objeto):
        pass

    def commit(self):
        pass


@pytest.fixture(autouse=True)
def _nao_gravar_eventos_de_erro(monkeypatch):
    """Vale para a suíte inteira, inclusive para os testes que não tocam o
    banco (`test_logs.py` sobe um app próprio com o middleware)."""
    monkeypatch.setattr(observabilidade, "fabrica_de_sessao", _SessaoDescartavel)


@pytest.fixture
def eventos_erro_no_banco(session, monkeypatch):
    """Faz o registro de evento de erro cair na transação do teste.

    `join_transaction_mode="create_savepoint"` permite que esta segunda
    sessão dê `commit()` sobre a mesma conexão sem encerrar a transação
    externa: o commit vira liberação de savepoint, e o rollback do fim do
    teste leva tudo embora.
    """
    conexao = session.get_bind()

    def fabrica():
        return Session(bind=conexao, expire_on_commit=False, join_transaction_mode="create_savepoint")

    monkeypatch.setattr(observabilidade, "fabrica_de_sessao", fabrica)
    return fabrica


# --------------------------------------------------------------------------
# autenticação (D-014)
# --------------------------------------------------------------------------

def criar_usuario(session: Session, papel: Papel, login: str | None = None) -> Usuario:
    """Usuário ativo, com a senha `SENHA_DE_TESTE`.

    O login leva um sufixo aleatório porque a coluna é UNIQUE e vários
    testes criam mais de um usuário na mesma transação.
    """
    usuario = Usuario(
        nome=f"Teste {papel.value}",
        login=login or f"{papel.value}.{uuid.uuid4().hex[:8]}",
        senha_hash=_HASH_DE_TESTE,
        senha_salt=_SALT_DE_TESTE,
        papel=papel,
        ativo=True,
    )
    session.add(usuario)
    session.commit()
    return usuario


def abrir_sessao(session: Session, usuario: Usuario, horas: int = 12) -> str:
    """Cria a linha em `sessoes` e devolve o token em claro do cookie.

    Direto no banco, sem passar por `POST /auth/login`: o caminho do login
    é testado à parte, e fazê-lo aqui custaria um scrypt por teste da suíte
    inteira. O que se quer destas fixtures é *estar autenticado*, não
    reexercitar a autenticação.
    """
    token = uuid.uuid4().hex + uuid.uuid4().hex
    session.add(
        Sessao(
            token_hash=hash_token(token),
            usuario_id=usuario.id,
            expira_em=agora() + timedelta(hours=horas),
            ip="127.0.0.1",
            agente="pytest",
        )
    )
    session.commit()
    return token


def _cliente_com_papel(session: Session, papel: Papel | None):
    """TestClient amarrado à sessão transacional do teste, autenticado (ou
    não, com `papel=None`) — ver a docstring de `cliente`."""
    app.dependency_overrides[get_session] = lambda: session
    cliente = TestClient(app)
    if papel is not None:
        usuario = criar_usuario(session, papel)
        cliente.cookies.set(NOME_COOKIE, abrir_sessao(session, usuario))
        # Guardado no próprio cliente para que o teste possa comparar ids
        # (auto-exclusão, autoria de evento) sem recriar o usuário.
        cliente.usuario = usuario
    return cliente


@pytest.fixture
def cliente(session):
    """TestClient amarrado à sessão transacional do teste, **autenticado
    como admin**, para que nada escrito pela API sobreviva ao teste.

    Vem autenticado porque, a partir do D-014, praticamente toda rota exige
    sessão: sem isto os ~340 testes anteriores a esta fase passariam a
    receber 401 em massa. O conserto é na fixture e **não** afrouxando a
    autorização das rotas — se um dia esta fixture deixar de autenticar, o
    certo é que a suíte inteira quebre, e não que a API deixe de proteger.

    Admin, e não um papel menor, porque é o único que alcança toda a API; a
    cobertura de quem *não* pode alcançar está nas fixtures irmãs.
    """
    yield _cliente_com_papel(session, Papel.ADMIN)
    app.dependency_overrides.clear()


@pytest.fixture
def cliente_pleno(session):
    """Autenticado como `pleno`: o produto inteiro, dicionário e DELETEs,
    mas nada de `/usuarios` nem `/admin/*`."""
    yield _cliente_com_papel(session, Papel.PLENO)
    app.dependency_overrides.clear()


@pytest.fixture
def cliente_basico(session):
    """Autenticado como `basico`: sem `/dicionario` e sem nenhum DELETE."""
    yield _cliente_com_papel(session, Papel.BASICO)
    app.dependency_overrides.clear()


@pytest.fixture
def cliente_anonimo(session):
    """Sem cookie de sessão. Tudo que não for `/health` deve dar 401."""
    yield _cliente_com_papel(session, None)
    app.dependency_overrides.clear()
