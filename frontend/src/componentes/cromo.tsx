/**
 * Cromo das telas públicas: barra de topo e rodapé utilitário.
 *
 * Vive fora do palco da splash de propósito. O monograma quicante trata cada
 * controle DENTRO do palco como parede; qualquer coisa que ele não possa
 * atingir é mais barata de manter do lado de fora do que de descrever para o
 * rAF. Barra e rodapé são navegação persistente, então não precisam ser parede
 * — precisam ser inalcançáveis.
 *
 * Escopo: só as telas de entrada (`#/`, `#/guia`, `#/cadastro`). O aplicativo
 * de taxonomia tem o próprio cromo, com as abas Gerar/Dicionário/Histórico —
 * essas continuam de fora daqui, porque são navegação DENTRO de um assunto,
 * não navegação entre assuntos (Rosenfeld/Morville: sistemas de organização
 * diferentes não compartilham a mesma barra).
 */
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

import marcaSimbolo from '../ativos/marca.png'
import { useSessao } from '../sessao'
import { ROTULO_PAPEL, type Papel } from '../tipos'
import { AlternadorTema } from './AlternadorTema'
import { IconeChevron, IconeConta } from './icones'

type Secao = 'guia' | 'cadastro'

/**
 * A linha que paga o custo de descoberta do gating (UX-NAVEGACAO §4.1).
 *
 * A regra do produto é "permissão esconde, condição desabilita com motivo":
 * o `basico` não vê controles mortos espalhados pela tela. O contra-argumento
 * honesto — esconder prejudica a descoberta — é resolvido AQUI, num lugar
 * canônico e previsível, com uma frase, em vez de dezenas de tooltips.
 */
const EXPLICACAO_PAPEL: Record<Papel, string> = {
  basico:
    'Seu perfil gera nomenclaturas e consulta o histórico. Dicionário e exclusões precisam de um perfil Pleno.',
  pleno: 'Seu perfil usa o produto inteiro: gerar, dicionário, histórico e planos de mídia.',
  admin: 'Seu perfil usa o produto inteiro e administra acessos.',
}

function primeiroNome(nome: string): string {
  return nome.trim().split(/\s+/)[0] || nome
}

/**
 * Menu de conta: identidade, papel, o que o papel destrava, tema e sair.
 *
 * Por que **disclosure** e não `role="menu"` do APG, apesar de o desenho o
 * chamar de menu button: dentro dele mora o `AlternadorTema`, que é um grupo
 * de rádios NATIVO. Um `role="menu"` obrigaria cada filho a ser `menuitem` /
 * `menuitemradio`, o que exigiria reimplementar o radiogroup à mão e perder o
 * que o `<fieldset>` já entrega de graça. O comportamento observável que o
 * desenho pede continua: `aria-expanded`, Esc fecha e devolve o foco ao
 * gatilho, clique fora fecha, e o conteúdo é percorrido por Tab.
 */
export function MenuConta() {
  const { usuario, papel, permissoes, sair } = useSessao()
  const [aberto, setAberto] = useState(false)
  const idPainel = useId()
  const gatilho = useRef<HTMLButtonElement>(null)
  const painel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!aberto) return
    function aoApontar(evento: PointerEvent) {
      const alvo = evento.target as Node
      if (painel.current?.contains(alvo) || gatilho.current?.contains(alvo)) return
      setAberto(false)
    }
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key !== 'Escape') return
      setAberto(false)
      gatilho.current?.focus()
    }
    document.addEventListener('pointerdown', aoApontar)
    document.addEventListener('keydown', aoTeclar)
    return () => {
      document.removeEventListener('pointerdown', aoApontar)
      document.removeEventListener('keydown', aoTeclar)
    }
  }, [aberto])

  if (!usuario) return null

  return (
    <div className="menu-conta">
      <button
        type="button"
        className="menu-conta-gatilho"
        ref={gatilho}
        aria-expanded={aberto}
        aria-controls={idPainel}
        onClick={() => setAberto((v) => !v)}
      >
        <IconeConta />
        <span className="menu-conta-nome">{primeiroNome(usuario.nome)}</span>
        <span className="apenas-leitor"> · conta</span>
        <IconeChevron sentido={aberto ? 'cima' : 'baixo'} />
      </button>

      {aberto && (
        <div className="menu-conta-painel card pilha" data-espaco="4" id={idPainel} ref={painel}>
          <div className="pilha" data-espaco="1">
            <p className="menu-conta-identidade">{usuario.nome}</p>
            <p className="texto-auxiliar mono">@{usuario.login}</p>
            <p className="texto-auxiliar">Perfil: {papel ? ROTULO_PAPEL[papel] : '—'}</p>
            {papel && <p className="texto-auxiliar">{EXPLICACAO_PAPEL[papel]}</p>}
          </div>

          <hr className="menu-conta-divisor" />

          <AlternadorTema tamanho="sm" />

          {permissoes.podeAdministrar && (
            <>
              <hr className="menu-conta-divisor" />
              {/* Administração é atributo de QUEM VOCÊ É, não de o que você
                  está fazendo — por isso mora aqui e não na barra de
                  navegação, que mudaria de tamanho conforme o papel. */}
              <a className="menu-conta-item" href="#/admin">
                Administração
              </a>
            </>
          )}

          <hr className="menu-conta-divisor" />

          {/* Sem confirmação: sair não destrói nada — nomenclatura salva é
              imutável e o rascunho é limpo de propósito. */}
          <button
            type="button"
            className="menu-conta-item menu-conta-sair"
            onClick={() => {
              setAberto(false)
              void sair()
            }}
          >
            Sair
          </button>
        </div>
      )}
    </div>
  )
}

