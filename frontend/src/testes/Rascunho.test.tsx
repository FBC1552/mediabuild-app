/**
 * Rascunho do gerador (UX-NAVEGACAO §4.4).
 *
 * A rede de segurança INDEPENDENTE da sessão. O diálogo de reautenticação
 * cobre "a sessão venceu enquanto eu preenchia"; ele não cobre F5, queda do
 * navegador nem fechar a aba sem querer. O rascunho cobre.
 *
 * Por isso o teste central aqui é a REMONTAGEM: desmontar e montar de novo
 * simula exatamente o que um F5 faz com a árvore React.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Gerador } from '../componentes/Gerador'
import { CHAVE_RASCUNHO_GERADOR } from '../sessao'
import { ComSessao } from './ajudaSessao'

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
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const corpo = url.includes('/templates') ? TEMPLATES : url.includes('/dicionario') ? [] : []
      return { ok: true, status: 200, json: async () => corpo } as Response
    }),
  )
})

function montar() {
  return render(
    <ComSessao>
      <Gerador plataformas={[META]} versaoDicionario={0} />
    </ComSessao>,
  )
}

function lerRascunho() {
  const bruto = window.sessionStorage.getItem(CHAVE_RASCUNHO_GERADOR)
  return bruto ? JSON.parse(bruto) : null
}

describe('rascunho do gerador', () => {
  it('sobrevive à remontagem — que é o que um F5 faz', async () => {
    const user = userEvent.setup()
    const tela = montar()

    await user.selectOptions(screen.getByLabelText('Plataforma'), META.id)
    const nome = await screen.findByLabelText('Nome interno')
    await user.type(nome, SENTINELA)

    // 500 ms de debounce: gravar a cada tecla é `JSON.stringify` jogado fora,
    // e `sessionStorage` é síncrono — escreve na thread que está desenhando.
    await waitFor(() => expect(lerRascunho()?.nomes?.CAMPANHA).toBe(SENTINELA), { timeout: 3000 })

    tela.unmount()
    montar()

    expect(await screen.findByLabelText('Nome interno')).toHaveValue(SENTINELA)
    // A plataforma volta junto — sem ela o formulário restaurado não teria
    // template e os campos apareceriam bloqueados.
    expect(screen.getByLabelText('Plataforma')).toHaveValue(META.id)
  })

  it('restaurar a plataforma NÃO dispara o reset de troca de plataforma', async () => {
    window.sessionStorage.setItem(
      CHAVE_RASCUNHO_GERADOR,
      JSON.stringify({
        plataformaId: META.id,
        nomes: { CAMPANHA: SENTINELA, GRUPO: '', ANUNCIO: '' },
        campos: { CAMPANHA: { objetivo: 'Conversão' }, GRUPO: {}, ANUNCIO: {} },
      }),
    )

    montar()

    // Sem a guarda de primeira carga, o efeito de montagem chamaria
    // `reiniciarSessao()` e apagaria o que o rascunho acabou de devolver — o
    // F5 pareceria não ter preservado nada.
    expect(await screen.findByLabelText('Nome interno')).toHaveValue(SENTINELA)
    // A plataforma restaurada é a mesma: nada de voltar para "Selecione…".
    expect(screen.getByLabelText('Plataforma')).toHaveValue(META.id)
  })

  it('formulário vazio não deixa vestígio', async () => {
    const user = userEvent.setup()
    montar()
    window.sessionStorage.setItem(CHAVE_RASCUNHO_GERADOR, '{"sujeira":true}')

    await user.selectOptions(screen.getByLabelText('Plataforma'), '')

    await waitFor(() => expect(lerRascunho()).toBeNull(), { timeout: 3000 })
  })

  it('rascunho corrompido não derruba a tela', async () => {
    window.sessionStorage.setItem(CHAVE_RASCUNHO_GERADOR, 'não é json')
    montar()
    // Começar limpo é sempre melhor que quebrar a tela por causa da rede de
    // segurança.
    expect(await screen.findByLabelText('Plataforma')).toHaveValue('')
  })

  it('usa sessionStorage, nunca localStorage', async () => {
    const user = userEvent.setup()
    montar()
    await user.selectOptions(screen.getByLabelText('Plataforma'), META.id)
    await user.type(await screen.findByLabelText('Nome interno'), 'X')

    await waitFor(() => expect(lerRascunho()).not.toBeNull(), { timeout: 3000 })
    // Rascunho com nome de cliente sobrevivendo numa máquina compartilhada é
    // vazamento — e `localStorage` sobrevive ao fechamento do navegador.
    expect(window.localStorage.getItem(CHAVE_RASCUNHO_GERADOR)).toBeNull()
  })
})
