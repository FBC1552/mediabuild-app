import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import { renderComSessao, USUARIO_ADMIN } from './ajudaSessao'

/**
 * O teste que prova o D-005 sob roteamento: sair de `#/taxonomia/*` e voltar
 * NÃO pode descartar o formulário meio preenchido. Sem ele, as invariantes
 * I-1 (o ramo só liga, nunca desliga) e I-2 (a rota nunca vira `key` de
 * ancestral) seriam só comentário no código.
 */

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

const SENTINELA = 'Black Friday 2026'

beforeEach(() => {
  window.localStorage.clear()
  window.history.replaceState(null, '', '#/taxonomia/gerar')
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const corpo = url.includes('/templates')
        ? TEMPLATES
        : url.includes('/plataformas')
          ? [META]
          : []
      return { ok: true, status: 200, json: async () => corpo } as Response
    }),
  )
})

async function irPara(hash: string) {
  await act(async () => {
    window.location.hash = hash
    // jsdom despacha `hashchange` de forma assíncrona.
    await new Promise((r) => setTimeout(r, 0))
  })
}

const gerador = () => screen.getByLabelText('Plataforma').closest('section')!.parentElement!

/**
 * O ramo inteiro da taxonomia (o wrapper com `hidden` do App).
 *
 * Ler ISTO é o que separa "o formulário sobreviveu" de "o formulário voltou a
 * aparecer". A busca do Testing Library atravessa `hidden`, então asserção de
 * VALOR passa mesmo com o ramo invisível — foi exatamente esse o furo que
 * deixou o bug de navegação passar por 37 testes verdes.
 */
function ramoTaxonomia(): HTMLElement {
  const painel = document.getElementById('painel-gerar')
  if (!painel) throw new Error('o ramo da taxonomia nem chegou a montar')
  const ramo = painel.closest('main')!.parentElement as HTMLElement
  return ramo
}

/** Visível = o ramo não está `hidden` E o painel da aba pedida também não. */
function abaVisivel(aba: string): boolean {
  const painel = document.getElementById(`painel-${aba}`)
  return !!painel && !painel.hidden && !ramoTaxonomia().hidden
}

async function preencherSentinela() {
  const user = userEvent.setup()
  // Admin: a ida ao catálogo faz parte do percurso testado, e ele é área
  // administrativa desde a Parte II §3.
  renderComSessao(<App />, USUARIO_ADMIN)
  await waitFor(() => expect(screen.getByLabelText('Plataforma')).toBeInTheDocument())
  await user.selectOptions(screen.getByLabelText('Plataforma'), META.id)
  const nome = await screen.findByLabelText('Nome interno')
  await user.type(nome, SENTINELA)
  expect(nome).toHaveValue(SENTINELA)
  return user
}

