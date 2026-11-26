/**
 * Roteador por hash (D-010), sem dependência de runtime.
 *
 * Duas escolhas que não são estilo:
 *  1. `useSyncExternalStore`, não `useState` + `useEffect('hashchange')`.
 *     Sob StrictMode e render concorrente o segundo padrão gera tearing e
 *     hash defasado no primeiro paint.
 *  2. `substituir()` usa `history.replaceState`, não `location.hash =`.
 *     `assign` empilha entrada no histórico e o botão voltar entra em loop.
 *     Como `replaceState` NÃO dispara `hashchange`, o módulo mantém a própria
 *     lista de ouvintes e notifica na mão.
 */
import { useMemo, useSyncExternalStore } from 'react'

import type { Papel } from './tipos'

export type AbaTaxonomia = 'gerar' | 'dicionario' | 'historico'

export type SecaoCatalogo =
  | 'fundacao'
  | 'componentes'
  | 'padroes'
  | 'carregamento'
  | 'estados'
  | 'movimento'
  | 'redacao'

/**
 * O endereço sem a query string. `Rota` é isto mais os parâmetros.
 */
export type Alvo =
  | { nome: 'entrar' }
  | { nome: 'splash' }
  | { nome: 'assunto' }
  | { nome: 'guia' }
  | { nome: 'cadastro' }
  | { nome: 'taxonomia'; aba: AbaTaxonomia }
  | { nome: 'plano-lista' }
  | { nome: 'plano-metricas' }
  | { nome: 'plano'; id: string }
  | { nome: 'admin-acessos' }
  | { nome: 'admin-monitoramento' }
  | { nome: 'catalogo'; secao: SecaoCatalogo }
  | { nome: 'isolado'; exemplo: string }
  | { nome: 'desconhecida'; caminho: string }

/**
 * Condicional DISTRIBUTIVA de propósito: `(A | B) & C` não estreita de forma
 * confiável por discriminante, mas `(A & C) | (B & C)` sim. Sem isso,
 * `if (rota.nome === 'plano') rota.id` deixa de compilar.
 */
type ComParametros<T> = T extends unknown ? T & { params: URLSearchParams } : never

export type Rota = ComParametros<Alvo>

/** O que `caminhoDe` aceita: a rota inteira ou só o alvo, sem parâmetros. */
type ComParametrosOpcionais<T> = T extends unknown
  ? T & { params?: URLSearchParams }
  : never

export const ABAS_TAXONOMIA: AbaTaxonomia[] = ['gerar', 'dicionario', 'historico']

export const SECOES_CATALOGO: SecaoCatalogo[] = [
  'fundacao',
  'componentes',
  'padroes',
  'carregamento',
  'estados',
  'movimento',
  'redacao',
]

export const ROTULO_SECAO: Record<SecaoCatalogo, string> = {
  fundacao: 'Fundação',
  componentes: 'Componentes',
  padroes: 'Padrões de tela',
  carregamento: 'Carregamento',
  estados: 'Vazio e erro',
  movimento: 'Movimento',
  redacao: 'Redação',
}

export const ROTULO_ABA: Record<AbaTaxonomia, string> = {
  gerar: 'Gerar',
  dicionario: 'Dicionário',
  historico: 'Histórico',
}

/**
 * As abas que o papel enxerga (UX-NAVEGACAO §4.2).
 *
 * A constante `ABAS_TAXONOMIA` continua existindo — é o conjunto de rotas
 * VÁLIDAS, e `#/taxonomia/dicionario` continua sendo endereço legítimo para
 * qualquer papel. O que muda por papel é o que a interface OFERECE; quem
 * digita o endereço sem permissão vê o painel de acesso negado (§4.3), nunca
 * um 404 e nunca um redirecionamento silencioso.
 *
 * `papel` nulo = sessão ainda desconhecida; devolve o conjunto mínimo, para
 * a barra de abas não piscar uma aba que sumirá em seguida.
 */
export function abasVisiveis(papel: Papel | null): AbaTaxonomia[] {
  if (papel === 'pleno' || papel === 'admin') return ABAS_TAXONOMIA
  return ABAS_TAXONOMIA.filter((aba) => aba !== 'dicionario')
}

function ehAba(valor: string): valor is AbaTaxonomia {
  return (ABAS_TAXONOMIA as string[]).includes(valor)
}

function ehSecao(valor: string): valor is SecaoCatalogo {
  return (SECOES_CATALOGO as string[]).includes(valor)
}

/**
 * URLs que o PRÓPRIO produto publicou e que mudaram de lugar (§3.2).
 *
 * Não contradiz a regra de "não redirecionar em silêncio": aquela vale para
 * endereço DESCONHECIDO, onde o silêncio esconde um erro do usuário. Aqui o
 * endereço é conhecido, mudou de lugar, e quem distribuiu o link antigo fomos
 * nós — `cromo.tsx` o punha no rodapé de toda tela de entrada. Semântica de
 * 301, não de 404.
 *
 * O redirecionamento em si é de graça: `lerRota` reescreve o caminho, e a
 * canonização do `App` (`caminhoDe` + `substituir`) troca a barra de endereço.
 *
 * Datado: criada em 07/08/2026. Pode ser apagada quando não houver mais
 * bookmark vivo apontando para `#/admin/<secao>`.
 */
export const REDIRECIONAMENTOS_LEGADOS: Record<string, string> = Object.fromEntries(
  SECOES_CATALOGO.map((secao) => [`/admin/${secao}`, `/admin/design/${secao}`]),
)

