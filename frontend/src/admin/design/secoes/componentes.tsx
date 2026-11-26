import { useState } from 'react'

import { ArvoreCampanha, type CampanhaCorrente } from '../../../componentes/ArvoreCampanha'
import { BarraTopo, RodapeUtilitario } from '../../../componentes/cromo'
import {
  IconeChevron,
  IconeConta,
  IconeCopiar,
  IconeGuia,
  IconeMais,
  IconeNivel,
  LogoPlataforma,
  PLATAFORMAS_COM_LOGO,
  type ComponenteIcone,
  type TamanhoIcone,
} from '../../../componentes/icones'
import { Preview } from '../../../componentes/Preview'
import { Botao, CartaoOpcao, Selo } from '../../../componentes/ui'
import { NIVEIS, ROTULO_NIVEL } from '../../../tipos'
import type { ErroApi, NoDaArvore, PreviewResposta } from '../../../tipos'
import { Selecao } from '../MostraExemplo'
import type { Exemplo } from '../MostraExemplo'

const VARIANTES = ['primario', 'secundario', 'fantasma', 'perigo'] as const
const TAMANHOS = ['sm', 'md', 'lg'] as const

function Botoes() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Variantes</p>
        <div className="linha">
          {VARIANTES.map((variante) => (
            <Botao key={variante} variante={variante}>
              {variante}
            </Botao>
          ))}
        </div>
      </div>
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Tamanhos</p>
        <div className="linha">
          {TAMANHOS.map((tamanho) => (
            <Botao key={tamanho} tamanho={tamanho}>
              Gerar nomenclatura
            </Botao>
          ))}
        </div>
      </div>
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Tamanho hero (eixo de métrica, independente da variante)</p>
        <div className="linha">
          <Botao tamanho="hero">Gerar nomenclatura</Botao>
          <Botao tamanho="hero" variante="secundario">
            Escolher assunto
          </Botao>
        </div>
      </div>
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Estados</p>
        <div className="linha">
          <Botao disabled>Desabilitado</Botao>
          <Botao carregando>Gerando…</Botao>
          <Botao variante="secundario" disabled>
            Secundário desabilitado
          </Botao>
        </div>
      </div>
    </div>
  )
}

function Selos() {
  return (
    <div className="linha">
      <Selo>Em breve</Selo>
      <Selo variante="acao">Rascunho</Selo>
      <Selo variante="ok">Gerada</Selo>
      <Selo variante="erro">Falhou</Selo>
      <Selo variante="alerta">Perto do limite</Selo>
    </div>
  )
}

function Cartoes() {
  return (
    <div className="grade" data-base="larga">
      <CartaoOpcao
        titulo="Construção de taxonomia"
        descricao="Gere nomenclaturas padronizadas para campanha, grupo e anúncio."
        href="#/taxonomia/gerar"
      />
      <CartaoOpcao
        titulo="Social"
        selo="Em breve"
        descricao="Ainda não faz parte desta versão do MediaBuild."
      />
    </div>
  )
}

function Campos() {
  return (
    <div className="pilha" data-espaco="5">
      <div>
        <label htmlFor="ex-campo-ok">Objetivo</label>
        <input id="ex-campo-ok" defaultValue="Conversão" />
      </div>
      <div>
        <label htmlFor="ex-campo-erro">Posicionamento</label>
        <input
          id="ex-campo-erro"
          aria-invalid="true"
          aria-describedby="ex-campo-erro-msg"
          defaultValue="Instagram Reels"
        />
        <p id="ex-campo-erro-msg" className="estado-id">
          Termo não cadastrado no dicionário. Opções: IGST, IGFD, FBFD.
        </p>
      </div>
      <div>
        <label htmlFor="ex-campo-select">Plataforma</label>
        <select id="ex-campo-select" defaultValue="Meta">
          <option>Meta</option>
          <option>Google</option>
          <option>TikTok</option>
        </select>
      </div>
    </div>
  )
}

const TAMANHOS_ICONE: TamanhoIcone[] = ['sm', 'md', 'lg', 'xl', '2xl']

