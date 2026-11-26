/**
 * Voltar hierárquico (UX-NAVEGACAO §2).
 *
 * **Sobe um nível na hierarquia da informação. Não é `history.back()`.**
 *
 * Três razões, em ordem de peso:
 *
 * 1. `history.back()` tem destino desconhecido, e um rótulo não pode mentir.
 *    `← Voltar para os assuntos` é verificável ANTES do clique; `← Voltar`
 *    sozinho obriga o usuário a testar.
 * 2. O histórico do navegador aqui está poluído por navegação que o usuário
 *    não considera navegação: `trocarAba()` empilha, então depois de circular
 *    Gerar → Dicionário → Histórico o `back()` anda uma aba de cada vez.
 * 3. Por link direto ou F5 não existe "atrás" — e um controle que às vezes não
 *    faz nada é pior que controle nenhum.
 *
 * O voltar do navegador continua funcionando e continua sendo o desfazer de
 * navegação. As duas coisas coexistem porque fazem coisas diferentes.
 *
 * É `<a href>` e não `<button>`: Ctrl+clique, botão do meio e "copiar endereço
 * do link" saem de graça, e o leitor de tela anuncia "link".
 */
import type { Alvo, Rota, SecaoCatalogo } from '../roteador'

export type Destino = { href: string; rotulo: string }

/** Os quatro destinos possíveis, para o rótulo nunca divergir entre telas. */
export const DESTINOS = {
  inicio: { href: '#/', rotulo: 'Voltar para o início' },
  assuntos: { href: '#/assunto', rotulo: 'Voltar para os assuntos' },
  planos: { href: '#/plano', rotulo: 'Voltar para os planos' },
  administracao: { href: '#/admin/acessos', rotulo: 'Voltar para a administração' },
} as const satisfies Record<string, Destino>

export type ChaveDestino = keyof typeof DESTINOS

/**
 * Tabela do §2.3. `null` = a tela é raiz e **não renderiza** o controle —
 * nenhum espaço é reservado. Um controle permanentemente desabilitado ensina
 * o usuário a ignorar a região onde ele mora.
 *
 * `#/isolado/<id>` não está aqui porque o destino dele é CALCULADO a partir da
 * seção do exemplo (`EXEMPLOS_POR_SECAO`); quem o conhece é o `ExemploIsolado`,
 * que passa `href`/`rotulo` explícitos. Voltar de um exemplo para a seção
 * errada é o tipo de detalhe que faz desconfiar da navegação inteira.
 */
export function destinoDaRota(rota: Rota | Alvo): Destino | null {
  switch (rota.nome) {
    case 'splash':
    case 'entrar':
      return null
    case 'assunto':
    case 'guia':
    case 'cadastro':
    case 'desconhecida':
      return DESTINOS.inicio
    // Aba não é tela: as três abas da taxonomia mostram o MESMO destino, e o
    // controle mora fora dos `tabpanel` justamente por isso.
    case 'taxonomia':
    case 'plano-lista':
    case 'admin-acessos':
    case 'admin-monitoramento':
      return DESTINOS.assuntos
    case 'plano-metricas':
    case 'plano':
      return DESTINOS.planos
    case 'catalogo':
      return DESTINOS.administracao
    case 'isolado':
      return { href: '#/admin/design/fundacao', rotulo: 'Voltar para o catálogo' }
  }
}

/** Destino do catálogo a partir da seção a que o exemplo pertence. */
export function destinoDoExemplo(secao: SecaoCatalogo): Destino {
  return { href: `#/admin/design/${secao}`, rotulo: 'Voltar para o catálogo' }
}

type Props = Partial<Destino> & { de?: ChaveDestino }

/**
 * Primeiro filho do `<header class="cabecalho-tela">`, acima do `<h1>`.
 *
 * Variante fantasma, tamanho sm: não compete com a ação primária da tela — ela
 * é o preview/salvar, não a saída.
 */
export function VoltarPara({ de, href, rotulo }: Props) {
  const destino: Destino | undefined =
    href && rotulo ? { href, rotulo } : de ? DESTINOS[de] : undefined
  if (!destino) return null
  return (
    <a className="voltar-para" href={destino.href}>
      {/* A seta é texto dentro do link, não ícone solto. */}
      <span aria-hidden="true">←</span> {destino.rotulo}
    </a>
  )
}
