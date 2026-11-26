import { useEffect, useId, useMemo, useRef, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import { substituir, useRota } from '../roteador'
import { usePermissao } from '../sessao'
import { contemBusca } from '../texto'
import type { Abreviacao, Plataforma } from '../tipos'
import { Botao, Estado } from './ui'

interface Props {
  plataformas: Plataforma[]
}

/**
 * Administração das drop lists — a aba "Dicionario" da planilha do cliente.
 *
 * É a contrapartida do D-005: o motor recusa um termo que não existe e manda
 * cadastrar, então cadastrar não pode depender de desenvolvedor.
 *
 * A BUSCA É LOCAL (§6.1). `api.dicionarioCompleto()` já carrega tudo na
 * montagem e o dicionário tem ordem de centenas de linhas: filtrar o array
 * roda em fração de milissegundo. Ir ao servidor custaria latência a cada
 * tecla e obrigaria a duplicar a regra de acento em SQL, que é onde moram os
 * bugs de `unaccent`/collation. Gatilho para revisar: se `entradas.length`
 * passar de ~2000, a busca migra para o servidor mantendo o mesmo contrato de
 * URL. Contraste deliberado com o Histórico, que filtra no servidor e deve
 * continuar assim — ele é ilimitado e recortado por data.
 *
 * SEM DEBOUNCE NO FILTRO (§6.4). Atrasar de propósito o que é imediato só
 * produz sensação de travamento. Os 300 ms existem para dois efeitos
 * colaterais: gravar `?q=` na URL e anunciar a contagem no `role="status"` —
 * sem isso o leitor de tela é metralhado a cada tecla.
 */
export function Dicionario({ plataformas }: Props) {
  const permissoes = usePermissao()
  const rota = useRota()

  /* --- entrada pela URL (§6.5) ------------------------------------------
     Lido UMA vez, como valor inicial de estado: o React descarta o argumento
     de `useState` depois do primeiro render, então não há efeito, não há
     `setState` durante o render e não há briga com o `substituir()` de baixo.
     Depois da montagem quem manda é o que a pessoa digitou.

     O ganho concreto: o erro do Preview (`Termo "X" não cadastrado`) linka
     `#/taxonomia/dicionario?q=X`, e a tela já abre filtrada E com o campo De
     preenchido — quem chegou por ali quer digitar o Para, não redigitar o
     termo que o motor acabou de recusar. */
  const qInicial = rota.nome === 'taxonomia' ? (rota.params.get('q') ?? '') : ''
  const catInicial = rota.nome === 'taxonomia' ? (rota.params.get('cat') ?? '') : ''

  const [entradas, setEntradas] = useState<Abreviacao[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  // Formulário de criação.
  const [categoria, setCategoria] = useState('')
  const [termo, setTermo] = useState(qInicial)
  const [abreviacao, setAbreviacao] = useState('')
  const [plataformaId, setPlataformaId] = useState('')
  const [novaCategoria, setNovaCategoria] = useState('')
  const [salvando, setSalvando] = useState(false)

  // Busca e recorte da lista.
  const [busca, setBusca] = useState(qInicial)
  const [categoriaFiltro, setCategoriaFiltro] = useState(catInicial)
  const [contagemAnunciada, setContagemAnunciada] = useState('')

  // Edição inline e remoção.
  const [editando, setEditando] = useState<{ id: string; valor: string } | null>(null)
  const [aRemover, setARemover] = useState<Abreviacao | null>(null)

  const idBusca = useId()
  const idCategoriaFiltro = useId()
  const idCategoria = useId()
  const idNova = useId()
  const idTermo = useId()
  const idAbrev = useId()
  const idPlataforma = useId()
  const campoTermo = useRef<HTMLInputElement>(null)
  const campoAbrev = useRef<HTMLInputElement>(null)
  const dialogoRemover = useRef<HTMLDialogElement>(null)

  async function recarregar() {
    setCarregando(true)
    try {
      setEntradas(await api.dicionarioCompleto())
      setErro(null)
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    void recarregar()
  }, [])

  const categorias = useMemo(
    () => [...new Set(entradas.map((e) => e.categoria))].sort(),
    [entradas],
  )

  const nomePlataforma = useMemo(() => {
    const mapa = new Map(plataformas.map((p) => [p.id, p.nome]))
    return (id: string | null) => (id ? (mapa.get(id) ?? '—') : 'Todas')
  }, [plataformas])

  /* Filtro é RECORTE, busca é PROCURA: combinam por E, não por OU (§6.2).
     A categoria entra na busca porque a pergunta real do analista é
     frequentemente "que abreviações existem em objetivo?", e digitar
     `objetivo` é mais rápido que caçar o valor num `<select>`. */
  const visiveis = entradas.filter((e) => {
    if (categoriaFiltro && e.categoria !== categoriaFiltro) return false
    if (!busca.trim()) return true
    return (
      contemBusca(e.termo, busca) ||
      contemBusca(e.abreviacao, busca) ||
      contemBusca(e.categoria, busca)
    )
  })

  /* Os 300 ms (§6.4) valem SÓ para os dois efeitos colaterais: gravar `?q=` na
     URL e anunciar a contagem. O filtro em si não espera nada.

     `substituir()` (replaceState) e não `location.hash =`: cada tecla virando
     entrada no histórico deixaria o botão voltar do navegador inútil.

     Só escreve enquanto a aba do dicionário está na tela — o componente é
     desmontado ao trocar de aba, mas um timer em voo ainda poderia reescrever
     a URL da aba seguinte; o `clearTimeout` do cleanup fecha esse buraco. */
  useEffect(() => {
    const timer = setTimeout(() => {
      const params = new URLSearchParams()
      if (busca.trim()) params.set('q', busca.trim())
      if (categoriaFiltro) params.set('cat', categoriaFiltro)
      const query = params.toString()
      substituir(`#/taxonomia/dicionario${query ? `?${query}` : ''}`)
      setContagemAnunciada(
        busca.trim() || categoriaFiltro
          ? `${visiveis.length} de ${entradas.length} termos`
          : `${entradas.length} termos`,
      )
    }, 300)
    return () => clearTimeout(timer)
    // `visiveis` é derivado dos três valores abaixo; incluí-lo na lista só
    // trocaria a comparação de três primitivos por a de um array novo a cada
    // render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busca, categoriaFiltro, entradas.length])

  const categoriaEfetiva = (novaCategoria.trim() || categoria).trim()
  const podeSalvar =
    categoriaEfetiva !== '' && termo.trim() !== '' && abreviacao.trim() !== '' && !salvando

  async function adicionar(evento: React.FormEvent) {
    evento.preventDefault()
    setSalvando(true)
    setErro(null)
    try {
      await api.criarAbreviacao({
        categoria: categoriaEfetiva,
        termo: termo.trim(),
        abreviacao: abreviacao.trim(),
        plataforma_id: plataformaId || undefined,
      })
      setTermo('')
      setAbreviacao('')
      setNovaCategoria('')
      if (!categoria) setCategoria(categoriaEfetiva)
      await recarregar()
    } catch (e) {
      setErro(
        e instanceof ErroRequisicao ? e.corpo.mensagem : `Não foi possível adicionar: ${String(e)}`,
      )
    } finally {
      setSalvando(false)
    }
  }

  /* Edição INLINE, não `window.prompt` (§6.7). O prompt não é estilizável, não
     é anunciado direito por leitor de tela, bloqueia a aba inteira e some com
     o contexto da linha que está sendo editada. O único campo editável é
     `abreviacao`, igual à API. */
  async function salvarEdicao() {
    if (!editando) return
    const valor = editando.valor.trim()
    if (!valor) return
    try {
      await api.atualizarAbreviacao(editando.id, valor)
      setEditando(null)
      await recarregar()
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : String(e))
    }
  }

  async function confirmarRemocao() {
    if (!aRemover) return
    const alvo = aRemover
    setARemover(null)
    try {
      await api.removerAbreviacao(alvo.id)
      await recarregar()
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : String(e))
    }
  }

  // `<dialog>` nativo: fundo, trap de foco e `inert` vêm do navegador — focus
  // trap escrito à mão é onde nascem os bugs de acessibilidade.
  useEffect(() => {
    const elemento = dialogoRemover.current
    if (!elemento) return
    if (aRemover && !elemento.open) {
      if (typeof elemento.showModal === 'function') elemento.showModal()
      else elemento.setAttribute('open', '')
    }
    if (!aRemover && elemento.open) {
      if (typeof elemento.close === 'function') elemento.close()
      else elemento.removeAttribute('open')
    }
  }, [aRemover])

  /** Fecha o ciclo erro → busca → cadastro sem redigitar (§6.6). */
  function cadastrarBuscado() {
    setTermo(busca.trim())
    campoAbrev.current?.focus()
  }

  const filtrando = Boolean(busca.trim()) || Boolean(categoriaFiltro)

  return (
    <div className="pilha" data-espaco="5">
      {/* Criar e procurar são conversas diferentes: a busca NÃO fica aqui, e
          sim no cabeçalho da seção da lista (Jarrett & Gaffney). */}
      <section className="card bloco pilha" data-espaco="4">
        <div className="pilha" data-espaco="1">
          <h2 className="rotulo-secao">Adicionar termo</h2>
          <p className="texto-auxiliar medida">
            Cada termo é um par <strong>De → Para</strong>. O "De" é o que o analista escolhe na
            tela; o "Para" é o que entra na nomenclatura.
          </p>
        </div>

        {/* `.grade.campos` (formulário), não `.filtros`: são coisas
            diferentes, e reaproveitar a classe de filtro aqui reintroduziria
            no CSS a confusão que a tela acabou de desfazer no layout. */}
        <form className="grade campos" onSubmit={(e) => void adicionar(e)}>
          <div>
            <label htmlFor={idCategoria}>Categoria</label>
            <select
              id={idCategoria}
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
            >
              <option value="">Selecione…</option>
              {categorias.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor={idNova}>ou categoria nova</label>
            <input
              id={idNova}
              value={novaCategoria}
              placeholder="ex.: produto"
              onChange={(e) => setNovaCategoria(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor={idTermo}>De</label>
            <input
              id={idTermo}
              ref={campoTermo}
              value={termo}
              placeholder="Conversão"
              onChange={(e) => setTermo(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor={idAbrev}>Para</label>
            <input
              id={idAbrev}
              ref={campoAbrev}
              value={abreviacao}
              placeholder="CONV"
              onChange={(e) => setAbreviacao(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor={idPlataforma}>Vale para</label>
            <select
              id={idPlataforma}
              value={plataformaId}
              onChange={(e) => setPlataformaId(e.target.value)}
            >
              <option value="">Todas as plataformas</option>
              {plataformas.map((p) => (
                <option key={p.id} value={p.id}>
                  Só {p.nome}
                </option>
              ))}
            </select>
          </div>

          <div className="linha" data-alinhar="base">
            <Botao type="submit" disabled={!podeSalvar} carregando={salvando}>
              Adicionar
            </Botao>
          </div>
        </form>
      </section>

      {erro && (
        <div role="alert" className="aviso-erro">
          {erro}
        </div>
      )}

      <section className="card bloco pilha" data-espaco="4">
        <div className="cabecalho-lista">
          <h2 className="rotulo-secao">
            Termos
            <span className="contador-lista">
              {' '}
              ·{' '}
              {filtrando
                ? `${visiveis.length} de ${entradas.length} termos`
                : `${entradas.length} termos`}
            </span>
          </h2>

          <div className="filtros-acoes">
            <div className="campo-busca">
              <label className="apenas-leitor" htmlFor={idBusca}>
                Buscar termo
              </label>
              <input
                id={idBusca}
                type="search"
                value={busca}
                placeholder="conversão, CV, objetivo"
                onChange={(e) => setBusca(e.target.value)}
              />
              {busca && (
                <Botao variante="fantasma" tamanho="sm" onClick={() => setBusca('')}>
                  Limpar busca
                </Botao>
              )}
            </div>

            <div>
              <label className="apenas-leitor" htmlFor={idCategoriaFiltro}>
                Categoria da lista
              </label>
              <select
                id={idCategoriaFiltro}
                value={categoriaFiltro}
                onChange={(e) => setCategoriaFiltro(e.target.value)}
              >
                <option value="">Todas as categorias</option>
                {categorias.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* A contagem sai por live region com 300 ms de atraso — sem isso, o
            leitor de tela é metralhado a cada tecla. */}
        <span className="apenas-leitor" role="status" aria-live="polite">
          {contagemAnunciada}
        </span>

        {carregando ? (
          <p className="texto-auxiliar">Carregando…</p>
        ) : entradas.length === 0 ? (
          // Vazio ABSOLUTO: o dicionário não tem termo nenhum.
          <Estado
            tipo="vazio"
            titulo="Nenhum termo cadastrado ainda."
            texto="O gerador recusa termos que não estão aqui. Comece cadastrando o primeiro acima."
          />
        ) : visiveis.length === 0 && busca.trim() ? (
          // Vazio de BUSCA — distinto do anterior, e a diferença é a informação.
          <Estado tipo="sem-resultado" titulo={`Nenhum termo com "${busca.trim()}".`}>
            <div className="linha">
              <Botao variante="secundario" onClick={() => setBusca('')}>
                Limpar busca
              </Botao>
              {/* O item de maior valor da tela: fecha o ciclo erro → busca →
                  cadastro sem redigitar. */}
              <Botao onClick={cadastrarBuscado}>Cadastrar "{busca.trim()}"</Botao>
            </div>
          </Estado>
        ) : visiveis.length === 0 ? (
          // Vazio de CATEGORIA: existe termo, só não nesta gaveta.
          <Estado tipo="sem-resultado" titulo={`Nenhum termo em "${categoriaFiltro}".`}>
            <div className="linha">
              <Botao variante="secundario" onClick={() => setCategoriaFiltro('')}>
                Ver todas as categorias
              </Botao>
            </div>
          </Estado>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela" data-densidade="alta">
              <caption className="apenas-leitor">Termos do dicionário de abreviações</caption>
              <thead>
                <tr>
                  <th className="tabela-celula" scope="col">
                    Categoria
                  </th>
                  <th className="tabela-celula" data-coluna="principal" scope="col">
                    De
                  </th>
                  <th className="tabela-celula" scope="col">
                    Para
                  </th>
                  <th className="tabela-celula" scope="col">
                    Vale para
                  </th>
                  <th className="tabela-celula" data-coluna="acao" scope="col">
                    <span className="apenas-leitor">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visiveis.map((e) => (
                  <tr key={e.id}>
                    <td className="tabela-celula">{e.categoria}</td>
                    <td className="tabela-celula" data-coluna="principal">
                      {e.termo}
                    </td>
                    <td className="tabela-celula mono">
                      {editando?.id === e.id ? (
                        <>
                          <label className="apenas-leitor" htmlFor={`${idAbrev}-edit`}>
                            Abreviação de {e.termo}
                          </label>
                          <input
                            id={`${idAbrev}-edit`}
                            autoFocus
                            value={editando.valor}
                            onChange={(ev) =>
                              setEditando({ id: e.id, valor: ev.target.value })
                            }
                            onKeyDown={(ev) => {
                              if (ev.key === 'Enter') void salvarEdicao()
                              if (ev.key === 'Escape') setEditando(null)
                            }}
                          />
                        </>
                      ) : (
                        <strong>{e.abreviacao}</strong>
                      )}
                    </td>
                    <td className="tabela-celula">{nomePlataforma(e.plataforma_id)}</td>
                    <td className="tabela-celula" data-coluna="acao">
                      {editando?.id === e.id ? (
                        <span className="linha" data-espaco="2">
                          <Botao tamanho="sm" onClick={() => void salvarEdicao()}>
                            Salvar
                          </Botao>
                          <Botao
                            variante="fantasma"
                            tamanho="sm"
                            onClick={() => setEditando(null)}
                          >
                            Cancelar
                          </Botao>
                        </span>
                      ) : (
                        <span className="linha" data-espaco="2">
                          <Botao
                            variante="secundario"
                            tamanho="sm"
                            onClick={() => setEditando({ id: e.id, valor: e.abreviacao })}
                          >
                            Editar
                          </Botao>
                          {/* Permissão ESCONDE (§4.1): sem `podeExcluir` o
                              botão não existe — nada de `disabled` com "sem
                              permissão", que é motivo sobre o qual ninguém
                              pode agir. */}
                          {permissoes.podeExcluir && (
                            <Botao
                              variante="perigo"
                              tamanho="sm"
                              onClick={() => setARemover(e)}
                            >
                              Remover
                            </Botao>
                          )}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* `<dialog>` nomeando o termo, no lugar do `window.confirm` (§6.7): o
          confirm não diz qual linha está sendo removida nem o que a remoção
          não faz. */}
      <dialog
        className="dialogo"
        ref={dialogoRemover}
        aria-label="Remover termo"
        onCancel={(e) => {
          e.preventDefault()
          setARemover(null)
        }}
      >
        {aRemover && (
          <div className="pilha" data-espaco="5">
            <h2 className="painel-titulo">
              Remover "{aRemover.termo}" de {aRemover.categoria}?
            </h2>
            <p className="texto-auxiliar">
              Termos já usados em nomenclaturas geradas não são afetados — elas são imutáveis
              (D-004). O que muda é que novas gerações deixam de aceitar este termo.
            </p>
            <div className="linha" data-alinhar="fim">
              <Botao variante="fantasma" onClick={() => setARemover(null)}>
                Cancelar
              </Botao>
              <Botao variante="perigo" onClick={() => void confirmarRemocao()}>
                Remover termo
              </Botao>
            </div>
          </div>
        )}
      </dialog>
    </div>
  )
}
