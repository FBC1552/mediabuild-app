import { BarraTopo, RodapeUtilitario } from './cromo'
import { VoltarPara } from './VoltarPara'

/**
 * Guia de uso (`#/guia`).
 *
 * Conteúdo, não marketing: cada seção existe porque a regra que ela descreve
 * custa dinheiro quando é ignorada. A ordem é a do trabalho (montar o nome →
 * cruzar com a planilha → conferir a URL), não a da arquitetura do sistema.
 *
 * Sem índice com âncoras de propósito: a navegação é por hash (D-010), então
 * um `href="#niveis"` seria lido como rota e cairia em "Endereço não
 * encontrado". Quem quiser varrer a página usa os títulos.
 */
export function Guia() {
  return (
    <div className="casca-conteudo">
      <BarraTopo atual="guia" />

      {/* §7.3: texto corrido é a única classe de tela em que crescer é ERRO —
          linha de 140 caracteres é o defeito de legibilidade mais comum em
          monitor grande. */}
      <main className="pagina contexto-pagina pilha" data-largura="leitura" data-espaco="9">
        <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
          <VoltarPara de="inicio" />
          <h1 className="titulo-tela">Guia de uso</h1>
          <p className="marca-subtitulo medida">
            O MediaBuild monta o nome de campanha, grupo e anúncio a partir de um padrão
            cadastrado, e devolve um código curto que liga esse nome à planilha de
            performance. Este guia explica as regras que decidem o resultado.
          </p>
        </header>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">1 · Os três níveis</h2>
          <p className="texto-guia medida">
            A hierarquia é a do domínio: <strong>campanha → grupo de anúncio → anúncio</strong>.
            O formulário segue essa ordem e é uma cascata — o grupo só abre quando a campanha
            está válida, e o anúncio só abre quando o grupo está. É restrição, não burocracia:
            o nome do grupo depende do contexto da campanha.
          </p>
          <p className="texto-guia medida">
            Cada nível gera <strong>um nome próprio</strong> e recebe <strong>um código
            próprio</strong>. O campo <em>Nome interno</em> não entra no nome gerado — é como
            você chama aquilo no dia a dia, para reencontrar o registro depois.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">2 · O nome vem do padrão cadastrado</h2>
          <p className="texto-guia medida">
            Para cada combinação de plataforma e nível existe um <strong>template</strong>: uma
            sequência ordenada de peças e um separador. As peças são de três tipos — um literal
            (a sigla da plataforma), os campos que você preenche e o código de cruzamento no
            fim.
          </p>
          <p className="exemplo-nome mono">METAA_CV_RMKT_IGST_G0001</p>
          <p className="texto-guia medida">
            Os campos que aparecem na tela, os rótulos deles, o limite de caracteres e quais são
            opcionais saem todos desse template. Por isso mudar o padrão de nomenclatura é
            atualizar um cadastro, não publicar uma versão nova do sistema — e por isso duas
            plataformas podem pedir campos diferentes na mesma tela.
          </p>
          <p className="texto-guia medida">
            Toda alteração do padrão cria uma <strong>versão nova</strong> do template. O nome
            já gerado guarda a versão que o produziu, então continua explicável mesmo depois de
            o padrão mudar.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">3 · O match ID é a chave, o nome é o rótulo</h2>
          <p className="texto-guia medida">
            O match ID é o código curto no fim do nome: <span className="mono">C0001</span> para
            campanha, <span className="mono">G0001</span> para grupo,{' '}
            <span className="mono">A0001</span> para anúncio. Ele é gerado por sequência, então
            é único, e <strong>pertence à entidade, não ao nome</strong>.
          </p>
          <p className="texto-guia medida">
            A consequência prática é a razão de o produto existir: se você regerar o nome de uma
            campanha, o match ID <strong>não muda</strong>. O cruzamento com a planilha de
            performance continua fechando mesmo depois de o rótulo ter sido reescrito.
          </p>
          <p className="texto-guia medida">
            Regra de análise que vale sempre: <strong>cruze pelo match ID</strong>, nunca
            separando o nome pelo <span className="mono">_</span>. A quantidade de campos pode
            mudar entre versões de template; o código, não.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">4 · Dicionário de abreviações</h2>
          <p className="texto-guia medida">
            Campo de lista consulta o dicionário: cada termo tem uma abreviação cadastrada
            (<em>Conversão → CV</em>, <em>Remarketing → RMKT</em>), por categoria e, quando
            necessário, por plataforma. O que entra no nome é a abreviação.
          </p>
          <p className="texto-guia medida">
            Termo sem abreviação cadastrada é <strong>erro</strong>, não passagem livre. A
            mensagem traz as duas saídas: escolher um dos termos que já existem, ou cadastrar o
            novo na aba <strong>Dicionário</strong>. Deixar passar geraria{' '}
            <span className="mono">CONVERSAO</span> onde deveria estar{' '}
            <span className="mono">CV</span> — e ninguém perceberia até o relatório não fechar.
          </p>
          <p className="texto-guia medida">
            Campo livre é a exceção: não consulta dicionário, tem limite de caracteres próprio e
            só é normalizado.
          </p>
          <p className="texto-guia medida">
            <strong>Acento e caixa não são problema seu.</strong> Antes de qualquer validação o
            valor é normalizado: acento vira a letra sem acento e tudo sobe para maiúsculas.
            Escrever “Conversão” está certo.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">5 · Limite de caracteres</h2>
          <p className="texto-guia medida">
            Cada plataforma tem um limite por nível, cadastrado junto com o template — as
            plataformas não concordam entre si, e estourar o limite faz a plataforma recusar ou
            cortar o nome.
          </p>
          <p className="texto-guia medida">
            O contador aparece abaixo da nomenclatura enquanto você preenche (
            <span className="mono">142 / 400 caracteres</span>). Passar do limite é erro
            declarado, com o campo apontado —{' '}
            <strong>o nome nunca é cortado em silêncio</strong>.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">6 · Campo opcional em branco grava NA</h2>
          <p className="texto-guia medida">
            Campo opcional deixado em branco não some do nome: ele grava o marcador{' '}
            <span className="mono">NA</span>. Assim a posição de cada campo fica fixa — mesma
            plataforma e mesmo nível significam sempre a mesma quantidade de campos.
          </p>
          <p className="texto-guia medida">
            O motivo é a planilha. Quando o token sumia, quem separava o nome pelo{' '}
            <span className="mono">_</span> via as colunas <strong>deslocarem</strong> de linha
            para linha: a secundagem caía onde deveria estar a versão. O nome continuava certo;
            o relatório é que não fechava.
          </p>
          <p className="texto-guia medida">
            Por isso <span className="mono">NA</span> é reservado: nenhum termo do dicionário
            pode ter <span className="mono">NA</span> como abreviação, senão não haveria como
            distinguir “não se aplica” de um valor real. Cadastrar dá erro na hora.
          </p>
          <p className="texto-guia medida" data-tom="ressalva">
            Ressalva para quem analisa fora do Excel: em pandas e em R,{' '}
            <span className="mono">NA</span> está na lista padrão de valores nulos ao ler CSV, e
            o <span className="mono">groupby</span> descarta essas linhas por padrão. Leia com{' '}
            <span className="mono">keep_default_na=False</span> ou agrupe com{' '}
            <span className="mono">dropna=False</span>. No Excel e no Sheets,{' '}
            <span className="mono">NA</span> digitado continua sendo o texto{' '}
            <span className="mono">NA</span>.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">7 · Validador de UTM</h2>
          <p className="texto-guia medida">
            Na aba <strong>Gerar</strong> você cola a URL de destino e o MediaBuild responde se
            os parâmetros batem com a taxonomia gerada. Ele <strong>confere</strong>, não monta
            a URL: a montagem depende de landing page, redirecionador e macro de cada
            plataforma.
          </p>
          <p className="texto-guia medida">
            O item mais caro que o laudo pega é a URL copiada de outra campanha — o link
            funciona, o site abre, e o custo é atribuído no lugar errado por semanas.
          </p>
          <dl className="lista-definicao">
            <dt className="mono">utm_id</dt>
            <dd>
              Match ID da campanha. É por ele que o GA4 junta o custo importado com a sessão;
              sem ele o ROAS não fecha mesmo com as outras cinco UTMs perfeitas.
            </dd>
            <dt className="mono">utm_campaign</dt>
            <dd>Precisa conter o match ID da campanha.</dd>
            <dt className="mono">utm_content</dt>
            <dd>Match ID do anúncio.</dd>
            <dt className="mono">utm_term</dt>
            <dd>
              Match ID do grupo — aceito também em <span className="mono">utm_content</span>,
              porque em Search este parâmetro é a palavra-chave.
            </dd>
            <dt className="mono">utm_source · utm_medium</dt>
            <dd>
              Conferidos contra o vocabulário cadastrado no dicionário para a plataforma. Sem
              vocabulário cadastrado, a divergência é só aviso.
            </dd>
          </dl>
          <p className="texto-guia medida">
            O laudo separa <strong>erro</strong> de <strong>aviso</strong>, e a distinção é o
            ponto: erro é o que faz o dado chegar errado ou não chegar (parâmetro dentro da
            âncora, match ID de outro nível, acento no valor); aviso é o que funciona mas
            envelhece mal (caixa mista, <span className="mono">http://</span>, nome divergente
            da nomenclatura gerada). Nada é salvo ao conferir uma URL.
          </p>
        </section>

        <section className="secao-guia pilha" data-espaco="4">
          <h2 className="titulo-secao">8 · O que foi gerado não se edita</h2>
          <p className="texto-guia medida">
            Nomenclatura gerada é imutável. Não existe editar nem excluir no Histórico, e a
            ausência é proposital: o nome já pode estar rodando na plataforma, e alterá-lo aqui
            descolaria em silêncio o cruzamento com a planilha.
          </p>
          <p className="texto-guia medida">
            Errou? <strong>Gere de novo.</strong> Sai um registro novo, com nome novo, e o
            anterior continua no histórico com a versão de template que o produziu. O match ID
            da entidade segue o mesmo. O histórico pode ser exportado para Excel com os filtros
            aplicados.
          </p>
        </section>

        <nav className="linha" aria-label="Continuar">
          <a className="botao" href="#/taxonomia/gerar">
            <span className="botao-rotulo">Gerar nomenclatura</span>
          </a>
          <a className="botao" data-variante="fantasma" href="#/">
            <span className="botao-rotulo">Voltar ao início</span>
          </a>
        </nav>
      </main>

      <RodapeUtilitario />
    </div>
  )
}

export default Guia
