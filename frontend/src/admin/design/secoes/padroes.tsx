import { Botao, Selo } from '../../../componentes/ui'
import { LINHAS_HISTORICO, TERMOS_DICIONARIO } from '../fixturas'
import type { Exemplo } from '../MostraExemplo'

function Cabecalho() {
  return (
    <div className="pilha" data-espaco="6">
      <header className="pilha" data-espaco="1">
        <h1 className="titulo-tela">MediaBuild</h1>
        <p className="marca-subtitulo">
          Nomenclaturas padronizadas para campanhas de mídia paga
        </p>
      </header>
      <nav className="abas" role="tablist" aria-label="Exemplo de abas">
        <button type="button" role="tab" className="aba" aria-selected="true" tabIndex={0}>
          Gerar
        </button>
        <button type="button" role="tab" className="aba" aria-selected="false" tabIndex={-1}>
          Dicionário
        </button>
        <button type="button" role="tab" className="aba" aria-selected="false" tabIndex={-1}>
          Histórico
        </button>
      </nav>
    </div>
  )
}

function Grade() {
  return (
    <div className="grade">
      {['Campanha', 'Grupo', 'Anúncio'].map((nivel) => (
        <div key={nivel} className="card pilha" data-espaco="3">
          <p className="rotulo-secao">{nivel}</p>
          <p className="cartao-opcao-descricao">
            Colunas por espaço disponível, sem ponto de quebra: dentro de um palco de 360 px a
            grade vira uma coluna sozinha.
          </p>
        </div>
      ))}
    </div>
  )
}

function Tabela() {
  return (
    <table>
      <caption className="rotulo-secao">Histórico (dados de exemplo)</caption>
      <thead>
        <tr>
          <th scope="col">Match ID</th>
          <th scope="col">Nomenclatura</th>
          <th scope="col">Plataforma</th>
          <th scope="col">Campanha</th>
        </tr>
      </thead>
      <tbody>
        {LINHAS_HISTORICO.map((linha) => (
          <tr key={linha.match_id}>
            <td>
              <code className="mono">{linha.match_id}</code>
            </td>
            <td>
              <code className="mono">{linha.nomenclatura_final}</code>{' '}
              <Selo>{linha.caracteres} caracteres</Selo>
            </td>
            <td>{linha.plataforma}</td>
            <td>{linha.campanha}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function BarraDeFiltros() {
  return (
    <div className="linha">
      <span className="controle-inline">
        <label htmlFor="ex-filtro-nivel">Nível</label>
        <select id="ex-filtro-nivel" defaultValue="">
          <option value="">Todos</option>
          <option>CAMPANHA</option>
          <option>GRUPO</option>
          <option>ANÚNCIO</option>
        </select>
      </span>
      <span className="controle-inline">
        <label htmlFor="ex-filtro-cat">Categoria</label>
        <select id="ex-filtro-cat" defaultValue="">
          <option value="">Todas</option>
          {TERMOS_DICIONARIO.map((t) => (
            <option key={t.categoria}>{t.categoria}</option>
          ))}
        </select>
      </span>
      <span className="empurra" />
      <Botao variante="secundario" tamanho="sm" disabled>
        Limpar filtros
      </Botao>
    </div>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'padroes-cabecalho',
    titulo: 'Cabeçalho de tela com abas',
    nota: 'As abas são `role="tab"` com roving tabindex, não links: a URL é consequência do clique, não o mecanismo. Setas, Home e End percorrem a lista.',
    render: () => <Cabecalho />,
  },
  {
    id: 'padroes-grade',
    titulo: 'Grade intrínseca',
    nota: 'Reduza a largura do palco: a grade reflui sem @media. É a prova de que o catálogo não mente sobre responsividade.',
    render: () => <Grade />,
  },
  {
    id: 'padroes-tabela',
    titulo: 'Tabela de resultados',
    nota: 'O que aparece é o match_id; o UUID interno nunca. E não há botão de editar ou excluir — taxonomia é imutável (D-004), o caminho de correção é regerar.',
    render: () => <Tabela />,
  },
  {
    id: 'padroes-filtros',
    titulo: 'Barra de filtros',
    nota: '"Limpar filtros" nasce desabilitado: oferecer limpar o que já está limpo gasta um clique para descobrir que nada acontece.',
    render: () => <BarraDeFiltros />,
  },
]
