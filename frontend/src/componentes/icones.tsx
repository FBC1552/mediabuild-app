/**
 * MediaBuild · camada de iconografia
 * ---------------------------------------------------------------------------
 * SVG inline, desenhado à mão. Nenhum arquivo de imagem, nenhuma dependência,
 * nenhuma requisição — ícone é código, versionado junto do componente que o usa.
 *
 * Três famílias, com contratos diferentes:
 *
 *   1. Logos de plataforma  — marcas de TERCEIROS, coloridas. A cor sai dos
 *      tokens `--logo-*` de index.css, aplicada por CSS (`data-tinta`), nunca
 *      por atributo de apresentação: `fill="var(--x)"` não resolve em
 *      presentation attribute, e hexadecimal literal em .tsx é proibido aqui.
 *   2. Ícones de nível      — campanha / grupo / anúncio, família de traço.
 *   3. Ícones de interface  — o mínimo que as telas novas pedem.
 *
 * Acessibilidade: TODO ícone é decorativo por padrão (`aria-hidden`,
 * `focusable="false"`), porque quase sempre acompanha um rótulo de texto. Passe
 * `titulo` só quando o ícone for a única fonte da informação — aí ele vira
 * `role="img"` com `<title>` ligado por `aria-labelledby`.
 *
 * Tamanho é CSS: o padrão é `1em` (o ícone acompanha o texto ao lado). Para o
 * ícone que não acompanha texto nenhum, use `tamanho` — escala fechada
 * `--icone-*` de index.css. Nunca width/height fixos no elemento.
 */
import { useId } from 'react'
import type { ReactElement, ReactNode } from 'react'
import type { Nivel } from '../tipos'

export type TamanhoIcone = 'sm' | 'md' | 'lg' | 'xl' | '2xl'

export type PropsIcone = {
  /** Presente = ícone informativo (role="img" + <title>). Ausente = decorativo. */
  titulo?: string
  /** Escala fechada `--icone-*`. Ausente = 1em, acompanhando o texto. */
  tamanho?: TamanhoIcone
  /** Classe extra do consumidor, composta com a classe base. */
  className?: string
}

export type PropsLogo = PropsIcone & {
  /**
   * Monocromático: o logo herda `currentColor` (via `color: inherit` nas
   * peças) e perde os ecos de cor da TikTok.
   *
   * O QUE `mono` GARANTE: que o logo pare de usar a paleta de marca
   * (`--logo-*`) e passe a desenhar com a cor de texto do elemento que o
   * envolve — então ele acompanha tema e estado (ex.: item selecionado)
   * como qualquer ícone do sistema.
   *
   * O QUE `mono` NÃO GARANTE: contraste. `currentColor` só é legível se a
   * cor de texto AMBIENTE já for legível naquela superfície — `mono` não
   * calcula nem verifica isso, só resolve a herança.
   *
   * REGRA: logo em superfície invertida (`--card-inverso` e afins) usa
   * `mono`, e quem o envolve precisa estar com uma cor de texto que já é
   * legível ali (ex. `--texto-inverso` / `--texto-inverso-suave`) — não
   * com `--texto`/`--texto-suave`, pensados para superfície clara. Prova
   * concreta do risco: `--logo-tiktok-tinta` é `#010101`; sem `mono`, o
   * logo colorido da TikTok fica ilegível sobre `--card-inverso`
   * (`#151b2b`) — quase preto sobre quase preto. `mono` resolve a cor,
   * mas só se o texto ao redor já resolveu o contraste.
   */
  mono?: boolean
}

/** Assinatura comum de todo ícone de nível e de interface deste módulo. */
export type ComponenteIcone = (props: PropsIcone) => ReactElement

/** Assinatura comum de todo logo de plataforma. */
export type ComponenteLogo = (props: PropsLogo) => ReactElement

type PropsGlifo = PropsLogo & {
  /** Classe base: `icone` (família de traço) ou `logo-plataforma`. */
  base: string
  /** Identifica a marca no DOM e no DevTools. */
  marca?: string
  /** Só o chevron usa: rotação por CSS, não por segundo desenho. */
  sentido?: string
  children: ReactNode
}

/**
 * Casca comum. Concentra o contrato de acessibilidade num lugar só — é o que
 * impede um ícone novo de nascer sem `aria-hidden` ou sem `focusable`.
 */
function Glifo({ base, marca, sentido, titulo, tamanho, className, mono, children }: PropsGlifo) {
  const idTitulo = useId()
  const decorativo = titulo === undefined
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      className={className ? `${base} ${className}` : base}
      data-marca={marca}
      data-sentido={sentido}
      data-tamanho={tamanho}
      data-mono={mono ? 'true' : undefined}
      role={decorativo ? undefined : 'img'}
      aria-hidden={decorativo ? true : undefined}
      aria-labelledby={decorativo ? undefined : idTitulo}
      focusable="false"
    >
      {!decorativo && <title id={idTitulo}>{titulo}</title>}
      {children}
    </svg>
  )
}

