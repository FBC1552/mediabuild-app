import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import marcaSimbolo from '../ativos/marca.png'
import { criarBaralho, FILMES_PREMIADOS, type FilmePremiado } from '../dados/filmesPremiados'
import { BarraTopo, RodapeUtilitario } from './cromo'
import { PLATAFORMAS_COM_LOGO } from './icones'
import { CHAVE_ULTIMO_ASSUNTO } from './SeletorDeAssunto'
import { LinkBotao } from './ui'

const CORES = ['--marca-1', '--marca-2', '--marca-3', '--marca-4']
/** Abaixo disso o CSS já esconde a marca móvel; o rAF também não roda. */
const LARGURA_MINIMA = 720
const ALTURA_MINIMA = 560

type Retangulo = { x: number; y: number; largura: number; altura: number }

function usaMovimentoReduzido(): boolean {
  const [reduzido, setReduzido] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  )

  useEffect(() => {
    const consulta = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!consulta) return
    const aoMudar = (evento: MediaQueryListEvent) => setReduzido(evento.matches)
    // Ler uma vez não basta: o usuário troca a preferência com a aba aberta.
    consulta.addEventListener('change', aoMudar)
    setReduzido(consulta.matches)
    return () => consulta.removeEventListener('change', aoMudar)
  }, [])

  return reduzido
}

/**
 * Tela inicial (`#/`).
 *
 * Anatomia: barra de topo fina → palco → rodapé utilitário. Barra e rodapé
 * ficam FORA do palco, e é essa escolha que mantém o movimento correto: o
 * monograma quica dentro do palco e não tem como alcançá-los. Dentro do palco
 * sobra uma parede só, o bloco central do hero — a marca reflete nele e, por
 * geometria (não por z-index), nunca cobre os dois CTAs.
 */