/** Um item só por destino: o rótulo é o mesmo na barra e no rodapé. */
const LINKS: { secao: Secao; rotulo: string; href: string }[] = [
  { secao: 'guia', rotulo: 'Guia de uso', href: '#/guia' },
  { secao: 'cadastro', rotulo: 'Cadastro', href: '#/cadastro' },
]

type PropsBarra = {
  atual?: Secao
  /**
   * O catálogo monta a barra como EXEMPLO: ali ela não pode mostrar a conta
   * de quem estiver logado, senão o palco deixa de ser dado de mentira.
   */
  conta?: boolean
}

export function BarraTopo({ atual, conta = true }: PropsBarra) {
  return (
    <header className="barra-topo">
      <div className="barra-topo-interna">
        {/* A marca é o caminho de volta para a tela inicial — convenção de
            Jakob, e o único jeito de reencontrar a home depois que o app passa
            a abrir direto na taxonomia. */}
        <a className="barra-topo-marca" href="#/" aria-label="MediaBuild · tela inicial">
          <img
            className="simbolo-topo"
            src={marcaSimbolo}
            alt=""
            aria-hidden="true"
            width={256}
            height={256}
            decoding="async"
          />
          <span className="marca marca-logotipo" data-tamanho="sm">
            MDBuilder
          </span>
        </a>

        <div className="barra-topo-direita">
          <nav className="barra-topo-nav" aria-label="Navegação principal">
            {LINKS.map((link) => (
              <a
                key={link.secao}
                className="link-topo"
                href={link.href}
                aria-current={atual === link.secao ? 'page' : undefined}
              >
                {link.rotulo}
              </a>
            ))}
          </nav>

          {/* Identidade e saída ficam sempre no mesmo lugar (Nielsen #4).
              O menu se desenha sozinho como nada quando não há sessão. */}
          {conta && <MenuConta />}
        </div>
      </div>
    </header>
  )
}

/**
 * Rodapé fino. `children` entra ANTES dos links utilitários e existe para o
 * controle de pausa da splash (WCAG 2.2.2), que precisa ficar visível e fora
 * do alcance do monograma.
 */
export function RodapeUtilitario({ children }: { children?: ReactNode }) {
  // O catálogo de interface é ferramenta de quem administra o design system,
  // não item de navegação do produto: some para quem não administra (§3.3).
  const { permissoes } = useSessao()
  return (
    <footer className="rodape-utilitario">
      <div className="rodape-utilitario-interno">
        {children}
        <nav className="rodape-links" aria-label="Links utilitários">
          <a className="link-rodape" href="#/guia">
            Guia de uso
          </a>
          <a className="link-rodape" href="#/taxonomia/gerar">
            Gerar nomenclatura
          </a>
          {permissoes.podeAdministrar && (
            <a className="link-rodape" href="#/admin/design/fundacao">
              Catálogo de interface
            </a>
          )}
        </nav>
        <p className="rodape-nota">MediaBuild · uso local</p>
      </div>
    </footer>
  )
}