const ICONES_DE_INTERFACE: { nome: string; Icone: ComponenteIcone }[] = [
  { nome: 'IconeMais', Icone: IconeMais },
  { nome: 'IconeChevron', Icone: IconeChevron },
  { nome: 'IconeConta', Icone: IconeConta },
  { nome: 'IconeGuia', Icone: IconeGuia },
  { nome: 'IconeCopiar', Icone: IconeCopiar },
]

const SENTIDOS = ['baixo', 'cima', 'esquerda', 'direita'] as const

function Logos() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Plataformas conhecidas · tamanho xl</p>
        <div className="linha" data-espaco="5">
          {PLATAFORMAS_COM_LOGO.map(({ sigla, nome }) => (
            <span key={sigla} className="linha" data-espaco="2">
              <LogoPlataforma sigla={sigla} tamanho="xl" />
              <span className="mono">{sigla}</span>
              <span>{nome}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Escala</p>
        <div className="linha" data-alinhar="base">
          {TAMANHOS_ICONE.map((tamanho) => (
            <span key={tamanho} className="linha" data-espaco="2">
              <LogoPlataforma sigla="GOOGLE" tamanho={tamanho} />
              <span className="mono">{tamanho}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Monocromático</p>
        <div className="linha" data-espaco="5">
          {PLATAFORMAS_COM_LOGO.map(({ sigla }) => (
            <LogoPlataforma key={sigla} sigla={sigla} tamanho="xl" mono />
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Sigla desconhecida</p>
        <div className="linha" data-espaco="5">
          <LogoPlataforma sigla="PINTR" tamanho="xl" titulo="Pinterest" />
          <LogoPlataforma sigla="LKDIN" tamanho="xl" titulo="LinkedIn" />
          <LogoPlataforma sigla="" tamanho="xl" titulo="Plataforma sem sigla" />
        </div>
      </div>
    </div>
  )
}

function IconesDeNivel() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">A família · tamanho lg</p>
        <div className="linha" data-espaco="5">
          {NIVEIS.map((nivel) => (
            <span key={nivel} className="linha" data-espaco="2">
              <IconeNivel nivel={nivel} tamanho="lg" />
              <span>{ROTULO_NIVEL[nivel]}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">A 16px — o tamanho da árvore da campanha</p>
        <div className="linha" data-espaco="5">
          {NIVEIS.map((nivel) => (
            <span key={nivel} className="linha" data-espaco="2">
              <IconeNivel nivel={nivel} tamanho="sm" />
              <span className="mono">{nivel}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Acompanhando texto (1em, sem prop de tamanho)</p>
        <p>
          <IconeNivel nivel="CAMPANHA" /> Campanha <IconeNivel nivel="GRUPO" /> Grupo{' '}
          <IconeNivel nivel="ANUNCIO" /> Anúncio
        </p>
      </div>
    </div>
  )
}

function IconesDeInterface() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Conjunto · tamanho lg</p>
        <div className="linha" data-espaco="5">
          {ICONES_DE_INTERFACE.map(({ nome, Icone }) => (
            <span key={nome} className="linha" data-espaco="2">
              <Icone tamanho="lg" />
              <span className="mono">{nome}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Chevron · um desenho, quatro sentidos</p>
        <div className="linha" data-espaco="5">
          {SENTIDOS.map((sentido) => (
            <span key={sentido} className="linha" data-espaco="2">
              <IconeChevron sentido={sentido} tamanho="lg" />
              <span className="mono">{sentido}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="pilha" data-espaco="3">
        <p className="rotulo-secao">Dentro de botão</p>
        <div className="linha">
          <Botao>
            <IconeMais /> Nova campanha
          </Botao>
          <Botao variante="secundario">
            <IconeCopiar /> Copiar
          </Botao>
          <Botao variante="fantasma">
            <IconeGuia /> Guia de uso
          </Botao>
        </div>
      </div>
    </div>
  )
}

/* ===========================================================================
   Barra de topo + rodapé utilitário
   =========================================================================== */

function Cromo() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="pilha" data-espaco="2">
        <p className="rotulo-secao">Barra de topo</p>
        <BarraTopo atual="guia" conta={false} />
      </div>
      <div className="pilha" data-espaco="2">
        <p className="rotulo-secao">Rodapé utilitário</p>
        <RodapeUtilitario />
      </div>
    </div>
  )
}

/* ===========================================================================
   Árvore da estrutura da campanha
   ---------------------------------------------------------------------------
   Um único `ArvoreCampanha` montado por vez, trocado por cenário: os estados
   (preenchida / vazia / sem campanha / carregando / erro) são mutuamente
   exclusivos, e mostrar todos simultaneamente inflaria o exemplo sem ganho —
   o seletor de cenário é sobre isso, não sobre id. O componente já usa
   `useId()` internamente, então duas instâncias montadas ao mesmo tempo não
   colidiriam.
   =========================================================================== */

const CAMPANHA_EXEMPLO: CampanhaCorrente = {
  id: 'ex-campanha-1',
  match_id: 'C0001',
  nome_interno: 'Black Friday',
}

const GRUPOS_EXEMPLO: NoDaArvore[] = [
  {
    id: 'ex-grupo-1',
    pai_id: CAMPANHA_EXEMPLO.id,
    nome_interno: 'Conversão · Feed',
    match_id: 'G0001',
    nomenclatura: 'ALF_METAA_FEED_CV_C0001_G0001',
    taxonomia_id: 'ex-taxo-g1',
    gerado_em: '2026-08-01T10:05:00Z',
    criado_em: '2026-08-01T09:40:00Z',
  },
  {
    id: 'ex-grupo-2',
    pai_id: CAMPANHA_EXEMPLO.id,
    nome_interno: 'Conversão · Stories',
    match_id: 'G0002',
    nomenclatura: null,
    taxonomia_id: null,
    gerado_em: null,
    criado_em: '2026-08-01T09:50:00Z',
  },
  {
    id: 'ex-grupo-3',
    pai_id: CAMPANHA_EXEMPLO.id,
    nome_interno: 'Remarketing · Feed',
    match_id: 'G0003',
    nomenclatura: 'ALF_METAA_FEED_RMKT_C0001_G0003',
    taxonomia_id: 'ex-taxo-g3',
    gerado_em: '2026-08-02T08:15:00Z',
    criado_em: '2026-08-02T08:00:00Z',
  },
]

const ANUNCIOS_EXEMPLO: Record<string, NoDaArvore[]> = {
  'ex-grupo-1': [
    {
      id: 'ex-anuncio-1',
      pai_id: 'ex-grupo-1',
      nome_interno: 'Carrossel de produtos',
      match_id: 'A0001',
      nomenclatura: 'ALF_METAA_FEED_CV_CARROSSEL_C0001_G0001_A0001',
      taxonomia_id: 'ex-taxo-a1',
      gerado_em: '2026-08-01T10:10:00Z',
      criado_em: '2026-08-01T10:00:00Z',
    },
    {
      id: 'ex-anuncio-2',
      pai_id: 'ex-grupo-1',
      nome_interno: 'Vídeo depoimento',
      match_id: 'A0002',
      nomenclatura: null,
      taxonomia_id: null,
      gerado_em: null,
      criado_em: '2026-08-01T10:20:00Z',
    },
  ],
}

const CENARIOS_ARVORE = [
  { valor: 'preenchida', rotulo: 'Estrutura preenchida' },
  { valor: 'vazia', rotulo: 'Campanha sem grupo' },
  { valor: 'sem-campanha', rotulo: 'Nenhuma campanha salva' },
  { valor: 'carregando', rotulo: 'Carregando' },
  { valor: 'erro', rotulo: 'Erro ao carregar' },
] as const

type CenarioArvore = (typeof CENARIOS_ARVORE)[number]['valor']

function ArvoreExemplo() {
  const [cenario, setCenario] = useState<CenarioArvore>('preenchida')

  let grupos: NoDaArvore[] = []
  let anunciosPorGrupo: Record<string, NoDaArvore[]> = {}
  let carregando = false
  let erro: string | null = null

  if (cenario === 'preenchida') {
    grupos = GRUPOS_EXEMPLO
    anunciosPorGrupo = ANUNCIOS_EXEMPLO
  } else if (cenario === 'carregando') {
    carregando = true
  } else if (cenario === 'erro') {
    erro = 'Não foi possível carregar os grupos desta campanha.'
  }

  return (
    <div className="pilha" data-espaco="4">
      <Selecao
        rotulo="Cenário"
        valor={cenario}
        opcoes={CENARIOS_ARVORE.map((c) => ({ valor: c.valor, rotulo: c.rotulo }))}
        aoMudar={(valor) => setCenario(valor as CenarioArvore)}
      />
      <ArvoreCampanha
        campanha={cenario === 'sem-campanha' ? null : CAMPANHA_EXEMPLO}
        grupos={grupos}
        anunciosPorGrupo={anunciosPorGrupo}
        carregando={carregando}
        erro={erro}
        aoNovoGrupo={() => {}}
        aoNovoAnuncio={() => {}}
      />
    </div>
  )
}

/* ===========================================================================
   Barra de preview
   =========================================================================== */

const NOMENCLATURA_OK = 'ALF_METAA_FEED_CV_C0001'
const RESULTADO_OK: PreviewResposta = {
  nomenclatura: NOMENCLATURA_OK,
  match_id_provisorio: true,
  template_versao: 3,
  limite_caracteres: 60,
  caracteres: NOMENCLATURA_OK.length,
}

const NOMENCLATURA_PERTO_DO_LIMITE = 'ALF_METAA_FEED_CV_REMARKETING_BF_C0001'
const RESULTADO_PERTO_DO_LIMITE: PreviewResposta = {
  nomenclatura: NOMENCLATURA_PERTO_DO_LIMITE,
  match_id_provisorio: false,
  template_versao: 3,
  limite_caracteres: 40,
  caracteres: NOMENCLATURA_PERTO_DO_LIMITE.length,
}

const ERRO_PREVIEW: ErroApi = {
  erro: 'termo_nao_cadastrado',
  mensagem: 'Termo "Reels" não encontrado no dicionário de posicionamento.',
  campo: 'posicionamento',
  opcoes: ['IGST', 'IGFD', 'FBFD'],
}

function PreviewExemplo() {
  return (
    <div className="pilha" data-espaco="6">
      <div className="grade" data-base="larga">
        <div className="pilha" data-espaco="2">
          <p className="rotulo-secao">Vazio</p>
          <Preview resultado={null} erro={null} carregando={false} />
        </div>
        <div className="pilha" data-espaco="2">
          <p className="rotulo-secao">Gerando</p>
          <Preview resultado={null} erro={null} carregando />
        </div>
        <div className="pilha" data-espaco="2">
          <p className="rotulo-secao">Preenchido</p>
          <Preview resultado={RESULTADO_OK} erro={null} carregando={false} />
        </div>
        <div className="pilha" data-espaco="2">
          <p className="rotulo-secao">Perto do limite</p>
          <Preview resultado={RESULTADO_PERTO_DO_LIMITE} erro={null} carregando={false} />
        </div>
        <div className="pilha" data-espaco="2">
          <p className="rotulo-secao">Erro do servidor</p>
          <Preview resultado={null} erro={ERRO_PREVIEW} carregando={false} />
        </div>
      </div>

      <div className="pilha" data-espaco="2">
        <p className="rotulo-secao">Logo de plataforma sobre a superfície invertida</p>
        <div className="preview-barra" data-estado="ok">
          <p className="preview-titulo">Verificação de contraste</p>
          <p className="preview-medida">
            Colorido — <LogoPlataforma sigla="TIKTOK" tamanho="lg" titulo="TikTok, colorido" /> o
            traço central usa --logo-tiktok-tinta (#010101), quase preto sobre --card-inverso: some.
          </p>
          <p className="preview-medida">
            Mono — <LogoPlataforma sigla="TIKTOK" tamanho="lg" mono titulo="TikTok, monocromático" />{' '}
            herda `currentColor` de `.preview-medida` e volta a ficar legível.
          </p>
        </div>
      </div>
    </div>
  )
}

export const EXEMPLOS: Exemplo[] = [
  {
    id: 'componentes-botao',
    titulo: 'Botão',
    nota: 'Observe a largura no estado carregando: o rótulo continua ocupando espaço e o botão não encolhe sob o ponteiro. Use `hero` só na ação primária da splash.',
    render: () => <Botoes />,
  },
  {
    id: 'componentes-selo',
    titulo: 'Selo',
    nota: 'Selo classifica, não age. Se precisar ser clicável, o componente certo é botão ou filtro.',
    render: () => <Selos />,
  },
  {
    id: 'componentes-cartao-opcao',
    titulo: 'Cartão de opção',
    nota: 'O cartão indisponível é `aria-disabled`, não `disabled`: continua alcançável por Tab, sem hover e sem cursor proibido — o usuário não errou nada.',
    render: () => <Cartoes />,
  },
  {
    id: 'componentes-campo',
    titulo: 'Campo de formulário',
    nota: 'O erro vem do motor, não do cliente: `aria-invalid` marca o campo que o servidor apontou e `aria-describedby` liga a mensagem, com as opções aceitas quando existem.',
    render: () => <Campos />,
  },
  {
    id: 'componentes-logo-plataforma',
    titulo: 'Logo de plataforma',
    nota: 'Marcas de terceiros: a cor vem dos tokens `--logo-*` e nunca vira cor de estado do produto. Sigla desconhecida cai na placa com iniciais — plataforma nova cadastrada no banco não pode quebrar a tela. Use `mono` em lista densa, onde quatro marcas coloridas competiriam com o dado.',
    render: () => <Logos />,
  },
  {
    id: 'componentes-icone-nivel',
    titulo: 'Ícone de nível',
    nota: 'Campanha, grupo e anúncio na mesma grade e no mesmo peso de traço. O teste que importa é a linha de 16px: se os três não se distinguirem ali, o desenho está errado — é o tamanho da árvore da campanha.',
    render: () => <IconesDeNivel />,
  },
  {
    id: 'componentes-icone-interface',
    titulo: 'Ícone de interface',
    nota: 'Decorativos por padrão (`aria-hidden`): quase sempre acompanham um rótulo de texto e repetir a informação só faz o leitor de tela falar duas vezes. Passe `titulo` apenas quando o ícone estiver sozinho. O chevron é um desenho só girado por CSS, então recolher/expandir é a mesma peça em movimento.',
    render: () => <IconesDeInterface />,
  },
  {
    id: 'componentes-cromo',
    titulo: 'Barra de topo e rodapé utilitário',
    nota: 'Reduza a Largura do palco para "Estreito 360": abaixo de 480px de contêiner o wordmark "MDBuilder" some da barra e sobra só o símbolo, sem tocar em `@media` — a barra declara o próprio `@container` e resolve isolada aqui, sem depender da casca da tela real. O nome acessível do link continua completo no `aria-label`.',
    render: () => <Cromo />,
  },
  {
    id: 'componentes-arvore-campanha',
    titulo: 'Árvore da estrutura da campanha',
    nota: 'Um cenário por vez, trocado pelo seletor acima: campanha com três grupos (um sem nomenclatura ainda, um com anúncios) e os estados sem grupo, sem campanha, carregando e erro parcial. Clique no chevron de "Conversão · Stories" para recolher/expandir — é a mesma peça girando, não dois desenhos trocando de lugar. Sem editar nem excluir nomenclatura em nenhum cenário (D-004); só `match_id` aparece, nunca o `id`.',
    render: () => <ArvoreExemplo />,
  },
  {
    id: 'componentes-preview',
    titulo: 'Barra de preview',
    nota: 'Vazio, gerando, preenchido, perto do limite (contador em `data-tom="alerta"`) e erro — o erro não usa a superfície invertida, porque não existe token de erro para ela e vermelho aproximado no escuro reprova AA. No bloco de baixo, o logo colorido do TikTok fica quase invisível sobre `--card-inverso`: `--logo-tiktok-tinta` é #010101. Trocar para `mono` resolve porque o glifo passa a herdar a cor de texto do contêiner em vez de carregar a própria tinta.',
    render: () => <PreviewExemplo />,
  },
]
