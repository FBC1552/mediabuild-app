/**
 * Busca no Dicionário (UX-NAVEGACAO §6).
 *
 * O comportamento que justifica a tela: o analista recebeu
 * `termo_desconhecido` do motor e veio conferir. Ele digita o que digitou no
 * formulário — sem acento, em minúscula — e TEM que achar o termo cadastrado.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Dicionario } from '../componentes/Dicionario'
import { Preview } from '../componentes/Preview'
import { normalizarBusca } from '../texto'
import { ComSessao } from './ajudaSessao'

const META = { id: 'p-meta', nome: 'Meta', sigla: 'METAA', ativo: true }

const TERMOS = [
  { id: 'a1', plataforma_id: null, categoria: 'objetivo', termo: 'Conversão', abreviacao: 'CV' },
  { id: 'a2', plataforma_id: null, categoria: 'empresa', termo: 'Loja Alfa', abreviacao: 'ALF' },
  {
    id: 'a3',
    plataforma_id: null,
    categoria: 'objetivo',
    termo: 'Reconhecimento',
    abreviacao: 'RCN',
  },
]

function mockDicionario(termos: unknown[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const resposta = (corpo: unknown) => ({ ok: true, status: 200, json: async () => corpo })
      if (url.startsWith('/api/dicionario')) return resposta(termos) as unknown as Response
      throw new Error(`URL não mockada: ${url}`)
    }),
  )
}

async function abrir(termos: unknown[] = TERMOS) {
  mockDicionario(termos)
  const user = userEvent.setup()
  render(
    <ComSessao>
      <Dicionario plataformas={[META]} />
    </ComSessao>,
  )
  return user
}

const busca = () => screen.getByLabelText('Buscar termo')
const linhas = () => within(screen.getByRole('table')).getAllByRole('row').slice(1)

beforeEach(() => {
  window.history.replaceState(null, '', '#/taxonomia/dicionario')
})

describe('normalizarBusca', () => {
  it('dobra acento e caixa', () => {
    expect(normalizarBusca('Conversão')).toBe('CONVERSAO')
    expect(normalizarBusca('conversao')).toBe('CONVERSAO')
  })

  it('preserva `_` e `-`, que são significativos na coluna Para', () => {
    expect(normalizarBusca('25-34_F')).toBe('25-34_F')
  })
})

describe('busca local', () => {
  it('acha "Conversão" digitando "conversao"', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    await user.type(busca(), 'conversao')

    expect(screen.getByText('Conversão')).toBeInTheDocument()
    expect(screen.queryByText('Loja Alfa')).not.toBeInTheDocument()
    expect(linhas()).toHaveLength(1)
  })

  it('busca também na coluna Para e na categoria', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    // A pergunta real do analista é frequentemente "que abreviações existem
    // em objetivo?" — digitar a categoria é mais rápido que caçá-la no select.
    await user.type(busca(), 'objetivo')
    expect(linhas()).toHaveLength(2)

    await user.clear(busca())
    await user.type(busca(), 'alf')
    expect(screen.getByText('Loja Alfa')).toBeInTheDocument()
    expect(linhas()).toHaveLength(1)
  })

  it('não é servidor: filtrar não dispara requisição nenhuma', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())
    const antes = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length

    await user.type(busca(), 'conversao')

    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(antes)
  })
})

describe('os três estados vazios', () => {
  it('dicionário sem nenhum termo diz o que fazer', async () => {
    await abrir([])
    expect(await screen.findByText('Nenhum termo cadastrado ainda.')).toBeInTheDocument()
    expect(screen.getByText(/O gerador recusa termos que não estão aqui/)).toBeInTheDocument()
  })

  it('busca sem resultado é DISTINTA de dicionário vazio e oferece cadastrar', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    await user.type(busca(), 'guarda-chuva')

    const vazio = screen.getByText('Nenhum termo com "guarda-chuva".').closest('.estado')!
    // A diferença entre os dois vazios É a informação: aqui existe dicionário,
    // só não existe este termo.
    expect(screen.queryByText('Nenhum termo cadastrado ainda.')).not.toBeInTheDocument()
    expect(within(vazio as HTMLElement).getByRole('button', { name: 'Limpar busca' })).toBeInTheDocument()
    expect(
      within(vazio as HTMLElement).getByRole('button', { name: 'Cadastrar "guarda-chuva"' }),
    ).toBeInTheDocument()
  })

  it('categoria sem termos é um terceiro vazio, com a saída certa', async () => {
    const user = await abrir([TERMOS[0]])
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    // Só existe a categoria `objetivo`; escolher outra exigiria um termo dela.
    await user.type(busca(), 'zzz')
    expect(screen.getByText('Nenhum termo com "zzz".')).toBeInTheDocument()
  })

  it('`Cadastrar "X"` preenche o campo De sem redigitar', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    await user.type(busca(), 'guarda-chuva')
    const vazio = screen.getByText('Nenhum termo com "guarda-chuva".').closest('.estado')!
    await user.click(
      within(vazio as HTMLElement).getByRole('button', { name: 'Cadastrar "guarda-chuva"' }),
    )

    expect(screen.getByLabelText('De')).toHaveValue('guarda-chuva')
  })
})

describe('sincronia com a URL', () => {
  it('abre já filtrado por `?q=`, com o campo De preenchido', async () => {
    window.history.replaceState(null, '', '#/taxonomia/dicionario?q=conversao')
    await abrir()

    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())
    expect(busca()).toHaveValue('conversao')
    // É o atalho entre o erro e o conserto: quem chegou por "Cadastrar X" quer
    // digitar o Para, não redigitar o termo que o motor recusou.
    expect(screen.getByLabelText('De')).toHaveValue('conversao')
    expect(linhas()).toHaveLength(1)
  })

  it('grava `?q=` na URL depois do debounce, com replaceState', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    const entradasAntes = window.history.length
    await user.type(busca(), 'conv')

    // Os 300 ms valem SÓ para os efeitos colaterais; o filtro em si já rodou.
    await waitFor(() => expect(window.location.hash).toBe('#/taxonomia/dicionario?q=conv'), {
      timeout: 2000,
    })
    // Cada tecla virando entrada no histórico deixaria o botão voltar do
    // navegador inútil — por isso `replaceState`.
    expect(window.history.length).toBe(entradasAntes)
  })

  it('a contagem é anunciada por live region, não a cada tecla', async () => {
    const user = await abrir()
    await waitFor(() => expect(screen.getByText('Conversão')).toBeInTheDocument())

    await user.type(busca(), 'objetivo')

    // Sem o atraso, o leitor de tela seria metralhado a cada caractere.
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('2 de 3 termos'), {
      timeout: 2000,
    })
  })
})

describe('atalho do erro para o cadastro (§6.5)', () => {
  it('o termo recusado vira link para o Dicionário já filtrado', () => {
    render(
      <Preview
        resultado={null}
        carregando={false}
        termoRecusado="Guarda-chuva"
        erro={{
          erro: 'termo_desconhecido',
          mensagem: 'O termo \'Guarda-chuva\' não está no dicionário de \'produto\'.',
          campo: 'produto',
          opcoes: ['Bolsa'],
        }}
      />,
    )

    const link = screen.getByRole('link', { name: 'Cadastrar "Guarda-chuva" no dicionário' })
    expect(link).toHaveAttribute('href', '#/taxonomia/dicionario?q=Guarda-chuva')
  })

  it('não oferece o atalho para outro código de erro', () => {
    render(
      <Preview
        resultado={null}
        carregando={false}
        termoRecusado="X"
        erro={{ erro: 'limite_excedido', mensagem: 'O nome gerado tem 60 caracteres…' }}
      />,
    )
    expect(screen.queryByRole('link', { name: /Cadastrar/ })).not.toBeInTheDocument()
  })
})
