import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PlanoDetalhe } from '../componentes/PlanoDetalhe'
import type { PlanoMidia } from '../tipos'

/**
 * D-B: desbalanço é estado válido de rascunho — a tela precisa ACEITAR e
 * EXIBIR (nunca redistribuir, nunca bloquear salvar). E a exportação com
 * desbalanço acima de 2% da verba total pede confirmação uma vez; abaixo
 * disso, exporta direto (docs/PLANO-DE-MIDIA-UI.md §4.2, decisão do usuário
 * repassada na tarefa).
 */

function planoBase(diferenca: string, verbaTotal: string): PlanoMidia {
  const somaCampanhas = (Number(verbaTotal) - Number(diferenca)).toFixed(2)
  return {
    id: 'plano-1',
    nome: 'Campanha Julho',
    verba_total: verbaTotal,
    observacoes: null,
    soma_campanhas: somaCampanhas,
    diferenca,
    criado_em: '2026-08-06T12:00:00Z',
    atualizado_em: '2026-08-06T12:00:00Z',
    campanhas: [
      {
        id: 'linha-c1',
        campanha_id: 'c1',
        plataforma_id: 'plat-1',
        nome_interno: 'Campanha de Julho',
        match_id: 'C3291',
        nomenclatura: 'AAAAA_BET_C3291',
        nomenclatura_atual: 'AAAAA_BET_C3291',
        nomenclatura_divergente: false,
        valor: somaCampanhas,
        percentual: '100.000',
        flight_inicio: null,
        flight_fim: null,
        kpi_primario_id: null,
        kpi_primario_codigo: null,
        kpi_primario_rotulo: null,
        kpi_primario_ativo: null,
        soma_grupos: '0.00',
        diferenca: somaCampanhas,
        grupos: [],
      },
    ],
  }
}

function stubFetch(plano: PlanoMidia) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/planos/plano-1')) {
        return { ok: true, status: 200, json: async () => plano } as Response
      }
      if (url.includes('/metricas')) {
        return { ok: true, status: 200, json: async () => [] } as Response
      }
      return { ok: true, status: 200, json: async () => [] } as Response
    }),
  )
}

beforeEach(() => {
  vi.stubGlobal('scrollTo', () => {})
})

describe('PlanoDetalhe — desbalanço', () => {
  it('aceita e exibe um plano desbalanceado, sem bloquear a tela', async () => {
    // R$ 500.000 de verba, R$ 13.500 sem campanha definida — igual ao mock do desenho.
    stubFetch(planoBase('13500.00', '500000.00'))
    render(<PlanoDetalhe planoId="plano-1" />)

    await screen.findByLabelText('Nome do plano')

    const faixa = screen.getByRole('status', { name: 'Saldo do plano' })
    expect(within(faixa).getByText(/R\$ 13\.500,00/)).toBeInTheDocument()
    expect(within(faixa).getByText(/não distribuído/)).toBeInTheDocument()

    // A árvore continua editável — nenhum campo desabilitado por causa do desbalanço.
    const campoValor = screen.getByLabelText('Campanha de Julho — valor em reais')
    expect(campoValor).not.toBeDisabled()
  })

  it('sobre-alocado usa um ícone de forma distinta do sub-alocado (não só cor)', async () => {
    stubFetch(planoBase('-5000.00', '500000.00'))
    render(<PlanoDetalhe planoId="plano-1" />)

    const faixa = await screen.findByRole('status', { name: 'Saldo do plano' })
    expect(within(faixa).getByText(/além do orçamento/)).toBeInTheDocument()
    // O selo de sobre-alocação é o único que usa a marca "sobrealocado" —
    // uma forma de ícone própria, não a mesma seta do sub-alocado girada.
    expect(faixa.querySelector('[data-marca="sobrealocado"]')).toBeInTheDocument()
    expect(faixa.querySelector('[data-marca="subalocado"]')).not.toBeInTheDocument()
  })
})

describe('PlanoDetalhe — exportação com desbalanço', () => {
  it('pede confirmação quando o desbalanço passa de 2% da verba total', async () => {
    const usuario = userEvent.setup()
    // 13.500 / 500.000 = 2,7% — acima do limiar.
    stubFetch(planoBase('13500.00', '500000.00'))
    render(<PlanoDetalhe planoId="plano-1" />)
    await screen.findByLabelText('Nome do plano')

    await usuario.click(screen.getByRole('button', { name: 'Baixar Excel' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/não alocados. Exportar mesmo assim/)
    expect(screen.getByRole('link', { name: 'Exportar' })).toHaveAttribute(
      'href',
      expect.stringContaining('/planos/export?plano_id=plano-1'),
    )

    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('exporta direto, sem confirmação, quando o desbalanço está dentro de 2%', async () => {
    const usuario = userEvent.setup()
    // 1.000 / 500.000 = 0,2% — abaixo do limiar.
    stubFetch(planoBase('1000.00', '500000.00'))
    render(<PlanoDetalhe planoId="plano-1" />)
    await screen.findByLabelText('Nome do plano')

    // jsdom não navega de verdade (`window.location.assign` não é
    // configurável ali) — o que este teste prova é que o clique NÃO abre a
    // confirmação: ela só aparece quando o desbalanço passa de 2%.
    await usuario.click(screen.getByRole('button', { name: 'Baixar Excel' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Exportar' })).not.toBeInTheDocument()
  })
})
