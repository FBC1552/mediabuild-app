/**
 * Sessão, login e visibilidade por papel (UX-NAVEGACAO Parte II §4 e §5).
 *
 * O que estes testes provam, em ordem de importância:
 *
 *  1. sessão expirada NÃO descarta o formulário e NÃO reenvia nada sozinho —
 *     reexecutar um POST consumiria um `match_id` e gravaria um nome que
 *     ninguém pediu;
 *  2. o papel `basico` não enxerga o Dicionário, e quem digita o endereço
 *     vê uma negativa legível em vez de redirecionamento ou 404;
 *  3. o boot não pisca a tela de login para quem já está autenticado;
 *  4. a tela de login não diz qual dos dois campos falhou.
 *
 * jsdom não vê layout nem contraste: nada aqui prova que a tela está
 * visualmente certa.
 */
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import { AplicativoTaxonomia } from '../componentes/AplicativoTaxonomia'
import { Dicionario } from '../componentes/Dicionario'
import { ProvedorSessao } from '../sessao'
import type { Usuario } from '../tipos'
import {
  renderComSessao,
  USUARIO_BASICO,
  USUARIO_PLENO,
} from './ajudaSessao'

const META = { id: 'p-meta', nome: 'Meta', sigla: 'METAA', ativo: true }

const TEMPLATES = ['CAMPANHA', 'GRUPO', 'ANUNCIO'].map((nivel) => ({
  id: `t-${nivel}`,
  plataforma_id: META.id,
  nivel,
  separador: '_',
  tokens: [
    { tipo: 'literal', valor: 'METAA' },
    { tipo: 'campo', chave: 'objetivo', rotulo: 'Objetivo' },
    { tipo: 'match_id' },
  ],
  versao: 1,
  ativo: true,
}))

const DICIONARIO = [
  { id: 'a1', plataforma_id: null, categoria: 'objetivo', termo: 'Conversão', abreviacao: 'CV' },
  { id: 'a2', plataforma_id: null, categoria: 'objetivo', termo: 'Tráfego', abreviacao: 'TRF' },
]

const SENTINELA = 'Black Friday 2026'

type Resposta = { status: number; corpo: unknown }

let chamadas: string[] = []
let usuarioDaSessao: Usuario | null = null
let respostaDoLogin: Resposta = { status: 200, corpo: USUARIO_PLENO }
let previewFalhaComoExpirada = false

function resposta(corpo: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => corpo } as Response
}

function instalarFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push(`${init?.method ?? 'GET'} ${url}`)

      if (url === '/api/auth/eu') {
        return usuarioDaSessao
          ? resposta(usuarioDaSessao)
          : resposta({ erro: 'nao_autenticado', mensagem: 'É preciso entrar.' }, 401)
      }
      if (url === '/api/auth/login') {
        if (respostaDoLogin.status === 200) usuarioDaSessao = respostaDoLogin.corpo as Usuario
        return resposta(respostaDoLogin.corpo, respostaDoLogin.status)
      }
      if (url === '/api/auth/logout') {
        usuarioDaSessao = null
        return resposta(undefined, 204)
      }

      if (url === '/api/taxonomias/preview') {
        if (previewFalhaComoExpirada) {
          previewFalhaComoExpirada = false
          return resposta(
            { erro: 'sessao_expirada', mensagem: 'Sua sessão expirou. Entre novamente.' },
            401,
          )
        }
        return resposta({
          nomenclatura: 'METAA_CV_C0000',
          match_id_provisorio: true,
          template_versao: 1,
          limite_caracteres: 400,
          caracteres: 14,
        })
      }

      if (url.includes('/templates')) return resposta(TEMPLATES)
      if (url.startsWith('/api/plataformas')) return resposta([META])
      if (url.startsWith('/api/dicionario')) return resposta(DICIONARIO)
      return resposta([])
    }),
  )
}

beforeEach(() => {
  chamadas = []
  usuarioDaSessao = null
  respostaDoLogin = { status: 200, corpo: USUARIO_PLENO }
  previewFalhaComoExpirada = false
  window.localStorage.clear()
  window.history.replaceState(null, '', '#/taxonomia/gerar')
  instalarFetch()
})

