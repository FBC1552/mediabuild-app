"""Autenticação por sessão opaca e autorização por papel (D-014).

Duas coisas moram aqui: o que sabe transformar senha em hash e cookie em
usuário, e as dependências do FastAPI que as rotas penduram.

**Por que sessão em banco e não JWT.** O requisito que decidiu foi
"o admin exclui um acesso e a sessão cai agora". Token assinado não revoga:
ele é válido porque a assinatura confere, e continuaria valendo até
expirar. Fazer JWT revogar exige uma lista de revogados consultada a cada
requisição — que é uma tabela de sessões com passos a mais. Então é a
tabela de sessões, direto.

**Por que `hashlib.scrypt` e não passlib/bcrypt/argon2.** A stack é travada
(D-002) e scrypt está na biblioteca padrão desde o Python 3.6, com custo de
memória configurável — que é justamente a propriedade que derruba ataque em
GPU. Uma dependência nova aqui traria superfície de supply chain para
resolver um problema que a stdlib já resolve.
"""

import hashlib
import hmac
import logging
import secrets
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.erros_acesso import NaoAutenticado, PermissaoInsuficiente, SessaoExpirada
from app.models import Papel, Sessao, Usuario
from app.models.acesso import TAMANHO_AGENTE

logger = logging.getLogger("mediabuild.acesso")

NOME_COOKIE = "mdbd_sessao"

# Parâmetros do scrypt. `n` é o custo de CPU/memória: 2**14 com r=8 usa
# ~16 MB por verificação, o que é irrelevante para um login humano e caro
# o bastante para tornar força bruta paralela desinteressante. Ficam como
# constantes nomeadas porque, se um dia subirem, o hash antigo precisa
# continuar verificável — e aí o caminho é gravar os parâmetros junto do
# hash, não trocar o número aqui e invalidar todas as senhas em silêncio.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64

# O id do usuário da requisição, para que o registro de erro
# (`app/observabilidade.py`) saiba de quem foi a falha sem receber o
# usuário como parâmetro. Mesmo motivo do `request_id` em `app/logs.py`.
_usuario_id: ContextVar[UUID | None] = ContextVar("usuario_id", default=None)


def usuario_id_atual() -> UUID | None:
    return _usuario_id.get()


def definir_usuario_atual(usuario_id: UUID | None) -> None:
    _usuario_id.set(usuario_id)


# --------------------------------------------------------------------------
# senha
# --------------------------------------------------------------------------

def normalizar_login(login: str) -> str:
    """Caixa e espaço em volta não podem criar dois usuários distintos.

    A forma aceita (`^[a-z0-9._-]{3,60}$`) é validada no schema, em
    `app/schemas.py::PADRAO_LOGIN`; aqui é só a normalização, que precisa
    rodar também no caminho do login, onde o valor digitado ainda não passou
    por validação de formato.
    """
    return login.strip().lower()


def hash_senha(senha: str, salt: str | None = None) -> tuple[str, str]:
    """Devolve `(hash_hex, salt_hex)`. Salt novo por usuário quando omitido.

    Salt por usuário e não global: sem ele, dois usuários com a mesma senha
    teriam o mesmo hash, e quebrar um quebraria todos de uma vez.
    """
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    derivado = hashlib.scrypt(
        senha.encode("utf-8"),
        salt=salt_bytes,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        # O scrypt consome ~128*N*r bytes. O default de `maxmem` no OpenSSL
        # é 32 MB, mas a checagem é estrita (`>`), então passar o valor
        # exato falha por um byte — daí o dobro.
        maxmem=128 * _SCRYPT_N * _SCRYPT_R * 2,
    )
    return derivado.hex(), salt_bytes.hex()


def conferir_senha(senha: str, senha_hash: str, senha_salt: str) -> bool:
    """Comparação em tempo constante.

    `==` sobre string vaza, pelo tempo de resposta, quantos caracteres do
    hash bateram — o suficiente para reconstruí-lo byte a byte.
    """
    try:
        calculado, _ = hash_senha(senha, senha_salt)
    except ValueError:
        # Salt corrompido no banco. Trata como senha errada em vez de 500:
        # o login não pode virar canal de diagnóstico do schema.
        return False
    return hmac.compare_digest(calculado, senha_hash)


# --------------------------------------------------------------------------
# sessão
# --------------------------------------------------------------------------

# Alfabeto da senha provisória, sem os caracteres que se confundem quando
# alguém lê a senha na tela e digita em outro lugar (ou dita por telefone):
# 0/O, 1/l/I, 5/S, 2/Z. A senha é temporária e vai ser transcrita à mão pelo
# menos uma vez — ambiguidade aqui vira chamado de "não aceita minha senha".
_ALFABETO_PROVISORIO = "ABCDEFGHJKLMNPQRTUVWXYabcdefghijkmnpqrtuvwxy346789"


