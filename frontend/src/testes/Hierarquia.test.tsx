import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AplicativoTaxonomia } from '../componentes/AplicativoTaxonomia'
import type { AbaTaxonomia } from '../roteador'
import { ComSessao } from './ajudaSessao'

/**
 * O 1→N na tela: uma campanha com vários grupos, um grupo com vários
 * anúncios. O banco sempre teve essa forma; o gerador era caminho único.
 *
 * O que se testa aqui é o comportamento do analista — criar outro grupo sem
 * refazer a campanha, e criar um anúncio escolhendo o grupo — não o estado
 * interno do componente.
 */

function Taxonomia() {
  const [aba, setAba] = useState<AbaTaxonomia>('gerar')
  // Papel `pleno`: estes testes são de formulário e de aba, não de permissão.
  // Quem cobre o gating por papel é `sessao.test.tsx`.
  return (
    <ComSessao>
      <AplicativoTaxonomia aba={aba} aoTrocarAba={setAba} />
    </ComSessao>
  )
}

const META = { id: 'p-meta', nome: 'Meta', sigla: 'FB', ativo: true }

const CAMPOS: Record<string, string> = {
  CAMPANHA: 'objetivo',
  GRUPO: 'publico',
  ANUNCIO: 'formato',
}

const ROTULOS: Record<string, string> = {
  objetivo: 'Objetivo',
  publico: 'Público',
  formato: 'Formato',
}

const TEMPLATES = ['CAMPANHA', 'GRUPO', 'ANUNCIO'].map((nivel) => ({
  id: `t-${nivel}`,
  plataforma_id: META.id,
  nivel,
  separador: '_',
  marcador_ausencia: 'NA',
  tokens: [
    { tipo: 'literal', valor: 'FB' },
    { tipo: 'campo', chave: CAMPOS[nivel], rotulo: ROTULOS[CAMPOS[nivel]] },
    { tipo: 'match_id' },
  ],
  versao: 3,
  ativo: true,
}))

const DICIONARIO = [
  { id: 'd1', plataforma_id: null, categoria: 'objetivo', termo: 'Conversão', abreviacao: 'CV' },
  { id: 'd2', plataforma_id: null, categoria: 'publico', termo: 'Remarketing', abreviacao: 'RMKT' },
  { id: 'd3', plataforma_id: null, categoria: 'publico', termo: 'Frio', abreviacao: 'FRIO' },
  { id: 'd4', plataforma_id: null, categoria: 'formato', termo: 'Stories', abreviacao: 'ST' },
  { id: 'd5', plataforma_id: null, categoria: 'formato', termo: 'Reels', abreviacao: 'RLS' },
]

/** Servidor falso com memória: é a hierarquia que está sendo testada. */
type No = { id: string; pai_id: string; nome_interno: string; match_id: string }

let grupos: No[] = []
let anuncios: No[] = []
/** Corpos recebidos em POST /anuncios, para conferir o vínculo escolhido. */
let anunciosCriados: { grupo_anuncio_id: string; nome_interno: string }[] = []

function no(item: No) {
  return {
    ...item,
    nomenclatura: `FB_${item.match_id}`,
    taxonomia_id: `tx-${item.id}`,
    gerado_em: '2026-08-04T12:00:00Z',
    criado_em: '2026-08-04T12:00:00Z',
  }
}

function servidorFalso() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const corpo = init?.body ? JSON.parse(String(init.body)) : undefined
    const resposta = (dados: unknown, status = 200) =>
      ({ ok: status < 400, status, json: async () => dados }) as Response

    if (url.startsWith('/api/plataformas?')) return resposta([META])
    if (url.includes('/templates')) return resposta(TEMPLATES)
    if (url.startsWith('/api/dicionario')) return resposta(DICIONARIO)

    if (url === '/api/taxonomias/preview') {
      const valores = Object.values(corpo.campos as Record<string, string>)
      const abrev = valores.map((v) => DICIONARIO.find((d) => d.termo === v)?.abreviacao ?? v)
      const nome = ['FB', ...abrev, 'X0000'].join('_')
      return resposta({
        nomenclatura: nome,
        match_id_provisorio: true,
        template_versao: 3,
        limite_caracteres: 400,
        caracteres: nome.length,
      })
    }

    if (url === '/api/campanhas') {
      return resposta({ id: 'c1', match_id: 'C0001', nome_interno: corpo.nome_interno })
    }

    if (url === '/api/grupos') {
      const item = {
        id: `g${grupos.length + 1}`,
        pai_id: corpo.campanha_id,
        nome_interno: corpo.nome_interno,
        match_id: `G000${grupos.length + 1}`,
      }
      grupos.push(item)
      return resposta(item)
    }

    if (url === '/api/anuncios') {
      anunciosCriados.push(corpo)
      const item = {
        id: `a${anuncios.length + 1}`,
        pai_id: corpo.grupo_anuncio_id,
        nome_interno: corpo.nome_interno,
        match_id: `A000${anuncios.length + 1}`,
      }
      anuncios.push(item)
      return resposta(item)
    }

    if (url === '/api/taxonomias') {
      return resposta({
        id: `tx-${corpo.entidade_id}`,
        nivel: corpo.nivel,
        nomenclatura_final: `FB_${corpo.nivel}_FINAL`,
      })
    }

    if (url === '/api/campanhas/c1/grupos') return resposta(grupos.map(no))

    const filhos = url.match(/^\/api\/grupos\/([^/]+)\/anuncios$/)
    if (filhos) return resposta(anuncios.filter((a) => a.pai_id === filhos[1]).map(no))

    throw new Error(`URL não mockada: ${url}`)
  })
}