/* ===========================================================================
   1 · Logos de plataforma
   ---------------------------------------------------------------------------
   Marcas reais, redesenhadas de forma simplificada na mesma grade 24×24: o
   traço característico é preservado (o ∞ da Meta, o G quadricolor, a nota com
   deslocamento ciano/rosa, a geometria do Google Marketing Platform) sem cópia
   de asset de terceiro. São marcas de outras empresas — não as trate como
   ilustração do produto nem derive delas cor de estado.
   =========================================================================== */

/** Meta — a fita ∞ contínua, em traço único. */
export function LogoMeta(props: PropsLogo) {
  return (
    <Glifo base="logo-plataforma" marca="META" {...props}>
      <path
        className="logo-parte"
        data-tinta="meta"
        data-forma="traco"
        d="M12 12.4c2-3.4 3.6-5.2 5.6-5.2 2.2 0 3.7 2.2 3.7 5.4s-1.5 5.4-3.7 5.4c-2 0-3.6-1.8-5.6-5.2-2-3.4-3.6-5.2-5.6-5.2-2.2 0-3.7 2.2-3.7 5.4s1.5 5.4 3.7 5.4c2 0 3.6-1.8 5.6-5.2Z"
      />
    </Glifo>
  )
}

/**
 * Google — o G quadricolor: um anel de raio 7 e espessura 4 partido em quatro
 * arcos, mais a barra horizontal azul que fecha a letra. Os vãos de ~4° entre
 * os arcos são o que faz as quatro cores lerem como quatro peças a 16px.
 */
export function LogoGoogle(props: PropsLogo) {
  return (
    <Glifo base="logo-plataforma" marca="GOOGLE" {...props}>
      <path
        className="logo-parte"
        data-tinta="google-vermelho"
        data-forma="anel"
        d="M5.42 9.61A7 7 0 0 1 15.29 5.82"
      />
      <path
        className="logo-parte"
        data-tinta="google-amarelo"
        data-forma="anel"
        d="M7.32 17.2A7 7 0 0 1 5.27 10.07"
      />
      <path
        className="logo-parte"
        data-tinta="google-verde"
        data-forma="anel"
        d="M18.93 12.97A7 7 0 0 1 7.69 17.52"
      />
      <path
        className="logo-parte"
        data-tinta="google-azul"
        data-forma="anel"
        d="M15.71 6.06A7 7 0 0 1 18.96 11.27"
      />
      <rect className="logo-parte" data-tinta="google-azul" x="11.8" y="10" width="9.2" height="4" />
    </Glifo>
  )
}

/** A nota da TikTok: anel + haste + bandeira. Reaproveitada nos três ecos. */
function NotaTikTok({ tinta, eco, deslocamento }: { tinta: string; eco?: boolean; deslocamento?: string }) {
  return (
    <g className={eco ? 'logo-eco' : undefined} transform={deslocamento}>
      <circle
        className="logo-parte"
        data-tinta={tinta}
        data-forma="anel-fino"
        cx="10.2"
        cy="15.4"
        r="4.1"
      />
      <rect className="logo-parte" data-tinta={tinta} x="13.1" y="4" width="3.2" height="11.4" />
      <path
        className="logo-parte"
        data-tinta={tinta}
        d="M16.3 4c.3 2.7 2.1 4.4 4.6 4.6v3.2c-1.7 0-3.3-.5-4.6-1.5z"
      />
    </g>
  )
}

/**
 * TikTok — a nota musical com os dois ecos deslocados. Os ecos são
 * `.logo-eco`: em modo monocromático somem, porque três cópias empilhadas na
 * mesma cor viram um borrão em vez de um glifo.
 */
export function LogoTikTok(props: PropsLogo) {
  return (
    <Glifo base="logo-plataforma" marca="TIKTOK" {...props}>
      <NotaTikTok tinta="tiktok-ciano" eco deslocamento="translate(-1.3 -0.9)" />
      <NotaTikTok tinta="tiktok-rosa" eco deslocamento="translate(1.1 1)" />
      <NotaTikTok tinta="tiktok-tinta" />
    </Glifo>
  )
}

/**
 * DV360 — losango arredondado com a ponta interna, no vocabulário geométrico
 * do Google Marketing Platform. Forma própria, não decalque do ícone oficial.
 */
