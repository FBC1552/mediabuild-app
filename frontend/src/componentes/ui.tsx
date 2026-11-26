/**
 * Primitivas de interface. Toda a aparência mora no CSS (`estilos/*.css`);
 * aqui só se decide qual classe e quais `data-*` vão para o DOM.
 *
 * Nenhuma delas conhece a API nem o domínio — por isso o catálogo pode
 * importá-las sem violar a fronteira de `src/admin/**`.
 */
import { useEffect, useState } from 'react'
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'

type VarianteBotao = 'primario' | 'secundario' | 'fantasma' | 'perigo'
/** `hero` é a métrica do CTA de abertura (altura, folga e tipo maiores),
 * independente de variante — combine com `variante="secundario"` para a
 * ação de mesma métrica e menos peso ao lado da primária. */
type TamanhoBotao = 'sm' | 'md' | 'lg' | 'hero'

type PropsBotao = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className'> & {
  variante?: VarianteBotao
  tamanho?: TamanhoBotao
  carregando?: boolean
  children: ReactNode
}

export function Botao({
  variante = 'primario',
  tamanho = 'md',
  carregando = false,
  children,
  type = 'button',
  ...resto
}: PropsBotao) {
  return (
    <button
      {...resto}
      type={type}
      className="botao"
      data-variante={variante === 'primario' ? undefined : variante}
      data-tamanho={tamanho === 'md' ? undefined : tamanho}
      data-carregando={carregando || undefined}
      aria-busy={carregando || undefined}
    >
      {/* O rótulo continua no fluxo mesmo carregando: some para o olho, não
          para o layout, e o botão não encolhe sob o ponteiro. */}
      <span className="botao-rotulo">{children}</span>
      {carregando && (
        <span className="botao-giro" aria-hidden="true">
          <Giro />
        </span>
      )}
    </button>
  )
}

type PropsLinkBotao = AnchorHTMLAttributes<HTMLAnchorElement> & {
  variante?: VarianteBotao
  tamanho?: TamanhoBotao
  children: ReactNode
}

export function LinkBotao({
  variante = 'primario',
  tamanho = 'md',
  children,
  ...resto
}: PropsLinkBotao) {
  return (
    <a
      {...resto}
      className="botao"
      data-variante={variante === 'primario' ? undefined : variante}
      data-tamanho={tamanho === 'md' ? undefined : tamanho}
    >
      <span className="botao-rotulo">{children}</span>
    </a>
  )
}

type PropsBotaoCopiar = {
  texto: string
  /** Rótulo em repouso. O de confirmação é sempre `Copiado`. */
  rotulo?: string
  variante?: VarianteBotao
  tamanho?: TamanhoBotao
}

/**
 * Copiar + confirmação temporária. Existia inline no `Preview`; virou
 * primitiva quando o validador de UTM passou a precisar do mesmo gesto para
 * a `url_sugerida`.
 *
 * A confirmação também sai por live region: sem ela, quem usa leitor de tela
 * aciona o botão e não recebe nada de volta.
 */
export function BotaoCopiar({
  texto,
  rotulo = 'Copiar',
  variante = 'secundario',
  tamanho = 'md',
}: PropsBotaoCopiar) {
  const [copiado, setCopiado] = useState(false)

  useEffect(() => {
    if (!copiado) return
    const timer = setTimeout(() => setCopiado(false), 1600)
    return () => clearTimeout(timer)
  }, [copiado])

  return (
    <>
      <Botao
        variante={variante}
        tamanho={tamanho}
        onClick={async () => {
          await navigator.clipboard.writeText(texto)
          setCopiado(true)
        }}
      >
        {copiado ? 'Copiado' : rotulo}
      </Botao>
      <span className="apenas-leitor" role="status" aria-live="polite">
        {copiado ? 'Copiado para a área de transferência.' : ''}
      </span>
    </>
  )
}

type PropsCartao = {
  titulo: string
  descricao: string
  selo?: string
  /** Com `href` vira link de verdade; sem, vira botão `aria-disabled`. */
  href?: string
  aoAtivar?: () => void
}

export function CartaoOpcao({ titulo, descricao, selo, href, aoAtivar }: PropsCartao) {
  const miolo = (
    <>
      <span className="cartao-opcao-titulo">{titulo}</span>
      {selo && <Selo>{selo}</Selo>}
      <span className="cartao-opcao-descricao">{descricao}</span>
    </>
  )

  if (href) {
    return (
      <a className="cartao-opcao" href={href} onClick={aoAtivar}>
        {miolo}
      </a>
    )
  }

  // `aria-disabled`, não `disabled` nativo: o item continua alcançável por
  // Tab, então o usuário de teclado descobre que a opção existe.
  return (
    <button type="button" className="cartao-opcao" aria-disabled="true">
      {miolo}
    </button>
  )
}

type PropsSelo = {
  variante?: 'neutro' | 'acao' | 'ok' | 'erro' | 'alerta'
  children: ReactNode
}

export function Selo({ variante = 'neutro', children }: PropsSelo) {
  return (
    <span className="selo" data-variante={variante === 'neutro' ? undefined : variante}>
      {children}
    </span>
  )
}

type PropsEsqueleto = {
  forma?: 'texto' | 'titulo' | 'controle' | 'cartao'
  final?: boolean
}

/** `data-movimento="essencial"` mantém a animação sob prefers-reduced-motion. */
export function Esqueleto({ forma = 'texto', final = false }: PropsEsqueleto) {
  return (
    <span
      className="esqueleto"
      data-forma={forma}
      data-final={final || undefined}
      data-movimento="essencial"
      aria-hidden="true"
    />
  )
}

export function Giro({ tamanho = 'sm' }: { tamanho?: 'sm' | 'lg' }) {
  return (
    <span
      className="giro"
      data-tamanho={tamanho === 'lg' ? 'lg' : undefined}
      data-movimento="essencial"
      aria-hidden="true"
    />
  )
}

type PropsEstado = {
  tipo: 'vazio' | 'sem-resultado' | 'erro' | 'erro-exemplo' | 'rota'
  titulo: string
  texto?: string
  identificador?: string
  /** `h1` nas telas de rota, onde o título do estado É o título da tela. */
  tituloComo?: 'p' | 'h1'
  children?: ReactNode
}

export function Estado({
  tipo,
  titulo,
  texto,
  identificador,
  tituloComo = 'p',
  children,
}: PropsEstado) {
  const Titulo = tituloComo
  return (
    <div className="estado" data-tipo={tipo} role={tipo === 'erro' ? 'alert' : undefined}>
      <Titulo className="estado-titulo" tabIndex={tituloComo === 'h1' ? -1 : undefined} data-foco-rota={tituloComo === 'h1' || undefined}>
        {titulo}
      </Titulo>
      {texto && <p className="estado-texto">{texto}</p>}
      {identificador && <p className="estado-id">{identificador}</p>}
      {children}
    </div>
  )
}
