/**
 * Vencedores do Oscar de Melhor Filme. Dado estático, sem rede: a splash não
 * pode depender de disponibilidade de servidor nenhum para ser divertida.
 */
export type FilmePremiado = {
  titulo: string
  ano: number
  direcao: string
}

export const FILMES_PREMIADOS: FilmePremiado[] = [
  { titulo: 'O Poderoso Chefão', ano: 1972, direcao: 'Francis Ford Coppola' },
  { titulo: 'Um Estranho no Ninho', ano: 1975, direcao: 'Miloš Forman' },
  { titulo: 'Annie Hall', ano: 1977, direcao: 'Woody Allen' },
  { titulo: 'Amadeus', ano: 1984, direcao: 'Miloš Forman' },
  { titulo: 'Rain Man', ano: 1988, direcao: 'Barry Levinson' },
  { titulo: 'Os Imperdoáveis', ano: 1992, direcao: 'Clint Eastwood' },
  { titulo: 'A Lista de Schindler', ano: 1993, direcao: 'Steven Spielberg' },
  { titulo: 'Forrest Gump', ano: 1994, direcao: 'Robert Zemeckis' },
  { titulo: 'Titanic', ano: 1997, direcao: 'James Cameron' },
  { titulo: 'Beleza Americana', ano: 1999, direcao: 'Sam Mendes' },
  { titulo: 'Gladiador', ano: 2000, direcao: 'Ridley Scott' },
  { titulo: 'Uma Mente Brilhante', ano: 2001, direcao: 'Ron Howard' },
  { titulo: 'Os Infiltrados', ano: 2006, direcao: 'Martin Scorsese' },
  { titulo: 'Onde os Fracos Não Têm Vez', ano: 2007, direcao: 'Joel e Ethan Coen' },
  { titulo: 'A Rede Social', ano: 2010, direcao: 'David Fincher' },
  { titulo: 'O Artista', ano: 2011, direcao: 'Michel Hazanavicius' },
  { titulo: 'Spotlight', ano: 2015, direcao: 'Tom McCarthy' },
  { titulo: 'Moonlight', ano: 2016, direcao: 'Barry Jenkins' },
  { titulo: 'Parasita', ano: 2019, direcao: 'Bong Joon-ho' },
  { titulo: 'Tudo em Todo Lugar ao Mesmo Tempo', ano: 2022, direcao: 'Daniel Kwan e Daniel Scheinert' },
  { titulo: 'Oppenheimer', ano: 2023, direcao: 'Christopher Nolan' },
]

/**
 * Baralho embaralhado (Fisher-Yates) em vez de sorteio independente:
 * aleatório puro repete o mesmo filme duas vezes seguidas com frequência e
 * o usuário lê isso como bug. O baralho garante ciclo sem repetição, e o
 * embaralhamento do próximo evita repetir a última carta na virada.
 */
export function criarBaralho<T>(itens: T[]): () => T {
  let restante: T[] = []
  let ultimo: T | undefined

  function embaralhar(): T[] {
    const copia = [...itens]
    for (let i = copia.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[copia[i], copia[j]] = [copia[j], copia[i]]
    }
    // A próxima carta é a do fim (o `pop`), então é ela que não pode repetir.
    const fim = copia.length - 1
    if (copia.length > 1 && copia[fim] === ultimo) {
      ;[copia[fim], copia[0]] = [copia[0], copia[fim]]
    }
    return copia
  }

  return () => {
    if (restante.length === 0) restante = embaralhar()
    const carta = restante.pop() as T
    ultimo = carta
    return carta
  }
}
