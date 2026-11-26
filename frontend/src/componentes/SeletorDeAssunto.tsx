import { CartaoOpcao } from './ui'
import { VoltarPara } from './VoltarPara'

export const CHAVE_ULTIMO_ASSUNTO = 'mdbd:ultimo-assunto'

function registrarEscolhaPlano() {
  try {
    window.localStorage.setItem(CHAVE_ULTIMO_ASSUNTO, 'plano')
  } catch {
    // localStorage indisponível (modo restrito) só custa a splash de novo.
  }
}

/**
 * Seletor de assunto (`#/assunto`).
 *
 * Rota própria em tela cheia, não modal: é nó de navegação, não tarefa
 * interruptiva. Sem modal não há focus trap escrito à mão — que é onde nascem
 * os bugs de acessibilidade — e o botão voltar do navegador sai de graça.
 */
export function SeletorDeAssunto() {
  function registrarEscolha() {
    try {
      window.localStorage.setItem(CHAVE_ULTIMO_ASSUNTO, 'taxonomia')
    } catch {
      // localStorage indisponível (modo restrito) só custa a splash de novo.
    }
  }

  return (
    <main className="pagina contexto-pagina pilha" data-espaco="8">
      {/* `data-foco-rota` no HEADER, não no `h1`: com o Voltar acima do
          título, focar o `h1` deixaria o link atrás do ponto de foco, e ele
          só seria alcançável por Shift+Tab (§2.3). */}
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara de="inicio" />
        <h1 className="titulo-tela">Escolher assunto</h1>
        {/* Arquitetura de informação, não enfeite: estabelece a expectativa
            antes de o usuário encontrar os cartões apagados. */}
        <p className="marca-subtitulo medida">
          Construção de taxonomia e Plano de mídia estão disponíveis nesta versão.
        </p>
      </header>

      <div className="grade" data-base="larga">
        <CartaoOpcao
          titulo="Construção de taxonomia"
          descricao="Gere nomenclaturas padronizadas para campanha, grupo e anúncio."
          href="#/taxonomia/gerar"
          aoAtivar={registrarEscolha}
        />
        <CartaoOpcao
          titulo="Social"
          selo="Em breve"
          descricao="Ainda não faz parte desta versão do MediaBuild."
        />
        <CartaoOpcao
          titulo="Mídia"
          descricao="Planeje o investimento e as metas por campanha, grupo e anúncio."
          href="#/plano"
          aoAtivar={registrarEscolhaPlano}
        />
      </div>
    </main>
  )
}

export default SeletorDeAssunto