def gerar_senha_provisoria(grupos: int = 3, tamanho: int = 4) -> str:
    """Senha temporária legível, no formato `XXXX-XXXX-XXXX`.

    12 caracteres de um alfabeto de 49 dão ~67 bits de entropia — muito
    acima do necessário para um valor que existe até o primeiro login, e
    ainda assim transcrevível sem erro.
    """
    return "-".join(
        "".join(secrets.choice(_ALFABETO_PROVISORIO) for _ in range(tamanho))
        for _ in range(grupos)
    )


def gerar_token() -> str:
    """Token do cookie. 32 bytes de `secrets` — não adivinhável."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 do token, que é o que vai para o banco.

    Sem KDF caro aqui de propósito: diferente de senha, o token já tem 256
    bits de entropia, então não há dicionário para tentar. E este hash é
    calculado em **toda** requisição autenticada — scrypt aqui custaria
    16 MB por request sem comprar segurança nenhuma.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ip_do_pedido(request: Request) -> str | None:
    """IP do cliente, respeitando o proxy reverso previsto em docs/NUVEM.md."""
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None


def agente_do_pedido(request: Request) -> str | None:
    agente = request.headers.get("user-agent")
    return agente[:TAMANHO_AGENTE] if agente else None


def agora() -> datetime:
    return datetime.now(UTC)


def criar_sessao(session: Session, usuario: Usuario, request: Request) -> str:
    """Abre uma sessão e devolve o token **em claro**, que só o cookie verá."""
    token = gerar_token()
    session.add(
        Sessao(
            token_hash=hash_token(token),
            usuario_id=usuario.id,
            expira_em=agora() + timedelta(hours=settings.sessao_duracao_horas),
            ip=ip_do_pedido(request),
            agente=agente_do_pedido(request),
        )
    )
    return token


def revogar_sessoes(session: Session, usuario_id: UUID) -> int:
    """Derruba todas as sessões vivas de um usuário. Devolve quantas caíram.

    Chamada em troca de senha, desativação e rebaixamento de papel: nos três
    casos a sessão aberta representa uma autorização que acabou de deixar de
    valer, e deixá-la de pé transformaria a mudança em "vale no próximo
    login" — que não é o que o admin pediu ao clicar.
    """
    resultado = session.execute(
        update(Sessao)
        .where(
            Sessao.usuario_id == usuario_id,
            Sessao.revogada_em.is_(None),
            Sessao.expira_em > agora(),
        )
        .values(revogada_em=agora())
    )
    return resultado.rowcount or 0


def gravar_cookie(response: Response, token: str) -> None:
    """Cookie da sessão.

    - `httponly`: JavaScript não lê, então XSS não rouba a sessão.
    - `samesite=lax`: bloqueia CSRF nas escritas (POST/PATCH/DELETE
      cross-site não levam o cookie) sem quebrar a navegação normal.
    - `secure` só fora do debug: em `http://localhost` o navegador
      **descarta** cookie `Secure`, e ligar isto em dev deixaria o login
      quebrado sem mensagem nenhuma. Ver docs/NUVEM.md: HTTPS passa a ser
      obrigatório na nuvem justamente por causa desta linha.
    """
    response.set_cookie(
        NOME_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        path="/",
        max_age=settings.sessao_duracao_horas * 3600,
    )


def limpar_cookie(response: Response) -> None:
    response.delete_cookie(NOME_COOKIE, path="/", httponly=True, samesite="lax")


@dataclass(frozen=True)
class Resolucao:
    """Resultado de ler o cookie: ou a sessão viva, ou o motivo de não ser.

    O motivo existe porque 401 não é um estado só. "Nunca houve sessão" e
    "havia e acabou" pedem reações diferentes na tela (ver
    `app/erros_acesso.py`), e essa distinção precisa nascer aqui, onde a
    informação existe — reconstruí-la depois seria adivinhação.
    """

    sessao: Sessao | None = None
    usuario: Usuario | None = None
    # None quando deu certo; senão 'ausente' ou 'expirada'.
    motivo: str | None = None

    @property
    def valida(self) -> bool:
        return self.usuario is not None


def resolver_sessao(session: Session, token: str | None) -> Resolucao:
    """Sessão viva e usuário ativo, ou o motivo da recusa.

    Uma sessão expirada é **revogada aqui** e registra `sessao_expirada` na
    trilha de acesso. Revogar no primeiro contato é o que faz o evento sair
    uma vez, e não a cada requisição do cliente que ficou com o cookie velho
    numa aba aberta desde ontem.
    """
    if not token:
        return Resolucao(motivo="ausente")

    # Import tardio: `observabilidade` importa daqui (para o id do usuário
    # da requisição) e o topo do módulo fecharia o ciclo.
    from app.observabilidade import registrar_evento_acesso

    sessao = session.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
    if sessao is None:
        # Cookie que não corresponde a nada: sessão nenhuma, não sessão
        # vencida. Pode ser um cookie de outro ambiente ou lixo.
        return Resolucao(motivo="ausente")

    if sessao.revogada_em is not None:
        # Revogada por logout ou pelo admin (troca de senha, desativação,
        # rebaixamento). Do ponto de vista de quem está na tela é o mesmo
        # que ter vencido: havia sessão, acabou.
        return Resolucao(motivo="expirada")

    if sessao.expira_em <= agora():
        sessao.revogada_em = agora()
        registrar_evento_acesso(
            session,
            tipo="sessao_expirada",
            usuario_id=sessao.usuario_id,
            detalhe="sessão vencida ao ser apresentada",
        )
        session.commit()
        return Resolucao(motivo="expirada")

    usuario = session.get(Usuario, sessao.usuario_id)
    if usuario is None or not usuario.ativo:
        # Conta apagada ou desativada no meio da sessão. Não é
        # 'conta_desativada': aquele código é do login, onde a pessoa já
        # provou a senha. Aqui ela só tem um cookie, e dizer "sua conta foi
        # desativada" para quem só tem um cookie roubado é informação de
        # graça.
        return Resolucao(motivo="ausente")

    return Resolucao(sessao=sessao, usuario=usuario)


# --------------------------------------------------------------------------
# dependências
# --------------------------------------------------------------------------

def _publicar(request: Request, usuario: Usuario) -> None:
    """Deixa o usuário visível para o resto da requisição.

    Guardado no estado do request para que outras dependências da mesma
    requisição (o guarda de DELETE, por exemplo) não repitam a consulta —
    e porque `scope["state"]` é compartilhado com o middleware de log, que
    precisa do autor para gravar o evento de erro (ver `app/logs.py`).
    """
    definir_usuario_atual(usuario.id)
    request.state.usuario = usuario
    request.state.usuario_id = usuario.id


def usuario_atual(request: Request, session: Session = Depends(get_session)) -> Usuario:
    """Usuário da sessão, ou 401 com o código que diz qual dos dois 401 é."""
    resolvido = resolver_sessao(session, request.cookies.get(NOME_COOKIE))
    if not resolvido.valida:
        raise SessaoExpirada() if resolvido.motivo == "expirada" else NaoAutenticado()

    _publicar(request, resolvido.usuario)
    return resolvido.usuario


def usuario_opcional(
    request: Request, session: Session = Depends(get_session)
) -> Usuario | None:
    """Como `usuario_atual`, mas sem 401. Para rota que muda de forma quando
    há sessão em vez de exigir uma."""
    resolvido = resolver_sessao(session, request.cookies.get(NOME_COOKIE))
    if not resolvido.valida:
        return None
    _publicar(request, resolvido.usuario)
    return resolvido.usuario


def exige_papel(*papeis: Papel) -> Callable[..., Usuario]:
    """Dependência que só deixa passar quem tem um dos papéis.

    403 e não 401: o pedido foi autenticado, ele só não é autorizado.
    Trocar por 401 faria o frontend mandar o usuário para a tela de login
    para resolver algo que login nenhum resolve.
    """
    permitidos = set(papeis)

    def dependencia(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if usuario.papel not in permitidos:
            raise PermissaoInsuficiente()
        return usuario

    return dependencia


def exige_acesso_ao_produto(
    request: Request, usuario: Usuario = Depends(usuario_atual)
) -> Usuario:
    """Acesso às rotas de produto, com a única restrição do papel `basico`:
    **nenhum DELETE, em lugar nenhum**.

    A regra é por método HTTP e não por rota justamente para não depender de
    alguém lembrar de proteger a próxima rota de remoção que for escrita.
    Rota nova que apague coisa já nasce fora do alcance do `basico`.
    """
    if usuario.papel is Papel.BASICO and request.method == "DELETE":
        raise PermissaoInsuficiente("Perfil básico não pode remover registros.")
    return usuario


# Dicionário inteiro (inclusive o GET) fica fora do alcance do `basico`: a
# aba some para ele, e uma aba que aparece vazia por 403 seria pior do que
# não aparecer.
exige_dicionario = exige_papel(Papel.PLENO, Papel.ADMIN)
exige_admin = exige_papel(Papel.ADMIN)