beforeEach(() => {
  grupos = []
  anuncios = []
  anunciosCriados = []
  vi.stubGlobal('fetch', servidorFalso())
  vi.stubGlobal('crypto', { ...crypto, randomUUID: () => 'lote-1' })
})

const painel = (titulo: string) =>
  screen.getByRole('heading', { name: titulo }).closest('section')!

async function preencher(user: ReturnType<typeof userEvent.setup>, titulo: string, opcoes: {
  nome: string
  campo: string
  valor: string
}) {
  const secao = painel(titulo)
  await user.type(within(secao).getByLabelText('Nome interno'), opcoes.nome)
  await user.selectOptions(within(secao).getByLabelText(new RegExp(opcoes.campo)), opcoes.valor)
}

/** Leva o gerador até ter campanha, grupo e anúncio salvos. */
async function primeiraTaxonomia() {
  const user = userEvent.setup()
  render(<Taxonomia />)
  await user.selectOptions(await screen.findByLabelText('Plataforma'), META.id)

  await waitFor(() => expect(screen.getByLabelText(/Objetivo/)).toBeInTheDocument())
  await preencher(user, 'Campanha', { nome: 'Black Friday', campo: 'Objetivo', valor: 'Conversão' })

  await waitFor(() => expect(screen.getByLabelText(/Público/)).toBeInTheDocument())
  await preencher(user, 'Grupo de anúncio', { nome: 'Remkt 30d', campo: 'Público', valor: 'Remarketing' })

  await waitFor(() => expect(screen.getByLabelText(/Formato/)).toBeInTheDocument())
  await preencher(user, 'Anúncio', { nome: 'Story 01', campo: 'Formato', valor: 'Stories' })

  const salvar = screen.getByRole('button', { name: /Salvar e gerar/ })
  await waitFor(() => expect(salvar).toBeEnabled())
  await user.click(salvar)

  // O cartão da estrutura já existe vazio desde o início, então esperar por
  // ele não prova nada: o que marca o fim do salvamento é a campanha aparecer
  // dentro dele.
  await waitFor(() =>
    expect(within(arvore()).getByText('Black Friday')).toBeInTheDocument(),
  )
  return user
}

const arvore = () => screen.getByRole('heading', { name: 'Estrutura da campanha' }).closest('section')!

// --------------------------------------------------------------------------

describe('árvore da campanha', () => {
  it('mostra a campanha com o grupo e o anúncio recém-criados', async () => {
    await primeiraTaxonomia()

    const secao = within(arvore())
    expect(secao.getByText('Black Friday')).toBeInTheDocument()
    expect(secao.getByText('C0001')).toBeInTheDocument()
    expect(secao.getByText('Remkt 30d')).toBeInTheDocument()
    expect(secao.getByText('G0001')).toBeInTheDocument()
    expect(secao.getByText('Story 01')).toBeInTheDocument()
    expect(secao.getByText('A0001')).toBeInTheDocument()
  })

  it('não oferece editar nem excluir nomenclatura (D-004)', async () => {
    await primeiraTaxonomia()

    const botoes = within(arvore())
      .getAllByRole('button')
      .map((b) => b.textContent ?? '')
    expect(botoes.some((t) => /editar|excluir|remover/i.test(t))).toBe(false)
  })

  it('nunca expõe o UUID da entidade, só o match ID', async () => {
    await primeiraTaxonomia()
    expect(arvore().textContent).not.toContain('g1')
    expect(arvore().textContent).not.toContain('a1')
  })
})

