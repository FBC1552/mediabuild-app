/**
 * Tema claro / escuro / sistema.
 *
 * `src/tema.ts` tem estado de MÓDULO e faz a primeira aplicação no import —
 * é isso que garante que o `<html>` já esteja pintado antes de qualquer
 * componente montar. A consequência para o teste é que cada caso precisa de
 * `vi.resetModules()` + import dinâmico: importar no topo do arquivo
 * congelaria o módulo no ambiente do PRIMEIRO teste, e os demais estariam
 * verificando um estado que não é o que dizem verificar.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

type Ouvinte = (evento: MediaQueryListEvent) => void

/**
 * `matchMedia` não existe no jsdom. O stub não é só um "retorna false": ele
 * precisa guardar os ouvintes e conseguir disparar a mudança, porque metade
 * do que se quer provar aqui é justamente a REAÇÃO à troca de preferência do
 * sistema — e a outra metade é a ausência dela quando há escolha explícita.
 */
function instalarMatchMedia(comecaEscuro: boolean) {
  const ouvintes = new Set<Ouvinte>()
  let escuro = comecaEscuro
  const consulta = {
    get matches() {
      return escuro
    },
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_tipo: string, ouvinte: Ouvinte) => void ouvintes.add(ouvinte),
    removeEventListener: (_tipo: string, ouvinte: Ouvinte) => void ouvintes.delete(ouvinte),
  }
  vi.stubGlobal('matchMedia', () => consulta)
  return {
    mudarSistemaPara(novo: 'claro' | 'escuro') {
      escuro = novo === 'escuro'
      for (const ouvinte of ouvintes) ouvinte({ matches: escuro } as MediaQueryListEvent)
    },
  }
}

const raiz = () => document.documentElement

beforeEach(() => {
  window.localStorage.clear()
  raiz().removeAttribute('data-tema')
  raiz().removeAttribute('data-aparencia')
  vi.resetModules()
})

describe('modo padrão', () => {
  it('sem nada salvo, o modo é `sistema` e a aparência vem do sistema', async () => {
    instalarMatchMedia(true)
    const tema = await import('../tema')

    expect(tema.lerModoSalvo()).toBe('sistema')
    expect(raiz().getAttribute('data-tema')).toBe('sistema')
    expect(raiz().getAttribute('data-aparencia')).toBe('escuro')
  })

  it('sem `matchMedia`, `sistema` resolve para claro em vez de quebrar', async () => {
    vi.stubGlobal('matchMedia', undefined)
    const tema = await import('../tema')

    expect(tema.preferenciaDoSistema()).toBe('claro')
    expect(raiz().getAttribute('data-aparencia')).toBe('claro')
  })
})

describe('escolha explícita', () => {
  it('persiste em localStorage e vence a preferência do sistema', async () => {
    instalarMatchMedia(true) // sistema no escuro…
    const tema = await import('../tema')

    tema.definirModo('claro') // …e a pessoa pede claro.

    expect(window.localStorage.getItem(tema.CHAVE_TEMA)).toBe('claro')
    expect(raiz().getAttribute('data-tema')).toBe('claro')
    expect(raiz().getAttribute('data-aparencia')).toBe('claro')
  })

  it('é relida na abertura seguinte', async () => {
    instalarMatchMedia(false)
    const primeira = await import('../tema')
    primeira.definirModo('escuro')

    // Nova abertura do app: módulo do zero, mesmo localStorage.
    vi.resetModules()
    raiz().removeAttribute('data-aparencia')
    const segunda = await import('../tema')

    expect(segunda.lerModoSalvo()).toBe('escuro')
    expect(raiz().getAttribute('data-aparencia')).toBe('escuro')
  })

  it('valor inválido no storage cai no padrão em vez de propagar lixo', async () => {
    window.localStorage.setItem('mdbd:tema', 'neon')
    instalarMatchMedia(false)
    const tema = await import('../tema')

    expect(tema.lerModoSalvo()).toBe('sistema')
    expect(raiz().getAttribute('data-tema')).toBe('sistema')
  })
})

describe('reação a prefers-color-scheme', () => {
  it('repinta quando o modo é `sistema`', async () => {
    const midia = instalarMatchMedia(false)
    await import('../tema')
    expect(raiz().getAttribute('data-aparencia')).toBe('claro')

    midia.mudarSistemaPara('escuro')

    expect(raiz().getAttribute('data-aparencia')).toBe('escuro')
    expect(raiz().getAttribute('data-tema')).toBe('sistema')
  })

  it('NÃO repinta quando há escolha explícita — é a regra que protege a escolha', async () => {
    const midia = instalarMatchMedia(false)
    const tema = await import('../tema')
    tema.definirModo('claro')

    midia.mudarSistemaPara('escuro')

    expect(raiz().getAttribute('data-aparencia')).toBe('claro')
  })

  it('volta a obedecer ao sistema quando o modo volta para `sistema`', async () => {
    const midia = instalarMatchMedia(false)
    const tema = await import('../tema')
    tema.definirModo('escuro')
    midia.mudarSistemaPara('escuro')

    tema.definirModo('sistema')
    expect(raiz().getAttribute('data-aparencia')).toBe('escuro')

    midia.mudarSistemaPara('claro')
    expect(raiz().getAttribute('data-aparencia')).toBe('claro')
  })
})

describe('AlternadorTema', () => {
  it('é um grupo de rádios rotulado, com o modo corrente marcado', async () => {
    instalarMatchMedia(false)
    const { AlternadorTema } = await import('../componentes/AlternadorTema')

    render(<AlternadorTema />)

    const grupo = screen.getByRole('group', { name: 'Tema' })
    expect(grupo).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Sistema' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Claro' })).not.toBeChecked()
  })

  it('escolher uma opção troca o tema do documento', async () => {
    instalarMatchMedia(false)
    const { AlternadorTema } = await import('../componentes/AlternadorTema')
    const usuario = userEvent.setup()

    render(<AlternadorTema />)
    await usuario.click(screen.getByRole('radio', { name: 'Escuro' }))

    expect(raiz().getAttribute('data-tema')).toBe('escuro')
    expect(raiz().getAttribute('data-aparencia')).toBe('escuro')
    expect(screen.getByRole('radio', { name: 'Escuro' })).toBeChecked()
  })

  it('dois alternadores montados juntos não compartilham `name` nem divergem', async () => {
    instalarMatchMedia(false)
    const { AlternadorTema } = await import('../componentes/AlternadorTema')
    const usuario = userEvent.setup()

    render(
      <>
        <AlternadorTema rotulo="Tema A" />
        <AlternadorTema rotulo="Tema B" />
      </>,
    )

    const grupoA = screen.getByRole('group', { name: 'Tema A' })
    const grupoB = screen.getByRole('group', { name: 'Tema B' })
    const escuroA = grupoA.querySelector<HTMLInputElement>('input[value="escuro"]')!
    const escuroB = grupoB.querySelector<HTMLInputElement>('input[value="escuro"]')!

    // `name` diferente: com o mesmo, os seis rádios virariam um grupo só.
    expect(escuroA.name).not.toBe(escuroB.name)

    await usuario.click(escuroA)

    // Estado de módulo, não de componente: o segundo alternador acompanha.
    expect(escuroA).toBeChecked()
    expect(escuroB).toBeChecked()
  })
})
