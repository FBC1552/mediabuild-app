/**
 * Normalização de texto para BUSCA.
 *
 * ISTO NORMALIZA PARA *ACHAR*, NUNCA PARA *GERAR*. A normalização que produz
 * nomenclatura mora em `app/taxonomia/normalizacao.py`, no servidor, e não tem
 * — nem pode ganhar — cópia no cliente: duas implementações da mesma regra
 * divergem, e a que diverge aqui gera nome errado numa campanha real.
 *
 * O produto inteiro dobra acento, e o motivo de a busca existir é o analista
 * ter recebido `termo_nao_cadastrado` e vir conferir. Digitar `conversao` TEM
 * que achar `Conversão`.
 *
 * `_` e `-` são preservados de propósito: são significativos na coluna Para.
 */
export function normalizarBusca(s: string): string {
  return s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toUpperCase()
}

/**
 * Substring, não prefixo e não difuso: numa ferramenta cujo produto é
 * exatidão, resultado aproximado obriga a reconferir tudo.
 */
export function contemBusca(alvo: string, consulta: string): boolean {
  return normalizarBusca(alvo).includes(normalizarBusca(consulta))
}
