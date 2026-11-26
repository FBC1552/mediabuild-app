import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useState } from 'react'

import { AplicativoTaxonomia } from '../componentes/AplicativoTaxonomia'
import type { AbaTaxonomia } from '../roteador'
import { ComSessao } from './ajudaSessao'

/**
 * As abas viraram rotas, então `<App />` em `#/` é a splash. Estes testes são
 * de formulário, não de navegação: renderizam o aplicativo de taxonomia
 * direto, com um dono de estado mínimo no lugar do roteador.
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


const META = { id: 'p-meta', nome: 'Meta', sigla: 'METAA', ativo: true }
const TIKTOK = { id: 'p-tt', nome: 'TikTok', sigla: 'TIKTOK', ativo: true }

const DICIONARIO = [
  { id: 'a1', plataforma_id: null, categoria: 'objetivo', termo: 'Conversão', abreviacao: 'CV' },
  { id: 'a2', plataforma_id: null, categoria: 'empresa', termo: 'Loja Alfa', abreviacao: 'ALF' },
  {
    id: 'a3',
    plataforma_id: META.id,
    categoria: 'posicionamento',
    termo: 'Instagram Stories',
    abreviacao: 'IGST',
  },
]

const CAMPANHAS = [
  { id: 'c1', match_id: 'C0001', nome_interno: 'Black Friday' },
  { id: 'c2', match_id: 'C0002', nome_interno: 'Natal' },
]

const HISTORICO = [
  {
    id: 'h1',
    nivel: 'CAMPANHA' as const,
    nomenclatura_final: 'ALV27_ALF_METAA_INSTA_CV_AGO_C0001',
    plataforma: 'Meta',
    campanha: 'Black Friday',
    nome_interno: 'Black Friday',
    match_id: 'C0001',
    caracteres: 34,
    template_versao: 2,
    campos: { objetivo: 'Conversão' },
    lote_id: 'lote-1',
    criado_em: '2026-08-03T12:00:00Z',
  },
  {
    id: 'h2',
    nivel: 'GRUPO' as const,
    nomenclatura_final: 'F_25-34_BOLSA_SUD_RJ_RMKT_G0001',
    plataforma: 'Meta',
    campanha: 'Black Friday',
    nome_interno: 'Remarketing 30d',
    match_id: 'G0001',
    caracteres: 31,
    template_versao: 2,
    campos: {},
    lote_id: 'lote-1',
    criado_em: '2026-08-03T12:00:05Z',
  },
]

/** URLs pedidas, para assertar os filtros que a tela envia ao servidor. */
let chamadas: string[] = []
let dicionarioAtual = DICIONARIO

function mockFetch() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    chamadas.push(`${init?.method ?? 'GET'} ${url}`)
    const resposta = (corpo: unknown, status = 200) =>
      ({ ok: status < 400, status, json: async () => corpo }) as Response

    if (url.startsWith('/api/plataformas?')) return resposta([META, TIKTOK])
    if (url.includes('/templates')) return resposta([])
    if (url.startsWith('/api/campanhas')) return resposta(CAMPANHAS)
    if (url.startsWith('/api/taxonomias/historico')) {
      const filtro = new URL(url, 'http://x').searchParams
      const linhas = filtro.get('nivel')
        ? HISTORICO.filter((h) => h.nivel === filtro.get('nivel'))
        : HISTORICO
      return resposta(linhas)
    }

    if (url.startsWith('/api/dicionario')) {
      if (init?.method === 'POST') {
        const corpo = JSON.parse(String(init.body))
        dicionarioAtual = [...dicionarioAtual, { id: 'novo', plataforma_id: null, ...corpo }]
        return resposta(dicionarioAtual.at(-1), 201)
      }
      if (init?.method === 'DELETE') {
        const id = url.split('/').pop()!
        dicionarioAtual = dicionarioAtual.filter((d) => d.id !== id)
        return resposta(undefined, 204)
      }
      return resposta(dicionarioAtual)
    }

    throw new Error(`URL não mockada: ${url}`)
  })
}

beforeEach(() => {
  chamadas = []
  dicionarioAtual = DICIONARIO
  vi.stubGlobal('fetch', mockFetch())
})

async function abrir(aba: string) {
  const user = userEvent.setup()
  render(<Taxonomia />)
  await screen.findByRole('tab', { name: 'Gerar' })
  await user.click(screen.getByRole('tab', { name: aba }))
  return user
}

/**
 * O gerador continua montado (apenas `hidden`) e tem um seletor
 * "Plataforma" próprio. O `hidden` não esconde o elemento das buscas do
 * testing-library, então as consultas do histórico precisam ser escopadas.
 */
// O cartão de filtros e o `<h2>Filtros` SAÍRAM (§7.3): eram ~120px verticais
// que valem cinco linhas de tabela, e os rótulos dos campos já dizem o que
// cada controle é. O escopo agora é a própria linha de controles.
const filtros = () => document.querySelector<HTMLElement>('.filtros')!
const acoesDoHistorico = () => document.querySelector<HTMLElement>('.filtros-acoes')!
const tabela = () => screen.getByRole('table')
const linhaDe = (texto: string) => within(tabela()).getByText(texto).closest('tr')!

