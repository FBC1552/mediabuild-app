import { useState } from 'react'

import { ErroRequisicao } from '../api'
import { Botao, Selo } from './ui'

interface Props {
  nomenclaturaSnapshot: string | null
  nomenclaturaAtual: string | null
  divergente: boolean
  /** Ausente enquanto o backend não expuser o verbo de sincronização — ver
   * relatório da tarefa: o botão fica escondido, não desabilitado, até o
   * contrato existir. */
  aoAtualizarSnapshot?: () => Promise<void>
}

/**
 * D do desenho (§4.4): avisa sempre, oferece atualizar, nunca atualiza
 * sozinho. `<details>` nativo — sem JS de posicionamento, sem modal — para
 * a revelação inline das duas strings lado a lado.
 */
export function DivergenciaNome({
  nomenclaturaSnapshot,
  nomenclaturaAtual,
  divergente,
  aoAtualizarSnapshot,
}: Props) {
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [feito, setFeito] = useState(false)

  if (!divergente) return null

  async function atualizar() {
    if (!aoAtualizarSnapshot) return
    setSalvando(true)
    setErro(null)
    try {
      await aoAtualizarSnapshot()
      setFeito(true)
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível atualizar.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <details className="divergencia-nome">
      <summary>
        <Selo variante="alerta">nome desatualizado</Selo>
      </summary>
      <div className="divergencia-nome-corpo pilha" data-espaco="2">
        <p className="texto-auxiliar">
          <strong>No plano:</strong> <code className="mono">{nomenclaturaSnapshot ?? '—'}</code>
        </p>
        <p className="texto-auxiliar">
          <strong>Agora:</strong> <code className="mono">{nomenclaturaAtual ?? '—'}</code>
        </p>

        {aoAtualizarSnapshot ? (
          <>
            <Botao tamanho="sm" variante="secundario" onClick={() => void atualizar()} carregando={salvando}>
              Atualizar snapshot do plano
            </Botao>
            {feito && (
              <p className="texto-auxiliar" role="status">
                ✓ snapshot atualizado.
              </p>
            )}
            {erro && (
              <p className="texto-auxiliar" data-tom="alerta" role="alert">
                {erro}
              </p>
            )}
          </>
        ) : (
          <p className="texto-auxiliar">
            Atualizar o snapshot direto pela tela ainda depende de um adendo no backend — regere a
            taxonomia deste nível e reabra o plano para reavaliar.
          </p>
        )}
      </div>
    </details>
  )
}
