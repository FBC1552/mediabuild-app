/**
 * Tema claro / escuro / sistema.
 *
 * O que este módulo faz e o que ele NÃO faz:
 *
 * · faz — guardar o MODO escolhido, resolver o modo `sistema` contra
 *   `prefers-color-scheme`, escrever os dois atributos no `<html>` e avisar
 *   quem estiver ouvindo;
 * · não faz — decidir cor nenhuma. As cores estão inteiras em `index.css`,
 *   nos blocos `[data-tema='claro']` e `[data-tema='escuro']`. Trocar de tema
 *   aqui é trocar um atributo, nunca um valor.
 *
 * Dois atributos, não um, e a diferença importa:
 *
 *   `data-tema`      = a ESCOLHA  → 'claro' | 'escuro' | 'sistema'
 *   `data-aparencia` = o RESULTADO → 'claro' | 'escuro'
 *
 * O CSS pinta pelo segundo. Sem ele, o modo `sistema` precisaria de um
 * `@media (prefers-color-scheme: dark)` duplicando o bloco escuro inteiro —
 * duas listas de ~50 tokens que divergem na primeira manutenção. Resolvendo
 * no JS, o bloco escuro existe uma vez só. O `data-tema` continua no DOM
 * porque é ele que o alternador lê para marcar qual opção está selecionada:
 * "Sistema" com o sistema no escuro não é a mesma coisa que "Escuro".
 *
 * A leitura de `localStorage` e a primeira aplicação acontecem no import — e
 * também, antes dele, no script inline do `index.html`, que é o que evita o
 * flash branco antes do primeiro paint. Rodar duas vezes é idempotente.
 */
import { useCallback, useSyncExternalStore } from 'react'

export type ModoTema = 'claro' | 'escuro' | 'sistema'
/** O tema efetivamente pintado. `sistema` nunca chega aqui: já foi resolvido. */
export type Aparencia = 'claro' | 'escuro'

export const CHAVE_TEMA = 'mdbd:tema'

export const MODOS: ModoTema[] = ['claro', 'escuro', 'sistema']

export const ROTULO_MODO: Record<ModoTema, string> = {
  claro: 'Claro',
  escuro: 'Escuro',
  sistema: 'Sistema',
}

const CONSULTA_ESCURO = '(prefers-color-scheme: dark)'

function ehModo(valor: unknown): valor is ModoTema {
  return valor === 'claro' || valor === 'escuro' || valor === 'sistema'
}

/**
 * O modo persistido. Qualquer coisa que não seja um dos três valores — chave
 * ausente, `localStorage` bloqueado, lixo escrito à mão — cai em `sistema`,
 * que é o padrão do produto.
 */
export function lerModoSalvo(): ModoTema {
  try {
    const salvo = window.localStorage.getItem(CHAVE_TEMA)
    return ehModo(salvo) ? salvo : 'sistema'
  } catch {
    return 'sistema'
  }
}

/**
 * A preferência do sistema operacional. Sem `matchMedia` (jsdom sem stub,
 * navegador antigo) a resposta é `claro` — o tema que o usuário já aprovou.
 */
export function preferenciaDoSistema(): Aparencia {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'claro'
  return window.matchMedia(CONSULTA_ESCURO).matches ? 'escuro' : 'claro'
}

export function resolverModo(modo: ModoTema): Aparencia {
  return modo === 'sistema' ? preferenciaDoSistema() : modo
}

/** Escreve os dois atributos no `<html>`. Único ponto que toca o DOM. */
function pintar(modo: ModoTema, resolvido: Aparencia) {
  if (typeof document === 'undefined') return
  const raiz = document.documentElement
  raiz.setAttribute('data-tema', modo)
  raiz.setAttribute('data-aparencia', resolvido)
}

type Estado = { modo: ModoTema; resolvido: Aparencia }

// O estado é de MÓDULO, não de componente: o `<html>` é um só, e o catálogo
// monta mais de um alternador ao mesmo tempo. Dois `useState` independentes
// divergiriam na primeira troca.
let estado: Estado = { modo: 'sistema', resolvido: 'claro' }
const ouvintes = new Set<() => void>()

function notificar() {
  for (const ouvinte of ouvintes) ouvinte()
}

function atualizar(modo: ModoTema) {
  const resolvido = resolverModo(modo)
  if (estado.modo === modo && estado.resolvido === resolvido) return
  // Objeto novo a cada mudança REAL, o mesmo objeto enquanto nada muda: é o
  // contrato de `useSyncExternalStore`, que compara por identidade.
  estado = { modo, resolvido }
  pintar(modo, resolvido)
  notificar()
}

/**
 * Aplica o modo e persiste a escolha. `sistema` também é persistido como
 * escolha explícita — "voltei para o sistema" é uma decisão, e apagar a chave
 * faria o modo depender de a chave nunca ter existido.
 */
export function definirModo(modo: ModoTema) {
  try {
    window.localStorage.setItem(CHAVE_TEMA, modo)
  } catch {
    // Sem localStorage a escolha vale só para esta aba. Degradação aceitável.
  }
  atualizar(modo)
}

/**
 * Lê o que estiver salvo e aplica. Chamado no import; exportado para os
 * testes, que precisam reavaliar o ambiente depois de trocar o stub.
 */
export function iniciarTema(): Estado {
  const modo = lerModoSalvo()
  const resolvido = resolverModo(modo)
  estado = { modo, resolvido }
  pintar(modo, resolvido)
  notificar()
  return estado
}

// A troca de tema do SISTEMA só repinta quando o modo é `sistema`. Com uma
// escolha explícita no lugar, o usuário já disse o que quer e o sistema não
// tem voto — repintar por cima seria ignorar a escolha dele.
function ouvirSistema() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
  const consulta = window.matchMedia(CONSULTA_ESCURO)
  const reagir = () => {
    if (estado.modo !== 'sistema') return
    const resolvido = preferenciaDoSistema()
    if (resolvido === estado.resolvido) return
    estado = { modo: 'sistema', resolvido }
    pintar('sistema', resolvido)
    notificar()
  }
  if (typeof consulta.addEventListener === 'function') {
    consulta.addEventListener('change', reagir)
  } else if (typeof (consulta as MediaQueryList).addListener === 'function') {
    // Safari < 14. Uma linha para não perder a reação num navegador inteiro.
    ;(consulta as MediaQueryList).addListener(reagir)
  }
}

iniciarTema()
ouvirSistema()

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte)
  return () => {
    ouvintes.delete(ouvinte)
  }
}

function instantaneo(): Estado {
  return estado
}

export type UsoTema = {
  /** A escolha: 'claro' | 'escuro' | 'sistema'. É o que o alternador marca. */
  modo: ModoTema
  definirModo: (modo: ModoTema) => void
  /** O tema efetivamente pintado agora: 'claro' | 'escuro'. */
  resolvido: Aparencia
}

export function useTema(): UsoTema {
  const atual = useSyncExternalStore(assinar, instantaneo, instantaneo)
  const definir = useCallback((modo: ModoTema) => definirModo(modo), [])
  return { modo: atual.modo, definirModo: definir, resolvido: atual.resolvido }
}
