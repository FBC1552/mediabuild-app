import type { SecaoCatalogo } from '../../roteador'
import type { Exemplo } from './MostraExemplo'
import { EXEMPLOS as CARREGAMENTO } from './secoes/carregamento'
import { EXEMPLOS as COMPONENTES } from './secoes/componentes'
import { EXEMPLOS as ESTADOS } from './secoes/estados'
import { EXEMPLOS as FUNDACAO } from './secoes/fundacao'
import { EXEMPLOS as MOVIMENTO } from './secoes/movimento'
import { EXEMPLOS as PADROES } from './secoes/padroes'
import { EXEMPLOS as REDACAO } from './secoes/redacao'

export const EXEMPLOS_POR_SECAO: Record<SecaoCatalogo, Exemplo[]> = {
  fundacao: FUNDACAO,
  componentes: COMPONENTES,
  padroes: PADROES,
  carregamento: CARREGAMENTO,
  estados: ESTADOS,
  movimento: MOVIMENTO,
  redacao: REDACAO,
}

export function acharExemplo(id: string): Exemplo | undefined {
  return Object.values(EXEMPLOS_POR_SECAO)
    .flat()
    .find((exemplo) => exemplo.id === id)
}

/**
 * A que seção o exemplo pertence. Existe para o `← Voltar para o catálogo` do
 * `#/isolado/<id>` cair na seção CERTA (UX-NAVEGACAO §2.3) — voltar de um
 * exemplo para a seção errada é o tipo de detalhe que faz o usuário
 * desconfiar da navegação inteira.
 */
export function secaoDoExemplo(id: string): SecaoCatalogo | undefined {
  for (const [secao, exemplos] of Object.entries(EXEMPLOS_POR_SECAO)) {
    if (exemplos.some((exemplo) => exemplo.id === id)) return secao as SecaoCatalogo
  }
  return undefined
}