// --------------------------------------------------------------------------

describe('navegação por abas', () => {
  it('começa em Gerar e marca a aba ativa', async () => {
    render(<Taxonomia />)
    const gerar = await screen.findByRole('tab', { name: 'Gerar' })
    expect(gerar).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Histórico' })).toHaveAttribute(
      'aria-selected',
      'false',
    )
  })

  it('mantém o gerador montado ao visitar outra aba', async () => {
    const user = await abrir('Dicionário')
    // O seletor de plataforma continua no DOM, só escondido — é o que
    // preserva o formulário de quem saiu para cadastrar um termo.
    expect(screen.getByLabelText('Plataforma')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Gerar' }))
    expect(screen.getByRole('tab', { name: 'Gerar' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('aba Dicionário', () => {
  it('lista os termos cadastrados com o De → Para', async () => {
    await abrir('Dicionário')

    await waitFor(() => expect(screen.getByText('Loja Alfa')).toBeInTheDocument())
    expect(screen.getByText('ALF')).toBeInTheDocument()
    expect(screen.getByText('Conversão')).toBeInTheDocument()
  })

  it('mostra o escopo: global ou de uma plataforma só', async () => {
    await abrir('Dicionário')

    await waitFor(() => expect(screen.getByText('Instagram Stories')).toBeInTheDocument())
    const linha = screen.getByText('Instagram Stories').closest('tr')!
    expect(within(linha).getByText('Meta')).toBeInTheDocument()

    const global = screen.getByText('Loja Alfa').closest('tr')!
    expect(within(global).getByText('Todas')).toBeInTheDocument()
  })

  it('filtra a tabela por categoria', async () => {
    const user = await abrir('Dicionário')
    await waitFor(() => expect(screen.getByText('Loja Alfa')).toBeInTheDocument())

    // O `<select>` de categoria da LISTA é distinto do que escolhe a categoria
    // do termo novo (§6.6): filtrar e criar são conversas diferentes, e
    // misturá-las era o erro de agrupamento que a tela carregava.
    await user.selectOptions(screen.getByLabelText('Categoria da lista'), 'empresa')

    expect(screen.getByText('Loja Alfa')).toBeInTheDocument()
    expect(screen.queryByText('Conversão')).not.toBeInTheDocument()
  })

  it('cadastra um termo novo e recarrega a lista', async () => {
    const user = await abrir('Dicionário')
    await waitFor(() => expect(screen.getByText('Loja Alfa')).toBeInTheDocument())

    await user.type(screen.getByLabelText('ou categoria nova'), 'canal')
    await user.type(screen.getByLabelText('De'), 'Instagram')
    await user.type(screen.getByLabelText('Para'), 'INSTA')
    await user.click(screen.getByRole('button', { name: 'Adicionar' }))

    await waitFor(() => expect(screen.getByText('Instagram')).toBeInTheDocument())
    expect(chamadas).toContain('POST /api/dicionario')
  })

  it('exige categoria, De e Para antes de habilitar o botão', async () => {
    const user = await abrir('Dicionário')
    const botao = screen.getByRole('button', { name: 'Adicionar' })
    expect(botao).toBeDisabled()

    await user.type(screen.getByLabelText('ou categoria nova'), 'canal')
    await user.type(screen.getByLabelText('De'), 'Instagram')
    expect(botao).toBeDisabled()

    await user.type(screen.getByLabelText('Para'), 'INSTA')
    expect(botao).toBeEnabled()
  })

  it('remove um termo depois de confirmar no diálogo', async () => {
    const user = await abrir('Dicionário')
    await waitFor(() => expect(screen.getByText('Loja Alfa')).toBeInTheDocument())

    const linha = screen.getByText('Loja Alfa').closest('tr')!
    await user.click(within(linha).getByRole('button', { name: 'Remover' }))

    // `window.confirm` saiu (§6.7): ele não diz QUAL linha está sendo
    // removida, nem o que a remoção não faz. O diálogo nomeia o termo e a
    // categoria, e explica que nomenclatura já gerada não é afetada (D-004).
    const dialogo = await screen.findByRole('dialog')
    expect(
      within(dialogo).getByRole('heading', { name: 'Remover "Loja Alfa" de empresa?' }),
    ).toBeInTheDocument()
    expect(within(dialogo).getByText(/não são afetados/)).toBeInTheDocument()

    await user.click(within(dialogo).getByRole('button', { name: 'Remover termo' }))

    await waitFor(() => expect(screen.queryByText('Loja Alfa')).not.toBeInTheDocument())
    expect(chamadas).toContain('DELETE /api/dicionario/a2')
  })

  it('cancelar no diálogo não remove nada', async () => {
    const user = await abrir('Dicionário')
    await waitFor(() => expect(screen.getByText('Loja Alfa')).toBeInTheDocument())

    const linha = screen.getByText('Loja Alfa').closest('tr')!
    await user.click(within(linha).getByRole('button', { name: 'Remover' }))
    const dialogo = await screen.findByRole('dialog')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar' }))

    expect(screen.getByText('Loja Alfa')).toBeInTheDocument()
    expect(chamadas.some((c) => c.startsWith('DELETE'))).toBe(false)
  })

  it('edita a abreviação na própria linha, sem window.prompt', async () => {
    const user = await abrir('Dicionário')
    await waitFor(() => expect(screen.getByText('Loja Alfa')).toBeInTheDocument())

    const prompt = vi.spyOn(window, 'prompt')
    const linha = screen.getByText('Loja Alfa').closest('tr')!
    await user.click(within(linha).getByRole('button', { name: 'Editar' }))

    // O único campo editável é `abreviacao` — igual à API.
    const campo = within(linha).getByLabelText('Abreviação de Loja Alfa')
    expect(campo).toHaveValue('ALF')
    expect(prompt).not.toHaveBeenCalled()
  })
})

describe('aba Histórico', () => {
  it('lista as nomenclaturas com plataforma e campanha resolvidas', async () => {
    await abrir('Histórico')

    await waitFor(() =>
      expect(within(tabela()).getByText('ALV27_ALF_METAA_INSTA_CV_AGO_C0001')).toBeInTheDocument(),
    )
    const linha = linhaDe('ALV27_ALF_METAA_INSTA_CV_AGO_C0001')
    expect(within(linha).getByText('Meta')).toBeInTheDocument()
    expect(within(linha).getByText('Black Friday')).toBeInTheDocument()
    expect(within(linha).getByText(/34 caracteres/)).toBeInTheDocument()
  })

  it('oferece os filtros de data, plataforma e campanha', async () => {
    await abrir('Histórico')

    expect(within(filtros()).getByLabelText('Criado a partir de')).toHaveAttribute('type', 'date')
    expect(within(filtros()).getByLabelText('até')).toHaveAttribute('type', 'date')
    expect(within(filtros()).getByLabelText('Plataforma')).toBeInTheDocument()
    await waitFor(() =>
      expect(
        within(within(filtros()).getByLabelText('Campanha')).getByRole('option', {
          name: /Black Friday/,
        }),
      ).toBeInTheDocument(),
    )
  })

  it('manda o filtro escolhido para o servidor', async () => {
    const user = await abrir('Histórico')
    await waitFor(() => expect(within(tabela()).getAllByText('Black Friday').length).toBeGreaterThan(0))

    chamadas = []
    await user.selectOptions(within(filtros()).getByLabelText('Nível'), 'GRUPO')

    await waitFor(() =>
      expect(chamadas.some((c) => c.includes('nivel=GRUPO'))).toBe(true),
    )
    await waitFor(() =>
      expect(within(tabela()).queryByText('ALV27_ALF_METAA_INSTA_CV_AGO_C0001')).toBeNull(),
    )
  })

  it('limpa os filtros e recarrega tudo', async () => {
    const user = await abrir('Histórico')
    await waitFor(() => expect(within(tabela()).getAllByText('Black Friday').length).toBeGreaterThan(0))

    const limpar = within(acoesDoHistorico()).getByRole('button', { name: 'Limpar filtros' })
    expect(limpar).toBeDisabled()

    await user.selectOptions(within(filtros()).getByLabelText('Nível'), 'GRUPO')
    await waitFor(() => expect(limpar).toBeEnabled())

    await user.click(limpar)
    await waitFor(() =>
      expect(within(tabela()).getByText('ALV27_ALF_METAA_INSTA_CV_AGO_C0001')).toBeInTheDocument(),
    )
  })

  it('o link de Excel carrega os mesmos filtros da tela', async () => {
    const user = await abrir('Histórico')
    await waitFor(() => expect(within(tabela()).getAllByText('Black Friday').length).toBeGreaterThan(0))

    await user.selectOptions(within(filtros()).getByLabelText('Nível'), 'GRUPO')

    const link = within(acoesDoHistorico()).getByRole('link', { name: 'Baixar Excel' })
    await waitFor(() => expect(link).toHaveAttribute('href', expect.stringContaining('nivel=GRUPO')))
    expect(link.getAttribute('href')).toContain('/taxonomias/export')
  })

  it('não oferece editar nem excluir — histórico é imutável (D-004)', async () => {
    await abrir('Histórico')
    await waitFor(() => expect(within(tabela()).getAllByText('Black Friday').length).toBeGreaterThan(0))

    expect(within(tabela()).queryByRole('button', { name: 'Editar' })).toBeNull()
    expect(within(tabela()).queryByRole('button', { name: 'Remover' })).toBeNull()
  })

  it('copia a nomenclatura da linha', async () => {
    const user = await abrir('Histórico')
    await waitFor(() => expect(within(tabela()).getAllByText('Black Friday').length).toBeGreaterThan(0))

    const linha = linhaDe('ALV27_ALF_METAA_INSTA_CV_AGO_C0001')
    await user.click(within(linha).getByRole('button', { name: 'Copiar' }))

    expect(await navigator.clipboard.readText()).toBe('ALV27_ALF_METAA_INSTA_CV_AGO_C0001')
  })
})
