/**
 * Contraste calculado (WCAG 2.x, relação de luminância relativa).
 *
 * Trinta linhas de matemática local transformam a vitrine em ferramenta: o
 * catálogo passa a reprovar o próprio design system em vez de ilustrá-lo.
 */
export type Veredito = 'AA' | 'AA (texto grande)' | 'Falha'

function canal(valor: number): number {
  const v = valor / 255
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
}

/** Aceita `#rgb`, `#rrggbb` e `rgb(r g b)` / `rgb(r, g, b)`. */
export function paraRgb(cor: string): [number, number, number] | null {
  const limpa = cor.trim()
  if (limpa.startsWith('#')) {
    const hex =
      limpa.length === 4
        ? limpa
            .slice(1)
            .split('')
            .map((c) => c + c)
            .join('')
        : limpa.slice(1)
    if (hex.length < 6) return null
    return [
      Number.parseInt(hex.slice(0, 2), 16),
      Number.parseInt(hex.slice(2, 4), 16),
      Number.parseInt(hex.slice(4, 6), 16),
    ]
  }
  const numeros = limpa.match(/-?\d+(\.\d+)?/g)
  if (!numeros || numeros.length < 3) return null
  return [Number(numeros[0]), Number(numeros[1]), Number(numeros[2])]
}

export function luminancia(cor: string): number | null {
  const rgb = paraRgb(cor)
  if (!rgb) return null
  const [r, g, b] = rgb.map(canal)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function razaoDeContraste(frente: string, fundo: string): number | null {
  const a = luminancia(frente)
  const b = luminancia(fundo)
  if (a === null || b === null) return null
  const [claro, escuro] = a > b ? [a, b] : [b, a]
  return (claro + 0.05) / (escuro + 0.05)
}

export function classificar(razao: number): Veredito {
  if (razao >= 4.5) return 'AA'
  if (razao >= 3) return 'AA (texto grande)'
  return 'Falha'
}
