import { useId, useState } from 'react'

import type { NoDaArvore } from '../tipos'
import { IconeChevron, IconeMais, IconeNivel } from './icones'
import { Botao, Giro } from './ui'

export interface CampanhaCorrente {
  id: string
  match_id: string
  nome_interno: string
}

interface Props {
  /** Nula até a primeira campanha ser salva — o cartão continua na coluna. */
  campanha: CampanhaCorrente | null
  grupos: NoDaArvore[]
  anunciosPorGrupo: Record<string, NoDaArvore[]>
  carregando: boolean
  erro: string | null
  aoNovoGrupo: () => void
  aoNovoAnuncio: (grupoId: string) => void
}

/**
 * O 1→N que o banco sempre teve e a tela não mostrava: uma campanha com
 * vários grupos, cada grupo com vários anúncios.
 *
 * É a coluna de contexto da aba Gerar: um resumo do que já existe na campanha
 * corrente, com as duas ações que faltavam — outro grupo na mesma campanha e
 * outro anúncio num grupo escolhido. Quem preenche continua sendo o
 * formulário da coluna larga.
 *
 * Não há botão de editar nem de excluir nomenclatura: taxonomia é imutável
 * (D-004) e o caminho de correção é regerar. `match_id` aparece; o `id`
 * (UUID) nunca — nem como texto, nem em `aria-label`.
 */
export function ArvoreCampanha({
  campanha,
  grupos,
  anunciosPorGrupo,
  carregando,
  erro,
  aoNovoGrupo,
  aoNovoAnuncio,
}: Props) {
  // Ids gerados por instância: o catálogo de componentes monta várias
  // árvores na mesma página, e um id literal duplicaria entre elas — o
  // segundo `aria-labelledby`/`aria-controls` passaria a apontar para o
  // elemento da PRIMEIRA instância no documento, não para o da própria seção.
  const idTitulo = useId()
  const idBaseFilhos = useId()

  // Recolher é estado de leitura, e mora aqui: ninguém acima precisa dele.
  // O padrão é aberto — o analista acabou de criar o que está na lista.
  const [recolhidos, setRecolhidos] = useState<Record<string, boolean>>({})

  const alternar = (grupoId: string) =>
    setRecolhidos((atual) => ({ ...atual, [grupoId]: !atual[grupoId] }))

  return (
    <section className="card bloco pilha arvore-cartao" data-espaco="4" aria-labelledby={idTitulo}>
      <header className="linha" data-espaco="3" data-alinhar="entre">
        <h2 id={idTitulo} className="rotulo-secao">
          Estrutura da campanha
        </h2>
        {/* Sem campanha salva não há a que pendurar um grupo. O botão fica
            desabilitado em vez de sumir: quem chega na tela precisa ver que
            a ação existe. */}
        <Botao tamanho="sm" onClick={aoNovoGrupo} disabled={!campanha}>
          <IconeMais /> Novo grupo
        </Botao>
      </header>

      {erro && (
        <p className="texto-auxiliar" role="status">
          {erro}
        </p>
      )}

      {!campanha ? (
        <p className="texto-auxiliar">
          A estrutura aparece aqui assim que a primeira campanha for salva.
        </p>
      ) : (
        <>
          <p className="arvore-no" data-nivel="campanha">
            {/* Ícone decorativo: quem nomeia o nível é o título do cartão e o
                `aria-label` da lista de filhos, não uma repetição por linha. */}
            <IconeNivel nivel="CAMPANHA" tamanho="sm" />
            <span className="arvore-nome">{campanha.nome_interno}</span>
            <span className="arvore-codigo">{campanha.match_id}</span>
          </p>

          {carregando && grupos.length === 0 ? (
            <p className="texto-auxiliar">
              <Giro /> Carregando a estrutura…
            </p>
          ) : grupos.length === 0 ? (
            <p className="texto-auxiliar">Esta campanha ainda não tem grupo de anúncio.</p>
          ) : (
            <ul
              className="arvore-lista"
              aria-label={`Grupos de ${campanha.nome_interno}`}
              aria-busy={carregando || undefined}
            >
              {grupos.map((grupo) => {
                const anuncios = anunciosPorGrupo[grupo.id] ?? []
                const aberto = !recolhidos[grupo.id]
                const idFilhos = `${idBaseFilhos}-${grupo.match_id}`

                return (
                  <li key={grupo.id} className="pilha" data-espaco="2">
                    <div className="arvore-no" data-nivel="grupo">
                      {/* Um botão de expandir por grupo: sem nome distinto
                          seriam N "Expandir" idênticos na mesma lista. */}
                      <button
                        type="button"
                        className="arvore-botao"
                        aria-expanded={aberto}
                        aria-controls={anuncios.length > 0 ? idFilhos : undefined}
                        aria-label={
                          aberto
                            ? `Recolher anúncios de ${grupo.nome_interno}`
                            : `Expandir anúncios de ${grupo.nome_interno}`
                        }
                        onClick={() => alternar(grupo.id)}
                      >
                        <IconeChevron sentido={aberto ? 'baixo' : 'direita'} />
                      </button>

                      <IconeNivel nivel="GRUPO" tamanho="sm" />
                      <span className="arvore-nome">{grupo.nome_interno}</span>
                      <span className="arvore-codigo">{grupo.match_id}</span>

                      {/* O nome acessível contém o rótulo visível (WCAG 2.5.3)
                          — aqui o rótulo visível é só o ícone, então o nome
                          carrega o grupo inteiro. */}
                      <span className="empurra">
                        <button
                          type="button"
                          className="arvore-botao"
                          data-acao="adicionar"
                          aria-label={`Novo anúncio em ${grupo.nome_interno}`}
                          onClick={() => aoNovoAnuncio(grupo.id)}
                        >
                          <IconeMais />
                        </button>
                      </span>
                    </div>

                    {grupo.nomenclatura ? (
                      <code className="arvore-nomenclatura">{grupo.nomenclatura}</code>
                    ) : (
                      <span className="texto-auxiliar">Sem nomenclatura gerada.</span>
                    )}

                    {anuncios.length > 0 && aberto && (
                      <ul
                        id={idFilhos}
                        className="arvore-lista"
                        data-nivel="anuncio"
                        aria-label={`Anúncios de ${grupo.nome_interno}`}
                      >
                        {anuncios.map((anuncio) => (
                          <li key={anuncio.id} className="pilha" data-espaco="1">
                            <div className="arvore-no" data-nivel="anuncio">
                              <IconeNivel nivel="ANUNCIO" tamanho="sm" />
                              <span className="arvore-nome">{anuncio.nome_interno}</span>
                              <span className="arvore-codigo">{anuncio.match_id}</span>
                            </div>
                            {anuncio.nomenclatura ? (
                              <code className="arvore-nomenclatura">{anuncio.nomenclatura}</code>
                            ) : (
                              <span className="texto-auxiliar">Sem nomenclatura gerada.</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
