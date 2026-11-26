/**
 * Área administrativa (UX-NAVEGACAO §3) e voltar hierárquico (§2).
 *
 * O que estes testes protegem, em ordem de gravidade:
 *
 * · papel não-admin em rota de admin recebe NEGATIVA LEGÍVEL — não 404, não
 *   redirecionamento silencioso, não 500;
 * · as URLs antigas do catálogo continuam abrindo, porque foi o próprio
 *   produto que as publicou;
 * · o Voltar tem destino verificável antes do clique, por rota.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import Acessos from '../admin/Acessos'
import { destinoDaRota } from '../componentes/VoltarPara'
import { lerRota } from '../roteador'
import type { Usuario } from '../tipos'
import { ComSessao, USUARIO_ADMIN, USUARIO_BASICO, USUARIO_PLENO, renderComSessao } from './ajudaSessao'

const USUARIOS: Usuario[] = [
  USUARIO_ADMIN,
  { ...USUARIO_PLENO, ultimo_acesso_em: '2026-08-06T18:40:00Z' },
  { ...USUARIO_BASICO, ativo: false, ultimo_acesso_em: null },
]

let chamadas: string[] = []
let usuariosAtuais: Usuario[] = USUARIOS

function mockFetch(respostas: Record<string, unknown> = {}) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    chamadas.push(`${init?.method ?? 'GET'} ${url}`)
    const resposta = (corpo: unknown, status = 200) =>
      ({ ok: status < 400, status, json: async () => corpo }) as Response

    for (const [prefixo, corpo] of Object.entries(respostas)) {
      if (url.startsWith(prefixo)) return resposta(corpo)
    }
    if (url === '/api/usuarios' && init?.method === 'POST') {
      const corpo = JSON.parse(String(init.body))
      const novo: Usuario = {
        id: 'u-novo',
        nome: corpo.nome,
        login: corpo.login,
        papel: corpo.papel,
        ativo: true,
        criado_em: '2026-08-07T10:00:00Z',
        ultimo_acesso_em: null,
      }
      usuariosAtuais = [...usuariosAtuais, novo]
      return resposta(novo, 201)
    }
    if (url.startsWith('/api/usuarios/') && init?.method === 'PATCH') {
      return resposta(usuariosAtuais[0])
    }
    if (url.startsWith('/api/usuarios/') && url.endsWith('/senha')) {
      return resposta({ usuario_id: 'u-pleno', login: 'marina.alves', senha_provisoria: 'Xk9pQr2m' })
    }
    if (url.startsWith('/api/usuarios')) return resposta(usuariosAtuais)
    if (url.startsWith('/api/plataformas')) return resposta([])
    throw new Error(`URL não mockada: ${url}`)
  })
}

beforeEach(() => {
  chamadas = []
  usuariosAtuais = USUARIOS
  vi.stubGlobal('fetch', mockFetch())
})

function abrir(hash: string, usuario: Usuario = USUARIO_ADMIN) {
  window.history.replaceState(null, '', hash)
  return renderComSessao(<App />, usuario)
}

// ---------------------------------------------------------------------------

describe('portão de admin (§4.3)', () => {
  it('nega com texto para papel pleno, sem 404 e sem redirecionar', async () => {
    abrir('#/admin/acessos', USUARIO_PLENO)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Você não tem acesso à administração' }),
    ).toBeInTheDocument()
    // "Não existe" seria mentira: existe, não é para este perfil.
    expect(screen.queryByText('Endereço não encontrado')).not.toBeInTheDocument()
    // E o usuário NÃO é teleportado — ser levado sem explicação se lê como bug.
    expect(window.location.hash).toBe('#/admin/acessos')
  })

  it('nega monitoramento e catálogo para papel básico', async () => {
    abrir('#/admin/monitoramento', USUARIO_BASICO)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Você não tem acesso à administração' }),
    ).toBeInTheDocument()
  })

  it('deixa o admin entrar', async () => {
    abrir('#/admin/acessos')
    expect(await screen.findByRole('heading', { level: 1, name: 'Administração' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Gestão de acessos' })).toBeInTheDocument()
  })

  it('não chama a API de acessos quando o papel não permite', async () => {
    abrir('#/admin/acessos', USUARIO_BASICO)
    await screen.findByRole('heading', { level: 1, name: 'Você não tem acesso à administração' })
    expect(chamadas.some((c) => c.includes('/usuarios'))).toBe(false)
  })
})

describe('rotas da administração (§3.1–3.2)', () => {
  it('#/admin cai em Acessos', async () => {
    abrir('#/admin')
    await screen.findByRole('heading', { name: 'Gestão de acessos' })
    await waitFor(() => expect(window.location.hash).toBe('#/admin/acessos'))
  })

  it('a URL antiga do catálogo redireciona, em vez de 404', async () => {
    abrir('#/admin/fundacao')
    // Foi o próprio produto que publicou este endereço no rodapé; 404 aqui é
    // dano autoinfligido. Semântica de 301.
    //
    // Timeout folgado: o catálogo é `React.lazy` e, sob a suíte inteira, o
    // carregamento do chunk passa do 1s padrão do `findBy*`.
    expect(
      await screen.findByRole('heading', { name: 'Catálogo de interface' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    await waitFor(() => expect(window.location.hash).toBe('#/admin/design/fundacao'))
  })

  it('a faixa de contexto aparece, e é contexto — não cor de estado', async () => {
    abrir('#/admin/acessos')
    await screen.findByRole('heading', { name: 'Gestão de acessos' })
    const faixa = document.querySelector('.faixa-admin')!
    expect(faixa).toHaveTextContent('Administração')
    expect(faixa).toHaveTextContent('você está fora do produto')
  })

  it('o título do documento diz onde a pessoa está', async () => {
    abrir('#/admin/monitoramento')
    await waitFor(() => expect(document.title).toBe('Administração · Monitoramento · MediaBuild'))
  })

  it('a nav das três áreas é de links com aria-current, não de tabs', async () => {
    abrir('#/admin/acessos')
    await screen.findByRole('heading', { name: 'Gestão de acessos' })

    const nav = screen.getByRole('navigation', { name: 'Áreas da administração' })
    // `role="tab"` brigaria com a nav lateral de seções do catálogo: dois
    // `tablist` aninhados é ruído de leitor de tela garantido.
    expect(within(nav).queryAllByRole('tab')).toHaveLength(0)
    expect(within(nav).getByRole('link', { name: 'Acessos' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(nav).getByRole('link', { name: 'Design' })).toHaveAttribute(
      'href',
      '#/admin/design/fundacao',
    )
  })
})

describe('voltar hierárquico (§2.3)', () => {
  it('tem rótulo e destino exatos por rota', () => {
    const casos: [string, string | null, string | null][] = [
      ['#/', null, null],
      ['#/entrar', null, null],
      ['#/assunto', 'Voltar para o início', '#/'],
      ['#/guia', 'Voltar para o início', '#/'],
      ['#/cadastro', 'Voltar para o início', '#/'],
      ['#/taxonomia/gerar', 'Voltar para os assuntos', '#/assunto'],
      ['#/taxonomia/dicionario', 'Voltar para os assuntos', '#/assunto'],
      ['#/taxonomia/historico', 'Voltar para os assuntos', '#/assunto'],
      ['#/plano', 'Voltar para os assuntos', '#/assunto'],
      ['#/plano/metricas', 'Voltar para os planos', '#/plano'],
      ['#/plano/abc', 'Voltar para os planos', '#/plano'],
      ['#/admin/acessos', 'Voltar para os assuntos', '#/assunto'],
      ['#/admin/monitoramento', 'Voltar para os assuntos', '#/assunto'],
      ['#/admin/design/movimento', 'Voltar para a administração', '#/admin/acessos'],
      ['#/nao-existe', 'Voltar para o início', '#/'],
    ]

    for (const [hash, rotulo, href] of casos) {
      const destino = destinoDaRota(lerRota(hash))
      expect(destino?.rotulo ?? null, hash).toBe(rotulo)
      expect(destino?.href ?? null, hash).toBe(href)
    }
  })

  it('a tela raiz não renderiza um controle desabilitado', () => {
    // Controle permanentemente desabilitado ensina o usuário a ignorar a
    // região onde ele mora — e o layout não pode saltar entre telas.
    expect(destinoDaRota(lerRota('#/'))).toBeNull()
    expect(destinoDaRota(lerRota('#/entrar'))).toBeNull()
  })
})

describe('gestão de acessos (§3.6)', () => {
  function abrirAcessos() {
    const user = userEvent.setup()
    render(
      <ComSessao usuario={USUARIO_ADMIN}>
        <Acessos />
      </ComSessao>,
    )
    return user
  }

  it('lista as pessoas com papel, situação e último acesso', async () => {
    abrirAcessos()
    expect(await screen.findByText('Marina Alves')).toBeInTheDocument()
    const linha = screen.getByText('Marina Alves').closest('tr')!
    expect(within(linha).getByText('marina.alves')).toBeInTheDocument()
    expect(within(linha).getByText('Ativo')).toBeInTheDocument()
  })

  it('o admin não altera o próprio papel — desabilitado COM MOTIVO', async () => {
    abrirAcessos()
    await screen.findByText('Ana Souza')
    const minhaLinha = screen.getByText('Ana Souza').closest('tr')!

    // É condição, não permissão: por isso desabilita em vez de esconder, e o
    // motivo é acionável (peça a outro administrador).
    expect(within(minhaLinha).getByLabelText('Papel de Ana Souza')).toBeDisabled()
    expect(within(minhaLinha).getByText('Você não pode alterar o próprio acesso.')).toBeInTheDocument()
  })

  it('troca o papel inline e anuncia a mudança', async () => {
    const user = abrirAcessos()
    await screen.findByText('Marina Alves')
    const linha = screen.getByText('Marina Alves').closest('tr')!

    await user.selectOptions(within(linha).getByLabelText('Papel de Marina Alves'), 'admin')

    await waitFor(() =>
      expect(chamadas.some((c) => c.startsWith('PATCH /api/usuarios/u-pleno'))).toBe(true),
    )
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'Papel de Marina Alves alterado para Administrador.',
      ),
    )
  })

  it('excluir exige digitar o usuário — é a única ação irreversível', async () => {
    const user = abrirAcessos()
    await screen.findByText('Marina Alves')
    const linha = screen.getByText('Marina Alves').closest('tr')!

    await user.click(within(linha).getByRole('button', { name: 'Ações de Marina Alves' }))
    await user.click(screen.getByRole('button', { name: 'Excluir' }))

    const dialogo = await screen.findByRole('dialog')
    const confirmar = within(dialogo).getByRole('button', { name: 'Excluir acesso' })
    expect(confirmar).toBeDisabled()

    await user.type(within(dialogo).getByRole('textbox'), 'marina.alves')
    expect(confirmar).toBeEnabled()

    await user.click(confirmar)
    await waitFor(() =>
      expect(chamadas.some((c) => c === 'DELETE /api/usuarios/u-pleno')).toBe(true),
    )
  })

  it('a senha provisória aparece uma vez, com o aviso de que não volta', async () => {
    const user = abrirAcessos()
    await screen.findByText('Marina Alves')
    const linha = screen.getByText('Marina Alves').closest('tr')!

    await user.click(within(linha).getByRole('button', { name: 'Ações de Marina Alves' }))
    await user.click(screen.getByRole('button', { name: 'Redefinir senha' }))

    const dialogo = await screen.findByRole('dialog')
    expect(within(dialogo).getByText('Xk9pQr2m')).toBeInTheDocument()
    expect(
      within(dialogo).getByText(/esta senha não será mostrada de novo/i),
    ).toBeInTheDocument()
    expect(within(dialogo).getByRole('button', { name: 'Copiar' })).toBeInTheDocument()
  })

  it('recusa login inválido antes de chamar o servidor, e explica o formato', async () => {
    const user = abrirAcessos()
    await screen.findByText('Marina Alves')

    await user.click(screen.getByRole('button', { name: '+ Novo acesso' }))
    const dialogo = await screen.findByRole('dialog')

    await user.type(within(dialogo).getByLabelText('Nome'), 'Ana Lima')
    await user.type(within(dialogo).getByLabelText('Usuário'), 'ana lima@x')
    await user.click(within(dialogo).getByRole('button', { name: 'Criar acesso' }))

    expect(within(dialogo).getByRole('alert')).toHaveTextContent(/letras, números, ponto/i)
    expect(within(dialogo).getByLabelText('Usuário')).toHaveAttribute('aria-invalid', 'true')
    // A autoridade continua sendo o servidor; o cliente só evita a ida em vão.
    expect(chamadas.some((c) => c.startsWith('POST /api/usuarios'))).toBe(false)
  })

  it('mostra a mensagem do servidor no 409 de último admin', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        chamadas.push(`${init?.method ?? 'GET'} ${url}`)
        if (init?.method === 'PATCH') {
          return {
            ok: false,
            status: 409,
            json: async () => ({
              erro: 'ultimo_admin',
              mensagem: 'Este é o último administrador ativo.',
            }),
          } as Response
        }
        return { ok: true, status: 200, json: async () => usuariosAtuais } as Response
      }),
    )

    const user = abrirAcessos()
    await screen.findByText('Marina Alves')
    const linha = screen.getByText('Marina Alves').closest('tr')!
    await user.selectOptions(within(linha).getByLabelText('Papel de Marina Alves'), 'basico')

    // A mensagem do servidor, não um genérico que apaga o motivo.
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Este é o último administrador ativo.',
    )
  })

  it('filtro sem resultado é distinto de lista vazia', async () => {
    const user = abrirAcessos()
    await screen.findByText('Marina Alves')

    await user.type(screen.getByLabelText('Buscar pessoa'), 'zzz')

    expect(screen.getByText('Ninguém encontrado com esses filtros.')).toBeInTheDocument()
    expect(screen.queryByText('Nenhum acesso cadastrado.')).not.toBeInTheDocument()
  })

  it('a busca de pessoa também dobra acento', async () => {
    const user = abrirAcessos()
    await screen.findByText('Ana Souza')

    await user.type(screen.getByLabelText('Buscar pessoa'), 'ana.souza')

    expect(screen.getByText('Ana Souza')).toBeInTheDocument()
    expect(screen.queryByText('Marina Alves')).not.toBeInTheDocument()
  })
})
