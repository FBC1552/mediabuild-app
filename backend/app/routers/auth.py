"""Login, logout e "quem sou eu" (D-014).

A regra que governa este arquivo: **falhar não pode dizer quem existe**.

Login inexistente e senha errada devolvem exatamente o mesmo 401, com o
mesmo código (`credenciais_invalidas`) e a mesma mensagem. Qualquer
diferença entre os dois entrega de graça a lista de quem tem conta — e a
versão sutil desse vazamento (responder mais rápido quando o login não
existe, porque não houve scrypt a calcular) é tratada gastando o mesmo
trabalho nos dois caminhos, contra um hash descartável.

**Conta desativada é a exceção deliberada**, e devolve `conta_desativada`.
Ela só é alcançável *depois* de a senha conferir, então quem chega lá já
provou saber a senha e não está descobrindo nada. Em troca, o usuário
legítimo descobre que o problema é a conta e não os dedos, em vez de
repetir a mesma senha até abrir chamado. Inverter essa ordem — checar
`ativo` antes da senha — transformaria o código num oráculo de enumeração;
o comentário dentro de `entrar()` marca o ponto.

A trilha fica em `eventos_acesso`, onde a distinção completa **existe**: lá
dentro é seguro, e é o que permite ao admin ver "quinze falhas seguidas
contra este login" na tela de monitoramento.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autorizacao import (
    NOME_COOKIE,
    agente_do_pedido,
    agora,
    conferir_senha,
    criar_sessao,
    gravar_cookie,
    hash_senha,
    hash_token,
    ip_do_pedido,
    limpar_cookie,
    normalizar_login,
    usuario_atual,
)
from app.db import get_session
from app.erros_acesso import ContaDesativada, CredenciaisInvalidas
from app.models import Sessao, Usuario
from app.observabilidade import registrar_evento_acesso
from app.schemas import LoginPedido, UsuarioLer

router = APIRouter(prefix="/auth", tags=["autenticação"])

logger = logging.getLogger("mediabuild.acesso")

_SALT_FALSO = "00" * 16
_HASH_FALSO, _ = hash_senha("comparacao-em-vazio", _SALT_FALSO)


@router.post("/login", response_model=UsuarioLer)
def entrar(
    dados: LoginPedido,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    login = normalizar_login(dados.login)
    ip = ip_do_pedido(request)
    agente = agente_do_pedido(request)

    usuario = session.scalar(select(Usuario).where(Usuario.login == login))

    # A ORDEM DESTE BLOCO É REGRA DE SEGURANÇA, não estilo.
    #
    # A senha é conferida SEMPRE, inclusive quando o login não existe (aí
    # contra um hash descartável) e inclusive quando a conta está
    # desativada. Só depois é que `ativo` entra na decisão.
    #
    # Se `ativo` fosse checado antes, o código `conta_desativada` viraria um
    # oráculo: qualquer um descobriria quais logins existem mandando senha
    # errada e olhando se a resposta muda. Conferindo a senha primeiro,
    # chegar em `conta_desativada` exige já saber a senha — e quem sabe a
    # senha não está descobrindo nada.
    #
    # `falha` é o erro devolvido; `motivo` é o texto que vai só para
    # `eventos_acesso.detalhe`, nunca para a resposta.
    if usuario is None:
        conferir_senha(dados.senha, _HASH_FALSO, _SALT_FALSO)
        falha, motivo = CredenciaisInvalidas(), "login inexistente"
    elif not conferir_senha(dados.senha, usuario.senha_hash, usuario.senha_salt):
        falha, motivo = CredenciaisInvalidas(), "senha incorreta"
    elif not usuario.ativo:
        # Senha correta, conta desligada. Distinguível de propósito: o
        # usuário legítimo precisa saber que o problema é a conta e não os
        # dedos, senão repete a mesma senha para sempre.
        falha, motivo = ContaDesativada(), "conta desativada"
    else:
        falha, motivo = None, None

    if falha is not None:
        # Os dois casos entram na trilha como `login_falha`, mas com
        # `detalhe` diferente: o admin precisa distinguir varredura de
        # credencial de um funcionário desligado tentando entrar.
        registrar_evento_acesso(
            session,
            tipo="login_falha",
            usuario_id=usuario.id if usuario else None,
            login_tentado=login,
            ip=ip,
            agente=agente,
            detalhe=motivo,
        )
        session.commit()
        raise falha

    token = criar_sessao(session, usuario, request)
    usuario.ultimo_acesso_em = agora()
    registrar_evento_acesso(
        session,
        tipo="login_ok",
        usuario_id=usuario.id,
        login_tentado=login,
        ip=ip,
        agente=agente,
    )
    session.commit()

    gravar_cookie(response, token)
    return usuario


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def sair(request: Request, session: Session = Depends(get_session)) -> Response:
    """Revoga a sessão e limpa o cookie.

    Sempre 204, inclusive sem sessão válida: sair de um lugar onde não se
    está não é erro, e devolver 401 aqui só faria a tela mostrar um alarme
    a quem já tinha o cookie vencido na aba aberta.

    A revogação é do lado do servidor, não só do cookie. Apagar apenas o
    cookie deixaria o token válido para quem tivesse ficado com uma cópia —
    que é precisamente a diferença entre sessão opaca e JWT.
    """
    token = request.cookies.get(NOME_COOKIE)
    if token:
        sessao = session.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
        if sessao is not None and sessao.revogada_em is None:
            sessao.revogada_em = agora()
            registrar_evento_acesso(
                session,
                tipo="logout",
                usuario_id=sessao.usuario_id,
                ip=ip_do_pedido(request),
                agente=agente_do_pedido(request),
            )
            session.commit()

    # A resposta é construída aqui, e não recebida como parâmetro, para que
    # o cabeçalho de remoção do cookie seja escrito no objeto que de fato
    # volta ao cliente.
    resposta = Response(status_code=status.HTTP_204_NO_CONTENT)
    limpar_cookie(resposta)
    return resposta


@router.get("/eu", response_model=UsuarioLer)
def eu(usuario: Usuario = Depends(usuario_atual)):
    """Quem está na sessão. É o que o frontend chama no boot para decidir
    entre a tela de login e a aplicação — e o único jeito honesto de saber,
    já que o cookie é HttpOnly e o JavaScript não consegue lê-lo."""
    return usuario
