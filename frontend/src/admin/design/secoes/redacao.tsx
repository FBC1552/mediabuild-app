import { REGRAS_DE_REDACAO } from '../fixturas'
import type { Exemplo } from '../MostraExemplo'

function Regras() {
  return (
    <table>
      <caption className="rotulo-secao">Redação de interface</caption>
      <thead>
        <tr>
          <th scope="col">Regra</th>
          <th scope="col">Escreva</th>
          <th scope="col">Evite</th>
        </tr>
      </thead>
      <tbody>
        {REGRAS_DE_REDACAO.map((linha) => (
          <tr key={linha.regra}>
            <th scope="row">{linha.regra}</th>
            <td>{linha.sim}</td>
            <td className="estado-id">{linha.nao}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Terminologia() {
  return (
    <dl className="pilha" data-espaco="4">
      <div>
        <dt className="rotulo-secao">Idioma</dt>
        <dd className="cartao-opcao-descricao">
          Rótulos, mensagens e nomes do domínio em português: plataforma, nível, nomenclatura
          final. Traduzir metade do modelo é pior que não traduzir nada.
        </dd>
      </div>
      <div>
        <dt className="rotulo-secao">Rótulos de campo</dt>
        <dd className="cartao-opcao-descricao">
          Nenhum rótulo é escrito no cliente: todos vêm do token do template
          (`templates_taxonomia`). Se um rótulo está errado, o conserto é um UPDATE, não um
          deploy.
        </dd>
      </div>
      <div>
        <dt className="rotulo-secao">Nome do produto</dt>
        <dd className="cartao-opcao-descricao">
          MediaBuild, sempre. o nome de trabalho anterior aparece na spec original e é nome morto (D-001).
        </dd>
      </div>
    </dl>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'redacao-regras',
    titulo: 'Regras de redação',
    nota: 'A coluna "Evite" não é piada interna: cada linha ali já apareceu em alguma tela deste produto ou da spec original.',
    render: () => <Regras />,
  },
  {
    id: 'redacao-terminologia',
    titulo: 'Terminologia',
    nota: 'Consulte antes de inventar um termo novo na interface. Divergência de vocabulário entre tela e banco custa caro na primeira dúvida do analista.',
    render: () => <Terminologia />,
  },
]
