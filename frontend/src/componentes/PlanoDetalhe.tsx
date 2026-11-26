import { useEffect, useRef, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import type { CampanhaDoPlano, GrupoDoPlano, Metrica, PlanoMidia } from '../tipos'
import { ArvorePlano } from './ArvorePlano'
import { FaixaDeSaldo } from './FaixaDeSaldo'
import { formatarMoedaComPrefixo, paraNumero } from './formatoPlano'
import { TabelaMetas } from './TabelaMetas'
import { Botao, Estado, Giro } from './ui'
import { VoltarPara } from './VoltarPara'

type AbaPlano = 'estrutura' | 'metas'

interface Props {
  planoId: string
}

/**
 * Tela de um plano (`#/plano/{id}`) — header com nome/verba editáveis
 * inline e a faixa de saldo sempre visível, duas abas internas (Estrutura e
 * verba / Metas) com o mesmo `.abas` já estilizado do resto do produto.
 *
 * Nunca desmonta a árvore ao trocar de aba dentro da tela — as duas abas
 * são views do MESMO plano, então tanto faz; o que importa preservar aqui é
 * o próprio `plano` já carregado, que não se perde ao trocar de aba porque
 * as duas vivem no mesmo componente.
 */
export function PlanoDetalhe({ planoId }: Props) {
  const [plano, setPlano] = useState<PlanoMidia | null>(null)
  const [metricas, setMetricas] = useState<Metrica[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [aba, setAba] = useState<AbaPlano>('estrutura')
  const [focoCampanhaId, setFocoCampanhaId] = useState<string | null>(null)
  const [focoGrupoId, setFocoGrupoId] = useState<string | null>(null)
  const [exportandoConfirmacao, setExportandoConfirmacao] = useState(false)

  const abortRef = useRef<AbortController | null>(null)

  async function carregar() {
    abortRef.current?.abort()
    const controlador = new AbortController()
    abortRef.current = controlador
    try {
      const r = await api.planos.obter(planoId, controlador.signal)
      setPlano(r)
      setErro(null)
    } catch (e) {
      if (controlador.signal.aborted) return
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível carregar o plano.')
    }
  }

  useEffect(() => {
    void carregar()
    api
      .metricas.listar()
      .then(setMetricas)
      .catch(() => setMetricas([]))
    return () => abortRef.current?.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planoId])

  if (erro) {
    return (
      <main className="pagina contexto-pagina pilha" data-espaco="6">
        <VoltarPara de="planos" />
        <Estado tipo="erro" titulo="Não foi possível carregar o plano" texto={erro} tituloComo="h1" />
      </main>
    )
  }

  if (!plano) {
    return (
      <main className="pagina contexto-pagina pilha" data-espaco="6">
        <p className="texto-auxiliar">
          <Giro /> Carregando o plano…
        </p>
      </main>
    )
  }

  const diferencaPlano = paraNumero(plano.diferenca)
  const verbaTotal = paraNumero(plano.verba_total)
  const percentualDesbalanco =
    verbaTotal > 0 ? (Math.abs(diferencaPlano) / verbaTotal) * 100 : diferencaPlano !== 0 ? 100 : 0
  const precisaConfirmarExport = percentualDesbalanco > 2

  const campanhaEmFoco: CampanhaDoPlano | null =
    plano.campanhas.find((c) => c.id === focoCampanhaId) ?? null
  const grupoEmFoco: GrupoDoPlano | null =
    campanhaEmFoco?.grupos.find((g) => g.id === focoGrupoId) ?? null

  return (
    <main className="pagina contexto-pagina pilha" data-largura="densa" data-espaco="6">
      {/* O `h1` é o NOME DO PLANO, não "MediaBuild": é o objeto que a pessoa
          abriu, e repetir a marca aqui duplicaria a barra global. O campo
          editável de `NomeEVerba` continua sendo o caminho de renomear — o
          título só reflete o valor salvo. */}
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara de="planos" />
        <h1 className="titulo-tela">{plano.nome}</h1>
        <NomeEVerba plano={plano} aoAtualizarPlano={carregar} />
      </header>

      <FaixaDeSaldo
        plano={{ nome: plano.nome, verba_total: plano.verba_total, diferenca: plano.diferenca }}
        campanha={campanhaEmFoco}
        grupo={grupoEmFoco}
      />

      <div className="linha" data-alinhar="entre">
        <span />
        {!exportandoConfirmacao ? (
          <Botao
            tamanho="sm"
            variante="secundario"
            onClick={() => {
              if (precisaConfirmarExport) setExportandoConfirmacao(true)
              else window.location.assign(api.planos.urlExport(plano.id))
            }}
          >
            Baixar Excel
          </Botao>
        ) : (
          <span className="linha" data-espaco="3" role="alert">
            <span className="texto-auxiliar">
              Este plano tem {formatarMoedaComPrefixo(Math.abs(diferencaPlano))} não alocados. Exportar
              mesmo assim?
            </span>
            <a
              className="botao"
              data-tamanho="sm"
              href={api.planos.urlExport(plano.id)}
              onClick={() => setExportandoConfirmacao(false)}
            >
              Exportar
            </a>
            <Botao tamanho="sm" variante="fantasma" onClick={() => setExportandoConfirmacao(false)}>
              Cancelar
            </Botao>
          </span>
        )}
      </div>

      <nav className="abas" role="tablist" aria-label="Seções do plano">
        <button
          id="aba-plano-estrutura"
          type="button"
          role="tab"
          className="aba"
          aria-selected={aba === 'estrutura'}
          aria-controls="painel-plano-estrutura"
          tabIndex={aba === 'estrutura' ? 0 : -1}
          onClick={() => setAba('estrutura')}
        >
          Estrutura e verba
        </button>
        <button
          id="aba-plano-metas"
          type="button"
          role="tab"
          className="aba"
          aria-selected={aba === 'metas'}
          aria-controls="painel-plano-metas"
          tabIndex={aba === 'metas' ? 0 : -1}
          onClick={() => setAba('metas')}
        >
          Metas
        </button>
      </nav>

      <div
        id="painel-plano-estrutura"
        role="tabpanel"
        aria-labelledby="aba-plano-estrutura"
        hidden={aba !== 'estrutura'}
      >
        <ArvorePlano
          plano={plano}
          metricas={metricas}
          aoAtualizarPlano={carregar}
          aoMudarFoco={(campanhaId, grupoId) => {
            setFocoCampanhaId(campanhaId)
            setFocoGrupoId(grupoId)
          }}
        />
      </div>

      <div id="painel-plano-metas" role="tabpanel" aria-labelledby="aba-plano-metas" hidden={aba !== 'metas'}>
        <TabelaMetas plano={plano} metricas={metricas} aoAtualizarPlano={carregar} />
      </div>
    </main>
  )
}

/** Nome e verba total do plano — editáveis inline, mesma UX de "Nome interno" do gerador. */
function NomeEVerba({ plano, aoAtualizarPlano }: { plano: PlanoMidia; aoAtualizarPlano: () => Promise<void> }) {
  const [nome, setNome] = useState(plano.nome)
  const [verba, setVerba] = useState(String(paraNumero(plano.verba_total)))
  const [salvando, setSalvando] = useState<'nome' | 'verba' | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    setNome(plano.nome)
    setVerba(String(paraNumero(plano.verba_total)))
  }, [plano.nome, plano.verba_total])

  async function salvar(campo: 'nome' | 'verba_total', valor: string) {
    setSalvando(campo === 'nome' ? 'nome' : 'verba')
    setErro(null)
    try {
      if (campo === 'nome') {
        await api.planos.atualizar(plano.id, { nome: valor })
      } else {
        await api.planos.atualizar(plano.id, { verba_total: valor.replace(',', '.') })
      }
      await aoAtualizarPlano()
    } catch (e) {
      setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível salvar.')
    } finally {
      setSalvando(null)
    }
  }

  return (
    <div className="linha" data-alinhar="base" data-espaco="5">
      <div className="campo-largo">
        <label htmlFor="plano-detalhe-nome">Nome do plano</label>
        <input
          id="plano-detalhe-nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          onBlur={(e) => {
            if (e.target.value.trim() !== plano.nome) void salvar('nome', e.target.value.trim())
          }}
        />
      </div>
      <div>
        <label htmlFor="plano-detalhe-verba">Verba total (R$)</label>
        <input
          id="plano-detalhe-verba"
          inputMode="decimal"
          value={verba}
          onChange={(e) => setVerba(e.target.value)}
          onBlur={(e) => {
            if (e.target.value.trim() !== String(paraNumero(plano.verba_total))) {
              void salvar('verba_total', e.target.value)
            }
          }}
        />
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

export default PlanoDetalhe
