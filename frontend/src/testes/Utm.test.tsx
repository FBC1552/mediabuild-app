import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ValidadorUtm } from '../componentes/ValidadorUtm'
import type { LaudoUtm } from '../tipos'

/**
 * O contrato é o da D-012: `POST /utm/validar` responde **sempre 200**, com
 * erros e avisos separados. O endpoint pode ainda não estar de pé — o mock
 * aqui segue o contrato da decisão, não um formato inventado.
 */

const ALVOS = [
  { taxonomia_id: 'tx-anuncio', rotulo: 'Anúncio · FB_ST_A0001' },
  { taxonomia_id: 'tx-campanha', rotulo: 'Campanha · FB_CV_C0001' },
]

const LAUDO_RUIM: LaudoUtm = {
  valido: false,
  erros: [
    {
      codigo: 'match_id_divergente',
      parametro: 'utm_campaign',
      mensagem:
        "O 'utm_campaign' aponta para 'c0007', mas esta campanha é 'c0001'. " +
        'Provavelmente a URL foi copiada de outra campanha.',
      encontrado: 'c0007',
      esperado: 'c0001',
    },
  ],
  avisos: [
    {
      codigo: 'utm_id_ausente',
      parametro: 'utm_id',
      mensagem: 'Sem utm_id. É por ele que o GA4 junta o custo importado com a sessão.',
      encontrado: null,
      esperado: 'c0001',
    },
  ],
  parametros: { utm_source: 'facebook', utm_medium: 'cpc', utm_campaign: 'promo_c0007' },
  sugestao: { utm_campaign: 'fb_cv_c0001' },
  url_sugerida: 'https://exemplo.com.br/?utm_source=facebook&utm_campaign=fb_cv_c0001',
}

const LAUDO_BOM: LaudoUtm = {
  valido: true,
  erros: [],
  avisos: [],
  parametros: { utm_source: 'facebook', utm_campaign: 'fb_cv_c0001' },
  sugestao: {},
  // O servidor manda string vazia, não nulo, quando não há o que sugerir.
  url_sugerida: '',
}

let laudo: LaudoUtm = LAUDO_RUIM
let pedidos: { url: string; taxonomia_id: string }[] = []

beforeEach(() => {
  laudo = LAUDO_RUIM
  pedidos = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url !== '/api/utm/validar') throw new Error(`URL não mockada: ${url}`)
      pedidos.push(JSON.parse(String(init!.body)))
      // Sempre 200: URL problemática não é requisição malformada.
      return { ok: true, status: 200, json: async () => laudo } as Response
    }),
  )
})

async function conferir(url: string) {
  const user = userEvent.setup()
  render(<ValidadorUtm alvos={ALVOS} />)
  await user.type(screen.getByLabelText('URL de destino'), url)
  await user.click(screen.getByRole('button', { name: 'Conferir URL' }))
  return user
}

// --------------------------------------------------------------------------

describe('estado anterior à primeira nomenclatura', () => {
  it('explica que é preciso gerar antes, em vez de deixar um campo morto', () => {
    render(<ValidadorUtm alvos={[]} />)
    expect(screen.queryByLabelText('URL de destino')).not.toBeInTheDocument()
    expect(screen.getByText(/Gere uma nomenclatura para conferir/)).toBeInTheDocument()
  })
})

describe('laudo', () => {
  it('separa erro de aviso visualmente e manda a taxonomia escolhida', async () => {
    await conferir('https://exemplo.com.br/?utm_campaign=promo_c0007')

    const bloco = await screen.findByRole('alert')
    expect(bloco).toHaveAttribute('data-tipo', 'erro')
    expect(within(bloco).getByText(/copiada de outra campanha/)).toBeInTheDocument()

    // O aviso está em outro bloco, com outro tipo — a distinção é o ponto.
    const aviso = screen.getByText(/Sem utm_id/).closest('.laudo')!
    expect(aviso).toHaveAttribute('data-tipo', 'aviso')
    expect(aviso).not.toBe(bloco)

    expect(pedidos).toEqual([
      {
        url: 'https://exemplo.com.br/?utm_campaign=promo_c0007',
        taxonomia_id: 'tx-anuncio',
      },
    ])
  })

  it('mostra encontrado e esperado, que é o que resolve o caso', async () => {
    await conferir('https://exemplo.com.br/?utm_campaign=promo_c0007')
    expect(await screen.findByText(/encontrado: c0007 · esperado: c0001/)).toBeInTheDocument()
  })

  it('lista os parâmetros lidos da URL', async () => {
    await conferir('https://exemplo.com.br/?utm_campaign=promo_c0007')
    await screen.findByRole('alert')

    expect(screen.getByText('utm_source')).toBeInTheDocument()
    expect(screen.getByText('facebook')).toBeInTheDocument()
    expect(screen.getByText('promo_c0007')).toBeInTheDocument()
  })

  it('copia a URL sugerida', async () => {
    const user = await conferir('https://exemplo.com.br/?utm_campaign=promo_c0007')
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: 'Copiar URL sugerida' }))
    expect(await navigator.clipboard.readText()).toBe(LAUDO_RUIM.url_sugerida)
  })

  it('confirma quando não há erro nenhum', async () => {
    laudo = LAUDO_BOM
    await conferir('https://exemplo.com.br/?utm_campaign=fb_cv_c0001')

    expect(await screen.findByText('Nenhum erro na URL.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Copiar URL sugerida/ })).not.toBeInTheDocument()
  })

  it('confere contra a taxonomia escolhida no seletor', async () => {
    const user = await conferir('https://exemplo.com.br/?utm_campaign=promo_c0007')
    await screen.findByRole('alert')

    await user.selectOptions(screen.getByLabelText('Conferir contra'), 'tx-campanha')
    // Trocar o alvo invalida o laudo anterior: ele era de outro nível.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Conferir URL' }))
    await waitFor(() => expect(pedidos).toHaveLength(2))
    expect(pedidos[1].taxonomia_id).toBe('tx-campanha')
  })

  it('não deixa conferir com o campo vazio', () => {
    render(<ValidadorUtm alvos={ALVOS} />)
    expect(screen.getByRole('button', { name: 'Conferir URL' })).toBeDisabled()
  })
})