describe('coluna de contexto', () => {
  it('mostra o cartão da estrutura antes de existir campanha, com a ação desabilitada', async () => {
    render(<Taxonomia />)
    await screen.findByLabelText('Plataforma')

    const secao = within(arvore())
    expect(
      secao.getByText('A estrutura aparece aqui assim que a primeira campanha for salva.'),
    ).toBeInTheDocument()
    expect(secao.getByRole('button', { name: 'Novo grupo' })).toBeDisabled()
  })

  it('recolhe e expande os anúncios de um grupo', async () => {
    const user = await primeiraTaxonomia()

    const alternar = within(arvore()).getByRole('button', {
      name: 'Recolher anúncios de Remkt 30d',
    })
    expect(alternar).toHaveAttribute('aria-expanded', 'true')
    expect(within(arvore()).getByText('Story 01')).toBeInTheDocument()

    await user.click(alternar)

    expect(within(arvore()).queryByText('Story 01')).not.toBeInTheDocument()
    expect(
      within(arvore()).getByRole('button', { name: 'Expandir anúncios de Remkt 30d' }),
    ).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('vários grupos na mesma campanha', () => {
  it('cria outro grupo sem refazer a campanha e sem pedir vínculo', async () => {
    const user = await primeiraTaxonomia()

    await user.click(within(arvore()).getByRole('button', { name: 'Novo grupo' }))

    // A campanha sai do formulário: ela já existe, e o grupo pertence a ela.
    expect(screen.queryByRole('heading', { name: 'Campanha' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Vincular ao grupo')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Grupo de anúncio' })).toBeInTheDocument()

    await preencher(user, 'Grupo de anúncio', { nome: 'Publico frio', campo: 'Público', valor: 'Frio' })

    const salvar = screen.getByRole('button', { name: /Salvar grupo/ })
    await waitFor(() => expect(salvar).toBeEnabled())
    await user.click(salvar)

    await waitFor(() => expect(within(arvore()).getByText('Publico frio')).toBeInTheDocument())
    expect(within(arvore()).getByText('G0002')).toBeInTheDocument()
    // O primeiro grupo continua na árvore: 1→N, não substituição.
    expect(within(arvore()).getByText('Remkt 30d')).toBeInTheDocument()
  })
})

describe('vários anúncios no grupo escolhido', () => {
  it('assume o último grupo criado como padrão e permite trocar', async () => {
    const user = await primeiraTaxonomia()

    // Segundo grupo, para haver escolha de verdade.
    await user.click(within(arvore()).getByRole('button', { name: 'Novo grupo' }))
    await preencher(user, 'Grupo de anúncio', { nome: 'Publico frio', campo: 'Público', valor: 'Frio' })
    const salvarGrupo = screen.getByRole('button', { name: /Salvar grupo/ })
    await waitFor(() => expect(salvarGrupo).toBeEnabled())
    await user.click(salvarGrupo)
    await waitFor(() => expect(within(arvore()).getByText('Publico frio')).toBeInTheDocument())

    // Cada grupo tem o seu "+", e o nome acessível é o que os distingue.
    await user.click(within(arvore()).getByRole('button', { name: 'Novo anúncio em Publico frio' }))

    const vinculo = screen.getByLabelText('Vincular ao grupo')
    expect(vinculo).toHaveValue('g2')

    // Trocar o vínculo é o ponto: o anúncio vai para o grupo escolhido.
    await user.selectOptions(vinculo, 'g1')
    await preencher(user, 'Anúncio', { nome: 'Reels 01', campo: 'Formato', valor: 'Reels' })

    const salvar = screen.getByRole('button', { name: /Salvar anúncio/ })
    await waitFor(() => expect(salvar).toBeEnabled())
    await user.click(salvar)

    await waitFor(() => expect(within(arvore()).getByText('Reels 01')).toBeInTheDocument())
    expect(anunciosCriados.at(-1)).toMatchObject({ grupo_anuncio_id: 'g1', nome_interno: 'Reels 01' })
  })

  it('o botão de um grupo específico já traz aquele grupo no vínculo', async () => {
    const user = await primeiraTaxonomia()

    await user.click(
      within(arvore()).getByRole('button', { name: 'Novo anúncio em Remkt 30d' }),
    )
    // O seletor aparece mesmo com um grupo só: além de permitir a troca, ele
    // é o que diz em qual grupo o anúncio vai cair.
    expect(screen.getByLabelText('Vincular ao grupo')).toHaveValue('g1')

    await preencher(user, 'Anúncio', { nome: 'Reels 02', campo: 'Formato', valor: 'Reels' })
    const salvar = screen.getByRole('button', { name: /Salvar anúncio/ })
    await waitFor(() => expect(salvar).toBeEnabled())
    await user.click(salvar)

    expect(anunciosCriados.at(-1)).toMatchObject({ grupo_anuncio_id: 'g1' })
  })
})
