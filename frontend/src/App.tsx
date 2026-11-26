import { lazy, Suspense, useEffect, useRef, useState } from 'react'

import { FaixaAdmin } from './admin/CascaAdmin'
import { AcessoNegado } from './componentes/AcessoNegado'
import { AplicativoTaxonomia } from './componentes/AplicativoTaxonomia'
import { Cadastro } from './componentes/Cadastro'
import { BarraTopo } from './componentes/cromo'
import { DialogoSessaoExpirada } from './componentes/DialogoSessaoExpirada'
import { Entrar } from './componentes/Entrar'
import { CatalogoMetricas } from './componentes/CatalogoMetricas'
import { Guia } from './componentes/Guia'
import { PlanoDetalhe } from './componentes/PlanoDetalhe'
import { PlanoIndice } from './componentes/PlanoIndice'
import { RotaNaoEncontrada } from './componentes/RotaNaoEncontrada'
import { CHAVE_ULTIMO_ASSUNTO, SeletorDeAssunto } from './componentes/SeletorDeAssunto'
import { Splash } from './componentes/Splash'
import { Giro } from './componentes/ui'
import {
  caminhoDe,
  navegar,
  ROTULO_SECAO,
  substituir,
  useRota,
  type AbaTaxonomia,
  type Rota,
} from './roteador'
import { destinoPosLogin, lembrarDestino, useSessao } from './sessao'

/** Vire para `true` e a splash volta a aparecer em toda abertura. */
export const SEMPRE_MOSTRAR_SPLASH = false

// I-4 diz respeito só ao ramo da taxonomia: o catálogo é justamente o código
// que não deve entrar no bundle de quem só gera nomenclatura.
const Catalogo = lazy(() => import('./admin/design/Catalogo'))
const ExemploIsolado = lazy(() => import('./admin/design/ExemploIsolado'))
const Acessos = lazy(() => import('./admin/Acessos'))
const Monitoramento = lazy(() => import('./admin/Monitoramento'))

const TITULO: Record<string, string> = {
  entrar: 'Entrar · MediaBuild',
  splash: 'MediaBuild',
  assunto: 'Escolher assunto · MediaBuild',
  guia: 'Guia de uso · MediaBuild',
  cadastro: 'Acesso ao MediaBuild',
  taxonomia: 'Construção de taxonomia · MediaBuild',
  'plano-lista': 'Planos de mídia · MediaBuild',
  'plano-metricas': 'Catálogo de métricas · MediaBuild',
  plano: 'Plano de mídia · MediaBuild',
  'admin-acessos': 'Administração · Acessos · MediaBuild',
  'admin-monitoramento': 'Administração · Monitoramento · MediaBuild',
  isolado: 'Exemplo isolado · MediaBuild',
  desconhecida: 'Endereço não encontrado · MediaBuild',
}

/**
 * Rotas que NÃO recebem a barra de topo global.
 *
 * `entrar` e `splash` não têm para onde navegar (a splash é o próprio
 * início); `isolado` é palco de exemplo e qualquer cromo por perto o
 * contamina; `guia` e `cadastro` já montam a sua própria barra, porque são
 * donas da casca inteira da tela.
 */
const SEM_BARRA_GLOBAL = new Set<Rota['nome']>([
  'entrar',
  'splash',
  'isolado',
  'guia',
  'cadastro',
])

