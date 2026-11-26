/**
 * Alternador de tema: Claro · Escuro · Sistema.
 *
 * Por que `<fieldset>` com três `<input type="radio">` e não três botões:
 * o padrão do WAI-ARIA APG para "escolher um entre N" é o Radio Group, e o
 * grupo de rádios NATIVO já entrega tudo o que o padrão exige — um único ponto
 * de parada no Tab, setas navegando entre as opções, `aria-checked` correto,
 * nome do grupo lido pelo leitor de tela. Sem Radix, escrever isso à mão seria
 * reimplementar roving tabindex para chegar no mesmo lugar, com mais bugs.
 *
 * Os rádios ficam visualmente escondidos (`.apenas-leitor`), mas continuam no
 * fluxo e continuam focáveis: quem pinta é o `<label>` irmão, e o anel de foco
 * é reemitido nele por `input:focus-visible + label`. Nada de `display: none`,
 * que tiraria o controle do teclado.
 *
 * `useId()` e não id literal — regra do projeto: o catálogo monta vários
 * exemplos ao mesmo tempo, e id repetido faria o `htmlFor` de um alternador
 * apontar para o rádio de outro. O mesmo id serve de `name`, que é o que
 * agrupa os três rádios (dois alternadores com o mesmo `name` viram um grupo
 * só de seis opções).
 *
 * O componente não decide margem externa nem largura: quem posiciona é o
 * contêiner, como todo o resto do sistema.
 */
import { useId } from 'react'

import { MODOS, ROTULO_MODO, useTema, type ModoTema } from '../tema'

type Props = {
  /** Rótulo do grupo. Trocável porque o contexto muda (barra de topo × catálogo). */
  rotulo?: string
  tamanho?: 'md' | 'sm'
}

export function AlternadorTema({ rotulo = 'Tema', tamanho = 'md' }: Props) {
  const id = useId()
  const { modo, definirModo } = useTema()

  return (
    <fieldset className="alternador-tema" data-tamanho={tamanho}>
      <legend className="alternador-tema-rotulo">{rotulo}</legend>
      <div className="alternador-tema-opcoes">
        {MODOS.map((opcao: ModoTema) => (
          <span key={opcao} className="alternador-tema-opcao">
            <input
              className="apenas-leitor"
              type="radio"
              id={`${id}-${opcao}`}
              name={id}
              value={opcao}
              checked={modo === opcao}
              onChange={() => definirModo(opcao)}
            />
            <label htmlFor={`${id}-${opcao}`}>{ROTULO_MODO[opcao]}</label>
          </span>
        ))}
      </div>
    </fieldset>
  )
}
