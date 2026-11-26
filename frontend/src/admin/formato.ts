/** Formatação de data/hora das telas de administração. */

const HORA = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const DIA_CURTO = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' })

/**
 * `hoje, 09:12` · `ontem, 18:40` · `12/07, 11:02`.
 *
 * Relativo só nos dois dias em que "hoje" e "ontem" são mais rápidos de ler
 * que a data. Além disso, data absoluta — "há 34 dias" obriga a fazer conta.
 */
export function formatarQuando(iso: string | null | undefined): string {
  if (!iso) return '—'
  const data = new Date(iso)
  if (Number.isNaN(data.valueOf())) return iso

  const hoje = new Date()
  const meiaNoite = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const dias = Math.round((meiaNoite(hoje) - meiaNoite(data)) / 86_400_000)

  if (dias === 0) return `hoje, ${HORA.format(data)}`
  if (dias === 1) return `ontem, ${HORA.format(data)}`
  return `${DIA_CURTO.format(data)}, ${HORA.format(data)}`
}

/** Alfabeto sem `0/O/1/l/I`: a senha é ditada e anotada à mão. */
const ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'

/**
 * Senha provisória gerada no cliente para `POST /usuarios`.
 *
 * O servidor não gera senha na criação (só em `POST /usuarios/{id}/senha`),
 * então quem precisa produzir uma é esta tela. `crypto.getRandomValues`, nunca
 * `Math.random`: é credencial, ainda que temporária.
 */
export function gerarSenhaProvisoria(tamanho = 14): string {
  const numeros = crypto.getRandomValues(new Uint32Array(tamanho))
  return Array.from(numeros, (n) => ALFABETO[n % ALFABETO.length]).join('')
}
