import { useEffect, useId, useState } from 'react'

import { ErroRequisicao } from '../api'
import {
  formatarMoeda,
  formatarPercentual,
  parseNumeroDigitado,
  paraNumero,
  textoEdicaoPercentual,
  textoEdicaoValor,
} from './formatoPlano'
import { Giro } from './ui'

export type CampoDoRateio = 'valor' | 'percentual'

interface Props {
  /** Decimal do servidor, sempre a fonte da verdade fora de edição. */
  valor: string
  /** Nulo quando o pai vale zero — a divisão não tem sentido (D-B). */
  percentual: string | null
  /** Valor em reais do nível acima, para derivar o percentual em memória. */
  valorPai: string
  /** Nome do nó, só para os `aria-label` — nunca aparece na tela repetido. */
  rotulo: string
  desabilitado?: boolean
  /**
   * Persiste exatamente UM dos dois campos (nunca os dois — mesmo contrato
   * do backend). Deve rejeitar (throw) em caso de erro; a resolução
   * atualiza `valor`/`percentual` via as props (o servidor é quem decide o
   * valor final, D-A) — este componente não aplica otimisticamente.
   */
  aoSalvar: (campo: CampoDoRateio, textoDigitado: string) => Promise<void>
}

/**
 * O controle duplo R$/% do rateio (docs/PLANO-DE-MIDIA-UI.md §4.3).
 *
 * Só o campo COM FOCO guarda o texto bruto digitado — nunca reformatado a
 * cada tecla, isso rouba o cursor. O irmão sem foco deriva ao vivo EM
 * MEMÓRIA (sem chamada de rede) e ganha `data-derivado`, sinal visual de
 * "isto é calculado, não é o que você digitou". O PATCH sai só no blur (ou
 * Enter), mandando só o campo editado; a resposta do servidor (via props)
 * é quem substitui os dois números — a distinção derivado/digitado some
 * depois de salvo.
 */
