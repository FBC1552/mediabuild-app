import { useEffect, useState } from 'react'

import { ErroRequisicao } from '../api'
import { Giro } from './ui'

interface Props {
  /** Nome acessível da célula — "Impressões de A0975 (BNR_1080X1350...)". */
  rotulo: string
  valor: number | null
  aoSalvar: (valor: number | null) => Promise<void>
}

/**
 * Célula da grade de Metas. Todas as onze métricas são contagem (D do
 * domínio §1): sem casas decimais, salva no blur com o mesmo padrão de
 * confirmação transitória do `CampoRateio`.
 *
 * A distinção "célula não se aplica" (branco ≠ zero, §5.1/E) nasce fora de
 * escopo aqui — não existe hoje, em nenhum schema, a regra de qual métrica
 * vale para qual combinação plataforma+formato (ver docs/PLANO-DE-MIDIA.md
 * §3 e docs/PLANO-DE-MIDIA-UI.md §5.1): a aba nasce com toda célula
 * editável, estado inicial honesto até esse levantamento existir.
 */
export function CelulaMeta({ rotulo, valor, aoSalvar }: Props) {
  const [texto, setTexto] = useState(valor === null ? '' : String(valor))
  const [foco, setFoco] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [salvo, setSalvo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    if (foco) return
    setTexto(valor === null ? '' : String(valor))
  }, [valor, foco])

  useEffect(() => {
    if (!salvo) return
    const t = setTimeout(() => setSalvo(false), 1500)
    return () => clearTimeout(t)
  }, [salvo])

  async function confirmar() {
    setFoco(false)
    const limpo = texto.trim()
    const novo = limpo === '' ? null : Math.trunc(Number(limpo))
    if (novo !== null && !Number.isFinite(novo)) return
    if (novo === valor || (novo === null && valor === null)) return
    setSalvando(true)
    setErro(null)
    try {
      await aoSalvar(novo)
      setSalvo(true)
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível salvar.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <span className="celula-meta">
      <input
        className="celula-meta-input"
        type="number"
        inputMode="numeric"
        step={1}
        aria-label={rotulo}
        aria-invalid={Boolean(erro)}
        value={texto}
        onFocus={() => setFoco(true)}
        onChange={(e) => setTexto(e.target.value)}
        onBlur={() => void confirmar()}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur()
        }}
      />
      {salvando && <Giro />}
      {salvo && !salvando && (
        <span className="apenas-leitor" role="status" aria-live="polite">
          {rotulo}: salvo.
        </span>
      )}
      {erro && (
        <span className="celula-meta-erro" role="alert">
          {erro}
        </span>
      )}
    </span>
  )
}
