import { BarraTopo, RodapeUtilitario } from './cromo'
import { useSessao } from '../sessao'
import { ROTULO_PAPEL } from '../tipos'
import { VoltarPara } from './VoltarPara'

/**
 * Acesso ao MediaBuild (`#/cadastro`).
 *
 * ESTA TELA FOI REESCRITA, NÃO REMOVIDA — e a escolha merece justificativa,
 * porque a alternativa (tirá-la da barra) era defensável.
 *
 * O que ela dizia até aqui era literalmente falso: "o MediaBuild não tem
 * autenticação". Tem, desde o D-014. Deixar o texto no ar seria o pior dos
 * mundos — uma tela do produto contradizendo o portão pelo qual a pessoa
 * acabou de passar (Nielsen #1: o sistema tem que dizer a verdade sobre o
 * próprio estado).
 *
 * Por que não simplesmente apagá-la da barra:
 *
 * 1. O produto **publicou** `#/cadastro` — ele está na barra de topo e no
 *    rodapé desde a Parte I. Sumir com o endereço transforma bookmark em 404,
 *    o mesmo dano autoinfligido que o §3.2 evita nas URLs do catálogo.
 * 2. A pergunta que trazia alguém aqui ("como consigo uma conta?") continua
 *    existindo — e agora TEM resposta, que é a do §3.6: quem cria e redefine
 *    acesso é um administrador, pessoalmente. Uma tela que responde isso vale
 *    mais que um item de menu a menos.
 * 3. Não existe autoatendimento e não vai existir: sem canal de e-mail, um
 *    formulário de cadastro seria um caminho que não leva a lugar nenhum —
 *    exatamente o que a §5.3 recusa ao proibir "esqueci minha senha" clicável.
 *
 * Então: **zero formulário, zero campo, zero botão que finja enviar algo.**
 * A tela é conteúdo — diz quem cria acesso, o que cada perfil faz, e como
 * trocar a própria senha (falando com um administrador). Isso também é o que
 * a tira do caminho do teclado sem `fieldset disabled`: não há controle a
 * desabilitar quando não há controle.
 */
export function Cadastro() {
  const { usuario, papel } = useSessao()

  return (
    <div className="casca-conteudo">
      <BarraTopo atual="cadastro" />

      {/* Texto corrido: largura de leitura (§7.3). */}
      <main className="pagina contexto-pagina pilha" data-largura="leitura" data-espaco="7">
        <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
          <VoltarPara de="inicio" />
          <h1 className="titulo-tela">Acesso ao MediaBuild</h1>
          <p className="marca-subtitulo medida">
            Quem cria uma conta, o que cada perfil faz e como trocar a senha.
          </p>
        </header>

        {usuario && (
          <section className="card bloco pilha" data-espaco="2">
            <h2 className="rotulo-secao">Você está usando</h2>
            <p className="texto-guia">
              <strong>{usuario.nome}</strong> · <span className="mono">@{usuario.login}</span> ·
              perfil <strong>{papel ? ROTULO_PAPEL[papel] : '—'}</strong>
            </p>
            <p className="texto-auxiliar">
              O perfil e o que ele destrava também aparecem no menu de conta, no canto
              superior direito — é o lugar canônico dessa informação.
            </p>
          </section>
        )}

        <section className="pilha" data-espaco="3">
          <h2 className="titulo-secao">Não há autocadastro</h2>
          <p className="texto-guia medida">
            Contas são criadas por um <strong>administrador</strong>, na área de
            administração. Não existe formulário de cadastro nesta tela nem em nenhuma
            outra, e isso é decisão, não pendência: o MediaBuild roda localmente e não tem
            canal de e-mail, então um cadastro que você mesmo preenchesse não teria como ser
            confirmado nem recuperado.
          </p>
          <p className="texto-guia medida">
            A identidade do produto é o <strong>usuário</strong> — não o e-mail. Não há
            coluna de e-mail no sistema, justamente porque o único poder que um e-mail teria
            aqui (recuperar acesso sozinho) não existe.
          </p>
        </section>

        <section className="pilha" data-espaco="3">
          <h2 className="titulo-secao">Esqueci a senha</h2>
          <p className="texto-guia medida">
            Peça a um administrador. Ele gera uma senha provisória, que é exibida{' '}
            <strong>uma única vez</strong> e entregue pessoalmente. Não há link de
            recuperação na tela de entrada porque não há para onde ele apontar — e um link
            que não leva a lugar nenhum custa mais que esta frase.
          </p>
        </section>

        <section className="pilha" data-espaco="3">
          <h2 className="titulo-secao">Os três perfis</h2>
          <dl className="lista-definicao">
            <dt>Básico</dt>
            <dd>Gera nomenclaturas e consulta o histórico. Não vê o Dicionário e não exclui nada.</dd>
            <dt>Pleno</dt>
            <dd>Usa o produto inteiro: gerar, dicionário, histórico e planos de mídia.</dd>
            <dt>Administrador</dt>
            <dd>Tudo do Pleno, mais a administração de acessos e o monitoramento.</dd>
          </dl>
          <p className="texto-auxiliar medida">
            Controles que o seu perfil não permite não aparecem na tela — em vez de
            aparecerem cinzentos. Um botão morto que você nunca vai poder usar é ruído
            permanente; a frase que explica o perfil mora num lugar só, no menu de conta.
          </p>
        </section>

        <div className="linha">
          <a className="botao" href="#/taxonomia/gerar">
            <span className="botao-rotulo">Gerar nomenclatura</span>
          </a>
          <a className="botao" data-variante="fantasma" href="#/guia">
            <span className="botao-rotulo">Ler o guia de uso</span>
          </a>
        </div>
      </main>

      <RodapeUtilitario />
    </div>
  )
}

export default Cadastro