export function LogoDv360(props: PropsLogo) {
  return (
    <Glifo base="logo-plataforma" marca="DV360" {...props}>
      <path
        className="logo-parte"
        data-tinta="dv360-1"
        d="M10.6 3.6a2 2 0 0 1 2.8 0l7 7a2 2 0 0 1 0 2.8l-7 7a2 2 0 0 1-2.8 0l-7-7a2 2 0 0 1 0-2.8Z"
      />
      <path className="logo-parte" data-tinta="dv360-2" d="M12 6.8 17.2 12 12 17.2Z" />
    </Glifo>
  )
}

/**
 * Reserva para sigla desconhecida. Plataforma nova cadastrada no banco não
 * pode quebrar a tela nem aparecer sem nada: ganha placa neutra com as duas
 * primeiras letras da sigla.
 */
export function LogoGenerico({ sigla = '', ...props }: PropsLogo & { sigla?: string }) {
  const iniciais = sigla.replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || '?'
  return (
    <Glifo base="logo-plataforma" marca="GENERICO" {...props}>
      <rect className="logo-placa" x="1" y="1" width="22" height="22" rx="5" />
      <text className="logo-iniciais" x="12" y="12.6">
        {iniciais}
      </text>
    </Glifo>
  )
}

export type PlataformaComLogo = {
  /** Sigla do seed — é a chave de resolução (`plataformas.sigla`). */
  sigla: string
  nome: string
  Logo: ComponenteLogo
}

/**
 * Plataformas com logo desenhado. A faixa "plataformas suportadas" da home
 * renderiza a partir daqui; a tela Gerar resolve por sigla via
 * `LogoPlataforma`. A ordem é a de reconhecimento no mercado brasileiro.
 */
export const PLATAFORMAS_COM_LOGO: PlataformaComLogo[] = [
  { sigla: 'METAA', nome: 'Meta', Logo: LogoMeta },
  { sigla: 'GOOGLE', nome: 'Google', Logo: LogoGoogle },
  { sigla: 'TIKTOK', nome: 'TikTok', Logo: LogoTikTok },
  { sigla: 'DV360', nome: 'DV360', Logo: LogoDv360 },
]

const LOGO_POR_SIGLA = new Map(PLATAFORMAS_COM_LOGO.map((p) => [p.sigla, p.Logo]))

/** Existe logo desenhado para esta sigla? Útil para decidir layout de lista. */
export function temLogo(sigla: string): boolean {
  return LOGO_POR_SIGLA.has(sigla.trim().toUpperCase())
}

export type PropsLogoPlataforma = PropsLogo & {
  /** `plataformas.sigla` do banco. Sigla desconhecida cai no glifo neutro. */
  sigla: string
}

/**
 * Resolve o logo pela sigla. Nunca lança e nunca devolve nada: sigla
 * desconhecida vira placa com iniciais.
 */
export function LogoPlataforma({ sigla, ...props }: PropsLogoPlataforma) {
  const Logo = LOGO_POR_SIGLA.get(sigla.trim().toUpperCase())
  if (!Logo) return <LogoGenerico sigla={sigla} {...props} />
  return <Logo {...props} />
}

/* ===========================================================================
   2 · Ícones dos três níveis
   ---------------------------------------------------------------------------
   Família: mesma grade 24×24, mesmo peso de traço, mesmo raio de canto. A
   leitura é a da hierarquia — campanha é o alcance, grupo é a subdivisão,
   anúncio é a peça que o público vê. Testar sempre a 16px: é o tamanho da
   árvore da campanha e das listas densas.
   =========================================================================== */

/** Campanha — o megafone: o nível que define alcance e objetivo. */
export function IconeCampanha(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="campanha" {...props}>
      <path d="M8 9.5 16 5v14l-8-4.5H5A1.5 1.5 0 0 1 3.5 13v-2A1.5 1.5 0 0 1 5 9.5z" />
      <path d="M6.6 14.7 7.7 19.6" />
      <path d="M18.6 9.2a4.2 4.2 0 0 1 0 5.6" />
    </Glifo>
  )
}

/** Grupo — duas colunas: a campanha repartida em segmentos irmãos. */
export function IconeGrupo(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="grupo" {...props}>
      <rect x="3.5" y="6.5" width="7.5" height="11" rx="2" />
      <rect x="13" y="6.5" width="7.5" height="11" rx="2" />
    </Glifo>
  )
}

/** Anúncio — a peça criativa: o quadro com a imagem dentro. */
export function IconeAnuncio(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="anuncio" {...props}>
      <rect x="4.5" y="4.5" width="15" height="15" rx="2.5" />
      <circle cx="9.4" cy="9.6" r="1.4" />
      <path d="M5.2 17.9 10 13.1l3.2 3.2 2.4-2.2 2.9 2.8" />
    </Glifo>
  )
}