export default function App() {
  const rota = useRota()
  const { estado, idSessao, permissoes, papel } = useSessao()
  const autenticado = estado.fase === 'autenticado'

  // ATENÇÃO — os dois memorandos abaixo são `useRef`, não `useState`, e isso
  // NÃO é estilo. `setState` durante o render deste componente quebra o
  // `useSyncExternalStore` de `useRota`: no re-render disparado na hora, o
  // React já vê o snapshot novo em `hook.memoizedState`, conclui que nada
  // mudou e não agenda o efeito que atualiza a cópia interna da store. Essa
  // cópia congela no valor do primeiro commit e toda navegação de VOLTA para
  // ele passa a ser silenciosamente ignorada — era esse o bug de "clico em
  // Gerar e não acontece nada" depois de abrir o app já em `#/taxonomia/gerar`.
  // Os dois valores são memória derivada da rota, não estado: escrevê-los em
  // ref é idempotente e o render que os atualiza é o próprio render da rota.

  // I-1: liga na primeira visita e NUNCA volta. Quem só abriu a splash não
  // paga o custo; quem entrou uma vez nunca mais perde o formulário.
  const jaVisitouTaxonomia = useRef(rota.nome === 'taxonomia')
  if (rota.nome === 'taxonomia') jaVisitouTaxonomia.current = true
  const taxonomiaJaVisitada = jaVisitouTaxonomia.current

  // I-7: a aba ativa sobrevive à ida ao catálogo. Sem isto, voltar cairia
  // sempre em `Gerar` mesmo tendo saído do `Histórico`.
  const abaLembrada = useRef<AbaTaxonomia>(rota.nome === 'taxonomia' ? rota.aba : 'gerar')
  if (rota.nome === 'taxonomia') abaLembrada.current = rota.aba
  const ultimaAba = abaLembrada.current

  const [anuncio, setAnuncio] = useState('')
  const bootRef = useRef(false)

  // Pular a splash de quem já escolheu um assunto. O analista abre isto
  // dezenas de vezes por dia; tela de marca a cada abertura é imposto.
  useEffect(() => {
    if (bootRef.current) return
    bootRef.current = true
    if (SEMPRE_MOSTRAR_SPLASH) return
    if (window.location.hash !== '' && window.location.hash !== '#/') return
    try {
      const ultimoAssunto = window.localStorage.getItem(CHAVE_ULTIMO_ASSUNTO)
      if (ultimoAssunto === 'taxonomia') {
        substituir('#/taxonomia/gerar')
      } else if (ultimoAssunto === 'plano') {
        substituir('#/plano')
      }
    } catch {
      // Sem localStorage, a splash aparece — degradação aceitável.
    }
  }, [])

  // Portão de sessão (UX-NAVEGACAO §5.1–§5.2). Roda só depois de o boot
  // resolver: enquanto a fase é `verificando` ninguém é mandado a lugar
  // nenhum, senão quem já tem sessão vê a tela de login piscar.
  //
  // `substituir()` e não `location.hash =`: empilhar entrada faria o botão
  // voltar do navegador cair de volta no portão, em loop.
  useEffect(() => {
    if (estado.fase === 'verificando') return
    if (!autenticado && rota.nome !== 'entrar') {
      lembrarDestino(window.location.hash)
      substituir('#/entrar')
      return
    }
    if (autenticado && rota.nome === 'entrar') substituir(destinoPosLogin())
  }, [estado.fase, autenticado, rota.nome])

  // Canoniza `#/taxonomia` → `#/taxonomia/gerar` e `#/admin` → `#/admin/fundacao`
  // com replaceState: `location.hash =` empilharia entrada e o botão voltar
  // ficaria preso no redirecionamento.
  useEffect(() => {
    if (rota.nome === 'desconhecida') return
    const canonico = caminhoDe(rota)
    if (window.location.hash !== canonico && window.location.hash !== '') substituir(canonico)
  }, [rota])

  // Foco e rolagem só quando a TELA muda. Trocar de aba não mexe no foco —
  // o widget de tabs já gerencia o dele.
  const chaveTela =
    rota.nome === 'catalogo'
      ? `catalogo:${rota.secao}`
      : rota.nome === 'plano'
        ? `plano:${rota.id}`
        : rota.nome
  useEffect(() => {
    // §3.5: `document.title` das telas de admin ganha o prefixo
    // `Administração · `, para o anúncio de rota já dizer onde a pessoa está.
    const titulo =
      rota.nome === 'catalogo'
        ? `Administração · ${ROTULO_SECAO[rota.secao]} · Catálogo de interface · MediaBuild`
        : TITULO[rota.nome]
    document.title = titulo
    setAnuncio(titulo)
    window.scrollTo({ top: 0 })
    // O alvo é marcado pela tela; sem isso o foco cai no <body> ao esconder
    // o ramo da taxonomia e o teclado recomeça do zero.
    const alvo = document.querySelector<HTMLElement>('[data-foco-rota]')
    alvo?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveTela])

  function trocarAba(aba: AbaTaxonomia) {
    navegar(`#/taxonomia/${aba}`)
  }

  // Estado indeterminado é explícito: nem produto, nem login. É o que impede
  // a tela de login de piscar para quem já está autenticado.
  if (estado.fase === 'verificando') {
    return (
      <div className="carregando-regiao">
        <Giro tamanho="lg" />
        Carregando…
      </div>
    )
  }

  // Sem sessão só existe uma tela. O ramo da taxonomia nem chegou a montar
  // aqui — não há formulário a preservar, e por isso este `return` não
  // contraria o I-1.
  if (!autenticado) return <Entrar />

  const podeVerAdmin = permissoes.podeAdministrar
  // Toda a área administrativa passa pelo mesmo portão: as três áreas do §3.1
  // mais o exemplo isolado, que é palco do catálogo.
  const rotaDeAdmin =
    rota.nome === 'catalogo' ||
    rota.nome === 'isolado' ||
    rota.nome === 'admin-acessos' ||
    rota.nome === 'admin-monitoramento'

  return (
    <>
      <div className="apenas-leitor" role="status" aria-live="polite">
        {anuncio}
      </div>

      {!SEM_BARRA_GLOBAL.has(rota.nome) && <BarraTopo />}

      <DialogoSessaoExpirada />

      {rota.nome === 'splash' && <Splash />}
      {rota.nome === 'assunto' && <SeletorDeAssunto />}
      {rota.nome === 'guia' && <Guia />}
      {rota.nome === 'cadastro' && <Cadastro />}
      {rota.nome === 'plano-lista' && <PlanoIndice />}
      {rota.nome === 'plano-metricas' && <CatalogoMetricas />}
      {rota.nome === 'plano' && <PlanoDetalhe key={rota.id} planoId={rota.id} />}
      {rota.nome === 'desconhecida' && <RotaNaoEncontrada caminho={rota.caminho} />}

      {/* §4.3: tela de acesso negado com texto, nunca 404 e nunca
          redirecionamento silencioso. Isto é cosmético — a autoridade é o
          servidor, que devolve 403 de qualquer maneira. */}
      {rotaDeAdmin && !podeVerAdmin && (
        <main className="pagina contexto-pagina pilha" data-largura="estreita" data-espaco="6">
          <AcessoNegado
            titulo="Você não tem acesso à administração"
            papel={papel}
            tituloComo="h1"
            saidaHref="#/assunto"
            saidaRotulo="Ir para os assuntos"
          />
        </main>
      )}

      {/* §3.5: UM sinal só, forte, e fora do conteúdo. O exemplo isolado fica
          de fora — ali qualquer cromo por perto contamina o palco. */}
      {rotaDeAdmin && podeVerAdmin && rota.nome !== 'isolado' && <FaixaAdmin />}

      {rotaDeAdmin && podeVerAdmin && (
        <Suspense
          fallback={
            <div className="carregando-regiao">
              <Giro tamanho="lg" />
              Carregando a administração…
            </div>
          }
        >
          {rota.nome === 'catalogo' && <Catalogo secao={rota.secao} />}
          {rota.nome === 'isolado' && <ExemploIsolado exemplo={rota.exemplo} />}
          {rota.nome === 'admin-acessos' && <Acessos />}
          {rota.nome === 'admin-monitoramento' && <Monitoramento />}
        </Suspense>
      )}

      {/* I-1/I-2/I-4: sem `key`, sem `lazy`, sem desmontar. A visibilidade é
          `hidden` — que também tira o ramo da árvore de acessibilidade e do
          Tab, coisa que `display:none` por classe não garante. */}
      {taxonomiaJaVisitada && (
        // `key={idSessao}` é a ÚNICA exceção autorizada ao I-2, e existe para
        // um caso só: outra pessoa senta na máquina depois do `Sair` e não
        // pode herdar o formulário da anterior. `idSessao` muda apenas em
        // login e logout — jamais em troca de rota, jamais na reautenticação
        // depois de a sessão expirar. Qualquer outra coisa entrando nesta
        // `key` é exatamente o bug que o I-2 descreve.
        <div key={idSessao} hidden={rota.nome !== 'taxonomia'}>
          <AplicativoTaxonomia
            aba={ultimaAba}
            aoTrocarAba={trocarAba}
          />
        </div>
      )}
    </>
  )
}
