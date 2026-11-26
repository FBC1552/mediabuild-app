"""Configuração da aplicação.

Tudo vem de variável de ambiente. Os defaults aqui são de
**desenvolvimento local** e existem só para que `docker compose up` funcione
num clone novo sem passo prévio.

A proteção contra levar esses defaults para produção é o
`_recusar_defaults_de_desenvolvimento()`: com `DEBUG=false`, subir com a
senha de exemplo derruba a aplicação no import, não em runtime.
"""

import json
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor do .env.example. Serve só para reconhecê-lo e recusá-lo fora de dev.
_SENHA_DE_EXEMPLO = "mdbd"

# Placeholder da senha do admin inicial no .env.example. Mesma lógica:
# reconhecer para recusar. Não é lista negra de senhas fracas — é a checagem
# de que alguém trocou o valor que veio no repositório. A senha real nunca é
# versionada: mora no `.env`, que o .gitignore cobre.
_SENHA_ADMIN_DE_EXEMPLO = "mudar-agora"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MediaBuild"
    debug: bool = False

    # --- banco -----------------------------------------------------------
    # Em partes, e não só uma URL, porque o docker-compose já monta as
    # variáveis assim e um Postgres gerenciado na nuvem entrega os mesmos
    # campos separados. `database_url` continua aceita e tem precedência.
    postgres_user: str = "mdbd"
    postgres_password: str = _SENHA_DE_EXEMPLO
    postgres_db: str = "mediabuild"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str | None = None

    # --- autenticação (D-014) ---------------------------------------------
    # Duração da sessão opaca. 12 horas cobre um dia de trabalho sem obrigar
    # a relogar no meio da tarde, e é curta o bastante para que um cookie
    # esquecido numa máquina compartilhada não valha até a semana seguinte.
    # A revogação imediata continua existindo pelo admin — este número é o
    # teto para quem ninguém revogou.
    sessao_duracao_horas: int = 12

    # Credencial do primeiro administrador, criada pelo `python -m app.seed`.
    # A identidade é um **login**, não um e-mail: o produto não envia
    # e-mail e não tem recuperação de senha por link, então uma coluna de
    # e-mail seria um campo que ninguém preenche e ninguém usa.
    #
    # O seed **nunca** sobrescreve a senha de um admin que já existe, então
    # trocar estas variáveis depois do primeiro boot não faz nada — a troca
    # de senha é `PATCH /usuarios/{id}`, feita por um admin.
    admin_login_inicial: str = "admin.mediabuilder"
    admin_senha_inicial: str = _SENHA_ADMIN_DE_EXEMPLO

    # --- observabilidade --------------------------------------------------
    log_level: str = "INFO"
    # JSON em produção (agregador lê); texto legível em dev.
    log_json: bool | None = None

    # --- tempo ------------------------------------------------------------
    # Fuso em que o analista pensa. **Não** é o fuso do servidor: o banco
    # grava `criado_em` em UTC e a nuvem provavelmente rodará em UTC
    # (docs/NUVEM.md), então ler o relógio da máquina daria o resultado
    # certo no notebook do analista e errado em produção. Filtro de data é
    # entrada humana ("hoje"), e "hoje" só existe dentro de um fuso — que
    # por isso é configuração explícita, e não inferência.
    fuso_horario: str = "America/Sao_Paulo"

    # --- rede -------------------------------------------------------------
    # `str` e não `list[str]`: o pydantic-settings tenta fazer JSON-parse de
    # campos de tipo complexo na **leitura** da variável, antes de qualquer
    # validator, e `CORS_ORIGINS=http://localhost:5173` não é JSON válido.
    #
    # O nome do campo é igual ao da variável de ambiente de propósito: com
    # um `validation_alias`, um kwarg passado pelo nome do atributo perde
    # precedência para o ambiente, o que torna a configuração difícil de
    # sobrescrever em teste. A lista sai de `origens_permitidas`.
    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url", "log_json", mode="before")
    @classmethod
    def _vazio_e_ausente(cls, valor: Any) -> Any:
        """Trata string vazia como não definida.

        O docker-compose expande `${LOG_JSON:-}` para string vazia quando a
        variável não existe no host; sem isto, o parse de `bool | None`
        falharia e o container não subiria.
        """
        return None if isinstance(valor, str) and not valor.strip() else valor

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url_do_banco(self) -> str:
        """DSN efetivo. `DATABASE_URL` inteiro vence as partes."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @field_validator("fuso_horario")
    @classmethod
    def _fuso_existe(cls, valor: str) -> str:
        """Falha no boot, não na primeira consulta com filtro de data."""
        try:
            ZoneInfo(valor)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(
                f"FUSO_HORARIO='{valor}' não é um fuso IANA conhecido "
                "(exemplos: 'America/Sao_Paulo', 'UTC')."
            ) from exc
        return valor

    @property
    def zona(self) -> ZoneInfo:
        """Fuso da aplicação. Property simples e não `computed_field` porque
        `ZoneInfo` não tem schema Pydantic — e isto não é parte da config
        serializável, é objeto de uso interno."""
        return ZoneInfo(self.fuso_horario)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def log_em_json(self) -> bool:
        return not self.debug if self.log_json is None else self.log_json

    @computed_field  # type: ignore[prop-decorator]
    @property
    def origens_permitidas(self) -> list[str]:
        """`CORS_ORIGINS` como lista.

        Aceita separado por vírgula, que é o que se escreve à mão num
        `.env`, e JSON, que é o que ferramentas de deploy costumam gerar.
        """
        bruto = self.cors_origins.strip()
        if bruto.startswith("["):
            return [str(o).strip() for o in json.loads(bruto) if str(o).strip()]
        return [o.strip() for o in bruto.split(",") if o.strip()]

    @model_validator(mode="after")
    def _recusar_defaults_de_desenvolvimento(self) -> "Settings":
        """Falha no boot, não em runtime, se subir em produção com dado de exemplo."""
        if self.debug:
            return self

        problemas = []

        # Checa o DSN efetivo, não só as partes: passar um DATABASE_URL
        # inteiro com a senha de exemplo é o jeito fácil de furar isto.
        if f":{_SENHA_DE_EXEMPLO}@" in self.url_do_banco:
            problemas.append("a senha do banco ainda é a senha de exemplo")
        if any("localhost" in origem for origem in self.origens_permitidas):
            problemas.append("CORS_ORIGINS aponta para localhost")

        # O admin inicial é conta de acesso total. Subir exposto com o
        # placeholder que está no .env.example do repositório é o mesmo tipo
        # de falha que a senha do banco — e mais barata de explorar, porque
        # o valor é público. O login não entra na checagem: ele é escolha do
        # usuário, não segredo.
        if self.admin_senha_inicial == _SENHA_ADMIN_DE_EXEMPLO:
            problemas.append("ADMIN_SENHA_INICIAL ainda é a senha de exemplo")

        if problemas:
            raise ValueError(
                "Configuração de desenvolvimento com DEBUG=false: "
                + "; ".join(problemas)
                + ". Defina as variáveis de ambiente do ambiente real "
                "ou rode com DEBUG=true."
            )
        return self


settings = Settings()