export const ICONE_POR_NIVEL: Record<Nivel, ComponenteIcone> = {
  CAMPANHA: IconeCampanha,
  GRUPO: IconeGrupo,
  ANUNCIO: IconeAnuncio,
}

export type PropsIconeNivel = PropsIcone & { nivel: Nivel }

/** Mapeador do nível para o ícone. O rótulo continua sendo de `ROTULO_NIVEL`. */
export function IconeNivel({ nivel, ...props }: PropsIconeNivel) {
  const Icone = ICONE_POR_NIVEL[nivel]
  return <Icone {...props} />
}

/* ===========================================================================
   3 · Ícones de interface
   ---------------------------------------------------------------------------
   Só o que as telas novas pedem. Ícone que não tem uso não entra: catálogo
   inflado é dívida, não sistema.
   =========================================================================== */

/** Mais / adicionar. */
export function IconeMais(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="mais" {...props}>
      <path d="M12 5v14M5 12h14" />
    </Glifo>
  )
}

export type PropsChevron = PropsIcone & {
  /** O desenho é sempre para baixo; o sentido é rotação CSS. */
  sentido?: 'baixo' | 'cima' | 'esquerda' | 'direita'
}

/**
 * Chevron de expandir/recolher. O glifo é único e a direção é rotação no CSS —
 * assim a transição entre recolhido e expandido é a mesma peça girando, e não
 * dois desenhos trocando de lugar.
 */
export function IconeChevron({ sentido = 'baixo', ...props }: PropsChevron) {
  return (
    <Glifo base="icone" marca="chevron" sentido={sentido} {...props}>
      <path d="m6.5 9.75 5.5 5.5 5.5-5.5" />
    </Glifo>
  )
}

/** Conta / usuário. */
export function IconeConta(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="conta" {...props}>
      <circle cx="12" cy="8.4" r="3.6" />
      <path d="M4.6 20a7.4 7.4 0 0 1 14.8 0" />
    </Glifo>
  )
}

/** Livro — guia de uso. */
export function IconeGuia(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="guia" {...props}>
      <path d="M6.5 3.5h11a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1h-11A2.5 2.5 0 0 1 4 18V6a2.5 2.5 0 0 1 2.5-2.5Z" />
      <path d="M4 18a2.5 2.5 0 0 1 2.5-2.5h12" />
    </Glifo>
  )
}

/** Copiar — o gesto mais repetido do produto. */
export function IconeCopiar(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="copiar" {...props}>
      <rect x="8.5" y="8.5" width="12" height="12" rx="2.5" />
      <path d="M15.5 8.5V6A2.5 2.5 0 0 0 13 3.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5" />
    </Glifo>
  )
}

/* ===========================================================================
   4 · Desbalanço do plano de mídia (docs/PLANO-DE-MIDIA-UI.md §4.2)
   ---------------------------------------------------------------------------
   Sub-alocado e sobre-alocado precisam de FORMAS diferentes, não da mesma
   seta girada: rotação sozinha falha o requisito de "perceptível sem
   depender só de orientação" para quem tem baixa acuidade visual. Fechado
   ganha um terceiro glifo (check), para não sobrar "ausência de ícone" como
   o único sinal de que fechou.
   =========================================================================== */

/** Fechado — o rateio bate exatamente com o valor do nível acima. */
export function IconeFechado(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="fechado" {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.3 12.3 2.5 2.5 5-5.2" />
    </Glifo>
  )
}

/** Sub-alocado — seta para cima: sobra verba ainda não distribuída. */
export function IconeSubalocado(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="subalocado" {...props}>
      <path d="M12 18.5V6.2" />
      <path d="m7 10.5 5-5 5 5" />
    </Glifo>
  )
}

/**
 * Sobre-alocado — triângulo CHEIO com exclamação: forma distinta (não uma
 * seta girada), porque é o estado mais grave (promete mais mídia do que a
 * verba cobre) e precisa ler como alerta mesmo sem cor. O preenchimento e o
 * "furo" da exclamação são resolvidos em CSS (`estilos/plano.css`), não por
 * atributo `fill=`/`stroke=` inline — presentation attribute perde para
 * `.icone { fill: none; stroke: currentColor }` na cascata.
 */
export function IconeSobrealocado(props: PropsIcone) {
  return (
    <Glifo base="icone" marca="sobrealocado" {...props}>
      <path className="icone-desbalanco-corpo" d="M12 4.2 21 19.5H3Z" />
      <path className="icone-desbalanco-furo" d="M12 10.2v4" />
      <circle className="icone-desbalanco-furo" cx="12" cy="16.6" r="0.9" />
    </Glifo>
  )
}
