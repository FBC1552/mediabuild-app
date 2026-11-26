import { useState } from 'react'

import { Botao } from '../../../componentes/ui'
import { NOMENCLATURA_EXEMPLO } from '../fixturas'
import type { Exemplo } from '../MostraExemplo'
import { CURVAS, DURACOES, valorDoToken } from '../tokens'

function Tokens() {
  return (
    <table>
      <caption className="rotulo-secao">Durações e curvas</caption>
      <thead>
        <tr>
          <th scope="col">Token</th>
          <th scope="col">Valor</th>
          <th scope="col">Onde se usa</th>
        </tr>
      </thead>
      <tbody>
        {[...DURACOES, ...CURVAS].map((token) => (
          <tr key={token}>
            <th scope="row">
              <code className="mono">{token}</code>
            </th>
            <td>
              <code className="mono">{valorDoToken(token)}</code>
            </td>
            <td>{USO[token] ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const USO: Record<string, string> = {
  '--dur-instantanea': 'Pressionar botão',
  '--dur-rapida': 'Hover, cor, borda',
  '--dur-media': 'Mudança de estado',
  '--dur-lenta': 'Entrada de conteúdo, sobreposição',
  '--dur-giro': 'Volta completa do spinner',
  '--dur-confirmacao': 'Confirmação efêmera ("Copiado!")',
  '--curva-padrao': 'Padrão',
  '--curva-entrada': 'Conteúdo entrando',
  '--curva-saida': 'Conteúdo saindo',
}

function Entrada() {
  const [visivel, setVisivel] = useState(true)
  return (
    <div className="pilha" data-espaco="5">
      <div className="linha">
        <Botao variante="secundario" tamanho="sm" onClick={() => setVisivel((v) => !v)}>
          Repetir animação
        </Botao>
      </div>
      {visivel && (
        <p className="card surge" data-espaco="3">
          <code className="mono">{NOMENCLATURA_EXEMPLO}</code>
        </p>
      )}
    </div>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'movimento-tokens',
    titulo: 'Durações e curvas',
    nota: 'Duração é decisão, não gosto: acima de ~300 ms a interface fica lenta para quem repete a tarefa quarenta vezes por dia.',
    render: () => <Tokens />,
  },
  {
    id: 'movimento-entrada',
    titulo: 'Entrada de conteúdo',
    nota: 'Vale animar a nomenclatura gerada e a revelação do próximo nível. Não vale animar troca de aba nem hover de linha. Só transform e opacity.',
    render: () => <Entrada />,
  },
]