const appComSessaoReal = () =>
  render(
    <ProvedorSessao>
      <App />
    </ProvedorSessao>,
  )

// --------------------------------------------------------------------------

describe('boot', () => {
  it('não pisca a tela de login para quem já tem sessão', async () => {
    usuarioDaSessao = USUARIO_PLENO
    appComSessaoReal()

    // Síncrono, antes de `GET /auth/eu` responder: a fase é `verificando` e
    // NENHUMA das duas telas pode estar na árvore.
    expect(screen.queryByRole('heading', { name: 'Entrar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Gerar' })).not.toBeInTheDocument()

    expect(await screen.findByRole('tab', { name: 'Gerar' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Entrar' })).not.toBeInTheDocument()
  })

  it('manda para o login quem não tem sessão, e volta ao endereço pretendido', async () => {
    usuarioDaSessao = null
    appComSessaoReal()

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(window.location.hash).toBe('#/entrar')
    // `substituir` (replaceState): empilhar entrada prenderia o botão voltar
    // do navegador no portão.
    expect(screen.queryByRole('tab', { name: 'Gerar' })).not.toBeInTheDocument()

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Usuário'), 'marina.alves')
    await user.type(screen.getByLabelText('Senha'), 'segredo')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('tab', { name: 'Gerar' })).toBeInTheDocument()
    expect(window.location.hash).toBe('#/taxonomia/gerar')
  })
})

describe('tela de login', () => {
  it('não diz qual dos dois campos estava errado', async () => {
    usuarioDaSessao = null
    respostaDoLogin = {
      status: 401,
      corpo: { erro: 'credenciais_invalidas', mensagem: 'Login ou senha inválidos.' },
    }
    appComSessaoReal()
    const user = userEvent.setup()
    await screen.findByRole('heading', { name: 'Entrar' })

    await user.type(screen.getByLabelText('Usuário'), 'marina.alves')
    await user.type(screen.getByLabelText('Senha'), 'errada')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    const alerta = await screen.findByRole('alert')
    // A mensagem é a do servidor, e cobre os dois casos numa frase só.
    expect(alerta).toHaveTextContent('Login ou senha inválidos.')
    expect(alerta.textContent).not.toMatch(/não (existe|encontrad)/i)

    // Os DOIS campos são marcados: destacar só um já entregaria o outro.
    expect(screen.getByLabelText('Usuário')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Senha')).toHaveAttribute('aria-invalid', 'true')

    // Senha limpa, usuário preservado.
    expect(screen.getByLabelText('Usuário')).toHaveValue('marina.alves')
    expect(screen.getByLabelText('Senha')).toHaveValue('')
  })

  it('mostra a mensagem própria de conta desativada', async () => {
    usuarioDaSessao = null
    respostaDoLogin = {
      status: 401,
      corpo: {
        erro: 'conta_desativada',
        mensagem: 'Sua conta está desativada. Procure um administrador para reativá-la.',
      },
    }
    appComSessaoReal()
    const user = userEvent.setup()
    await screen.findByRole('heading', { name: 'Entrar' })

    await user.type(screen.getByLabelText('Usuário'), 'joao.pedro')
    await user.type(screen.getByLabelText('Senha'), 'segredo')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/desativada/)
    // Conta desativada não é erro de digitação: os campos não são acusados.
    expect(screen.getByLabelText('Usuário')).not.toHaveAttribute('aria-invalid')
  })

  it('põe o foco no campo de usuário', async () => {
    usuarioDaSessao = null
    appComSessaoReal()
    await screen.findByRole('heading', { name: 'Entrar' })

    // Única tela do produto com foco automático em campo: é a única em que a
    // primeira ação é digitar, sem exceção.
    await waitFor(() => expect(screen.getByLabelText('Usuário')).toHaveFocus())
  })

  it('não oferece caminho de recuperação que não existe', async () => {
    usuarioDaSessao = null
    appComSessaoReal()
    await screen.findByRole('heading', { name: 'Entrar' })

    expect(screen.getByText(/Só um administrador pode redefinir/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /esqueci|esqueceu/i })).not.toBeInTheDocument()
  })
})

describe('visibilidade por papel', () => {
  function taxonomia(usuario: Usuario, aba: 'gerar' | 'dicionario' | 'historico' = 'gerar') {
    return renderComSessao(
      <AplicativoTaxonomia aba={aba} aoTrocarAba={() => {}} />,
      usuario,
    )
  }

  it('esconde a aba Dicionário do papel básico', async () => {
    taxonomia(USUARIO_BASICO)
    expect(await screen.findByRole('tab', { name: 'Gerar' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Histórico' })).toBeInTheDocument()
    // Permissão ESCONDE: nada de aba desabilitada com cadeado.
    expect(screen.queryByRole('tab', { name: 'Dicionário' })).not.toBeInTheDocument()
  })

  it('mostra a aba Dicionário do papel pleno', async () => {
    taxonomia(USUARIO_PLENO)
    expect(await screen.findByRole('tab', { name: 'Dicionário' })).toBeInTheDocument()
  })

  it('quem digita a rota do Dicionário sem permissão vê a negativa, não um redirecionamento', async () => {
    usuarioDaSessao = USUARIO_BASICO
    window.history.replaceState(null, '', '#/taxonomia/dicionario')
    appComSessaoReal()

    expect(
      await screen.findByText('Você não tem acesso ao Dicionário'),
    ).toBeInTheDocument()
    // Nem teleporte, nem 404: o endereço continua o que a pessoa digitou e a
    // tela de taxonomia continua em pé com as abas que ela tem.
    expect(window.location.hash).toBe('#/taxonomia/dicionario')
    expect(screen.getByRole('tab', { name: 'Gerar' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Endereço não encontrado' })).toBeNull()
  })

  it('não oferece remover termo a quem não pode excluir', async () => {
    renderComSessao(<Dicionario plataformas={[META]} />, USUARIO_BASICO)
    expect(await screen.findByText('Conversão')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remover' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Editar' }).length).toBeGreaterThan(0)
  })

  it('oferece remover termo a quem pode excluir', async () => {
    renderComSessao(<Dicionario plataformas={[META]} />, USUARIO_PLENO)
    expect(await screen.findByText('Conversão')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Remover' }).length).toBeGreaterThan(0)
  })
})

describe('menu de conta', () => {
  it('mostra identidade, papel e o que o papel destrava', async () => {
    const user = userEvent.setup()
    usuarioDaSessao = USUARIO_BASICO
    appComSessaoReal()
    await screen.findByRole('tab', { name: 'Gerar' })

    await user.click(screen.getByRole('button', { name: /João/ }))

    expect(screen.getByText('João Pedro')).toBeInTheDocument()
    expect(screen.getByText('@joao.pedro')).toBeInTheDocument()
    expect(screen.getByText(/Perfil: Básico/)).toBeInTheDocument()
    // O lugar canônico onde o gating é explicado, em vez de N controles
    // mortos espalhados pela tela.
    expect(screen.getByText(/Dicionário e exclusões precisam de um perfil Pleno/))
      .toBeInTheDocument()

    // O tema é controle de três estados e mora aqui — não um ícone sol/lua
    // solto na barra, que é ambíguo entre "estado atual" e "o que vai virar".
    expect(screen.getByRole('radio', { name: 'Sistema' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Escuro' })).toBeInTheDocument()
  })

  it('fecha com Esc e devolve o foco ao gatilho', async () => {
    const user = userEvent.setup()
    usuarioDaSessao = USUARIO_PLENO
    appComSessaoReal()
    await screen.findByRole('tab', { name: 'Gerar' })

    const gatilho = screen.getByRole('button', { name: /Marina/ })
    await user.click(gatilho)
    expect(gatilho).toHaveAttribute('aria-expanded', 'true')

    await user.keyboard('{Escape}')
    expect(gatilho).toHaveAttribute('aria-expanded', 'false')
    expect(gatilho).toHaveFocus()
  })

  it('sair encerra a sessão no servidor e devolve ao login', async () => {
    const user = userEvent.setup()
    usuarioDaSessao = USUARIO_PLENO
    appComSessaoReal()
    await screen.findByRole('tab', { name: 'Gerar' })

    await user.click(screen.getByRole('button', { name: /Marina/ }))
    await user.click(screen.getByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(chamadas).toContain('POST /api/auth/logout')
    expect(window.location.hash).toBe('#/entrar')
  })
})

describe('sessão expirada no meio de um formulário', () => {
  /** Deixa o gerador com o sentinela digitado e a sessão vencida. */
  async function expirarComFormularioPreenchido() {
    const user = userEvent.setup()
    usuarioDaSessao = USUARIO_PLENO
    renderComSessao(<App />, USUARIO_PLENO)

    await user.selectOptions(await screen.findByLabelText('Plataforma'), META.id)
    const nome = await screen.findByLabelText('Nome interno')
    await user.type(nome, SENTINELA)

    // O preview é a próxima chamada que sai sozinha: fazê-la voltar 401 é a
    // forma mais fiel de simular a sessão vencendo no meio do trabalho.
    previewFalhaComoExpirada = true
    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')

    const dialogo = await screen.findByRole('dialog')
    return { user, dialogo }
  }

  it('abre o diálogo por cima e mantém o formulário intacto', async () => {
    const { dialogo } = await expirarComFormularioPreenchido()

    expect(within(dialogo).getByText('Sua sessão expirou')).toBeInTheDocument()
    // O que estava atrás continua montado E preenchido: sessão não é rota.
    expect(screen.getByLabelText('Nome interno')).toHaveValue(SENTINELA)
    expect(window.location.hash).toBe('#/taxonomia/gerar')
    expect(screen.queryByRole('heading', { name: 'Entrar' })).not.toBeInTheDocument()

    // O usuário já é conhecido: o campo vem preenchido e somente leitura.
    const campoUsuario = within(dialogo).getByLabelText('Usuário')
    expect(campoUsuario).toHaveValue(USUARIO_PLENO.login)
    expect(campoUsuario).toHaveAttribute('readonly')
  })

  it('não reexecuta nenhuma mutação depois do relogin', async () => {
    const { user, dialogo } = await expirarComFormularioPreenchido()

    await user.type(within(dialogo).getByLabelText('Senha'), 'segredo')
    const marco = chamadas.length
    await user.click(within(dialogo).getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    // O formulário continua lá — remontar aqui seria a regressão do D-005
    // que o diálogo existe para evitar.
    expect(screen.getByLabelText('Nome interno')).toHaveValue(SENTINELA)

    // E NADA que grave foi reenviado sozinho. Repetir um POST /taxonomias
    // consumiria um `match_id` e gravaria um nome que ninguém pediu.
    const depois = chamadas.slice(marco)
    expect(depois).toContain('POST /api/auth/login')
    const mutacoes = depois.filter(
      (c) =>
        /^(POST|PATCH|DELETE) /.test(c) &&
        !c.startsWith('POST /api/auth/') &&
        !c.startsWith('POST /api/taxonomias/preview'),
    )
    expect(mutacoes).toEqual([])
  })

  it('sair pelo diálogo descarta tudo e vai para o login', async () => {
    const { user, dialogo } = await expirarComFormularioPreenchido()

    await user.click(within(dialogo).getByRole('button', { name: 'Sair da conta' }))

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Nome interno')).not.toBeInTheDocument()
  })
})

describe('remontagem do ramo da taxonomia', () => {
  it('o formulário da pessoa anterior não sobrevive a um novo login', async () => {
    const user = userEvent.setup()
    usuarioDaSessao = USUARIO_PLENO
    appComSessaoReal()

    await user.selectOptions(await screen.findByLabelText('Plataforma'), META.id)
    await user.type(await screen.findByLabelText('Nome interno'), SENTINELA)

    await user.click(screen.getByRole('button', { name: /Marina/ }))
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })

    respostaDoLogin = { status: 200, corpo: USUARIO_BASICO }
    await user.type(screen.getByLabelText('Usuário'), 'joao.pedro')
    await user.type(screen.getByLabelText('Senha'), 'segredo')
    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Entrar' }))
    })

    // `key={idSessao}`: outra pessoa sentou na máquina e não herda o
    // formulário da anterior. É a única exceção autorizada ao I-2.
    await waitFor(() => expect(screen.getByLabelText('Plataforma')).toHaveValue(''))
    expect(screen.queryByLabelText('Nome interno')).not.toBeInTheDocument()
  })
})
