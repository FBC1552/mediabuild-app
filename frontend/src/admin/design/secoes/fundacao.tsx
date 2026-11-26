import { Fragment, useEffect, useRef, useState } from 'react'

import { AlternadorTema } from '../../../componentes/AlternadorTema'
import { classificar, razaoDeContraste } from '../contraste'
import type { Exemplo } from '../MostraExemplo'
import {
  CORES,
  ELEVACOES,
  ESPACAMENTO,
  FUNDOS_AVALIADOS,
  RAIOS,
  TEXTOS_AVALIADOS,
  TIPOGRAFIA,
  valorDoToken,
} from '../tokens'

function Amostras() {
  return (
    <div className="pilha" data-espaco="7">
      {CORES.map((grupo) => (
        <div key={grupo.titulo} className="pilha" data-espaco="3">
          <p className="rotulo-secao">{grupo.titulo}</p>
          <div className="grade" data-base="estreita">
            {grupo.tokens.map((token) => (
              <div key={token} className="amostra">
                <span className="amostra-cor" ref={pintar(token)} />
                <code className="mono">{token}</code>
                <code className="mono">{valorDoToken(token) || '—'}</code>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Ref callback: a cor entra por `setProperty`, não por `style={{}}`. */
function pintar(token: string) {
  return (el: HTMLElement | null) => {
    el?.style.setProperty('background', `var(${token})`)
  }
}

function TabelaDeContraste() {
  return (
    <table>
      <caption className="rotulo-secao">Contraste calculado (WCAG 1.4.3)</caption>
      <thead>
        <tr>
          <th scope="col">Cor de texto</th>
          {FUNDOS_AVALIADOS.map((fundo) => (
            <th key={fundo} scope="col">
              {fundo}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {TEXTOS_AVALIADOS.map((frente) => (
          <tr key={frente}>
            <th scope="row">
              <code className="mono">{frente}</code>
            </th>
            {FUNDOS_AVALIADOS.map((fundo) => {
              const razao = razaoDeContraste(valorDoToken(frente), valorDoToken(fundo))
              if (razao === null) {
                return (
                  <td key={fundo}>
                    <span className="selo">sem valor</span>
                  </td>
                )
              }
              const veredito = classificar(razao)
              return (
                <td key={fundo}>
                  <span
                    className="selo"
                    data-variante={
                      veredito === 'AA' ? 'ok' : veredito === 'Falha' ? 'erro' : 'alerta'
                    }
                  >
                    {razao.toFixed(2)}:1 · {veredito}
                  </span>
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Tipografia() {
  return (
    <div className="pilha" data-espaco="4">
      {TIPOGRAFIA.map((token) => (
        <div key={token} className="linha" data-alinhar="base">
          <code className="mono">{token}</code>
          <code className="mono">{valorDoToken(token)}</code>
          <span ref={(el) => el?.style.setProperty('font-size', `var(${token})`)}>
            Nomenclatura padronizada
          </span>
        </div>
      ))}
    </div>
  )
}

function Espacamento() {
  return (
    <div className="pilha" data-espaco="2">
      {ESPACAMENTO.map((token) => (
        <div key={token} className="linha" data-espaco="3" data-alinhar="base">
          <code className="mono">{token}</code>
          <code className="mono">{valorDoToken(token)}</code>
          <span
            className="amostra-caixa"
            ref={(el) => {
              el?.style.setProperty('inline-size', `var(${token})`)
              el?.style.setProperty('block-size', 'var(--esp-4)')
            }}
          />
        </div>
      ))}
    </div>
  )
}

function Geometria() {
  return (
    <div className="grade" data-base="estreita">
      {RAIOS.map((token) => (
        <div key={token} className="amostra">
          <span
            className="amostra-cor amostra-caixa"
            ref={(el) => el?.style.setProperty('border-radius', `var(${token})`)}
          />
          <code className="mono">{token}</code>
        </div>
      ))}
    </div>
  )
}

function Elevacao() {
  return (
    <div className="grade" data-base="estreita">
      {ELEVACOES.map((token) => (
        <div key={token} className="amostra">
          <span
            className="amostra-cor"
            ref={(el) => {
              el?.style.setProperty('box-shadow', `var(${token})`)
              el?.style.setProperty('background', 'var(--card)')
            }}
          />
          <code className="mono">{token}</code>
        </div>
      ))}
    </div>
  )
}

/* ===========================================================================
   Tema — as duas paletas semânticas, lado a lado
   ---------------------------------------------------------------------------
   `[data-tema]` num elemento qualquer troca os tokens da subárvore inteira
   (ver o bloco 2 de index.css). É esse detalhe que permite ao catálogo mostrar
   os dois temas SIMULTANEAMENTE, em vez de pedir que a pessoa alterne e
   confie na memória para comparar.
   =========================================================================== */

const SEMANTICOS: { titulo: string; tokens: string[] }[] = [
  { titulo: 'Superfícies', tokens: ['--fundo', '--card', '--borda', '--borda-forte'] },
  {
    titulo: 'Texto',
    tokens: ['--texto', '--texto-suave', '--texto-fraco', '--texto-em-preenchimento'],
  },
  { titulo: 'Ação', tokens: ['--acao', '--acao-escura', '--acao-clara', '--acao-borda'] },
  { titulo: 'Sucesso', tokens: ['--ok', '--ok-escura', '--ok-clara', '--ok-borda'] },
  { titulo: 'Erro', tokens: ['--erro', '--erro-escura', '--erro-clara', '--erro-borda'] },
  { titulo: 'Alerta', tokens: ['--alerta', '--alerta-clara', '--alerta-borda'] },
  { titulo: 'Neutro e desabilitado', tokens: ['--neutro-clara', '--neutro-borda', '--desabilitado-fundo', '--desabilitado-texto'] },
  {
    titulo: 'Superfície de marca (existe nos dois temas)',
    tokens: ['--fundo-inverso', '--card-inverso', '--borda-inversa', '--texto-inverso', '--texto-inverso-suave'],
  },
  { titulo: 'Marca (decorativa)', tokens: ['--marca-1', '--marca-2', '--marca-3', '--marca-4'] },
]

const TODOS_SEMANTICOS = SEMANTICOS.flatMap((grupo) => grupo.tokens)

/**
 * Lê os tokens JÁ RESOLVIDOS dentro de uma subárvore temada.
 *
 * `valorDoToken` de `../tokens` lê do `<html>` e por isso só enxerga o tema
 * ativo. Aqui o alvo é um nó específico, que é o que torna a comparação
 * possível — e continua sendo leitura do que o navegador calculou, nunca uma
 * tabela escrita à mão que envelhece na primeira mudança de token.
 */
function useTokensDoNo(tokens: string[]) {
  const ref = useRef<HTMLDivElement>(null)
  const [valores, setValores] = useState<Record<string, string>>({})

  useEffect(() => {
    const no = ref.current
    if (!no || typeof window === 'undefined') return
    const estilo = getComputedStyle(no)
    const lidos: Record<string, string> = {}
    for (const token of tokens) lidos[token] = estilo.getPropertyValue(token).trim()
    setValores(lidos)
  }, [tokens])

  return { ref, valores }
}

function ColunaDeTema({ tema }: { tema: 'claro' | 'escuro' }) {
  const { ref, valores } = useTokensDoNo(TODOS_SEMANTICOS)

  return (
    <div className="superficie-tema pilha" data-espaco="6" data-tema={tema} ref={ref}>
      <p className="rotulo-secao">Tema {tema}</p>
      {SEMANTICOS.map((grupo) => (
        <div key={grupo.titulo} className="pilha" data-espaco="2">
          <p className="texto-auxiliar">{grupo.titulo}</p>
          <div className="grade" data-base="estreita">
            {grupo.tokens.map((token) => (
              <div key={token} className="amostra">
                <span className="amostra-cor" ref={pintar(token)} />
                <code className="mono">{token}</code>
                <code className="mono">{valores[token] || '—'}</code>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Pares que precisam passar nos DOIS temas, com o mínimo exigido por cada um.
 * 4.5 é texto normal (WCAG 1.4.3); 3.0 é borda de controle e anel de foco
 * (1.4.11). Um "Falha" aqui é bug de produto, não de catálogo.
 */
const PARES_CRITICOS: { frente: string; fundo: string; minimo: number; papel: string }[] = [
  { frente: '--texto', fundo: '--fundo', minimo: 4.5, papel: 'corpo na página' },
  { frente: '--texto', fundo: '--card', minimo: 4.5, papel: 'corpo no cartão' },
  { frente: '--texto-suave', fundo: '--card', minimo: 4.5, papel: 'rótulo de campo' },
  { frente: '--texto-fraco', fundo: '--fundo', minimo: 4.5, papel: 'anexo de rótulo' },
  { frente: '--acao', fundo: '--card', minimo: 4.5, papel: 'link e ícone de ação' },
  { frente: '--acao', fundo: '--card', minimo: 3, papel: 'anel de foco (1.4.11)' },
  { frente: '--acao-escura', fundo: '--acao-clara', minimo: 4.5, papel: 'selo e aba ativa' },
  { frente: '--texto-em-preenchimento', fundo: '--acao', minimo: 4.5, papel: 'rótulo do botão primário' },
  { frente: '--texto-em-preenchimento', fundo: '--erro', minimo: 4.5, papel: 'rótulo do botão de perigo' },
  { frente: '--borda-forte', fundo: '--card', minimo: 3, papel: 'borda de input (1.4.11)' },
  { frente: '--erro', fundo: '--card', minimo: 4.5, papel: 'texto de erro' },
  { frente: '--erro-escura', fundo: '--erro-clara', minimo: 4.5, papel: 'laudo de erro' },
  { frente: '--ok-escura', fundo: '--ok-clara', minimo: 4.5, papel: 'selo de sucesso' },
  { frente: '--alerta', fundo: '--alerta-clara', minimo: 4.5, papel: 'laudo de alerta' },
  { frente: '--desabilitado-texto', fundo: '--desabilitado-fundo', minimo: 4.5, papel: 'rótulo desabilitado' },
  { frente: '--texto-inverso', fundo: '--card-inverso', minimo: 4.5, papel: 'nomenclatura no preview' },
  { frente: '--texto-inverso-suave', fundo: '--card-inverso', minimo: 4.5, papel: 'contador do preview' },
  { frente: '--marca-1', fundo: '--fundo', minimo: 3, papel: 'marca decorativa' },
  { frente: '--marca-2', fundo: '--fundo', minimo: 3, papel: 'marca decorativa' },
  { frente: '--marca-3', fundo: '--fundo', minimo: 3, papel: 'marca decorativa' },
  { frente: '--marca-4', fundo: '--fundo', minimo: 3, papel: 'marca decorativa' },
]

const TOKENS_DOS_PARES = Array.from(
  new Set(PARES_CRITICOS.flatMap((par) => [par.frente, par.fundo])),
)

function ContrasteDoTema({ tema }: { tema: 'claro' | 'escuro' }) {
  const { ref, valores } = useTokensDoNo(TOKENS_DOS_PARES)

  return (
    <div data-tema={tema} ref={ref}>
      <div className="tabela-rolagem">
        <table className="tabela">
          <caption className="rotulo-secao">Tema {tema}</caption>
          <thead>
            <tr>
              <th className="tabela-celula" scope="col">
                Par
              </th>
              <th className="tabela-celula" scope="col">
                Papel
              </th>
              <th className="tabela-celula" scope="col">
                Mínimo
              </th>
              <th className="tabela-celula" scope="col">
                Medido
              </th>
            </tr>
          </thead>
          <tbody>
            {PARES_CRITICOS.map((par) => {
              const razao = razaoDeContraste(valores[par.frente], valores[par.fundo])
              const passa = razao !== null && razao >= par.minimo
              return (
                <tr key={`${par.frente}|${par.fundo}|${par.minimo}`}>
                  <th className="tabela-celula" scope="row">
                    <code className="mono">
                      {par.frente} / {par.fundo}
                    </code>
                  </th>
                  <td className="tabela-celula">{par.papel}</td>
                  <td className="tabela-celula">{par.minimo.toFixed(1)}:1</td>
                  <td className="tabela-celula">
                    {razao === null ? (
                      <span className="selo">sem valor</span>
                    ) : (
                      <span className="selo" data-variante={passa ? 'ok' : 'erro'}>
                        {razao.toFixed(2)}:1 · {passa ? 'passa' : 'FALHA'}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DoisTemas() {
  return (
    <div className="pilha" data-espaco="6">
      <AlternadorTema rotulo="Tema do produto" />
      <div className="grade" data-base="larga">
        <ColunaDeTema tema="claro" />
        <ColunaDeTema tema="escuro" />
      </div>
    </div>
  )
}

function ContrasteDosDoisTemas() {
  return (
    <div className="pilha" data-espaco="7">
      <ContrasteDoTema tema="claro" />
      <ContrasteDoTema tema="escuro" />
    </div>
  )
}

/* ===========================================================================
   Escala fluida
   =========================================================================== */

const FLUIDOS = [
  { token: '--tipo-xs', faixa: '11,5 → 13px' },
  { token: '--tipo-sm', faixa: '12,5 → 14px' },
  { token: '--tipo-md', faixa: '13 → 15px' },
  { token: '--tipo-base', faixa: '14 → 16,5px' },
  { token: '--tipo-lg', faixa: '15 → 18px' },
  { token: '--tipo-xl', faixa: '17 → 21px' },
  { token: '--tipo-2xl', faixa: '22 → 30px' },
  { token: '--tipo-3xl', faixa: '28 → 42px' },
  { token: '--tipo-4xl', faixa: '38 → 60px' },
]

/**
 * Mede o tamanho RESOLVIDO dentro do palco.
 *
 * É o ponto inteiro do exemplo: a interpolação é por `cqi`, então o número
 * muda quando a largura do palco muda — e é isso que o controle [Largura ▾]
 * do catálogo demonstra. Com `vw`, esta coluna mostraria o mesmo número em
 * todas as larguras de palco e o catálogo estaria mentindo.
 */
function EscalaFluida() {
  const ref = useRef<HTMLDivElement>(null)
  const [medidas, setMedidas] = useState<Record<string, string>>({})

  useEffect(() => {
    const no = ref.current
    if (!no || typeof window === 'undefined') return

    const medir = () => {
      const lidas: Record<string, string> = {}
      for (const { token } of FLUIDOS) {
        const alvo = no.querySelector<HTMLElement>(`[data-token="${token}"]`)
        if (alvo) lidas[token] = getComputedStyle(alvo).fontSize
      }
      setMedidas(lidas)
    }

    medir()
    if (typeof ResizeObserver === 'undefined') return
    const observador = new ResizeObserver(medir)
    observador.observe(no)
    return () => observador.disconnect()
  }, [])

  return (
    <div className="pilha" data-espaco="4" ref={ref}>
      {FLUIDOS.map(({ token, faixa }) => (
        <div key={token} className="pilha" data-espaco="1">
          <div className="linha" data-espaco="3" data-alinhar="base">
            <code className="mono">{token}</code>
            <code className="mono">{faixa}</code>
            <code className="mono">{medidas[token] ? `resolvido: ${medidas[token]}` : ''}</code>
          </div>
          <span
            data-token={token}
            ref={(el) => el?.style.setProperty('font-size', `var(${token})`)}
          >
            Nomenclatura padronizada
          </span>
        </div>
      ))}
    </div>
  )
}

const LARGURAS_DOCUMENTADAS = [
  { token: '--largura-leitura', papel: 'texto corrido (.medida)' },
  { token: '--largura-leitura-curta', papel: 'estado vazio, cartão da splash (.medida-curta)' },
  { token: '--largura-estreita', papel: 'casca de foco único (.pagina[data-largura=estreita])' },
  { token: '--largura-conteudo', papel: 'casca padrão (.pagina)' },
  { token: '--largura-densa', papel: 'casca de tabela (.pagina[data-largura=densa])' },
]

function LarguraseEspacos() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="pilha" data-espaco="2">
        <p className="rotulo-secao">Larguras</p>
        {/* `.lista-definicao` é um grid de duas colunas: dt e dd entram
            diretos, sem wrapper, senão a grade perde o alinhamento. */}
        <dl className="lista-definicao">
          {LARGURAS_DOCUMENTADAS.map(({ token, papel }) => (
            <Fragment key={token}>
              <dt>
                <code className="mono">{token}</code>
              </dt>
              <dd>
                <code className="mono">{valorDoToken(token) || '—'}</code> · {papel}
              </dd>
            </Fragment>
          ))}
        </dl>
      </div>
      <div className="pilha" data-espaco="2">
        <p className="rotulo-secao">Espaçamento fluido (degraus 5 a 12)</p>
        <div className="pilha" data-espaco="2">
          {ESPACAMENTO.slice(4).map((token) => (
            <div key={token} className="linha" data-espaco="3" data-alinhar="base">
              <code className="mono">{token}</code>
              <span
                className="amostra-caixa"
                ref={(el) => {
                  el?.style.setProperty('inline-size', `var(${token})`)
                  el?.style.setProperty('block-size', 'var(--esp-4)')
                }}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'fundacao-tema',
    titulo: 'Tema claro e escuro — a camada semântica inteira',
    nota: 'A paleta crua (--paleta-*) não aparece aqui de propósito: ela não é pública. Só estes papéis são referenciáveis, e é a lista inteira deles que o tema escuro reescreve — por isso nenhum componente precisou saber que o tema escuro existe. Repare em --*-escura: no claro é a variante escurecida, no escuro é a clareada. O papel ("um degrau mais forte") é que é estável; a direção não.',
    render: () => <DoisTemas />,
  },
  {
    id: 'fundacao-contraste-temas',
    titulo: 'Contraste AA nos dois temas',
    nota: 'Cada linha é um par que EXISTE na tela, com o mínimo que a regra exige (4.5 para texto, 3.0 para borda de controle e anel de foco). Os valores saem de getComputedStyle dentro de uma subárvore [data-tema], não de tabela escrita à mão — mudar um token em index.css muda esta tabela. Um "FALHA" é bug de produto.',
    render: () => <ContrasteDosDoisTemas />,
  },
  {
    id: 'fundacao-fluida',
    titulo: 'Escala tipográfica fluida',
    nota: 'Troque a Largura do palco e veja a coluna "resolvido" mudar: a interpolação é por cqi (unidade de contêiner), não por vw. É a mesma razão que proíbe @media neste projeto — com vw, o palco de 360px mostraria o tamanho do desktop e este exemplo seria uma ilustração bonita e falsa. Piso e teto são em rem, então o zoom de texto do navegador continua funcionando.',
    render: () => <EscalaFluida />,
  },
  {
    id: 'fundacao-larguras',
    titulo: 'Larguras e espaçamento fluido',
    nota: 'Duas medidas de leitura (em ch, acompanham a fonte) e três de casca. Todas crescem com a tela e param: esticar até a borda de um monitor ultrawide não é aproveitar a tela, é fazer o olho perder o começo da próxima linha. O espaçamento interpola pela mesma unidade da tipografia, para a densidade acompanhar o tamanho da fonte.',
    render: () => <LarguraseEspacos />,
  },
  {
    id: 'fundacao-contraste',
    titulo: 'Contraste calculado por par de tokens',
    nota: 'Ferramenta, não vitrine: os valores saem de getComputedStyle, então mudar um token em index.css muda esta tabela. Um "Falha" aqui é bug de produto, não de catálogo.',
    render: () => <TabelaDeContraste />,
  },
  {
    id: 'fundacao-cor',
    titulo: 'Paleta',
    nota: 'Cores de estado (--erro/--ok/--alerta) nunca são decoração; a paleta --marca-* existe justamente para o enfeite da splash não corroer o significado delas.',
    render: () => <Amostras />,
  },
  {
    id: 'fundacao-tipografia',
    titulo: 'Escala tipográfica',
    nota: 'Escala fechada. Se um tamanho novo parecer necessário, o problema costuma ser hierarquia, não escala.',
    render: () => <Tipografia />,
  },
  {
    id: 'fundacao-espacamento',
    titulo: 'Escala de espaçamento',
    nota: 'Em px de propósito: espaçamento estrutural não deve escalar com o font-size do usuário, senão a página desmonta em zoom de texto. Os degraus 5 a 12 são fluidos por LARGURA DE CONTÊINER (não por font-size), que é o que faz a densidade acompanhar a tela; 1 a 4 ficam fixos, porque são gaps de dentro de controle e precisam bater.',
    render: () => <Espacamento />,
  },
  {
    id: 'fundacao-raio',
    titulo: 'Raio',
    nota: 'Raio maior = superfície mais "cartão"; controles ficam em --raio-sm para não parecerem pílulas.',
    render: () => <Geometria />,
  },
  {
    id: 'fundacao-elevacao',
    titulo: 'Elevação',
    nota: 'Elevação comunica camada, não importância. Só sobreposição real sobe de nível.',
    render: () => <Elevacao />,
  },
]
