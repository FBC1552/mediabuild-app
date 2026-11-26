"""Administração de usuários (D-014). Tudo aqui exige papel `admin`.

Duas guardas sustentam este arquivo, e as duas existem porque a alternativa
é destravar o sistema por UPDATE manual no banco:

- **último admin ativo**: nenhuma operação pode zerar a contagem de
  administradores ativos — nem excluir, nem desativar, nem rebaixar;
- **auto-exclusão**: ninguém apaga a própria conta.

E uma regra de propagação: toda mudança que reduz o poder de um usuário
(senha nova, desativação, rebaixamento) **revoga as sessões dele na hora**.
Sem isso a mudança valeria só no próximo login, que é o comportamento que
sessão opaca existe para evitar.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.autorizacao import (
    exige_admin,
    gerar_senha_provisoria,
    hash_senha,
    normalizar_login,
    revogar_sessoes,
)
from app.db import get_session
from app.erros_acesso import AutoExclusao, UltimoAdmin
from app.models import Papel, Usuario
from app.schemas import SenhaProvisoriaLer, UsuarioAtualizar, UsuarioCriar, UsuarioLer

router = APIRouter(
    prefix="/usuarios",
    tags=["usuários"],
    dependencies=[Depends(exige_admin)],
)


def _obter(session: Session, usuario_id: UUID) -> Usuario:
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return usuario


def _outros_admins_ativos(session: Session, exceto: UUID) -> int:
    """Quantos admins ativos existem além deste.

    Contagem no banco e não em Python: a lista inteira de usuários não
    precisa vir até aqui para responder "sobra alguém?".
    """
    return session.scalar(
        select(func.count(Usuario.id)).where(
            Usuario.papel == Papel.ADMIN,
            Usuario.ativo.is_(True),
            Usuario.id != exceto,
        )
    ) or 0


def _exigir_outro_admin(session: Session, usuario: Usuario) -> None:
    """Levanta `UltimoAdmin` se remover o poder deste deixar o sistema órfão.

    Só vale se ele **é** admin ativo hoje: rebaixar quem já é `basico`, ou
    excluir um admin já desativado, não tira nada de ninguém.
    """
    if usuario.papel is Papel.ADMIN and usuario.ativo:
        if _outros_admins_ativos(session, usuario.id) == 0:
            raise UltimoAdmin()


@router.get("", response_model=list[UsuarioLer])
def listar(session: Session = Depends(get_session)):
    return session.scalars(select(Usuario).order_by(Usuario.nome, Usuario.login)).all()


@router.post("", response_model=UsuarioLer, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, session: Session = Depends(get_session)):
    """Login duplicado cai na UNIQUE e vira 409 pelo handler de
    `IntegrityError` que já existe — sem SELECT prévio, que seria uma
    corrida perdida entre duas requisições simultâneas."""
    senha_hash, senha_salt = hash_senha(dados.senha)
    usuario = Usuario(
        nome=dados.nome,
        login=normalizar_login(dados.login),
        senha_hash=senha_hash,
        senha_salt=senha_salt,
        papel=dados.papel,
        ativo=True,
    )
    session.add(usuario)
    session.commit()
    return usuario


@router.get("/{usuario_id}", response_model=UsuarioLer)
def obter(usuario_id: UUID, session: Session = Depends(get_session)):
    return _obter(session, usuario_id)


@router.patch("/{usuario_id}", response_model=UsuarioLer)
def atualizar(
    usuario_id: UUID,
    dados: UsuarioAtualizar,
    session: Session = Depends(get_session),
):
    usuario = _obter(session, usuario_id)
    campos = dados.model_dump(exclude_unset=True)

    # Rebaixar é o poder **diminuir**, não "o papel novo não é admin":
    # promover de `basico` para `pleno` satisfaz a segunda condição e
    # derrubaria a sessão de quem acabou de ganhar acesso.
    rebaixa = "papel" in campos and campos["papel"].poder < usuario.papel.poder
    desativa = campos.get("ativo") is False
    troca_senha = campos.get("senha") is not None

    # A guarda roda **antes** de qualquer escrita: um rebaixamento aplicado
    # e depois desfeito por exceção dependeria do rollback para não vazar.
    if rebaixa or desativa:
        _exigir_outro_admin(session, usuario)

    if "nome" in campos:
        usuario.nome = campos["nome"]
    if "papel" in campos:
        usuario.papel = campos["papel"]
    if "ativo" in campos:
        usuario.ativo = campos["ativo"]
    if troca_senha:
        usuario.senha_hash, usuario.senha_salt = hash_senha(campos["senha"])

    # Promover não derruba sessão: ganhar poder não invalida o que o usuário
    # já podia fazer, e obrigá-lo a relogar seria incômodo sem ganho.
    if troca_senha or desativa or rebaixa:
        revogar_sessoes(session, usuario.id)

    session.commit()
    return usuario


@router.post("/{usuario_id}/senha", response_model=SenhaProvisoriaLer)
def redefinir_senha(usuario_id: UUID, session: Session = Depends(get_session)):
    """Gera uma senha provisória e a devolve **uma única vez**.

    Rota própria e não `PATCH` com `senha` (que continua existindo, para o
    admin que quer definir um valor específico) porque as duas operações têm
    contratos diferentes: esta *produz* um segredo que precisa ser lido na
    resposta, e uma rota de edição que às vezes devolve segredo e às vezes
    não é a forma mais fácil de vazá-lo num log de auditoria genérico.

    O valor não é recuperável depois: o banco guarda só o hash scrypt. Se o
    admin fechar o diálogo sem copiar, o caminho é gerar outra.

    Como toda troca de senha, revoga as sessões vivas do usuário.
    """
    usuario = _obter(session, usuario_id)

    senha = gerar_senha_provisoria()
    usuario.senha_hash, usuario.senha_salt = hash_senha(senha)
    revogar_sessoes(session, usuario.id)
    session.commit()

    return SenhaProvisoriaLer(
        usuario_id=usuario.id, login=usuario.login, senha_provisoria=senha
    )


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    usuario_id: UUID,
    session: Session = Depends(get_session),
    autor: Usuario = Depends(exige_admin),
):
    """Exclui o usuário. As sessões dele caem por CASCADE; os eventos de
    acesso **ficam**, porque `eventos_acesso.usuario_id` não tem FK — a
    trilha de quem entrou onde sobrevive à conta (D-014)."""
    usuario = _obter(session, usuario_id)

    if usuario.id == autor.id:
        raise AutoExclusao()
    _exigir_outro_admin(session, usuario)

    session.delete(usuario)
    session.commit()
