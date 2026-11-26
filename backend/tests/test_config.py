"""Testes da configuração.

O que importa aqui é a rede de segurança: subir em produção com dado de
desenvolvimento tem que falhar no boot, não gerar um sistema aberto que
ninguém percebe.

Todas as instâncias usam `_env_file=None` e zeram `database_url` — sem
isso, o `.env` ou a `DATABASE_URL` exportada na máquina entrariam no meio
e o teste passaria (ou falharia) por motivo errado.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


def montar(**kwargs) -> Settings:
    base = {
        "_env_file": None,
        "database_url": None,
        "debug": True,
        "postgres_password": "senha-forte",
        "cors_origins": "https://mediabuild.exemplo.com",
        # Sem isto, os testes de `debug=False` bateriam na guarda da senha
        # do admin inicial (D-014) e falhariam pelo motivo errado.
        "admin_senha_inicial": "senha-admin-forte",
    }
    return Settings(**{**base, **kwargs})


# --------------------------------------------------------------------------
# DSN
# --------------------------------------------------------------------------

def test_monta_o_dsn_a_partir_das_partes():
    s = montar(
        postgres_user="u", postgres_password="p", postgres_host="h",
        postgres_port=6543, postgres_db="b",
    )
    assert s.url_do_banco == "postgresql+psycopg://u:p@h:6543/b"


def test_database_url_inteiro_tem_precedencia():
    """Postgres gerenciado costuma entregar a URL pronta."""
    s = montar(
        database_url="postgresql+psycopg://outro:x@nuvem:5432/prod",
        postgres_host="ignorado",
    )
    assert s.url_do_banco == "postgresql+psycopg://outro:x@nuvem:5432/prod"


# --------------------------------------------------------------------------
# proteção contra defaults de desenvolvimento
# --------------------------------------------------------------------------

def test_debug_true_aceita_os_defaults_de_desenvolvimento():
    """`docker compose up` num clone novo não pode exigir configuração."""
    s = Settings(_env_file=None, database_url=None, debug=True)
    assert "mdbd" in s.url_do_banco
    assert s.origens_permitidas == ["http://localhost:5173"]


def test_producao_recusa_a_senha_de_exemplo():
    with pytest.raises(ValidationError, match="senha de exemplo"):
        montar(debug=False, postgres_password="mdbd")


def test_producao_recusa_a_senha_de_exemplo_escondida_na_url():
    """O jeito fácil de furar a checagem seria passar a URL inteira."""
    with pytest.raises(ValidationError, match="senha de exemplo"):
        montar(debug=False, database_url="postgresql+psycopg://mdbd:mdbd@db:5432/mediabuild")


def test_producao_recusa_cors_apontando_para_localhost():
    with pytest.raises(ValidationError, match="localhost"):
        montar(debug=False, cors_origins="http://localhost:5173")


def test_producao_recusa_a_senha_de_exemplo_do_admin_inicial():
    """O admin inicial é conta de acesso total, e o placeholder está escrito
    no .env.example — ou seja, é público. Subir exposto com ele é pior que
    subir com a senha do banco de exemplo (D-014)."""
    with pytest.raises(ValidationError, match="ADMIN_SENHA_INICIAL"):
        montar(debug=False, admin_senha_inicial="mudar-agora")


def test_producao_aceita_um_login_de_admin_qualquer():
    """O login não entra na guarda: ele é escolha do usuário, não segredo.
    Recusar 'admin.mediabuilder' em produção seria recusar a configuração
    que o próprio projeto sugere."""
    s = montar(debug=False, admin_login_inicial="admin.mediabuilder")
    assert s.admin_login_inicial == "admin.mediabuilder"


def test_sessao_tem_duracao_padrao_de_doze_horas():
    assert montar().sessao_duracao_horas == 12


def test_producao_aceita_configuracao_real():
    s = montar(debug=False)
    assert s.debug is False


# --------------------------------------------------------------------------
# CORS e logging
# --------------------------------------------------------------------------

def test_cors_aceita_lista_separada_por_virgula():
    """Formato que se escreve à mão num .env."""
    s = montar(cors_origins="https://a.exemplo.com, https://b.exemplo.com")
    assert s.origens_permitidas == ["https://a.exemplo.com", "https://b.exemplo.com"]


def test_cors_aceita_json():
    """Formato que ferramentas de deploy costumam gerar."""
    s = montar(cors_origins='["https://a.exemplo.com", "https://b.exemplo.com"]')
    assert s.origens_permitidas == ["https://a.exemplo.com", "https://b.exemplo.com"]


def test_log_em_json_segue_o_debug_por_padrao():
    assert montar(debug=True).log_em_json is False
    assert montar(debug=False).log_em_json is True


def test_log_json_explicito_vence_o_debug():
    assert montar(debug=True, log_json=True).log_em_json is True
    assert montar(debug=False, log_json=False).log_em_json is False


def test_string_vazia_conta_como_nao_definida():
    """O docker-compose expande ${LOG_JSON:-} para "" quando a variável não
    existe no host; sem tratar isso, o container não subiria."""
    s = montar(log_json="", database_url="")
    assert s.log_json is None
    assert s.database_url is None
    assert s.log_em_json is False  # cai no default derivado do debug


# --------------------------------------------------------------------------
# leitura pelas variáveis de ambiente
# --------------------------------------------------------------------------
# Os testes acima passam kwargs, que pulam a fonte de ambiente do
# pydantic-settings. Foi exatamente por isso que a primeira versão do
# `cors_origins` passou nos testes e derrubou o container: campos de tipo
# complexo sofrem JSON-parse na leitura da variável, antes dos validators.

def test_le_cors_de_variavel_de_ambiente_sem_json(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.exemplo.com,https://b.exemplo.com")
    s = Settings(_env_file=None)
    assert s.origens_permitidas == ["https://a.exemplo.com", "https://b.exemplo.com"]


def test_le_cors_de_variavel_de_ambiente_em_json(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.exemplo.com"]')
    s = Settings(_env_file=None)
    assert s.origens_permitidas == ["https://a.exemplo.com"]


def test_le_o_ambiente_que_o_docker_compose_monta(monkeypatch):
    """Reproduz as variáveis do serviço `api` do docker-compose.yml,
    incluindo o LOG_JSON vazio de `${LOG_JSON:-}`."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://mdbd:mdbd@db:5432/mediabuild")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_JSON", "")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    s = Settings(_env_file=None)

    assert s.debug is True
    assert s.url_do_banco.endswith("@db:5432/mediabuild")
    assert s.origens_permitidas == ["http://localhost:5173"]
    assert s.log_em_json is False