export function Splash() {
  const movimentoReduzido = usaMovimentoReduzido()
  const [pausadoPeloBotao, setPausadoPeloBotao] = useState(false)
  const [filme, setFilme] = useState<FilmePremiado | null>(null)

  const palcoRef = useRef<HTMLDivElement>(null)
  const marcaRef = useRef<HTMLDivElement>(null)
  const blocoRef = useRef<HTMLDivElement>(null)
  const pausaTemporaria = useRef(false)
  const pausadoRef = useRef(false)
  pausadoRef.current = pausadoPeloBotao

  const sortear = useMemo(() => criarBaralho(FILMES_PREMIADOS), [])
  const recomendar = useCallback(() => setFilme(sortear()), [sortear])

  /** Ir direto para o gerador É escolher o assunto — o boot passa a pular a
      splash, exatamente como quando a escolha vem de `#/assunto`. */
  function registrarEscolha() {
    try {
      window.localStorage.setItem(CHAVE_ULTIMO_ASSUNTO, 'taxonomia')
    } catch {
      // localStorage indisponível (modo restrito) só custa a splash de novo.
    }
  }

  // ---- movimento -------------------------------------------------------
  useEffect(() => {
    if (movimentoReduzido) return
    const palco = palcoRef.current
    const marca = marcaRef.current
    const bloco = blocoRef.current
    if (!palco || !marca || !bloco) return

    const estilo = getComputedStyle(document.documentElement)
    const velocidade = Number(estilo.getPropertyValue('--marca-velocidade')) || 90
    const margemZonaMorta = Number.parseFloat(estilo.getPropertyValue('--esp-6')) || 20

    let limites: Retangulo = { x: 0, y: 0, largura: 0, altura: 0 }
    // Uma parede POR controle, mesmo havendo uma só hoje. A lista é o contrato:
    // qualquer controle novo DENTRO do palco entra aqui, e nunca como bounding
    // box da união — a envolvente de dois controles distantes come metade da
    // tela e a marca passa a varrer uma faixa, parecendo travada.
    let paredes: Retangulo[] = []
    let marcaLargura = 0
    let marcaAltura = 0
    let habilitado = false

    let x = 0
    let y = 0
    // Direção inicial com as duas componentes não nulas: só horizontal ou só
    // vertical faz a marca varrer uma faixa e parecer travada.
    let dx = velocidade * 0.78
    let dy = velocidade * 0.62
    let cor = 0
    let quadro = 0
    let ultimo = 0

    function medir() {
      const caixaPalco = palco!.getBoundingClientRect()
      const caixaBloco = bloco!.getBoundingClientRect()
      const caixaMarca = marca!.getBoundingClientRect()
      limites = { x: 0, y: 0, largura: caixaPalco.width, altura: caixaPalco.height }
      marcaLargura = caixaMarca.width
      marcaAltura = caixaMarca.height
      // Coordenadas relativas ao palco, expandidas pela margem de respiro.
      const emParede = (caixa: DOMRect): Retangulo => ({
        x: caixa.left - caixaPalco.left - margemZonaMorta,
        y: caixa.top - caixaPalco.top - margemZonaMorta,
        largura: caixa.width + margemZonaMorta * 2,
        altura: caixa.height + margemZonaMorta * 2,
      })
      paredes = [emParede(caixaBloco)]
      habilitado =
        caixaPalco.width >= LARGURA_MINIMA &&
        caixaPalco.height >= ALTURA_MINIMA &&
        marcaLargura > 0 &&
        marcaAltura > 0
      if (x === 0 && y === 0 && habilitado) {
        x = Math.max(0, limites.largura - marcaLargura - margemZonaMorta)
        y = margemZonaMorta
      }
      x = Math.min(x, Math.max(0, limites.largura - marcaLargura))
      y = Math.min(y, Math.max(0, limites.altura - marcaAltura))
    }

    function trocarCor() {
      let proxima = cor
      while (proxima === cor) proxima = Math.floor(Math.random() * CORES.length)
      cor = proxima
      marca!.style.setProperty('--marca-atual', `var(${CORES[cor]})`)
    }

    function sobrepoe(px: number, py: number, parede: Retangulo) {
      return (
        px < parede.x + parede.largura &&
        px + marcaLargura > parede.x &&
        py < parede.y + parede.altura &&
        py + marcaAltura > parede.y
      )
    }

    function paredeAtingida(px: number, py: number): Retangulo | null {
      for (const parede of paredes) if (sobrepoe(px, py, parede)) return parede
      return null
    }

    function passo(agora: number) {
      quadro = requestAnimationFrame(passo)
      const delta = ultimo ? Math.min((agora - ultimo) / 1000, 0.05) : 0
      ultimo = agora
      if (!habilitado || pausadoRef.current || pausaTemporaria.current || delta === 0) return

      // Delta de tempo, não incremento por quadro: em 144 Hz a marca voaria.
      let proximoX = x + dx * delta
      let proximoY = y + dy * delta
      let bateu = false

      if (proximoX <= 0 || proximoX + marcaLargura >= limites.largura) {
        dx = -dx
        proximoX = Math.max(0, Math.min(proximoX, limites.largura - marcaLargura))
        bateu = true
      }
      if (proximoY <= 0 || proximoY + marcaAltura >= limites.altura) {
        dy = -dy
        proximoY = Math.max(0, Math.min(proximoY, limites.altura - marcaAltura))
        bateu = true
      }

      const parede = paredeAtingida(proximoX, proximoY)
      if (parede) {
        // Reflete no eixo de menor penetração e devolve a marca para fora da
        // parede — é isso que impede o monograma de cobrir a ação primária.
        const porX = Math.min(
          Math.abs(proximoX + marcaLargura - parede.x),
          Math.abs(parede.x + parede.largura - proximoX),
        )
        const porY = Math.min(
          Math.abs(proximoY + marcaAltura - parede.y),
          Math.abs(parede.y + parede.altura - proximoY),
        )
        if (porX < porY) {
          dx = -dx
          proximoX = dx > 0 ? parede.x + parede.largura : parede.x - marcaLargura
        } else {
          dy = -dy
          proximoY = dy > 0 ? parede.y + parede.altura : parede.y - marcaAltura
        }
        // Sair de uma parede não pode empurrar para dentro de outra nem para
        // fora do palco: quem não couber volta para a posição anterior e só
        // inverte a direção — a marca nunca fica presa em cima do controle.
        const dentroDoPalco =
          proximoX >= 0 &&
          proximoY >= 0 &&
          proximoX + marcaLargura <= limites.largura &&
          proximoY + marcaAltura <= limites.altura
        if (!dentroDoPalco || paredeAtingida(proximoX, proximoY)) {
          proximoX = x
          proximoY = y
        }
        bateu = true
      }

      x = proximoX
      y = proximoY
      // translate3d, nunca top/left: top/left força layout a cada quadro.
      marca!.style.transform = `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`
      if (bateu) trocarCor()
    }

    medir()
    trocarCor()
    marca.style.transform = `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`

    const observador = new ResizeObserver(() => medir())
    observador.observe(palco)
    observador.observe(bloco)
    // A marca também: fora da consulta de contêiner ela é `display:none` e
    // mede 0×0, o que desliga o movimento. Sem observá-la, a primeira medida
    // ruim (layout ainda assentando, imagem ainda sem tamanho) congelava a
    // animação para sempre, porque palco e bloco não mudam mais de tamanho.
    observador.observe(marca)

    const aoTrocarVisibilidade = () => {
      pausaTemporaria.current = document.hidden || pausaTemporaria.current
      if (!document.hidden) ultimo = 0
    }
    document.addEventListener('visibilitychange', aoTrocarVisibilidade)
    quadro = requestAnimationFrame(passo)

    return () => {
      cancelAnimationFrame(quadro)
      observador.disconnect()
      document.removeEventListener('visibilitychange', aoTrocarVisibilidade)
    }
  }, [movimentoReduzido])

  // ---- interação com a marca -------------------------------------------
  function pausarERecomendar() {
    pausaTemporaria.current = true
    recomendar()
  }

  function retomar() {
    pausaTemporaria.current = false
  }

  return (
    <div className="casca-marca">
      <BarraTopo />

      <div className="splash" ref={palcoRef} data-estatica={movimentoReduzido || undefined}>
        <h1 className="apenas-leitor" tabIndex={-1} data-foco-rota>
          MediaBuild
        </h1>

        <div className="splash-bloco" ref={blocoRef}>
          {/* O wordmark é o herói: maior peso visual da tela, porque é o
              único elemento que responde "onde eu estou". */}
          <p className="marca marca-logotipo" data-tamanho="hero" aria-hidden="true">
            MDBuilder
          </p>
          <p className="marca-subtitulo medida">
            Nomenclaturas padronizadas para campanhas de mídia paga
          </p>

          {/* Duas ações, hierarquia inequívoca (Krug: qual é a primária tem de
              ser óbvia em 2s). A primária é o caminho de 95% das aberturas. */}
          <div className="hero-acoes">
            <LinkBotao href="#/taxonomia/gerar" tamanho="hero" onClick={registrarEscolha}>
              Gerar nomenclatura
            </LinkBotao>
            <LinkBotao href="#/assunto" variante="secundario" tamanho="hero">
              Escolher assunto
            </LinkBotao>
          </div>

          <div className="card splash-cartao pilha" data-espaco="3">
            <p className="rotulo-secao">Destaques e recomendações</p>
            <p className="destaque-item">
              <a href="#/guia">Guia de uso</a> — os três níveis, o match ID e o que o
              MediaBuild confere na sua URL.
            </p>
            {/* `role="status"` só no slot que muda: anunciar o cartão inteiro a
                cada sorteio repetiria o destaque fixo em toda leitura. */}
            <p className="destaque-item" role="status">
              {filme ? (
                <>
                  Cinema: <strong>{filme.titulo}</strong> ({filme.ano}), direção de{' '}
                  {filme.direcao}.
                </>
              ) : (
                // Altura reservada mesmo vazio: descobrir a marca é brinde, mas
                // a página não pode saltar quando o cartão preencher.
                <span aria-hidden="true">&nbsp;</span>
              )}
            </p>
          </div>

          {/* Prova concreta do que o produto cobre, no lugar de adjetivo. Os
              logos são decorativos: quem nomeia cada item é o texto ao lado —
              logo com `alt` e nome repetido faz o leitor de tela dizer tudo
              duas vezes. */}
          <div className="faixa-plataformas">
            <p className="rotulo-secao" id="rotulo-plataformas">
              Plataformas suportadas
            </p>
            <ul className="faixa-plataformas-lista" aria-labelledby="rotulo-plataformas">
              {PLATAFORMAS_COM_LOGO.map((plataforma) => (
                <li key={plataforma.sigla} className="plataforma-item">
                  <plataforma.Logo tamanho="md" />
                  {plataforma.nome}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Depois do bloco no DOM, de propósito: a ordem de Tab fica
            `Gerar nomenclatura` → `Escolher assunto` → guia → marca. */}
        <div className="splash-marca-movel" ref={marcaRef}>
          <button
            type="button"
            className="marca marca-monograma"
            aria-label="Recomendar um filme premiado"
            onMouseEnter={pausarERecomendar}
            onMouseLeave={retomar}
            onFocus={pausarERecomendar}
            onBlur={retomar}
            onClick={recomendar}
          >
            {/* A imagem é decorativa: quem nomeia o controle é o aria-label do
                <button>. `alt=""` + aria-hidden para o leitor não anunciar duas
                vezes. Dimensões explícitas evitam o salto de layout que faria a
                primeira medida do rAF nascer errada. */}
            <img
              className="marca-simbolo"
              src={marcaSimbolo}
              alt=""
              aria-hidden="true"
              width={256}
              height={256}
              decoding="async"
            />
          </button>
        </div>
      </div>

      <RodapeUtilitario>
        {/* WCAG 2.2.2: o mecanismo de pausa é requisito de conformidade, então
            é visível e permanente. Fora do palco, não precisa virar parede. */}
        {!movimentoReduzido && (
          <button
            type="button"
            className="botao"
            data-variante="fantasma"
            data-tamanho="sm"
            aria-pressed={pausadoPeloBotao}
            onClick={() => setPausadoPeloBotao((p) => !p)}
          >
            {pausadoPeloBotao ? 'Retomar animação' : 'Pausar animação'}
          </button>
        )}
      </RodapeUtilitario>
    </div>
  )
}

export default Splash
