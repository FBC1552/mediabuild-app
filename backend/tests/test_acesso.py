"""Autenticação, papéis e observabilidade de acesso (D-014).

Este arquivo protege as invariantes que, se quebrarem, quebram em silêncio:
uma mensagem de erro que passa a distinguir login inexistente de senha
errada, uma guarda de último admin que para de valer num dos quatro
caminhos, uma sessão que continua viva depois da troca de senha. Nenhuma
delas aparece na tela; todas aparecem aqui.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import observabilidade
from app.autorizacao import NOME_COOKIE, agora, conferir_senha, hash_token
from app.models import EventoAcesso, EventoErro, Papel, Sessao, TipoEventoAcesso, Usuario
from tests.conftest import SENHA_DE_TESTE, abrir_sessao, criar_usuario


# --------------------------------------------------------------------------
# login
# --------------------------------------------------------------------------

def test_login_com_credenciais_corretas_devolve_o_usuario_e_o_cookie(cliente_anonimo, session):
    usuario = criar_usuario(session, Papel.PLENO, login="ana.souza")

    resposta = cliente_anonimo.post(
        "/auth/login", json={"login": "ana.souza", "senha": SENHA_DE_TESTE}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["login"] == "ana.souza"
    assert corpo["papel"] == "pleno"
    assert corpo["id"] == str(usuario.id)
    assert NOME_COOKIE in resposta.cookies
    # O que nunca pode sair na resposta.
    assert "senha_hash" not in corpo
    assert "senha_salt" not in corpo


def test_o_cookie_de_sessao_e_httponly(cliente_anonimo, session):
    """HttpOnly é o que impede um XSS de roubar a sessão: o JavaScript da
    página não consegue ler o cookie."""
    criar_usuario(session, Papel.BASICO, login="bruno.lima")

    resposta = cliente_anonimo.post(
        "/auth/login", json={"login": "bruno.lima", "senha": SENHA_DE_TESTE}
    )

    bruto = resposta.headers["set-cookie"].lower()
    assert "httponly" in bruto
    assert "samesite=lax" in bruto
    assert "path=/" in bruto


def test_o_token_do_cookie_nunca_vai_em_claro_para_o_banco(cliente_anonimo, session):
    """Dump vazado não pode virar sessão viva."""
    criar_usuario(session, Papel.BASICO, login="carla.dias")
    resposta = cliente_anonimo.post(
        "/auth/login", json={"login": "carla.dias", "senha": SENHA_DE_TESTE}
    )
    token = resposta.cookies[NOME_COOKIE]

    guardados = list(session.scalars(select(Sessao.token_hash)))
    assert token not in guardados
    assert hash_token(token) in guardados


@pytest.mark.parametrize(
    "credenciais",
    [
        {"login": "nao.existe", "senha": SENHA_DE_TESTE},
        {"login": "dora.reis", "senha": "senha-errada"},
    ],
    ids=["login inexistente", "senha errada"],
)
def test_falha_de_login_tem_resposta_identica_nos_dois_modos(
    cliente_anonimo, session, credenciais
):
    """A invariante central: qualquer diferença entre estes dois ramos —
    código, mensagem ou status — entrega de graça a lista de quem tem
    conta no sistema."""
    criar_usuario(session, Papel.BASICO, login="dora.reis")

    resposta = cliente_anonimo.post("/auth/login", json=credenciais)

    assert resposta.status_code == 401
    assert resposta.json() == {
        "erro": "credenciais_invalidas",
        "mensagem": "Login ou senha inválidos.",
    }
    assert NOME_COOKIE not in resposta.cookies


def test_conta_desativada_com_senha_correta_e_distinguivel(cliente_anonimo, session):
    """Aqui não há o que vazar: quem chega neste ramo já provou saber a
    senha. E o usuário legítimo precisa saber que o problema é a conta, e
    não os dedos."""
    usuario = criar_usuario(session, Papel.PLENO, login="elias.gomes")
    usuario.ativo = False
    session.commit()

    resposta = cliente_anonimo.post(
        "/auth/login", json={"login": "elias.gomes", "senha": SENHA_DE_TESTE}
    )

    assert resposta.status_code == 401
    assert resposta.json()["erro"] == "conta_desativada"


def test_conta_desativada_com_senha_errada_nao_se_denuncia(cliente_anonimo, session):
    """A regressão que este teste existe para pegar: se alguém "otimizar" o
    login checando `ativo` antes da senha, o código `conta_desativada` vira
    um oráculo de enumeração — bastaria mandar qualquer senha para
    descobrir quais logins existem."""
    usuario = criar_usuario(session, Papel.PLENO, login="fabio.melo")
    usuario.ativo = False
    session.commit()

    resposta = cliente_anonimo.post(
        "/auth/login", json={"login": "fabio.melo", "senha": "chute"}
    )

    assert resposta.json()["erro"] == "credenciais_invalidas"


def test_login_com_espaco_ou_arroba_e_recusado(cliente_anonimo):
    """Login é identificador, não e-mail. Arroba fica de fora justamente
    para não induzir ninguém a tratá-lo como endereço."""
    for valor in ("com espaco", "alguem@exemplo.com"):
        resposta = cliente_anonimo.post(
            "/auth/login", json={"login": valor, "senha": SENHA_DE_TESTE}
        )
        assert resposta.status_code == 422, valor


def test_login_normaliza_caixa(cliente_anonimo, session):
    """Caixa alta digitada por engano não pode virar "usuário não existe"."""
    criar_usuario(session, Papel.BASICO, login="gil.matos")

    resposta = cliente_anonimo.post(
        "/auth/login", json={"login": "  GIL.MATOS  ", "senha": SENHA_DE_TESTE}
    )

    assert resposta.status_code == 200


def test_login_registra_evento_de_sucesso_e_de_falha(cliente_anonimo, session):
    criar_usuario(session, Papel.BASICO, login="helena.rocha")

    cliente_anonimo.post("/auth/login", json={"login": "helena.rocha", "senha": SENHA_DE_TESTE})
    cliente_anonimo.post("/auth/login", json={"login": "helena.rocha", "senha": "errada"})

    eventos = session.scalars(
        select(EventoAcesso).where(EventoAcesso.login_tentado == "helena.rocha")
    ).all()
    tipos = {e.tipo for e in eventos}
    assert tipos == {TipoEventoAcesso.LOGIN_OK, TipoEventoAcesso.LOGIN_FALHA}


def test_a_trilha_distingue_credencial_de_conta_desativada(cliente_anonimo, session):
    """O que a resposta esconde, o monitoramento mostra — é lá que o admin
    separa varredura de credenciais de um funcionário desligado tentando
    entrar."""
    usuario = criar_usuario(session, Papel.PLENO, login="igor.paz")
    usuario.ativo = False
    session.commit()

    cliente_anonimo.post("/auth/login", json={"login": "igor.paz", "senha": SENHA_DE_TESTE})
    cliente_anonimo.post("/auth/login", json={"login": "igor.paz", "senha": "errada"})

    detalhes = set(
        session.scalars(
            select(EventoAcesso.detalhe).where(EventoAcesso.login_tentado == "igor.paz")
        )
    )
    assert detalhes == {"conta desativada", "senha incorreta"}


def test_login_atualiza_o_ultimo_acesso(cliente_anonimo, session):
    usuario = criar_usuario(session, Papel.BASICO, login="julia.neves")
    assert usuario.ultimo_acesso_em is None

    cliente_anonimo.post("/auth/login", json={"login": "julia.neves", "senha": SENHA_DE_TESTE})

    session.refresh(usuario)
    assert usuario.ultimo_acesso_em is not None


# --------------------------------------------------------------------------
# sessão
# --------------------------------------------------------------------------

def test_eu_devolve_o_usuario_da_sessao(cliente):
    resposta = cliente.get("/auth/eu")
    assert resposta.status_code == 200
    assert resposta.json()["id"] == str(cliente.usuario.id)


def test_eu_sem_sessao_da_401_com_codigo_nao_autenticado(cliente_anonimo):
    resposta = cliente_anonimo.get("/auth/eu")
    assert resposta.status_code == 401
    assert resposta.json()["erro"] == "nao_autenticado"


def test_sessao_expirada_e_distinguivel_de_sessao_ausente(cliente_anonimo, session):
    """A tela reage diferente aos dois: `sessao_expirada` abre um diálogo
    por cima do formulário preenchido; `nao_autenticado` manda para o
    login. Sem códigos distintos, um dos dois comportamentos é impossível."""
    usuario = criar_usuario(session, Papel.PLENO)
    token = abrir_sessao(session, usuario, horas=-1)  # já nasceu vencida
    cliente_anonimo.cookies.set(NOME_COOKIE, token)

    resposta = cliente_anonimo.get("/auth/eu")

    assert resposta.status_code == 401
    assert resposta.json()["erro"] == "sessao_expirada"


def test_sessao_expirada_e_revogada_e_registrada_uma_vez(cliente_anonimo, session):
    """Revogar no primeiro contato é o que faz o evento sair uma vez, e não
    a cada requisição do cliente que ficou com o cookie velho numa aba."""
    usuario = criar_usuario(session, Papel.PLENO)
    token = abrir_sessao(session, usuario, horas=-1)
    cliente_anonimo.cookies.set(NOME_COOKIE, token)

    cliente_anonimo.get("/auth/eu")
    cliente_anonimo.get("/auth/eu")

    eventos = session.scalars(
        select(EventoAcesso).where(
            EventoAcesso.usuario_id == usuario.id,
            EventoAcesso.tipo == TipoEventoAcesso.SESSAO_EXPIRADA,
        )
    ).all()
    assert len(eventos) == 1


def test_cookie_que_nao_corresponde_a_nada_e_nao_autenticado(cliente_anonimo):
    """Cookie de outro ambiente, ou lixo: não houve sessão, não é sessão
    vencida."""
    cliente_anonimo.cookies.set(NOME_COOKIE, "isto-nao-e-um-token")
    assert cliente_anonimo.get("/auth/eu").json()["erro"] == "nao_autenticado"


def test_logout_revoga_a_sessao_no_servidor(cliente, session):
    """Não basta apagar o cookie: quem tiver ficado com uma cópia do token
    continuaria dentro. É exatamente a diferença entre sessão opaca e JWT."""
    assert cliente.get("/auth/eu").status_code == 200

    resposta = cliente.post("/auth/logout")
    assert resposta.status_code == 204

    sessoes = session.scalars(
        select(Sessao).where(Sessao.usuario_id == cliente.usuario.id)
    ).all()
    assert all(s.revogada_em is not None for s in sessoes)


def test_logout_registra_o_evento(cliente, session):
    cliente.post("/auth/logout")
    evento = session.scalar(
        select(EventoAcesso).where(
            EventoAcesso.usuario_id == cliente.usuario.id,
            EventoAcesso.tipo == TipoEventoAcesso.LOGOUT,
        )
    )
    assert evento is not None


def test_o_token_revogado_nao_serve_mais(cliente, session):
    token = cliente.cookies[NOME_COOKIE]
    cliente.post("/auth/logout")

    cliente.cookies.set(NOME_COOKIE, token)
    assert cliente.get("/auth/eu").json()["erro"] == "sessao_expirada"


def test_logout_sem_sessao_tambem_devolve_204(cliente_anonimo):
    """Sair de onde não se está não é erro — e um 401 aqui só faria a tela
    alarmar quem já tinha o cookie vencido."""
    assert cliente_anonimo.post("/auth/logout").status_code == 204


# --------------------------------------------------------------------------
# papéis
# --------------------------------------------------------------------------

def test_rota_de_produto_exige_sessao(cliente_anonimo):
    assert cliente_anonimo.get("/plataformas").status_code == 401


def test_health_continua_sem_autenticacao(cliente_anonimo):
    """Liveness precisa responder para o orquestrador, que não tem cookie."""
    assert cliente_anonimo.get("/health").status_code == 200


def test_docs_e_openapi_continuam_abertos(cliente_anonimo):
    assert cliente_anonimo.get("/openapi.json").status_code == 200
    assert cliente_anonimo.get("/docs").status_code == 200


def test_basico_nao_enxerga_o_dicionario(cliente_basico):
    """A aba inteira some para ele — inclusive o GET. Uma aba que abre
    vazia por 403 seria pior do que uma que não existe."""
    resposta = cliente_basico.get("/dicionario")
    assert resposta.status_code == 403
    assert resposta.json()["erro"] == "permissao_insuficiente"


def test_basico_nao_escreve_no_dicionario(cliente_basico):
    resposta = cliente_basico.post(
        "/dicionario",
        json={"categoria": "objetivo", "termo": "Teste", "abreviacao": "TST"},
    )
    assert resposta.status_code == 403


@pytest.mark.parametrize(
    "caminho",
    [
        "/campanhas/{id}",
        "/grupos/{id}",
        "/anuncios/{id}",
        "/plataformas/{id}",
        "/metricas/{id}",
        "/planos/{id}",
    ],
)
def test_basico_nao_faz_delete_em_lugar_nenhum(cliente_basico, caminho):
    """A guarda é por método HTTP, não por rota: uma rota de remoção nova já
    nasce fora do alcance do `basico`, sem depender de alguém lembrar.

    O 403 tem que vir **antes** do 404 — a checagem de permissão não pode
    depender de o registro existir, senão ela vira um detector de ids.
    """
    resposta = cliente_basico.delete(caminho.format(id=uuid.uuid4()))
    assert resposta.status_code == 403, caminho


def test_pleno_faz_delete(cliente_pleno):
    """O contraponto do teste acima: a guarda tem que barrar o `basico` sem
    barrar quem pode. Aqui o 404 é o desfecho certo — passou pela
    autorização e não achou o registro."""
    assert cliente_pleno.delete(f"/campanhas/{uuid.uuid4()}").status_code == 404


def test_pleno_usa_o_dicionario(cliente_pleno):
    assert cliente_pleno.get("/dicionario").status_code == 200


def test_pleno_nao_administra_usuarios(cliente_pleno):
    assert cliente_pleno.get("/usuarios").status_code == 403


def test_pleno_nao_ve_o_monitoramento(cliente_pleno):
    for caminho in ("/admin/acessos", "/admin/erros", "/admin/resumo"):
        assert cliente_pleno.get(caminho).status_code == 403, caminho


def test_basico_usa_o_produto(cliente_basico):
    """A restrição do `basico` é dicionário e DELETE — o resto do produto
    continua sendo o trabalho dele."""
    assert cliente_basico.get("/plataformas").status_code == 200
    assert cliente_basico.get("/taxonomias/historico").status_code == 200
    assert cliente_basico.get("/planos").status_code == 200


# --------------------------------------------------------------------------
# administração de usuários
# --------------------------------------------------------------------------

def test_admin_cria_usuario(cliente):
    resposta = cliente.post(
        "/usuarios",
        json={"nome": "Nova Pessoa", "login": "nova.pessoa", "senha": "senha-forte", "papel": "pleno"},
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["login"] == "nova.pessoa"
    assert corpo["ativo"] is True
    assert "senha" not in corpo and "senha_hash" not in corpo


def test_login_duplicado_vira_409(cliente):
    dados = {"nome": "A", "login": "repetido.login", "senha": "senha-forte", "papel": "basico"}
    assert cliente.post("/usuarios", json=dados).status_code == 201
    assert cliente.post("/usuarios", json=dados).status_code == 409


def test_a_listagem_nunca_expoe_o_hash_da_senha(cliente):
    corpo = cliente.get("/usuarios").json()
    assert corpo
    for linha in corpo:
        assert "senha_hash" not in linha
        assert "senha_salt" not in linha


def test_admin_nao_exclui_a_si_mesmo(cliente):
    """Excluir a própria conta derruba a própria sessão no meio da
    operação, e o desfecho fica indistinguível para quem clicou."""
    resposta = cliente.delete(f"/usuarios/{cliente.usuario.id}")
    assert resposta.status_code == 409
    assert resposta.json()["erro"] == "auto_exclusao"


def deixar_um_admin_so(cliente, session):
    """Deixa `unico` como o único admin ativo do banco e o autentica.

    Necessário porque o banco de desenvolvimento tem o admin do seed, e
    possivelmente outros: sem zerar os demais, a guarda de último admin
    corretamente **não** dispara, e o teste passaria a verificar o oposto
    do que diz o nome. A transação do teste é revertida no fim, então nada
    disso sobrevive.
    """
    unico = criar_usuario(session, Papel.ADMIN)
    for outro in session.scalars(
        select(Usuario).where(Usuario.papel == Papel.ADMIN, Usuario.id != unico.id)
    ):
        outro.papel = Papel.PLENO
    session.commit()
    cliente.cookies.set(NOME_COOKIE, abrir_sessao(session, unico))
    return unico


def test_o_ultimo_admin_ativo_nao_consegue_ser_excluido_por_ninguem(cliente, session):
    """A exclusão do último admin é impossível por construção, e vale
    registrar o raciocínio porque ele não é óbvio lendo o router.

    Quem chama `DELETE /usuarios` é obrigatoriamente um admin **ativo** (a
    dependência exige) e obrigatoriamente diferente do alvo (auto-exclusão
    é bloqueada antes). Logo, sempre que a chamada chega à guarda de estado
    já existem pelo menos dois admins ativos — e o alvo não é o último.

    A guarda `_exigir_outro_admin` continua no DELETE como defesa em
    profundidade: se um dia a auto-exclusão for permitida, ou surgir um
    caminho de exclusão que não passe por `exige_admin`, ela é o que
    impede o sistema de ficar trancado.
    """
    unico = deixar_um_admin_so(cliente, session)

    # Ele mesmo não consegue: auto-exclusão.
    cliente.cookies.set(NOME_COOKIE, abrir_sessao(session, unico))
    assert cliente.delete(f"/usuarios/{unico.id}").json()["erro"] == "auto_exclusao"

    # E qualquer outro que consiga chamar a rota é, por definição, um
    # segundo admin ativo — então o alvo deixou de ser o último, e a
    # exclusão passa a ser legítima.
    segundo = criar_usuario(session, Papel.ADMIN)
    cliente.cookies.set(NOME_COOKIE, abrir_sessao(session, segundo))
    assert cliente.delete(f"/usuarios/{unico.id}").status_code == 204


def test_nao_desativa_o_ultimo_admin_ativo(cliente, session):
    unico = deixar_um_admin_so(cliente, session)

    resposta = cliente.patch(f"/usuarios/{unico.id}", json={"ativo": False})

    assert resposta.status_code == 409
    assert resposta.json()["erro"] == "ultimo_admin"


def test_nao_rebaixa_o_ultimo_admin_ativo(cliente, session):
    """O caminho mais fácil de esquecer: rebaixar não parece destrutivo,
    mas deixa o sistema sem administrador do mesmo jeito."""
    unico = deixar_um_admin_so(cliente, session)

    resposta = cliente.patch(f"/usuarios/{unico.id}", json={"papel": "basico"})

    assert resposta.status_code == 409
    assert resposta.json()["erro"] == "ultimo_admin"


def test_com_dois_admins_o_rebaixamento_passa(cliente, session):
    """O contraponto: a guarda não pode travar a operação legítima."""
    outro = criar_usuario(session, Papel.ADMIN)

    resposta = cliente.patch(f"/usuarios/{outro.id}", json={"papel": "pleno"})

    assert resposta.status_code == 200
    assert resposta.json()["papel"] == "pleno"


def test_excluir_usuario_derruba_as_sessoes_dele(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO)
    abrir_sessao(session, alvo)

    assert cliente.delete(f"/usuarios/{alvo.id}").status_code == 204

    session.expire_all()
    restantes = session.scalars(select(Sessao).where(Sessao.usuario_id == alvo.id)).all()
    assert restantes == []


def test_excluir_usuario_preserva_os_eventos_de_acesso(cliente, session):
    """`eventos_acesso.usuario_id` não tem FK de propósito: a trilha de quem
    entrou onde sobrevive à conta. Com CASCADE, apagar o usuário sumiria
    com o próprio rastro dele — que é o oposto do que a trilha serve."""
    alvo = criar_usuario(session, Papel.PLENO, login="marcos.alves")
    session.add(
        EventoAcesso(
            tipo=TipoEventoAcesso.LOGIN_OK,
            usuario_id=alvo.id,
            login_tentado="marcos.alves",
        )
    )
    session.commit()

    cliente.delete(f"/usuarios/{alvo.id}")

    eventos = session.scalars(
        select(EventoAcesso).where(EventoAcesso.usuario_id == alvo.id)
    ).all()
    assert len(eventos) == 1
    assert eventos[0].login_tentado == "marcos.alves"


def test_trocar_a_senha_revoga_as_sessoes(cliente, session):
    """Senão a mudança valeria só no próximo login — que é exatamente o
    comportamento que sessão opaca existe para evitar."""
    alvo = criar_usuario(session, Papel.PLENO)
    token = abrir_sessao(session, alvo)

    cliente.patch(f"/usuarios/{alvo.id}", json={"senha": "outra-senha-forte"})

    sessao = session.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
    assert sessao.revogada_em is not None


def test_desativar_revoga_as_sessoes(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO)
    token = abrir_sessao(session, alvo)

    cliente.patch(f"/usuarios/{alvo.id}", json={"ativo": False})

    sessao = session.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
    assert sessao.revogada_em is not None


def test_promover_nao_derruba_a_sessao(cliente, session):
    """Ganhar poder não invalida o que a pessoa já podia fazer."""
    alvo = criar_usuario(session, Papel.BASICO)
    token = abrir_sessao(session, alvo)

    cliente.patch(f"/usuarios/{alvo.id}", json={"papel": "pleno"})

    sessao = session.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
    assert sessao.revogada_em is None


def test_a_senha_nova_passa_a_valer(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO)

    cliente.patch(f"/usuarios/{alvo.id}", json={"senha": "senha-novissima"})

    session.refresh(alvo)
    assert conferir_senha("senha-novissima", alvo.senha_hash, alvo.senha_salt)
    assert not conferir_senha(SENHA_DE_TESTE, alvo.senha_hash, alvo.senha_salt)


def test_senha_provisoria_sai_uma_vez_e_funciona(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO, login="nara.pinto")

    resposta = cliente.post(f"/usuarios/{alvo.id}/senha")

    assert resposta.status_code == 200
    provisoria = resposta.json()["senha_provisoria"]
    assert provisoria

    session.refresh(alvo)
    # Vale como senha...
    assert conferir_senha(provisoria, alvo.senha_hash, alvo.senha_salt)
    # ...e não é recuperável: o banco tem só o hash.
    assert provisoria not in (alvo.senha_hash, alvo.senha_salt)
    assert cliente.get(f"/usuarios/{alvo.id}").json().get("senha_provisoria") is None


def test_senha_provisoria_revoga_as_sessoes(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO)
    token = abrir_sessao(session, alvo)

    cliente.post(f"/usuarios/{alvo.id}/senha")

    sessao = session.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
    assert sessao.revogada_em is not None


# --------------------------------------------------------------------------
# monitoramento
# --------------------------------------------------------------------------

def test_acessos_traz_os_eventos_mais_recentes_primeiro(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO, login="otavio.reis")
    for minutos in (30, 10):
        session.add(
            EventoAcesso(
                tipo=TipoEventoAcesso.LOGIN_OK,
                usuario_id=alvo.id,
                login_tentado="otavio.reis",
                ocorrido_em=agora() - timedelta(minutes=minutos),
            )
        )
    session.commit()

    corpo = cliente.get("/admin/acessos?limite=500").json()
    nossos = [e for e in corpo if e["login_tentado"] == "otavio.reis"]

    assert len(nossos) == 2
    assert nossos[0]["ocorrido_em"] > nossos[1]["ocorrido_em"]
    assert nossos[0]["usuario_login"] == "otavio.reis"


def test_acessos_filtra_por_tipo(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO, login="paula.cruz")
    session.add_all(
        [
            EventoAcesso(tipo=TipoEventoAcesso.LOGIN_OK, usuario_id=alvo.id),
            EventoAcesso(tipo=TipoEventoAcesso.LOGIN_FALHA, login_tentado="paula.cruz"),
        ]
    )
    session.commit()

    corpo = cliente.get("/admin/acessos?tipo=login_falha&limite=500").json()
    assert all(e["tipo"] == "login_falha" for e in corpo)


def test_o_limite_tem_teto(cliente):
    """Sem teto, `?limite=10000000` é um negador de serviço de uma linha."""
    assert cliente.get("/admin/acessos?limite=9999").status_code == 422


def test_evento_de_acesso_de_usuario_excluido_fica_sem_login_mas_nao_anonimo(
    cliente, session
):
    session.add(
        EventoAcesso(
            tipo=TipoEventoAcesso.LOGIN_FALHA,
            usuario_id=uuid.uuid4(),  # id que não existe em `usuarios`
            login_tentado="quem.era",
        )
    )
    session.commit()

    corpo = cliente.get("/admin/acessos?limite=500").json()
    linha = next(e for e in corpo if e["login_tentado"] == "quem.era")
    assert linha["usuario_login"] is None


def test_resumo_agrega_logins_falhas_e_papeis(cliente, session):
    alvo = criar_usuario(session, Papel.PLENO, login="rita.souza")
    session.add_all(
        [
            EventoAcesso(tipo=TipoEventoAcesso.LOGIN_OK, usuario_id=alvo.id),
            EventoAcesso(tipo=TipoEventoAcesso.LOGIN_FALHA, login_tentado="rita.souza"),
            EventoAcesso(tipo=TipoEventoAcesso.LOGIN_FALHA, login_tentado="rita.souza"),
        ]
    )
    session.commit()

    corpo = cliente.get("/admin/resumo?dias=7").json()

    assert corpo["dias"] == 7
    assert corpo["total_logins_ok"] >= 1
    assert corpo["total_logins_falha"] >= 2
    assert 0.0 <= corpo["taxa_falha_login"] <= 1.0
    assert corpo["sessoes_ativas"] >= 1  # a do próprio `cliente`
    # Todos os papéis aparecem, inclusive zerados: a tela não deveria ter
    # que saber a lista de papéis para desenhar a linha que falta.
    assert set(corpo["usuarios_por_papel"]) == {"basico", "pleno", "admin"}


def test_resumo_sem_tentativa_nenhuma_nao_quebra(cliente):
    """Base vazia é o primeiro estado que a tela vê. Taxa 0.0, não nulo nem
    divisão por zero."""
    corpo = cliente.get("/admin/resumo?dias=1").json()
    assert isinstance(corpo["taxa_falha_login"], float)
    assert isinstance(corpo["logins_por_dia"], list)


def test_erros_lista_e_filtra_por_status(cliente, session):
    session.add_all(
        [
            EventoErro(metodo="GET", caminho="/x", status=404, request_id="r1"),
            EventoErro(metodo="GET", caminho="/y", status=500, request_id="r2"),
        ]
    )
    session.commit()

    todos = cliente.get("/admin/erros?limite=500").json()
    assert {"/x", "/y"} <= {e["caminho"] for e in todos}

    so500 = cliente.get("/admin/erros?status=500&limite=500").json()
    assert all(e["status"] == 500 for e in so500)


def test_resumo_separa_4xx_de_5xx(cliente, session):
    session.add_all(
        [
            EventoErro(metodo="GET", caminho="/a", status=422),
            EventoErro(metodo="GET", caminho="/b", status=503),
        ]
    )
    session.commit()

    corpo = cliente.get("/admin/resumo?dias=7").json()
    assert corpo["erros_4xx"] >= 1
    assert corpo["erros_5xx"] >= 1


# --------------------------------------------------------------------------
# registro de erro pelo middleware
# --------------------------------------------------------------------------

def test_evento_de_erro_e_gravado_com_o_request_id_da_resposta(
    cliente, session, eventos_erro_no_banco
):
    """O `request_id` é o que amarra a linha da tela de monitoramento à
    linha do log — os dois são o mesmo evento visto de dois lugares."""
    resposta = cliente.get(f"/campanhas/{uuid.uuid4()}")
    assert resposta.status_code == 404
    rid = resposta.headers["X-Request-ID"]

    evento = session.scalar(select(EventoErro).where(EventoErro.request_id == rid))
    assert evento is not None
    assert evento.status == 404
    assert evento.metodo == "GET"
    assert evento.caminho.startswith("/campanhas/")
    # Autoria: o middleware lê o usuário de `scope["state"]`, porque o
    # `call_next` roda numa task filha e ContextVar não volta de lá.
    assert evento.usuario_id == cliente.usuario.id
    assert evento.duracao_ms is not None


def test_o_codigo_estavel_do_erro_e_guardado(cliente, session, eventos_erro_no_banco):
    """Sem `codigo_erro`, a tela só saberia contar 422. Com ele, dá para
    responder "quais termos estão faltando no dicionário"."""
    resposta = cliente.post(
        "/dicionario",
        json={"categoria": "regiao", "termo": "Nacional", "abreviacao": "NA"},
    )
    assert resposta.status_code == 422

    evento = session.scalar(
        select(EventoErro).where(EventoErro.request_id == resposta.headers["X-Request-ID"])
    )
    assert evento.codigo_erro == "abreviacao_reservada"


def test_a_resposta_de_erro_chega_inteira_ao_cliente(cliente):
    """O middleware consome o corpo do stream para poder lê-lo, e precisa
    remontá-lo. Se esquecer, o cliente recebe 422 com corpo vazio — e o
    frontend perde o campo culpado que o D-005 existe para entregar."""
    resposta = cliente.post(
        "/dicionario",
        json={"categoria": "regiao", "termo": "Nacional", "abreviacao": "NA"},
    )
    corpo = resposta.json()
    assert corpo["erro"] == "abreviacao_reservada"
    assert corpo["mensagem"]


def test_falha_ao_gravar_o_evento_nao_derruba_a_requisicao(
    cliente, session, monkeypatch
):
    """Requisito duro: a observabilidade não pode virar ponto único de
    falha do produto. Se a tabela sumir ou o banco engasgar, o usuário
    recebe a resposta dele e o problema vira uma linha de log."""

    def fabrica_que_explode():
        raise RuntimeError("banco de eventos indisponivel")

    monkeypatch.setattr(observabilidade, "fabrica_de_sessao", fabrica_que_explode)

    resposta = cliente.get(f"/campanhas/{uuid.uuid4()}")

    assert resposta.status_code == 404
    assert resposta.json()["detail"]


def test_falha_ao_gravar_o_evento_nao_esconde_a_resposta_de_sucesso(
    cliente, monkeypatch
):
    """Complemento do anterior: resposta 2xx nem chega a tentar gravar."""

    def fabrica_que_explode():
        raise RuntimeError("banco de eventos indisponivel")

    monkeypatch.setattr(observabilidade, "fabrica_de_sessao", fabrica_que_explode)
    assert cliente.get("/plataformas").status_code == 200


def test_401_tambem_vira_evento_de_erro(cliente_anonimo, session, eventos_erro_no_banco):
    """Rajada de 401 é o sinal mais barato de que alguém está tentando
    entrar — precisa chegar ao monitoramento."""
    resposta = cliente_anonimo.get("/plataformas")
    rid = resposta.headers["X-Request-ID"]

    evento = session.scalar(select(EventoErro).where(EventoErro.request_id == rid))
    assert evento.status == 401
    assert evento.codigo_erro == "nao_autenticado"
    assert evento.usuario_id is None


# --------------------------------------------------------------------------
# senha
# --------------------------------------------------------------------------

def test_o_salt_e_diferente_por_usuario(session):
    """Sem salt por usuário, duas pessoas com a mesma senha teriam o mesmo
    hash, e quebrar um quebraria todos de uma vez."""
    from app.autorizacao import hash_senha

    h1, s1 = hash_senha("mesma-senha")
    h2, s2 = hash_senha("mesma-senha")
    assert s1 != s2
    assert h1 != h2


def test_salt_corrompido_no_banco_nao_vira_500(session):
    """Login não pode virar canal de diagnóstico do schema."""
    assert conferir_senha("qualquer", "hash", "nao-e-hexadecimal") is False


def test_o_seed_do_admin_e_idempotente_e_nao_troca_a_senha(session):
    """Rodar o seed é operação corriqueira. Se ele redefinisse a senha,
    qualquer `python -m app.seed` devolveria o acesso a quem conhecesse o
    valor antigo da variável de ambiente."""
    from app.config import settings
    from app.seed import garantir_admin_inicial

    login = settings.admin_login_inicial.lower()
    existente = session.scalar(select(Usuario).where(Usuario.login == login))
    if existente is None:
        assert garantir_admin_inicial(session) is True
        session.commit()
        existente = session.scalar(select(Usuario).where(Usuario.login == login))

    hash_antes = existente.senha_hash
    assert garantir_admin_inicial(session) is False
    session.commit()
    session.refresh(existente)
    assert existente.senha_hash == hash_antes
