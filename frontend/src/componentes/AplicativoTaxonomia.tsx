import { useEffect, useRef, useState } from 'react'

import { api } from '../api'
import { abasVisiveis, ROTULO_ABA, type AbaTaxonomia } from '../roteador'
import { useSessao } from '../sessao'
import type { Plataforma } from '../tipos'
import { AcessoNegado } from './AcessoNegado'
import { Dicionario } from './Dicionario'
import { Gerador } from './Gerador'
import { Historico } from './Historico'
import { VoltarPara } from './VoltarPara'

type Props = {
  aba: AbaTaxonomia
  aoTrocarAba: (aba: AbaTaxonomia) => void
}

/**
 * O aplicativo de taxonomia — o corpo histórico do `App.tsx`.
 *
 * Fica montado enquanto outras rotas estão na tela (D-005): sair para o
 * catálogo, para a splash ou para o seletor de assunto não pode descartar um
 * formulário meio preenchido. Quem esconde é o `App`, com `hidden`.
 */
export function AplicativoTaxonomia({ aba, aoTrocarAba }: Props) {
  const [plataformas, setPlataformas] = useState<Plataforma[]>([])
  const [erro, setErro] = useState<string | null>(null)
  // Incrementa ao sair da aba de dicionário, para o gerador recarregar as
  // drop lists sem perder o formulário que o analista já preencheu.
  const [versaoDicionario, setVersaoDicionario] = useState(0)
  const abaAnterior = useRef(aba)
  const { papel, permissoes } = useSessao()
  // Permissão ESCONDE (§4.1): para o `basico` a aba Dicionário não existe na
  // árvore — sem `disabled`, sem cadeado, sem tooltip.
  const abas = abasVisiveis(papel)

  useEffect(() => {
    api
      .plataformas()
      .then(setPlataformas)
      .catch((e) => setErro(`Não foi possível carregar as plataformas: ${e.message}`))
  }, [])

  // I-6: o bump não pode morar no clique da aba. A troca agora também vem da
  // URL e do botão voltar, então quem observa é a mudança do valor.
  useEffect(() => {
    if (abaAnterior.current === 'dicionario' && aba !== 'dicionario') {
      setVersaoDicionario((v) => v + 1)
    }
    abaAnterior.current = aba
  }, [aba])

  // Padrão APG de tabs: setas, Home e End percorrem a lista.
  function aoTeclar(evento: React.KeyboardEvent<HTMLButtonElement>) {
    // Percorre as abas VISÍVEIS: com o papel `basico` a lista tem duas, e o
    // roving tabindex não pode parar numa aba que não está na tela.
    const atual = abas.indexOf(aba)
    let destino = -1
    if (evento.key === 'ArrowRight') destino = (atual + 1) % abas.length
    if (evento.key === 'ArrowLeft') {
      destino = (atual - 1 + abas.length) % abas.length
    }
    if (evento.key === 'Home') destino = 0
    if (evento.key === 'End') destino = abas.length - 1
    if (destino < 0) return
    evento.preventDefault()
    aoTrocarAba(abas[destino])
    document.getElementById(`aba-${abas[destino]}`)?.focus()
  }

  return (
    // §7.2: a página não tem UMA largura máxima — cada tela recebe a que o seu
    // conteúdo justifica. Dicionário e Histórico são tabelas e ganham a
    // largura densa; Gerar é formulário e fica na padrão. Trocar de aba muda a
    // casca, não o conteúdo: o gerador continua montado atrás do `hidden`.
    <main
      className="pagina contexto-pagina pilha"
      data-largura={aba === 'gerar' ? undefined : 'densa'}
      data-espaco="6"
    >
      {/* ABA NÃO É TELA (§2.4). O `VoltarPara` mora AQUI, fora dos
          `tabpanel`, e não muda quando a aba muda: as abas são um sistema de
          organização DENTRO do assunto (Rosenfeld/Morville), e o Voltar opera
          ENTRE assuntos. Pelo mesmo motivo o `h1` é o nome do assunto —
          "Construção de taxonomia", o rótulo do cartão que trouxe a pessoa
          até aqui — e não o nome da aba ativa.

          Sair daqui com o formulário meio preenchido não descarta nada: o
          ramo é escondido com `hidden`, nunca desmontado (I-1). Por isso o
          link não pede confirmação.

          `data-foco-rota` no `<header>` e não no `h1`: com o link acima do
          título, focar o `h1` deixaria o Voltar atrás do ponto de foco, e o
          primeiro Tab pularia por cima dele. */}
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara de="assuntos" />
        <h1 className="titulo-tela">Construção de taxonomia</h1>
        <p className="marca-subtitulo">
          Nomenclaturas padronizadas para campanhas de mídia paga
        </p>
      </header>

      <nav className="abas" role="tablist" aria-label="Seções">
        {abas.map((id) => (
          <button
            key={id}
            id={`aba-${id}`}
            type="button"
            role="tab"
            className="aba"
            aria-selected={aba === id}
            aria-controls={`painel-${id}`}
            // Roving tabindex: só a aba ativa recebe Tab.
            tabIndex={aba === id ? 0 : -1}
            onClick={() => aoTrocarAba(id)}
            onKeyDown={aoTeclar}
          >
            {ROTULO_ABA[id]}
          </button>
        ))}
      </nav>

      {erro && (
        <div role="alert" className="aviso-erro">
          {erro}
        </div>
      )}

      {/* I-3: o gerador fica montado o tempo todo; sair para cadastrar um
          termo no dicionário não pode custar o formulário já preenchido. */}
      <div id="painel-gerar" role="tabpanel" aria-labelledby="aba-gerar" hidden={aba !== 'gerar'}>
        <Gerador plataformas={plataformas} versaoDicionario={versaoDicionario} />
      </div>

      {/* Quem digita `#/taxonomia/dicionario` sem permissão continua na tela
          de taxonomia, com as abas que tem, e lê por que não entra (§4.3).
          Redirecionar em silêncio se leria como bug; 404 seria mentira. */}
      {aba === 'dicionario' &&
        (permissoes.podeVerDicionario ? (
          <div id="painel-dicionario" role="tabpanel" aria-labelledby="aba-dicionario">
            <Dicionario plataformas={plataformas} />
          </div>
        ) : (
          // Sem `role="tabpanel"`: a aba correspondente não existe nesta
          // árvore, e um painel apontando para um `id` inexistente é pior
          // para o leitor de tela do que painel nenhum.
          <div id="painel-dicionario">
            <AcessoNegado titulo="Você não tem acesso ao Dicionário" papel={papel} />
          </div>
        ))}
      {aba === 'historico' && (
        <div id="painel-historico" role="tabpanel" aria-labelledby="aba-historico">
          <Historico plataformas={plataformas} />
        </div>
      )}
    </main>
  )
}

export default AplicativoTaxonomia
