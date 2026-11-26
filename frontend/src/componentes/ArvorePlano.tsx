import { useEffect, useId, useState } from 'react'

import { type CorpoRateio, ErroRequisicao, api } from '../api'
import type {
  CampanhaDoPlano,
  CampoRateioNome,
  Entidade,
  GrupoDoPlano,
  Metrica,
  PlanoMidia,
} from '../tipos'
import { CampoRateio } from './CampoRateio'
import { DivergenciaNome } from './DivergenciaNome'
import { formatarMoedaComPrefixo, paraNumero } from './formatoPlano'
import { IconeChevron, IconeNivel } from './icones'
import { SeletorEntidadeExistente } from './SeletorEntidadeExistente'
import { SeloDesbalanco } from './SeloDesbalanco'
import { Giro } from './ui'

interface Props {
  plano: PlanoMidia
  metricas: Metrica[]
  aoAtualizarPlano: () => Promise<void>
  aoMudarFoco: (campanhaId: string | null, grupoId: string | null) => void
}

/**
 * `AdicionarLinha` — busca as entidades candidatas só quando o combobox é
 * de fato aberto (I-6-like: não paga custo de rede por linha que ninguém
 * vai expandir) e filtra as que já estão na árvore.
 */
function AdicionarLinha({
  rotulo,
  jaAdicionados,
  buscar,
  aoAdicionar,
}: {
  rotulo: string
  jaAdicionados: Set<string>
  buscar: () => Promise<Entidade[]>
  aoAdicionar: (entidade: Entidade) => Promise<void>
}) {
  const [candidatos, setCandidatos] = useState<Entidade[] | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let cancelado = false
    setCarregando(true)
    buscar()
      .then((r) => {
        if (!cancelado) setCandidatos(r)
      })
      .catch(() => {
        if (!cancelado) setCandidatos([])
      })
      .finally(() => {
        if (!cancelado) setCarregando(false)
      })
    return () => {
      cancelado = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const disponiveis = (candidatos ?? []).filter((c) => !jaAdicionados.has(c.id))

  return (
    <div className="pilha" data-espaco="1">
      <SeletorEntidadeExistente
        rotulo={rotulo}
        candidatos={disponiveis}
        carregando={carregando}
        aoSelecionar={(entidade) => {
          setErro(null)
          void aoAdicionar(entidade).catch((e) => {
            setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível adicionar.')
          })
        }}
      />
      {erro && (
        <p className="texto-auxiliar" data-tom="alerta" role="alert">
          {erro}
        </p>
      )}
    </div>
  )
}

/**
 * Árvore editável do plano (§4.1) — generaliza `ArvoreCampanha` para N
 * campanhas em paralelo e para nós EDITÁVEIS, não só leitura. Cada nó
 * carrega o controle de rateio duplo (`CampoRateio`), o aviso de
 * nomenclatura desatualizada (`DivergenciaNome`) e o resumo de
 * soma/diferença dos filhos (`SeloDesbalanco`) — nunca bloqueia edição,
 * mesmo com o nível acima desbalanceado (D-B).
 */
export function ArvorePlano({ plano, metricas, aoAtualizarPlano, aoMudarFoco }: Props) {
  const idBase = useId()
  const [recolhidosCampanha, setRecolhidosCampanha] = useState<Record<string, boolean>>({})
  const [recolhidosGrupo, setRecolhidosGrupo] = useState<Record<string, boolean>>({})

  const idsCampanhaNoPlano = new Set(plano.campanhas.map((c) => c.campanha_id))

  async function salvarRateioCampanha(linha: CampanhaDoPlano, campo: CampoRateioNome, texto: string) {
    await api.planos.atualizarCampanha(plano.id, linha.id, { [campo]: texto } as CorpoRateio)
    await aoAtualizarPlano()
  }

  async function salvarRateioGrupo(
    campanha: CampanhaDoPlano,
    linha: GrupoDoPlano,
    campo: CampoRateioNome,
    texto: string,
  ) {
    await api.planos.atualizarGrupo(plano.id, campanha.id, linha.id, { [campo]: texto } as CorpoRateio)
    await aoAtualizarPlano()
  }

  async function salvarRateioAnuncio(
    campanha: CampanhaDoPlano,
    grupo: GrupoDoPlano,
    linhaId: string,
    campo: CampoRateioNome,
    texto: string,
  ) {
    await api.planos.atualizarAnuncio(plano.id, campanha.id, grupo.id, linhaId, {
      [campo]: texto,
    } as CorpoRateio)
    await aoAtualizarPlano()
  }

  return (
    <section className="card bloco pilha contexto plano-arvore-cartao" data-espaco="4">
      <header className="linha" data-alinhar="entre">
        <h2 className="rotulo-secao">Campanhas do plano</h2>
      </header>

      {plano.campanhas.length === 0 ? (
        <p className="texto-auxiliar">
          Adicione uma campanha para começar a ratear a verba.
        </p>
      ) : (
        <ul className="arvore-lista plano-arvore" aria-label="Campanhas do plano">
          {plano.campanhas.map((campanha) => {
            const abertaCampanha = !recolhidosCampanha[campanha.id]
            const idFilhosCampanha = `${idBase}-grupos-${campanha.id}`

            return (
              <li key={campanha.id} className="pilha" data-espaco="2">
                <div
                  className="arvore-no plano-no"
                  data-nivel="campanha"
                  onFocus={() => aoMudarFoco(campanha.id, null)}
                >
                  <button
                    type="button"
                    className="arvore-botao"
                    aria-expanded={abertaCampanha}
                    aria-controls={idFilhosCampanha}
                    aria-label={
                      abertaCampanha
                        ? `Recolher ${campanha.nome_interno}`
                        : `Expandir ${campanha.nome_interno}`
                    }
                    onClick={() => {
                      setRecolhidosCampanha((r) => ({ ...r, [campanha.id]: !r[campanha.id] }))
                      aoMudarFoco(campanha.id, null)
                    }}
                  >
                    <IconeChevron sentido={abertaCampanha ? 'baixo' : 'direita'} />
                  </button>
                  <IconeNivel nivel="CAMPANHA" tamanho="sm" />
                  <span className="arvore-nome">{campanha.nome_interno}</span>
                  <span className="arvore-codigo">{campanha.match_id}</span>
                  <DivergenciaNome
                    nomenclaturaSnapshot={campanha.nomenclatura}
                    nomenclaturaAtual={campanha.nomenclatura_atual}
                    divergente={campanha.nomenclatura_divergente}
                    aoAtualizarSnapshot={async () => {
                      await api.planos.atualizarCampanha(plano.id, campanha.id, {
                        valor: campanha.valor,
                        sincronizar_nomenclatura: true,
                      })
                      await aoAtualizarPlano()
                    }}
                  />
                  <span className="empurra">
                    <CampoRateio
                      valor={campanha.valor}
                      percentual={campanha.percentual}
                      valorPai={plano.verba_total}
                      rotulo={campanha.nome_interno}
                      aoSalvar={(campo, texto) => salvarRateioCampanha(campanha, campo, texto)}
                    />
                  </span>
                </div>

                {abertaCampanha && (
                  <div className="pilha plano-detalhe-no" data-espaco="3">
                    <CamposCampanha
                      planoId={plano.id}
                      campanha={campanha}
                      metricas={metricas}
                      aoAtualizarPlano={aoAtualizarPlano}
                    />

                    <div className="linha" data-alinhar="entre">
                      <span className="texto-auxiliar">
                        grupos: {formatarMoedaComPrefixo(paraNumero(campanha.soma_grupos))} de{' '}
                        {formatarMoedaComPrefixo(paraNumero(campanha.valor))}
                      </span>
                      <SeloDesbalanco
                        diferenca={campanha.diferenca}
                        base={campanha.valor}
                        rotulo={`Grupos de ${campanha.nome_interno}`}
                      />
                    </div>

                    {campanha.grupos.length > 0 && (
                      <ul id={idFilhosCampanha} className="arvore-lista plano-arvore" data-nivel="grupo">
                        {campanha.grupos.map((grupo) => {
                          const abertoGrupo = !recolhidosGrupo[grupo.id]
                          const idFilhosGrupo = `${idBase}-anuncios-${grupo.id}`

                          return (
                            <li key={grupo.id} className="pilha" data-espaco="2">
                              <div
                                className="arvore-no plano-no"
                                data-nivel="grupo"
                                onFocus={() => aoMudarFoco(campanha.id, grupo.id)}
                              >
                                <button
                                  type="button"
                                  className="arvore-botao"
                                  aria-expanded={abertoGrupo}
                                  aria-controls={idFilhosGrupo}
                                  aria-label={
                                    abertoGrupo
                                      ? `Recolher ${grupo.nome_interno}`
                                      : `Expandir ${grupo.nome_interno}`
                                  }
                                  onClick={() => {
                                    setRecolhidosGrupo((r) => ({ ...r, [grupo.id]: !r[grupo.id] }))
                                    aoMudarFoco(campanha.id, grupo.id)
                                  }}
                                >
                                  <IconeChevron sentido={abertoGrupo ? 'baixo' : 'direita'} />
                                </button>
                                <IconeNivel nivel="GRUPO" tamanho="sm" />
                                <span className="arvore-nome">{grupo.nome_interno}</span>
                                <span className="arvore-codigo">{grupo.match_id}</span>
                                <DivergenciaNome
                                  nomenclaturaSnapshot={grupo.nomenclatura}
                                  nomenclaturaAtual={grupo.nomenclatura_atual}
                                  divergente={grupo.nomenclatura_divergente}
                                  aoAtualizarSnapshot={async () => {
                                    await api.planos.atualizarGrupo(plano.id, campanha.id, grupo.id, {
                                      valor: grupo.valor,
                                      sincronizar_nomenclatura: true,
                                    })
                                    await aoAtualizarPlano()
                                  }}
                                />
                                <span className="empurra">
                                  <CampoRateio
                                    valor={grupo.valor}
                                    percentual={grupo.percentual}
                                    valorPai={campanha.valor}
                                    rotulo={grupo.nome_interno}
                                    aoSalvar={(campo, texto) =>
                                      salvarRateioGrupo(campanha, grupo, campo, texto)
                                    }
                                  />
                                </span>
                              </div>

                              {abertoGrupo && (
                                <div className="pilha plano-detalhe-no" data-espaco="3">
                                  <CampoCustoUnitario
                                    planoId={plano.id}
                                    campanhaLinhaId={campanha.id}
                                    grupo={grupo}
                                    aoAtualizarPlano={aoAtualizarPlano}
                                  />

                                  <div className="linha" data-alinhar="entre">
                                    <span className="texto-auxiliar">
                                      anúncios: {formatarMoedaComPrefixo(paraNumero(grupo.soma_anuncios))}{' '}
                                      de {formatarMoedaComPrefixo(paraNumero(grupo.valor))}
                                    </span>
                                    <SeloDesbalanco
                                      diferenca={grupo.diferenca}
                                      base={grupo.valor}
                                      rotulo={`Anúncios de ${grupo.nome_interno}`}
                                    />
                                  </div>

                                  {grupo.anuncios.length > 0 && (
                                    <ul id={idFilhosGrupo} className="arvore-lista plano-arvore" data-nivel="anuncio">
                                      {grupo.anuncios.map((anuncio) => (
                                        <li key={anuncio.id} className="pilha" data-espaco="1">
                                          <div className="arvore-no plano-no" data-nivel="anuncio">
                                            <IconeNivel nivel="ANUNCIO" tamanho="sm" />
                                            <span className="arvore-nome">{anuncio.nome_interno}</span>
                                            <span className="arvore-codigo">{anuncio.match_id}</span>
                                            <DivergenciaNome
                                              nomenclaturaSnapshot={anuncio.nomenclatura}
                                              nomenclaturaAtual={anuncio.nomenclatura_atual}
                                              divergente={anuncio.nomenclatura_divergente}
                                              aoAtualizarSnapshot={async () => {
                                                await api.planos.atualizarAnuncio(
                                                  plano.id,
                                                  campanha.id,
                                                  grupo.id,
                                                  anuncio.id,
                                                  { valor: anuncio.valor, sincronizar_nomenclatura: true },
                                                )
                                                await aoAtualizarPlano()
                                              }}
                                            />
                                            <span className="empurra">
                                              <CampoRateio
                                                valor={anuncio.valor}
                                                percentual={anuncio.percentual}
                                                valorPai={grupo.valor}
                                                rotulo={anuncio.nome_interno}
                                                aoSalvar={(campo, texto) =>
                                                  salvarRateioAnuncio(
                                                    campanha,
                                                    grupo,
                                                    anuncio.id,
                                                    campo,
                                                    texto,
                                                  )
                                                }
                                              />
                                            </span>
                                          </div>
                                        </li>
                                      ))}
                                    </ul>
                                  )}

                                  <AdicionarLinha
                                    rotulo="anúncio"
                                    jaAdicionados={new Set(grupo.anuncios.map((a) => a.anuncio_id))}
                                    buscar={() => api.anunciosDoGrupo(grupo.grupo_id)}
                                    aoAdicionar={async (entidade) => {
                                      await api.planos.adicionarAnuncio(plano.id, campanha.id, grupo.id, {
                                        anuncio_id: entidade.id,
                                        percentual: '0',
                                      })
                                      await aoAtualizarPlano()
                                    }}
                                  />
                                </div>
                              )}
                            </li>
                          )
                        })}
                      </ul>
                    )}

                    <AdicionarLinha
                      rotulo="grupo"
                      jaAdicionados={new Set(campanha.grupos.map((g) => g.grupo_id))}
                      buscar={() => api.gruposDaCampanha(campanha.campanha_id)}
                      aoAdicionar={async (entidade) => {
                        await api.planos.adicionarGrupo(plano.id, campanha.id, {
                          grupo_id: entidade.id,
                          percentual: '0',
                        })
                        await aoAtualizarPlano()
                      }}
                    />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <AdicionarLinha
        rotulo="campanha"
        jaAdicionados={idsCampanhaNoPlano}
        buscar={() => api.campanhas()}
        aoAdicionar={async (entidade) => {
          await api.planos.adicionarCampanha(plano.id, { campanha_id: entidade.id, percentual: '0' })
          await aoAtualizarPlano()
        }}
      />
    </section>
  )
}

/** Flight (início/fim) e KPI primário — campos exclusivos do nível CAMPANHA. */
function CamposCampanha({
  planoId,
  campanha,
  metricas,
  aoAtualizarPlano,
}: {
  planoId: string
  campanha: CampanhaDoPlano
  metricas: Metrica[]
  aoAtualizarPlano: () => Promise<void>
}) {
  const idBase = useId()
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function salvar(corpo: { flight_inicio?: string | null; flight_fim?: string | null; kpi_primario_id?: string | null }) {
    setSalvando(true)
    setErro(null)
    try {
      await api.planos.atualizarCampanha(planoId, campanha.id, { valor: campanha.valor, ...corpo })
      await aoAtualizarPlano()
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível salvar.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="linha" data-espaco="3" data-alinhar="base">
      <div>
        <label htmlFor={`${idBase}-inicio`}>Flight — início</label>
        <input
          id={`${idBase}-inicio`}
          type="date"
          defaultValue={campanha.flight_inicio ?? ''}
          onBlur={(e) => void salvar({ flight_inicio: e.target.value || null })}
        />
      </div>
      <div>
        <label htmlFor={`${idBase}-fim`}>Flight — fim</label>
        <input
          id={`${idBase}-fim`}
          type="date"
          defaultValue={campanha.flight_fim ?? ''}
          onBlur={(e) => void salvar({ flight_fim: e.target.value || null })}
        />
      </div>
      <div>
        <label htmlFor={`${idBase}-kpi`}>KPI primário</label>
        <select
          id={`${idBase}-kpi`}
          value={campanha.kpi_primario_id ?? ''}
          onChange={(e) => void salvar({ kpi_primario_id: e.target.value || null })}
        >
          <option value="">— nenhum —</option>
          {metricas.map((m) => (
            <option key={m.id} value={m.id}>
              {m.rotulo}
            </option>
          ))}
        </select>
        {campanha.kpi_primario_id && campanha.kpi_primario_ativo === false && (
          <p className="texto-auxiliar" data-tom="alerta">
            O KPI escolhido não está mais ativo no catálogo.
          </p>
        )}
      </div>
      {salvando && <Giro />}
      {erro && (
        <p className="texto-auxiliar" data-tom="alerta" role="alert">
          {erro}
        </p>
      )}
    </div>
  )
}

/** Custo unitário negociado (CPM/CPV) — campo exclusivo do nível GRUPO, informativo. */
function CampoCustoUnitario({
  planoId,
  campanhaLinhaId,
  grupo,
  aoAtualizarPlano,
}: {
  planoId: string
  campanhaLinhaId: string
  grupo: GrupoDoPlano
  aoAtualizarPlano: () => Promise<void>
}) {
  const id = useId()
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function salvar(texto: string) {
    setSalvando(true)
    setErro(null)
    try {
      await api.planos.atualizarGrupo(planoId, campanhaLinhaId, grupo.id, {
        valor: grupo.valor,
        custo_unitario_negociado: texto.trim() === '' ? null : texto.replace(',', '.'),
      })
      await aoAtualizarPlano()
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível salvar.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="linha" data-espaco="2" data-alinhar="base">
      <div>
        <label htmlFor={id}>Custo unitário negociado (CPM/CPV)</label>
        <input
          id={id}
          inputMode="decimal"
          defaultValue={grupo.custo_unitario_negociado ?? ''}
          placeholder="Informativo — não alimenta cálculo"
          onBlur={(e) => void salvar(e.target.value)}
        />
      </div>
      {salvando && <Giro />}
      {erro && (
        <span className="texto-auxiliar" data-tom="alerta" role="alert">
          {erro}
        </span>
      )}
    </div>
  )
}
