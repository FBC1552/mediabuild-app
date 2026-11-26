/**
 * Casca da área administrativa (UX-NAVEGACAO §3.4–§3.5).
 *
 * Como o admin se distingue do produto sem virar outro aplicativo: **um sinal
 * só, forte, e fora do conteúdo** — a faixa de contexto invertida logo abaixo
 * da barra global. O que deliberadamente NÃO se faz:
 *
 * · **Não trocar a paleta da área.** O catálogo de design existe para mostrar
 *   as cores do produto; recolorir a casca faria o palco mentir.
 * · **Não usar outra barra de topo, tipografia ou layout de página.** Seria um
 *   segundo aplicativo: o usuário perderia o caminho de volta e o custo de
 *   manutenção dobraria.
 * · **Não usar cor de estado na faixa.** Estar no admin não é erro nem risco.
 *
 * A nav das três áreas é de LINKS com `aria-current`, não `role="tab"`: são
 * telas distintas com URL própria, e em Design ela conviveria com a nav
 * lateral de seções — dois `tablist` aninhados é ruído de leitor de tela
 * garantido.
 */
import type { ReactNode } from 'react'

import { VoltarPara } from '../componentes/VoltarPara'
import type { Rota } from '../roteador'

export type AreaAdmin = 'acessos' | 'design' | 'monitoramento'

const AREAS: { id: AreaAdmin; rotulo: string; href: string }[] = [
  { id: 'acessos', rotulo: 'Acessos', href: '#/admin/acessos' },
  { id: 'design', rotulo: 'Design', href: '#/admin/design/fundacao' },
  { id: 'monitoramento', rotulo: 'Monitoramento', href: '#/admin/monitoramento' },
]

export const ROTULO_AREA: Record<AreaAdmin, string> = {
  acessos: 'Gestão de acessos',
  design: 'Catálogo de interface',
  monitoramento: 'Monitoramento',
}

/** Qual área uma rota de admin representa. */
export function areaDaRota(rota: Rota): AreaAdmin | null {
  if (rota.nome === 'admin-acessos') return 'acessos'
  if (rota.nome === 'admin-monitoramento') return 'monitoramento'
  if (rota.nome === 'catalogo') return 'design'
  return null
}

/** A faixa de contexto. Fica fora do `<main>` — é cromo, não conteúdo. */
export function FaixaAdmin() {
  return (
    <div className="faixa-admin">
      <div className="faixa-admin-interna">
        <strong>Administração</strong>
        <span className="faixa-admin-nota">você está fora do produto</span>
      </div>
    </div>
  )
}

type Props = {
  area: AreaAdmin
  /** Largura da página. Design precisa de espaço para o palco de 1440px. */
  largura?: 'densa' | 'padrao'
  children: ReactNode
}

/**
 * `h1` é sempre `Administração` e a área vai no `h2` (§3.5) — assim o anúncio
 * de rota já diz onde a pessoa está, junto com o prefixo de `document.title`.
 */
export function CascaAdmin({ area, largura = 'densa', children }: Props) {
  return (
    <main
      className="pagina contexto-pagina pilha"
      data-largura={largura === 'densa' ? 'densa' : undefined}
      data-espaco="6"
    >
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara de="assuntos" />
        <h1 className="titulo-tela">Administração</h1>
      </header>

      <nav className="nav-admin" aria-label="Áreas da administração">
        {AREAS.map((item) => (
          <a
            key={item.id}
            className="nav-admin-link"
            href={item.href}
            aria-current={item.id === area ? 'page' : undefined}
          >
            {item.rotulo}
          </a>
        ))}
      </nav>

      {children}
    </main>
  )
}