/** Corta a hash em `?` e devolve caminho e parâmetros separados. */
function partirHash(hash: string): { caminho: string; params: URLSearchParams } {
  const bruto = hash.replace(/^#/, '')
  const corte = bruto.indexOf('?')
  const caminho = corte === -1 ? bruto : bruto.slice(0, corte)
  const params = new URLSearchParams(corte === -1 ? '' : bruto.slice(corte + 1))
  return { caminho: REDIRECIONAMENTOS_LEGADOS[caminho] ?? caminho, params }
}

export function lerRota(hash: string): Rota {
  const { caminho, params } = partirHash(hash)
  return { ...lerAlvo(caminho), params } as Rota
}

function lerAlvo(caminho: string): Alvo {
  const partes = caminho.split('/').filter(Boolean)

  if (partes.length === 0) return { nome: 'splash' }

  const [raiz, segundo, terceiro] = partes

  // O portão fica ANTES da splash no fluxo (UX-NAVEGACAO §5.1): a splash é
  // marca e recomendação, não portão.
  if (raiz === 'entrar' && partes.length === 1) return { nome: 'entrar' }

  if (raiz === 'assunto' && partes.length === 1) return { nome: 'assunto' }

  // Telas de conteúdo alcançadas pela barra de topo. Segmento único: `#/guia/x`
  // é endereço desconhecido, não um subcapítulo silenciosamente ignorado.
  if (raiz === 'guia' && partes.length === 1) return { nome: 'guia' }
  if (raiz === 'cadastro' && partes.length === 1) return { nome: 'cadastro' }

  if (raiz === 'taxonomia' && partes.length <= 2) {
    // `#/taxonomia` sozinho é canonizado para a aba Gerar pelo App.
    if (segundo === undefined) return { nome: 'taxonomia', aba: 'gerar' }
    if (ehAba(segundo)) return { nome: 'taxonomia', aba: segundo }
  }

  // Plano de mídia: assunto irmão da taxonomia, não quarta aba (D-010).
  // `#/plano/metricas` é o catálogo de métricas (utilitário, análogo ao
  // Dicionário) — precisa ser checado antes do segmento dinâmico, senão
  // 'metricas' seria lido como um id de plano.
  if (raiz === 'plano' && partes.length === 1) return { nome: 'plano-lista' }
  if (raiz === 'plano' && partes.length === 2 && segundo === 'metricas') {
    return { nome: 'plano-metricas' }
  }
  if (raiz === 'plano' && partes.length === 2) {
    return { nome: 'plano', id: decodeURIComponent(segundo) }
  }

  // Administração em três áreas (§3.1). `#/admin` sozinho cai em Acessos —
  // é a área que responde à pergunta que traz alguém aqui ("quem tem acesso").
  if (raiz === 'admin') {
    if (segundo === undefined) return { nome: 'admin-acessos' }
    if (segundo === 'acessos' && partes.length === 2) return { nome: 'admin-acessos' }
    if (segundo === 'monitoramento' && partes.length === 2) {
      return { nome: 'admin-monitoramento' }
    }
    if (segundo === 'design' && partes.length === 2) {
      return { nome: 'catalogo', secao: 'fundacao' }
    }
    if (segundo === 'design' && partes.length === 3 && terceiro && ehSecao(terceiro)) {
      return { nome: 'catalogo', secao: terceiro }
    }
  }

  if (raiz === 'isolado' && partes.length === 2) {
    return { nome: 'isolado', exemplo: decodeURIComponent(segundo) }
  }

  return { nome: 'desconhecida', caminho: `/${partes.join('/')}` }
}

export function caminhoDe(rota: ComParametrosOpcionais<Alvo>): string {
  const query = rota.params?.toString() ?? ''
  return query ? `${caminhoBase(rota)}?${query}` : caminhoBase(rota)
}

function caminhoBase(rota: Alvo): string {
  switch (rota.nome) {
    case 'entrar':
      return '#/entrar'
    case 'splash':
      return '#/'
    case 'assunto':
      return '#/assunto'
    case 'guia':
      return '#/guia'
    case 'cadastro':
      return '#/cadastro'
    case 'taxonomia':
      return `#/taxonomia/${rota.aba}`
    case 'plano-lista':
      return '#/plano'
    case 'plano-metricas':
      return '#/plano/metricas'
    case 'plano':
      return `#/plano/${encodeURIComponent(rota.id)}`
    case 'admin-acessos':
      return '#/admin/acessos'
    case 'admin-monitoramento':
      return '#/admin/monitoramento'
    case 'catalogo':
      return `#/admin/design/${rota.secao}`
    case 'isolado':
      return `#/isolado/${encodeURIComponent(rota.exemplo)}`
    case 'desconhecida':
      return `#${rota.caminho}`
  }
}

const ouvintes = new Set<() => void>()

function notificar() {
  for (const ouvinte of ouvintes) ouvinte()
}

export function navegar(caminho: string): void {
  const destino = caminho.startsWith('#') ? caminho : `#${caminho}`
  if (window.location.hash === destino) return
  window.location.hash = destino
}

export function substituir(caminho: string): void {
  const destino = caminho.startsWith('#') ? caminho : `#${caminho}`
  if (window.location.hash === destino) return
  window.history.replaceState(null, '', destino)
  notificar()
}

function assinar(aoMudar: () => void): () => void {
  ouvintes.add(aoMudar)
  window.addEventListener('hashchange', aoMudar)
  return () => {
    ouvintes.delete(aoMudar)
    window.removeEventListener('hashchange', aoMudar)
  }
}

const hashAtual = () => window.location.hash
const hashDoServidor = () => '#/'

/** Única fonte de rota da aplicação. Nenhum componente lê `location.hash`. */
export function useRota(): Rota {
  const hash = useSyncExternalStore(assinar, hashAtual, hashDoServidor)
  return useMemo(() => lerRota(hash), [hash])
}
