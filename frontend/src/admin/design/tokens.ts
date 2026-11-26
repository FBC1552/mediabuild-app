/**
 * Leitura dos tokens em tempo de execução.
 *
 * O catálogo NÃO repete os valores de `index.css`: lê o que o navegador
 * resolveu. Uma matriz escrita à mão envelhece na primeira mudança de token e
 * passa a mentir; esta lista guarda só os NOMES, que são o contrato.
 */
export function valorDoToken(nome: string): string {
  if (typeof window === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim()
}

export type GrupoDeTokens = { titulo: string; tokens: string[] }

export const CORES: GrupoDeTokens[] = [
  { titulo: 'Superfícies', tokens: ['--fundo', '--card', '--borda', '--borda-forte'] },
  { titulo: 'Superfície inversa', tokens: ['--fundo-inverso', '--card-inverso', '--borda-inversa', '--texto-inverso', '--texto-inverso-suave'] },
  { titulo: 'Texto', tokens: ['--texto', '--texto-suave', '--texto-fraco'] },
  { titulo: 'Ação', tokens: ['--acao', '--acao-escura', '--acao-clara', '--acao-borda'] },
  { titulo: 'Sucesso', tokens: ['--ok', '--ok-escura', '--ok-clara', '--ok-borda'] },
  { titulo: 'Erro', tokens: ['--erro', '--erro-escura', '--erro-clara', '--erro-borda'] },
  { titulo: 'Alerta', tokens: ['--alerta', '--alerta-clara', '--alerta-borda'] },
  { titulo: 'Marca (decorativa)', tokens: ['--marca-1', '--marca-2', '--marca-3', '--marca-4'] },
]

export const TIPOGRAFIA = [
  '--tipo-xs',
  '--tipo-sm',
  '--tipo-md',
  '--tipo-base',
  '--tipo-lg',
  '--tipo-xl',
  '--tipo-2xl',
  '--tipo-3xl',
  '--tipo-4xl',
]

export const ESPACAMENTO = Array.from({ length: 12 }, (_, i) => `--esp-${i + 1}`)

export const RAIOS = ['--raio-xs', '--raio-sm', '--raio', '--raio-lg', '--raio-xl', '--raio-pilula']

export const ELEVACOES = ['--sombra-sm', '--sombra', '--sombra-md', '--sombra-lg']

export const DURACOES = [
  '--dur-instantanea',
  '--dur-rapida',
  '--dur-media',
  '--dur-lenta',
  '--dur-giro',
  '--dur-confirmacao',
]

export const CURVAS = ['--curva-padrao', '--curva-entrada', '--curva-saida']

/** Pares que o badge de contraste avalia (frente × fundo). */
export const TEXTOS_AVALIADOS = [
  '--texto',
  '--texto-suave',
  '--texto-fraco',
  '--acao',
  '--erro',
  '--ok',
  '--alerta',
]

export const FUNDOS_AVALIADOS = ['--card', '--fundo']
