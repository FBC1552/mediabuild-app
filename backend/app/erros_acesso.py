"""Erros de domínio da administração de usuários (D-014).

Existem como exceções de domínio, e não como `HTTPException` solta no
router, pelo mesmo motivo de `app/taxonomia/erros.py`: quem decide o status
e o formato do corpo é `app/erros_http.py`, num lugar só, e o cliente
recebe um código estável em `erro` para destacar o campo certo — em vez de
ter que parsear o texto da mensagem.

Os dois são **conflito de estado** (409), não entrada inválida (422): o
corpo do pedido está perfeito; o que não permite executá-lo é a situação
atual do banco.
"""


class ErroAcesso(Exception):
    """Base dos erros de administração de acesso. Vira 409."""

    codigo = "erro_acesso"


class ErroAutenticacao(Exception):
    """Base de 401/403, com código estável em `erro` como todo o resto.

    Existe para que 401 e 403 saiam pelo mesmo contrato dos outros erros do
    projeto (`{"erro", "mensagem"}`) e não pelo `{"detail"}` do FastAPI. O
    frontend decide o que fazer **pelo código**, e as reações são de fato
    diferentes: `sessao_expirada` abre um diálogo por cima do formulário
    preenchido, `nao_autenticado` manda para a tela de login. Distinguir
    isso por texto de mensagem seria frágil de um jeito que só aparece
    depois, quando alguém reescrever a frase.
    """

    codigo = "nao_autenticado"
    status = 401

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)


class NaoAutenticado(ErroAutenticacao):
    """Não há sessão — nem cookie, ou um cookie que não corresponde a nada."""

    codigo = "nao_autenticado"
    status = 401

    def __init__(self) -> None:
        super().__init__("É preciso entrar para acessar esta área.")


class SessaoExpirada(ErroAutenticacao):
    """Havia sessão; ela venceu ou foi revogada.

    Separado de `NaoAutenticado` de propósito: quem chega aqui estava
    trabalhando, e provavelmente tem um formulário preenchido na tela. Jogar
    essa pessoa para o login descartaria o trabalho dela.
    """

    codigo = "sessao_expirada"
    status = 401

    def __init__(self) -> None:
        super().__init__("Sua sessão expirou. Entre novamente para continuar.")


class CredenciaisInvalidas(ErroAutenticacao):
    """Login inexistente **ou** senha errada — resposta idêntica nos dois.

    A indistinguibilidade é o ponto: qualquer diferença entre os dois ramos
    (código, mensagem ou até tempo de resposta) entrega de graça a lista de
    quem tem conta no sistema.
    """

    codigo = "credenciais_invalidas"
    status = 401

    def __init__(self) -> None:
        super().__init__("Login ou senha inválidos.")


class ContaDesativada(ErroAutenticacao):
    """Senha **correta**, conta desativada.

    Só é alcançável depois da conferência da senha. Nesse ponto não há o que
    vazar: quem chegou aqui já provou saber a senha, então não está
    descobrindo nada. E o usuário legítimo precisa saber que o problema é a
    conta e não os dedos — senão fica repetindo a mesma senha para sempre e
    abre um chamado dizendo que "o sistema não aceita minha senha".

    A ordem importa e é frágil: conferir `ativo` **antes** da senha
    transformaria este código num oráculo de enumeração de contas.
    """

    codigo = "conta_desativada"
    status = 401

    def __init__(self) -> None:
        super().__init__(
            "Sua conta está desativada. Procure um administrador para reativá-la."
        )


class PermissaoInsuficiente(ErroAutenticacao):
    """403: autenticado, sem autorização.

    Não é 401. Mandar para o login quem já está logado só produz um ciclo:
    ele entra de novo, com o mesmo papel, e bate na mesma parede.
    """

    codigo = "permissao_insuficiente"
    status = 403

    def __init__(self, mensagem: str | None = None) -> None:
        super().__init__(mensagem or "Seu perfil não tem acesso a esta operação.")


class UltimoAdmin(ErroAcesso):
    """Bloqueia a operação que deixaria o sistema sem nenhum admin ativo.

    Cobre os quatro caminhos que levam ao mesmo buraco: excluir, desativar,
    rebaixar o papel e — indiretamente — qualquer combinação deles. Sem esta
    guarda, o sistema fica trancado para sempre e a única saída é um UPDATE
    manual no banco, que é exatamente o que a tela de usuários existe para
    evitar.
    """

    codigo = "ultimo_admin"

    def __init__(self) -> None:
        super().__init__(
            "Este é o último administrador ativo. Promova outro usuário a "
            "administrador antes de excluir, desativar ou rebaixar este."
        )


class AutoExclusao(ErroAcesso):
    """Bloqueia excluir a própria conta.

    Não é paternalismo: excluir a si mesmo derruba a própria sessão no meio
    da operação, e o desfecho — sucesso ou erro — fica indistinguível para
    quem clicou. Outro admin faz, ou o usuário se desativa.
    """

    codigo = "auto_exclusao"

    def __init__(self) -> None:
        super().__init__(
            "Você não pode excluir a própria conta. Peça a outro "
            "administrador, ou desative-a."
        )
