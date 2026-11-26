/**
 * Formatação e parse numérico do Plano de Mídia — usado por `CampoRateio`,
 * `SeloDesbalanco`, `FaixaDeSaldo` e `TabelaMetas`.
 *
 * Os campos Decimal do backend chegam como STRING (ver nota em `tipos.ts`);
 * as funções aqui só convertem ida e volta para exibição — o servidor
 * continua sendo quem decide o valor gravado (D-A/D-B).
 */

/** `'200000.50'` (o que o backend manda) → número JS. `null`/`''` → 0. */
export function paraNumero(valor: string | null | undefined): number {
  if (valor === null || valor === undefined || valor.trim() === '') return 0
  const n = Number(valor)
  return Number.isFinite(n) ? n : 0
}

/**
 * Texto digitado pelo analista → número, ou `null` se não é um número
 * reconhecível ainda (digitação em andamento). Aceita vírgula OU ponto como
 * separador decimal — o campo não força o usuário a escolher um teclado.
 */
export function parseNumeroDigitado(texto: string): number | null {
  const limpo = texto.trim().replace(',', '.')
  if (limpo === '' || limpo === '-') return null
  const n = Number(limpo)
  return Number.isFinite(n) ? n : null
}

/** Duas casas, separador brasileiro — só para EXIBIÇÃO (o servidor arredonda). */
export function formatarMoeda(n: number): string {
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** Três casas — mesma régua de `_percentual` em `app/routers/planos.py`. */
export function formatarPercentual(n: number): string {
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

/** Texto de edição do campo R$: sem o prefixo, só o número. */
export function textoEdicaoValor(valor: string | null | undefined): string {
  return valor === null || valor === undefined || valor.trim() === '' ? '' : formatarMoeda(paraNumero(valor))
}

/** Texto de edição do campo %. Nulo (pai zero) vira campo vazio, não '0'. */
export function textoEdicaoPercentual(percentual: string | null | undefined): string {
  return percentual === null || percentual === undefined ? '' : formatarPercentual(paraNumero(percentual))
}

/** `R$ 1.234,56`, para texto corrido (selos, faixa de saldo). */
export function formatarMoedaComPrefixo(n: number): string {
  return `R$ ${formatarMoeda(n)}`
}
