import { formatarMoedaComPrefixo, formatarPercentual, paraNumero } from './formatoPlano'
import { IconeFechado, IconeSobrealocado, IconeSubalocado } from './icones'
import { Selo } from './ui'

interface Props {
  /** `diferenca` do nível (positiva = sub-alocado, negativa = sobre-alocado). */
  diferenca: string
  /** Valor do próprio nível (denominador do percentual exibido). */
  base: string
  /** Nome do nó, só para o `aria-label` do selo. */
  rotulo: string
}

const TOLERANCIA_CENTAVO = 0.005

/**
 * B3 do desenho: sub-alocado e sobre-alocado com ÍCONE distinto, não só cor
 * — o requisito de acessibilidade é "perceptível sem depender de cor", e
 * uma seta que só troca de rotação falha esse teste para baixa acuidade
 * visual. D-B: nunca bloqueia, nunca redistribui — só informa.
 */
export function SeloDesbalanco({ diferenca, base, rotulo }: Props) {
  const d = paraNumero(diferenca)
  const b = paraNumero(base)
  const percentual = b > 0 ? formatarPercentual((Math.abs(d) / b) * 100) : null

  if (Math.abs(d) < TOLERANCIA_CENTAVO) {
    return (
      <Selo variante="ok">
        <IconeFechado /> fechado
      </Selo>
    )
  }

  if (d > 0) {
    return (
      <Selo variante="alerta">
        <IconeSubalocado titulo={`${rotulo}: sub-alocado`} />
        {formatarMoedaComPrefixo(d)}
        {percentual && ` (${percentual}%)`} não distribuído
      </Selo>
    )
  }

  return (
    <Selo variante="erro">
      <IconeSobrealocado titulo={`${rotulo}: sobre-alocado`} />
      {formatarMoedaComPrefixo(Math.abs(d))}
      {percentual && ` (${percentual}%)`} além do orçamento
    </Selo>
  )
}
