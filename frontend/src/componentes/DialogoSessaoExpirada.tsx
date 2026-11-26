/**
 * Reautenticação por cima da tela (UX-NAVEGACAO §4.4).
 *
 * O requisito duro: **expirar sessão não navega, não desmonta, não limpa
 * nada.** O que está atrás continua montado e preenchido; o diálogo só
 * devolve a credencial.
 *
 * Duas decisões que não são estilo:
 *
 * · `<dialog>` NATIVO com `showModal()`. Focus trap escrito à mão é onde
 *   nascem os bugs de acessibilidade — o elemento já entrega trap, `inert` no
 *   resto da página e devolução de foco.
 * · `Esc` não fecha (`cancel` prevenido). Fechar sem resolver deixaria a tela
 *   numa mentira: controles visíveis que não funcionam mais.
 *
 * E a proibição que justifica o diálogo existir: **nada é reexecutado
 * automaticamente depois do relogin.** Repetir sozinho um `POST /taxonomias`
 * consumiria um `match_id` e gravaria um nome que ninguém pediu. O usuário
 * aperta o botão de novo — o formulário está lá, intacto.
 */
import { useEffect, useRef } from 'react'

import { useSessao } from '../sessao'
import { FormularioEntrar } from './Entrar'

export function DialogoSessaoExpirada() {
  const { expirada, usuario, reautenticar, sair } = useSessao()
  const dialogo = useRef<HTMLDialogElement>(null)
  const focoAnterior = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const elemento = dialogo.current
    if (!elemento) return
    if (expirada && !elemento.open) {
      focoAnterior.current = document.activeElement as HTMLElement | null
      // jsdom só ganhou `showModal` em versões recentes; sem ele o diálogo
      // ainda abre (o atributo `open`), que é o que os testes observam.
      if (typeof elemento.showModal === 'function') elemento.showModal()
      else elemento.setAttribute('open', '')
    }
    if (!expirada && elemento.open) {
      if (typeof elemento.close === 'function') elemento.close()
      else elemento.removeAttribute('open')
      focoAnterior.current?.focus()
    }
  }, [expirada])

  // Sem `open` no JSX: quem abre é `showModal()`, e um `<dialog open>` de
  // marcação é NÃO-modal — sem fundo, sem trap, sem `inert`.
  return (
    <dialog className="dialogo" ref={dialogo} onCancel={(e) => e.preventDefault()}>
      {expirada && (
        <div className="pilha" data-espaco="5">
          <header className="pilha" data-espaco="2">
            <h2 className="painel-titulo">Sua sessão expirou</h2>
            <p className="texto-auxiliar">
              Entre de novo para continuar. Nada do que você preencheu foi perdido.
            </p>
          </header>

          <FormularioEntrar
            loginFixo={usuario?.login ?? undefined}
            autenticar={reautenticar}
            focoInicial="senha"
          />

          <div className="linha" data-alinhar="fim">
            <button
              type="button"
              className="botao"
              data-variante="fantasma"
              data-tamanho="sm"
              onClick={() => void sair()}
            >
              <span className="botao-rotulo">Sair da conta</span>
            </button>
          </div>
        </div>
      )}
    </dialog>
  )
}