export function CampoRateio({
  valor,
  percentual,
  valorPai,
  rotulo,
  desabilitado = false,
  aoSalvar,
}: Props) {
  const idBase = useId()
  const idErro = `${idBase}-erro`

  const [foco, setFoco] = useState<CampoDoRateio | null>(null)
  const [textoValor, setTextoValor] = useState(() => textoEdicaoValor(valor))
  const [textoPercentual, setTextoPercentual] = useState(() => textoEdicaoPercentual(percentual))
  const [salvando, setSalvando] = useState<CampoDoRateio | null>(null)
  const [salvo, setSalvo] = useState(false)
  const [erro, setErro] = useState<{ campo: CampoDoRateio; mensagem: string } | null>(null)

  // Ressincroniza com o servidor (fonte da verdade) quando não há edição em
  // curso nem erro pendente — um erro preserva o texto digitado na tela até
  // o analista tentar de novo, em vez de apagar silenciosamente o que ele
  // tinha escrito.
  useEffect(() => {
    if (foco || erro) return
    setTextoValor(textoEdicaoValor(valor))
    setTextoPercentual(textoEdicaoPercentual(percentual))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valor, percentual])

  useEffect(() => {
    if (!salvo) return
    const t = setTimeout(() => setSalvo(false), 1500) // --dur-confirmacao
    return () => clearTimeout(t)
  }, [salvo])

  const pai = paraNumero(valorPai)

  // Derivação em memória, sem rede — e sempre GRAVADA no estado do irmão
  // (não só calculada na hora do render): com Tab, o foco sai do campo
  // editado e entra no irmão DENTRO do mesmo componente antes de qualquer
  // outra coisa acontecer, e nesse instante o irmão precisa já estar
  // mostrando o valor derivado, não um texto parado de antes da edição.
  function editarValor(texto: string) {
    setTextoValor(texto)
    const n = parseNumeroDigitado(texto)
    if (n !== null && pai > 0) setTextoPercentual(formatarPercentual((n / pai) * 100))
  }

  function editarPercentual(texto: string) {
    setTextoPercentual(texto)
    const n = parseNumeroDigitado(texto)
    if (n !== null) setTextoValor(formatarMoeda((n / 100) * pai))
  }

  async function confirmar(campo: CampoDoRateio, textoDigitado: string) {
    setFoco(null)
    const textoLimpo = textoDigitado.trim()
    if (textoLimpo === '') return // nada digitado, nada a salvar
    setSalvando(campo)
    setErro(null)
    try {
      await aoSalvar(campo, textoLimpo.replace(',', '.'))
      setSalvo(true)
    } catch (e) {
      const mensagem =
        e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível salvar.'
      setErro({ campo, mensagem })
    } finally {
      setSalvando(null)
    }
  }

  function aoTeclar(campo: CampoDoRateio) {
    return (evento: React.KeyboardEvent<HTMLInputElement>) => {
      if (evento.key !== 'Enter') return
      evento.preventDefault()
      const alvo = evento.currentTarget
      // O blur nativo dispara `onBlur` (que chama `confirmar`); Enter só
      // acrescenta o salto de foco de planilha para a MESMA coluna da
      // próxima linha de rateio da árvore.
      alvo.blur()
      const grupo = Array.from(
        document.querySelectorAll<HTMLInputElement>(`[data-campo-rateio="${campo}"]`),
      )
      const indice = grupo.indexOf(alvo)
      if (indice >= 0 && indice < grupo.length - 1) {
        grupo[indice + 1].focus()
      }
    }
  }

  const erroValor = erro?.campo === 'valor' ? erro.mensagem : undefined
  const erroPercentual = erro?.campo === 'percentual' ? erro.mensagem : undefined

  return (
    <span className="campo-rateio" data-desabilitado={desabilitado || undefined}>
      <span className="campo-rateio-item">
        <span className="campo-rateio-prefixo" aria-hidden="true">
          R$
        </span>
        <input
          className="campo-rateio-input"
          data-campo-rateio="valor"
          data-derivado={foco === 'percentual' || undefined}
          inputMode="decimal"
          aria-label={`${rotulo} — valor em reais`}
          aria-invalid={Boolean(erroValor)}
          aria-describedby={erroValor ? idErro : undefined}
          aria-busy={salvando === 'valor' || undefined}
          disabled={desabilitado}
          value={textoValor}
          onFocus={() => {
            setFoco('valor')
            setErro(null)
          }}
          onChange={(e) => editarValor(e.target.value)}
          onBlur={(e) => void confirmar('valor', e.target.value)}
          onKeyDown={aoTeclar('valor')}
        />
      </span>

      <span className="campo-rateio-item">
        <input
          className="campo-rateio-input"
          data-campo-rateio="percentual"
          data-derivado={foco === 'valor' || undefined}
          inputMode="decimal"
          aria-label={`${rotulo} — percentual do orçamento acima`}
          aria-invalid={Boolean(erroPercentual)}
          aria-describedby={erroPercentual ? idErro : undefined}
          aria-busy={salvando === 'percentual' || undefined}
          disabled={desabilitado}
          value={textoPercentual}
          onFocus={() => {
            setFoco('percentual')
            setErro(null)
          }}
          onChange={(e) => editarPercentual(e.target.value)}
          onBlur={(e) => void confirmar('percentual', e.target.value)}
          onKeyDown={aoTeclar('percentual')}
        />
        <span className="campo-rateio-sufixo" aria-hidden="true">
          %
        </span>
      </span>

      {salvando && (
        <span className="campo-rateio-status" aria-hidden="true">
          <Giro />
        </span>
      )}
      {salvo && !salvando && <span className="campo-rateio-status campo-rateio-ok">✓ salvo</span>}

      <span className="apenas-leitor" role="status" aria-live="polite">
        {salvo && !salvando ? `${rotulo}: rateio salvo.` : ''}
      </span>

      {erro && (
        <span id={idErro} className="campo-rateio-erro" role="alert">
          {erro.mensagem}
        </span>
      )}
    </span>
  )
}
