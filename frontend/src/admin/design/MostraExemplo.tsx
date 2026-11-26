import {
  Component,
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react'

/**
 * O átomo do catálogo: cabeçalho, palco, régua e nota.
 *
 * `src/admin/**` não importa `src/api.ts` nem nada do gerador — a fronteira é
 * o que permite mover esta pasta para outra área depois com um `mv`, e o que
 * impede o catálogo de escrever no banco do analista ao demonstrar um form.
 */
export type Exemplo = {
  id: string
  titulo: string
  /** "O que observar / quando usar" — é a nota que separa catálogo de vitrine. */
  nota: string
  render: () => ReactNode
}

export type Preferencias = {
  largura: string
  zoom: string
  fundo: 'cartao' | 'pagina'
}

export const PADRAO: Preferencias = { largura: '100%', zoom: '1', fundo: 'cartao' }

export const ContextoPalco = createContext<Preferencias>(PADRAO)

export const LARGURAS: { valor: string; rotulo: string }[] = [
  { valor: 'herdar', rotulo: 'Herdar' },
  { valor: '360px', rotulo: 'Estreito 360' },
  { valor: '768px', rotulo: 'Compacto 768' },
  { valor: '1024px', rotulo: 'Padrão 1024' },
  { valor: '1440px', rotulo: 'Amplo 1440' },
  { valor: '100%', rotulo: 'Livre' },
]

export const ZOOMS: { valor: string; rotulo: string }[] = [
  { valor: 'herdar', rotulo: 'Herdar' },
  { valor: '1', rotulo: '100%' },
  { valor: '1.25', rotulo: '125%' },
  { valor: '1.5', rotulo: '150%' },
  { valor: '2', rotulo: '200%' },
]

export const FUNDOS: { valor: string; rotulo: string }[] = [
  { valor: 'herdar', rotulo: 'Herdar' },
  { valor: 'cartao', rotulo: 'Cartão' },
  { valor: 'pagina', rotulo: 'Página' },
]

type PropsSelecao = {
  rotulo: string
  valor: string
  opcoes: { valor: string; rotulo: string }[]
  aoMudar: (valor: string) => void
}

export function Selecao({ rotulo, valor, opcoes, aoMudar }: PropsSelecao) {
  const id = useId()
  return (
    <span className="controle-inline">
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => aoMudar(e.target.value)}>
        {opcoes.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.rotulo}
          </option>
        ))}
      </select>
    </span>
  )
}

/** Um exemplo quebrado não pode apagar o catálogo inteiro. */
class Limite extends Component<{ id: string; children: ReactNode }, { falhou: boolean }> {
  state = { falhou: false }

  static getDerivedStateFromError() {
    return { falhou: true }
  }

  render() {
    if (this.state.falhou) {
      return (
        <div className="estado" data-tipo="erro-exemplo">
          <p className="estado-titulo">Este exemplo não pôde ser renderizado.</p>
          <p className="estado-id">{this.props.id}</p>
        </div>
      )
    }
    return this.props.children
  }
}

export function MostraExemplo({ exemplo }: { exemplo: Exemplo }) {
  const herdado = useContext(ContextoPalco)
  const [largura, setLargura] = useState('herdar')
  const [zoom, setZoom] = useState('herdar')
  const [fundo, setFundo] = useState('herdar')
  const [medida, setMedida] = useState(0)
  const palcoRef = useRef<HTMLDivElement>(null)

  const larguraFinal = largura === 'herdar' ? herdado.largura : largura
  const zoomFinal = zoom === 'herdar' ? herdado.zoom : zoom
  const fundoFinal = fundo === 'herdar' ? herdado.fundo : fundo

  useEffect(() => {
    const palco = palcoRef.current
    if (!palco) return
    // A largura vai por `setProperty` e não por `style={{}}`: quem manda na
    // aparência é o CSS; o React só entrega o número.
    palco.style.setProperty('--palco-largura', larguraFinal)
    palco.style.setProperty('--palco-zoom', zoomFinal)
  }, [larguraFinal, zoomFinal])

  useEffect(() => {
    const palco = palcoRef.current
    if (!palco || typeof ResizeObserver === 'undefined') return
    const observador = new ResizeObserver(([entrada]) =>
      setMedida(Math.round(entrada.contentRect.width)),
    )
    observador.observe(palco)
    return () => observador.disconnect()
  }, [])

  return (
    <section className="pilha" data-espaco="3" aria-labelledby={`ex-${exemplo.id}`}>
      <div className="linha" data-alinhar="entre">
        <h3 id={`ex-${exemplo.id}`}>{exemplo.titulo}</h3>
        <div className="linha" data-espaco="3">
          <Selecao rotulo="Largura" valor={largura} opcoes={LARGURAS} aoMudar={setLargura} />
          <Selecao rotulo="Zoom" valor={zoom} opcoes={ZOOMS} aoMudar={setZoom} />
          <Selecao rotulo="Fundo" valor={fundo} opcoes={FUNDOS} aoMudar={setFundo} />
          <a
            className="botao"
            data-variante="fantasma"
            data-tamanho="sm"
            href={`#/isolado/${encodeURIComponent(exemplo.id)}`}
          >
            Abrir ⧉
          </a>
        </div>
      </div>

      <div className="palco contexto" ref={palcoRef} data-fundo={fundoFinal}>
        <Limite id={exemplo.id}>{exemplo.render()}</Limite>
      </div>

      <p className="palco-regua">
        <span>{exemplo.id}</span>
        <span>{medida} px</span>
      </p>

      <p className="cartao-opcao-descricao medida">{exemplo.nota}</p>
    </section>
  )
}
