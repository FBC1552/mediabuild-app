import { Fragment, useEffect, useRef, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import type { ItemLaudoUtm, LaudoUtm } from '../tipos'
import { Botao, BotaoCopiar } from './ui'

/** Uma nomenclatura já gerada, elegível para conferir a URL de destino. */
export interface AlvoUtm {
  taxonomia_id: string
  rotulo: string
}

interface Props {
  alvos: AlvoUtm[]
}

/**
 * Estado explícito, não três booleanos que podem se contradizer: não existe
 * "conferindo e pronto ao mesmo tempo".
 */
type Estado =
  | { fase: 'ocioso' }
  | { fase: 'conferindo' }
  | { fase: 'pronto'; laudo: LaudoUtm }
  | { fase: 'falhou'; mensagem: string }

function Itens({ itens }: { itens: ItemLaudoUtm[] }) {
  return (
    <ul className="laudo-lista">
      {itens.map((item, indice) => (
        <li key={`${item.codigo}-${item.parametro ?? indice}`} className="laudo-item">
          {item.mensagem}
          {(item.encontrado || item.esperado) && (
            <span className="laudo-detalhe">
              {item.encontrado ? `encontrado: ${item.encontrado}` : null}
              {item.encontrado && item.esperado ? ' · ' : null}
              {item.esperado ? `esperado: ${item.esperado}` : null}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

/**
 * Confere a URL de destino contra uma nomenclatura já gerada (D-012).
 *
 * O app **confere**, não monta: gerar a URL exigiria conhecer regra de
 * landing page e macro de cada plataforma, e o produto gera nomes.
 *
 * `POST /utm/validar` responde sempre 200 — o laudo é o resultado, não o
 * erro. `ErroRequisicao` aqui significa que a requisição em si falhou.
 */
export function ValidadorUtm({ alvos }: Props) {
  const [url, setUrl] = useState('')
  const [alvoId, setAlvoId] = useState('')
  const [estado, setEstado] = useState<Estado>({ fase: 'ocioso' })
  const emVoo = useRef<AbortController | null>(null)

  // Deriva o alvo padrão sem efeito: a nomenclatura mais recente é a que o
  // analista acabou de gerar, então é a que ele quer conferir.
  const alvoSelecionado = alvos.some((a) => a.taxonomia_id === alvoId)
    ? alvoId
    : (alvos[0]?.taxonomia_id ?? '')

  useEffect(() => () => emVoo.current?.abort(), [])

  if (alvos.length === 0) {
    return (
      <section className="card bloco pilha" data-espaco="3" aria-labelledby="titulo-utm">
        <h2 id="titulo-utm" className="rotulo-secao">
          Conferir URL de destino
        </h2>
        <div className="estado" data-tipo="vazio">
          <p className="estado-texto">
            Gere uma nomenclatura para conferir a URL de destino dela. A conferência compara
            as UTMs da URL com os match IDs desta campanha.
          </p>
        </div>
      </section>
    )
  }

  async function conferir() {
    if (!url.trim() || !alvoSelecionado) return

    // Cliques em sequência: a resposta atrasada da URL antiga não pode
    // sobrescrever o laudo da nova.
    emVoo.current?.abort()
    const controlador = new AbortController()
    emVoo.current = controlador
    setEstado({ fase: 'conferindo' })

    try {
      const laudo = await api.validarUtm(
        { url: url.trim(), taxonomia_id: alvoSelecionado },
        controlador.signal,
      )
      if (controlador.signal.aborted) return
      setEstado({ fase: 'pronto', laudo })
    } catch (e) {
      if (controlador.signal.aborted) return
      setEstado({
        fase: 'falhou',
        mensagem:
          e instanceof ErroRequisicao
            ? e.corpo.mensagem
            : 'Não foi possível conferir a URL agora.',
      })
    }
  }

  const laudo = estado.fase === 'pronto' ? estado.laudo : null
  const parametros = laudo ? Object.entries(laudo.parametros) : []

  return (
    <section className="card bloco pilha" data-espaco="4" aria-labelledby="titulo-utm">
      <h2 id="titulo-utm" className="rotulo-secao">
        Conferir URL de destino
      </h2>

      <div>
        <label htmlFor="utm-alvo">Conferir contra</label>
        <select
          id="utm-alvo"
          value={alvoSelecionado}
          onChange={(e) => {
            setAlvoId(e.target.value)
            setEstado({ fase: 'ocioso' })
          }}
        >
          {alvos.map((alvo) => (
            <option key={alvo.taxonomia_id} value={alvo.taxonomia_id}>
              {alvo.rotulo}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="utm-url">URL de destino</label>
        <input
          id="utm-url"
          type="url"
          value={url}
          placeholder="https://exemplo.com.br/?utm_source=…"
          onChange={(e) => {
            setUrl(e.target.value)
            if (estado.fase !== 'ocioso') setEstado({ fase: 'ocioso' })
          }}
        />
      </div>

      <div className="linha">
        <Botao
          onClick={conferir}
          disabled={!url.trim()}
          carregando={estado.fase === 'conferindo'}
        >
          Conferir URL
        </Botao>
      </div>

      {estado.fase === 'falhou' && (
        <div className="laudo" data-tipo="erro" role="alert">
          <p className="laudo-titulo">{estado.mensagem}</p>
        </div>
      )}

      {laudo && (
        <div className="pilha" data-espaco="4">
          {/* Erro e aviso em blocos separados: erro é dado que chega errado,
              aviso é o que funciona mas envelhece mal. */}
          {laudo.erros.length > 0 && (
            <div className="laudo" data-tipo="erro" role="alert">
              <p className="laudo-titulo">
                {laudo.erros.length === 1 ? '1 erro' : `${laudo.erros.length} erros`} · o dado
                vai chegar errado
              </p>
              <Itens itens={laudo.erros} />
            </div>
          )}

          {laudo.erros.length === 0 && (
            <div className="laudo" data-tipo="ok" role="status">
              <p className="laudo-titulo">Nenhum erro na URL.</p>
            </div>
          )}

          {laudo.avisos.length > 0 && (
            <div className="laudo" data-tipo="aviso" role="status">
              <p className="laudo-titulo">
                {laudo.avisos.length === 1 ? '1 aviso' : `${laudo.avisos.length} avisos`} ·
                funciona, mas envelhece mal
              </p>
              <Itens itens={laudo.avisos} />
            </div>
          )}

          {laudo.url_sugerida && (
            <div className="pilha" data-espaco="2">
              <span className="rotulo-secao">URL sugerida</span>
              <div className="linha" data-espaco="3">
                <code className="arvore-nomenclatura">{laudo.url_sugerida}</code>
                <span className="empurra">
                  <BotaoCopiar texto={laudo.url_sugerida} rotulo="Copiar URL sugerida" />
                </span>
              </div>
            </div>
          )}

          <div className="pilha" data-espaco="2">
            <span className="rotulo-secao">Parâmetros lidos</span>
            {parametros.length === 0 ? (
              <p className="texto-auxiliar">Nenhum parâmetro utm_ nesta URL.</p>
            ) : (
              <dl className="parametros">
                {/* Fragment, não <div>: o wrapper viraria item da grade e
                    destruiria o alinhamento de duas colunas do <dl>. */}
                {parametros.map(([chave, valor]) => (
                  <Fragment key={chave}>
                    <dt>{chave}</dt>
                    <dd>{valor}</dd>
                  </Fragment>
                ))}
              </dl>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
