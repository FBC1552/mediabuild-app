import { Estado } from './ui'
import { VoltarPara } from './VoltarPara'

/**
 * Rota desconhecida. Nielsen #9: mostrar o erro e oferecer saída, em vez de
 * redirecionar em silêncio — o redirecionamento mudo esconde link quebrado.
 */
export function RotaNaoEncontrada({ caminho }: { caminho: string }) {
  return (
    <main className="pagina contexto-pagina pilha" data-largura="leitura" data-espaco="5">
      <VoltarPara de="inicio" />
      <Estado
        tipo="rota"
        tituloComo="h1"
        titulo="Endereço não encontrado"
        texto="Este endereço não corresponde a nenhuma tela do MediaBuild."
        identificador={caminho}
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
    </main>
  )
}

export default RotaNaoEncontrada
