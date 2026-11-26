"""Usuários, sessões e observabilidade de acesso (D-014).

Três decisões de modelagem que valem o comentário, porque não são óbvias
lendo só as colunas:

1. **A sessão é opaca e mora no banco.** O cookie carrega um token aleatório
   em claro; aqui fica só o SHA-256 dele. Vazamento do dump não vira sessão
   viva, e — o motivo principal de não ser JWT — o admin consegue derrubar
   um acesso *agora*, bastando escrever `revogada_em`. Token assinado não
   revoga: ele vale até expirar, e "excluí o usuário mas ele continua
   dentro por 8 horas" é exatamente o que a tela de acessos não pode
   admitir.

2. **`eventos_acesso.usuario_id` não tem foreign key**, de propósito, pelo
   mesmo raciocínio de `taxonomias_geradas.entidade_id` (D-004/D-009): o
   histórico de quem entrou onde precisa sobreviver à exclusão do usuário.
   Um DELETE que apagasse a trilha de acesso junto seria a forma mais fácil
   de sumir com o próprio rastro. `sessoes.usuario_id`, ao contrário, **tem**
   FK com ON DELETE CASCADE: sessão de usuário excluído não é histórico, é
   credencial viva, e tem que morrer junto.

3. **`eventos_erro` guarda `codigo_erro`**, o mesmo código estável que
   `app/erros_http.py` devolve ao cliente. Sem ele, a tela de monitoramento
   só saberia contar 422 — com ele, dá para responder "quais termos estão
   faltando no dicionário" sem abrir o log.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Papel(enum.Enum):
    """Papéis de acesso, do menos para o mais poderoso.

    - `BASICO`: usa o produto (gera nome, vê histórico, mexe em plano de
      mídia) mas não enxerga o dicionário nem apaga nada. É o perfil de quem
      opera sem poder alterar o vocabulário que sustenta a nomenclatura.
    - `PLENO`: o produto inteiro, incluindo dicionário e remoções.
    - `ADMIN`: também administra usuários e vê a observabilidade.
    """

    BASICO = "basico"
    PLENO = "pleno"
    ADMIN = "admin"

    @property
    def poder(self) -> int:
        """Posição na escada, para comparar dois papéis.

        Existe porque "rebaixou?" não é `papel != ADMIN`: promover de
        `basico` para `pleno` também satisfaz essa condição, e trataria uma
        promoção como perda de poder — derrubando a sessão de quem acabou de
        ganhar acesso. A pergunta certa é se o poder **diminuiu**, e ela
        precisa de uma ordem explícita.
        """
        return {"basico": 0, "pleno": 1, "admin": 2}[self.value]


class TipoEventoAcesso(enum.Enum):
    LOGIN_OK = "login_ok"
    LOGIN_FALHA = "login_falha"
    LOGOUT = "logout"
    SESSAO_EXPIRADA = "sessao_expirada"


# Um único tipo enum nativo por nome, reaproveitado onde for preciso — mesma
# forma do `nivel_enum` em app/models/taxonomia.py.
papel_enum = Enum(
    Papel,
    name="papel_usuario",
    values_callable=lambda e: [m.value for m in e],
    create_type=True,
)

tipo_evento_acesso_enum = Enum(
    TipoEventoAcesso,
    name="tipo_evento_acesso",
    values_callable=lambda e: [m.value for m in e],
    create_type=True,
)

# User-agent não tem limite prático e ninguém investiga por ele além do
# começo. Truncar aqui evita que um cabeçalho absurdo engorde a tabela de
# eventos, que é a que mais cresce.
TAMANHO_AGENTE = 300


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    # A identidade de login é um **login**, não um e-mail: o produto não
    # envia e-mail e não tem recuperação de senha por link, então uma coluna
    # de e-mail seria campo morto. Normalizado para minúsculas na escrita
    # (ver `app/autorizacao.py::normalizar_login`) — caixa alta digitada por
    # engano não pode virar um segundo usuário.
    login: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    senha_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    papel: Mapped[Papel] = mapped_column(papel_enum, nullable=False)
    # Desativar em vez de excluir preserva a autoria dos registros que
    # apontam para este id sem manter a credencial viva.
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ultimo_acesso_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessoes: Mapped[list["Sessao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class Sessao(Base):
    """Sessão opaca. O cookie tem o token; aqui fica só o hash dele."""

    __tablename__ = "sessoes"
    __table_args__ = (
        Index("ix_sessao_usuario", "usuario_id"),
        # A varredura de "sessões ativas agora" filtra por estas duas.
        Index("ix_sessao_expiracao", "expira_em", "revogada_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # SHA-256 hexadecimal do token. Único porque o token é único; a busca do
    # request passa por aqui, então o índice não é opcional.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agente: Mapped[str | None] = mapped_column(String(TAMANHO_AGENTE), nullable=True)

    usuario: Mapped[Usuario] = relationship(back_populates="sessoes")


class EventoAcesso(Base):
    """Trilha de login/logout. Sem FK para `usuarios` de propósito."""

    __tablename__ = "eventos_acesso"
    __table_args__ = (
        Index("ix_evento_acesso_ocorrido", "ocorrido_em"),
        Index("ix_evento_acesso_tipo", "tipo", "ocorrido_em"),
        Index("ix_evento_acesso_usuario", "usuario_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ocorrido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    tipo: Mapped[TipoEventoAcesso] = mapped_column(tipo_evento_acesso_enum, nullable=False)
    # Guardado mesmo quando o login não existe: é justamente a tentativa
    # contra um login inexistente que denuncia varredura de credenciais.
    login_tentado: Mapped[str | None] = mapped_column(String(60), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agente: Mapped[str | None] = mapped_column(String(TAMANHO_AGENTE), nullable=True)
    detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)


class EventoErro(Base):
    """Uma linha por resposta com status >= 400.

    Grava o mesmo `request_id` que sai no cabeçalho `X-Request-ID`, então a
    linha da tela de monitoramento e a linha do log são o mesmo evento vistos
    de dois lugares.
    """

    __tablename__ = "eventos_erro"
    __table_args__ = (
        Index("ix_evento_erro_ocorrido", "ocorrido_em"),
        Index("ix_evento_erro_status", "status", "ocorrido_em"),
        Index("ix_evento_erro_request", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ocorrido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    caminho: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    # O `erro` estável do corpo (`termo_desconhecido`, `ultimo_admin`, ...).
    # Nulo quando a resposta não seguiu esse contrato — um 404 do FastAPI,
    # por exemplo.
    codigo_erro: Mapped[str | None] = mapped_column(String(60), nullable=True)
    mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    duracao_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
