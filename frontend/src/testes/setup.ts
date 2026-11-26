import '@testing-library/jest-dom/vitest'

import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// O clipboard é fornecido pelo stub do `userEvent.setup()`; os testes leem
// o conteúdo com `navigator.clipboard.readText()` em vez de espionar a chamada.

// jsdom não implementa nem `ResizeObserver` nem `scrollTo`. São APIs de
// ambiente, não comportamento: o stub mora aqui, e não num `typeof` espalhado
// pelos componentes de produção.
if (!('ResizeObserver' in globalThis)) {
  class ObservadorFalso {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', ObservadorFalso)
}
vi.stubGlobal('scrollTo', () => {})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  // `sessionStorage` e `localStorage` são compartilhados por TODO teste do
  // mesmo arquivo — jsdom não recria o ambiente por caso. Sem esta limpeza, o
  // rascunho do gerador (`mdbd:rascunho-gerador`) de um teste ressuscita a
  // plataforma escolhida no seguinte, e o próximo `render` começa com um
  // formulário que ninguém preencheu. Mesma coisa para o último assunto
  // (`mdbd:ultimo-assunto`), que decide se a splash é pulada.
  window.sessionStorage.clear()
  window.localStorage.clear()
})
