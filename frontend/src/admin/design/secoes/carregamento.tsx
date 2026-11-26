import { Botao, Esqueleto, Giro } from '../../../componentes/ui'
import type { Exemplo } from '../MostraExemplo'

function Esqueletos() {
  return (
    <div className="pilha" data-espaco="4">
      <Esqueleto forma="titulo" />
      <Esqueleto />
      <Esqueleto />
      <Esqueleto final />
      <Esqueleto forma="controle" />
      <Esqueleto forma="cartao" />
    </div>
  )
}

function Spinners() {
  return (
    <div className="pilha" data-espaco="5">
      <div className="linha">
        <Giro />
        <Giro tamanho="lg" />
      </div>
      <div className="carregando-regiao">
        <Giro tamanho="lg" />
        Carregando o histórico…
      </div>
      <div className="linha">
        <Botao carregando>Gerar nomenclatura</Botao>
      </div>
    </div>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'carregamento-esqueleto',
    titulo: 'Esqueleto',
    nota: 'Esqueleto só onde a forma do conteúdo é previsível (tabela, cartão). Para operação pontual, spinner. A última linha é mais curta de propósito — sem isso o bloco vira uma barra.',
    render: () => <Esqueletos />,
  },
  {
    id: 'carregamento-giro',
    titulo: 'Indicador de progresso',
    nota: 'Ambos carregam data-movimento="essencial": sob prefers-reduced-motion continuam girando, só que devagar. Um indicador de progresso congelado comunica "travou".',
    render: () => <Spinners />,
  },
]
