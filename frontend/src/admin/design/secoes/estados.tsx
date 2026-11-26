import { Botao, Estado } from '../../../componentes/ui'
import type { Exemplo } from '../MostraExemplo'

function Vazios() {
  return (
    <div className="pilha" data-espaco="6">
      <Estado
        tipo="vazio"
        titulo="Nenhuma nomenclatura gerada ainda"
        texto="Complete os três níveis na aba Gerar para ver o resultado aqui."
      />
      <Estado
        tipo="sem-resultado"
        titulo="Nenhum resultado para estes filtros"
        texto="Ajuste o período ou a plataforma para voltar a ver registros."
      >
        <Botao variante="secundario" tamanho="sm">
          Limpar filtros
        </Botao>
      </Estado>
    </div>
  )
}

function Erros() {
  return (
    <div className="pilha" data-espaco="6">
      <Estado
        tipo="erro"
        titulo="Não foi possível carregar as plataformas"
        texto="A API não respondeu. Verifique se o serviço está no ar e tente de novo."
      >
        <Botao variante="secundario" tamanho="sm">
          Tentar de novo
        </Botao>
      </Estado>
      <Estado
        tipo="erro-exemplo"
        titulo="Este exemplo não pôde ser renderizado."
        identificador="componentes-botao"
      />
    </div>
  )
}

function TelaDeErro() {
  return (
    <Estado
      tipo="rota"
      titulo="Endereço não encontrado"
      texto="Este endereço não corresponde a nenhuma tela do MediaBuild."
    >
      <div className="linha" data-espaco="3">
        <a className="botao" data-variante="secundario" href="#/">
          Ir para a inicial
        </a>
        <a className="botao" href="#/taxonomia/gerar">
          Ir para a taxonomia
        </a>
      </div>
    </Estado>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'estados-vazio',
    titulo: 'Vazio e sem resultado',
    nota: 'São estados diferentes com redação diferente: "ainda não existe" ensina o próximo passo; "o filtro não achou" oferece limpar o filtro.',
    render: () => <Vazios />,
  },
  {
    id: 'estados-erro',
    titulo: 'Erro',
    nota: 'O vermelho fica na borda e no título, não no fundo inteiro. O erro por exemplo do catálogo é isolado por ErrorBoundary — um exemplo quebrado não apaga a página.',
    render: () => <Erros />,
  },
  {
    id: 'estados-rota',
    titulo: 'Rota desconhecida',
    nota: 'Nada de redirecionar em silêncio (Nielsen #9): o endereço errado é mostrado e a saída é oferecida.',
    render: () => <TelaDeErro />,
  },
]