describe('permanência do gerador entre rotas', () => {
  it('preserva o formulário ao ir ao catálogo e voltar', async () => {
    await preencherSentinela()

    await irPara('#/admin/fundacao')
    // O catálogo é lazy: só depois de ele renderizar a ida é real.
    expect(
      // Timeout folgado de propósito: o catálogo é `React.lazy`, e sob a suíte
      // inteira o carregamento do chunk passa do 1s padrão do findBy*.
      await screen.findByRole('heading', { name: 'Catálogo de interface' }, { timeout: 5000 }),
    ).toBeInTheDocument()

    await irPara('#/taxonomia/gerar')
    expect(screen.getByLabelText('Nome interno')).toHaveValue(SENTINELA)
    expect(abaVisivel('gerar')).toBe(true)
  })

  it('preserva o formulário passando pela splash e pelo seletor de assunto', async () => {
    await preencherSentinela()

    await irPara('#/')
    expect(screen.getByRole('button', { name: 'Recomendar um filme premiado' })).toBeInTheDocument()

    await irPara('#/assunto')
    expect(screen.getByRole('heading', { name: 'Escolher assunto' })).toBeInTheDocument()

    await irPara('#/taxonomia/gerar')
    expect(screen.getByLabelText('Nome interno')).toHaveValue(SENTINELA)
    // Voltar para a MESMA rota em que o app abriu é o caso que quebrava:
    // sem ele, a asserção de valor acima passa com a tela em branco.
    expect(abaVisivel('gerar')).toBe(true)
  })

  it('preserva a aba ativa ao sair e voltar', async () => {
    await preencherSentinela()

    await irPara('#/taxonomia/historico')
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Histórico' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    )

    await irPara('#/admin/componentes')
    expect(
      // Timeout folgado de propósito: o catálogo é `React.lazy`, e sob a suíte
      // inteira o carregamento do chunk passa do 1s padrão do findBy*.
      await screen.findByRole('heading', { name: 'Catálogo de interface' }, { timeout: 5000 }),
    ).toBeInTheDocument()

    await irPara('#/taxonomia/historico')
    expect(screen.getByRole('tab', { name: 'Histórico' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Nome interno')).toHaveValue(SENTINELA)
    expect(abaVisivel('historico')).toBe(true)
  })

  it('volta para a aba Gerar depois de passar pelo Dicionário', async () => {
    // O caminho real do analista, e o que estava quebrado: o app abre em
    // `#/taxonomia/gerar`, ele vai cadastrar um termo e clica em Gerar de
    // volta. Voltar para a rota do primeiro commit era ignorado em silêncio.
    const user = await preencherSentinela()

    await user.click(screen.getByRole('tab', { name: 'Dicionário' }))
    await waitFor(() => expect(abaVisivel('dicionario')).toBe(true))
    expect(abaVisivel('gerar')).toBe(false)

    await user.click(screen.getByRole('tab', { name: 'Gerar' }))
    await waitFor(() => expect(abaVisivel('gerar')).toBe(true))
    expect(screen.getByRole('tab', { name: 'Gerar' })).toHaveAttribute('aria-selected', 'true')
    expect(window.location.hash).toBe('#/taxonomia/gerar')
    expect(screen.getByLabelText('Nome interno')).toHaveValue(SENTINELA)
  })

  it('sai da taxonomia e volta várias vezes sem travar', async () => {
    await preencherSentinela()

    for (const parada of ['#/assunto', '#/taxonomia/gerar', '#/', '#/taxonomia/gerar']) {
      await irPara(parada)
      if (parada === '#/taxonomia/gerar') expect(abaVisivel('gerar')).toBe(true)
      else expect(ramoTaxonomia().hidden).toBe(true)
    }
  })

  it('esconde o ramo com `hidden`, não com display por classe', async () => {
    await preencherSentinela()
    await irPara('#/assunto')

    // `hidden` tira o ramo da árvore de acessibilidade e do Tab; classe com
    // display:none não garante isso, e o resultado seriam dois <h1> lidos.
    const ramo = within(document.body).getByLabelText('Nome interno').closest('[hidden]')
    expect(ramo).not.toBeNull()
    expect(gerador()).toBeInTheDocument()
  })

  it('a folha base neutraliza qualquer classe de layout sobre `[hidden]`', async () => {
    // jsdom NÃO aplica as folhas do app: aqui `hidden` some por atributo, no
    // navegador some por CSS — e `[hidden]{display:none}` da folha do agente
    // perde para qualquer `.pilha{display:flex}`. Nenhum teste de DOM cobre
    // isso, então o que dá para provar é que a regra existe na folha base.
    // `?raw` não serve: com `css: false` o Vitest devolve string vazia para
    // qualquer .css. Caminho relativo à raiz do projeto, que é o cwd do runner.
    const { readFileSync } = await import('node:fs')
    const base = readFileSync('src/index.css', 'utf8')
    expect(base).toMatch(/\[hidden\][^{]*\{[^}]*display:\s*none\s*!important/)
  })
})
