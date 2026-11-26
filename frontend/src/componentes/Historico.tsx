import { useEffect, useId, useMemo, useState } from 'react'

import { type FiltrosHistorico, api } from '../api'
import {
  type Entidade,
  type LinhaHistorico,
  NIVEIS,
  type Nivel,
  type Plataforma,
  ROTULO_NIVEL,
} from '../tipos'
import { Botao, Estado, LinkBotao } from './ui'

interface Props {
  plataformas: Plataforma[]
}

function formatarData(iso: string): string {
  const data = new Date(iso)
  return Number.isNaN(data.valueOf()) ? iso : data.toLocaleString('pt-BR')
}

/**
 * Histórico de nomenclaturas geradas, com os filtros pedidos: data de criação,
 * plataforma e campanha.
 *
 * Não há edição nem exclusão aqui de propósito — taxonomia gerada é imutável
 * (D-004). Para corrigir um nome, gera-se outro; o antigo permanece, porque
 * pode já estar rodando numa plataforma de anúncios.
 *
 * DENSIDADE (UX-NAVEGACAO §7.3). A tela é uma tabela de seis colunas, e o que
 * ela precisa é de ALTURA, não de enfeite. Duas mudanças pagam isso:
 *
 * · Os filtros deixaram de morar num cartão e perderam o `<h2>Filtros`. Os
 *   rótulos dos campos já dizem o que cada um é — o título só repetia a
 *   palavra e custava ~120 px verticais, que é altura de cinco linhas de
 *   tabela (Krug: retire a palavra que não trabalha).
 * · Todo o estilo saiu do `.tsx` para classes tokenizadas. Não era só dívida
 *   estética: enquanto o padding estava escrito em `React.CSSProperties`, não
 *   havia como mudar a densidade da tabela sem editar componente.
 *
 * A meta é OBSERVÁVEL e não é o CSS: **≥ 18 linhas visíveis sem rolar em
 * 1920×1080**. Se der menos que isso, a densidade não foi resolvida.
 */
export function Historico({ plataformas }: Props) {
  const [filtros, setFiltros] = useState<FiltrosHistorico>({})
  const [linhas, setLinhas] = useState<LinhaHistorico[]>([])
  const [campanhas, setCampanhas] = useState<Entidade[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [copiado, setCopiado] = useState<string | null>(null)

  const idDesde = useId()
  const idAte = useId()
  const idPlataforma = useId()
  const idCampanha = useId()
  const idNivel = useId()
  const idBusca = useId()

  // As campanhas do seletor acompanham a plataforma escolhida.
  useEffect(() => {
    api
      .campanhas(filtros.plataforma_id)
      .then(setCampanhas)
      .catch(() => setCampanhas([]))
  }, [filtros.plataforma_id])

  useEffect(() => {
    let cancelado = false
    setCarregando(true)

    api
      .historico(filtros)
      .then((r) => {
        if (cancelado) return
        setLinhas(r)
        setErro(null)
      })
      .catch((e) => {
        if (cancelado) return
        setErro(`Não foi possível carregar o histórico: ${e.message}`)
      })
      .finally(() => {
        if (!cancelado) setCarregando(false)
      })

    return () => {
      cancelado = true
    }
  }, [filtros])

  const definir = (chave: keyof FiltrosHistorico, valor: string) =>
    setFiltros((atual) => {
      const proximo = { ...atual, [chave]: valor || undefined }
      // Trocar de plataforma invalida a campanha selecionada.
      if (chave === 'plataforma_id') delete proximo.campanha_id
      return proximo
    })

  const algumFiltro = useMemo(() => Object.values(filtros).some(Boolean), [filtros])

  async function copiar(texto: string) {
    await navigator.clipboard.writeText(texto)
    setCopiado(texto)
    setTimeout(() => setCopiado(null), 1500)
  }

  return (
    <div className="pilha" data-espaco="4">
      {/* Sem cartão e sem `<h2>Filtros`: é uma linha de controles, não uma
          seção. A busca continua indo ao SERVIDOR aqui — contraste deliberado
          com o Dicionário: o histórico é ilimitado e recortado por data. */}
      <div className="filtros">
        <div>
          <label htmlFor={idDesde}>Criado a partir de</label>
          <input
            id={idDesde}
            type="date"
            value={filtros.desde ?? ''}
            onChange={(e) => definir('desde', e.target.value)}
          />
        </div>

        <div>
          <label htmlFor={idAte}>até</label>
          <input
            id={idAte}
            type="date"
            value={filtros.ate ?? ''}
            onChange={(e) => definir('ate', e.target.value)}
          />
        </div>

        <div>
          <label htmlFor={idPlataforma}>Plataforma</label>
          <select
            id={idPlataforma}
            value={filtros.plataforma_id ?? ''}
            onChange={(e) => definir('plataforma_id', e.target.value)}
          >
            <option value="">Todas</option>
            {plataformas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={idCampanha}>Campanha</label>
          <select
            id={idCampanha}
            value={filtros.campanha_id ?? ''}
            onChange={(e) => definir('campanha_id', e.target.value)}
          >
            <option value="">Todas</option>
            {campanhas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome_interno} ({c.match_id})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={idNivel}>Nível</label>
          <select
            id={idNivel}
            value={filtros.nivel ?? ''}
            onChange={(e) => definir('nivel', e.target.value as Nivel)}
          >
            <option value="">Todos</option>
            {NIVEIS.map((n) => (
              <option key={n} value={n}>
                {ROTULO_NIVEL[n]}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={idBusca}>Buscar no nome</label>
          <input
            id={idBusca}
            value={filtros.busca ?? ''}
            placeholder="ALF_METAA…"
            onChange={(e) => definir('busca', e.target.value)}
          />
        </div>
      </div>

      <div className="filtros-acoes">
        <LinkBotao variante="secundario" tamanho="sm" href={api.urlExport({ ...filtros })} download>
          Baixar Excel
        </LinkBotao>

        <Botao
          variante="fantasma"
          tamanho="sm"
          disabled={!algumFiltro}
          onClick={() => setFiltros({})}
        >
          Limpar filtros
        </Botao>

        <span className="contador-lista" role="status" aria-live="polite">
          {carregando ? 'Carregando…' : `${linhas.length} nomenclaturas`}
        </span>
      </div>

      {erro && (
        <div role="alert" className="aviso-erro">
          {erro}
        </div>
      )}

      {!carregando && linhas.length === 0 ? (
        algumFiltro ? (
          <Estado tipo="sem-resultado" titulo="Nenhuma nomenclatura encontrada com esses filtros.">
            <div className="linha">
              <Botao variante="secundario" onClick={() => setFiltros({})}>
                Limpar filtros
              </Botao>
            </div>
          </Estado>
        ) : (
          <Estado
            tipo="vazio"
            titulo="Nenhuma nomenclatura gerada ainda."
            texto="O que você gerar na aba Gerar aparece aqui, com o código que liga o nome à planilha de performance."
          />
        )
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela" data-densidade="alta">
            <caption className="apenas-leitor">Nomenclaturas geradas</caption>
            <thead>
              <tr>
                {/* `Nomenclatura` toma o 1fr — é o que se lê. As demais ficam
                    com largura de conteúdo, à direita. */}
                <th className="tabela-celula" data-coluna="principal" scope="col">
                  Nomenclatura
                </th>
                <th className="tabela-celula" scope="col">
                  Nível
                </th>
                <th className="tabela-celula" scope="col">
                  Plataforma
                </th>
                <th className="tabela-celula" scope="col">
                  Campanha
                </th>
                <th className="tabela-celula" scope="col">
                  Criado em
                </th>
                <th className="tabela-celula" data-coluna="acao" scope="col">
                  <span className="apenas-leitor">Copiar</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => (
                <tr key={l.id}>
                  <td className="tabela-celula mono" data-coluna="principal">
                    <strong>{l.nomenclatura_final}</strong>
                    <span className="tabela-nota">
                      {' '}
                      · {l.caracteres} caracteres · v{l.template_versao}
                    </span>
                  </td>
                  <td className="tabela-celula">{ROTULO_NIVEL[l.nivel]}</td>
                  <td className="tabela-celula">{l.plataforma}</td>
                  <td className="tabela-celula">{l.campanha || '—'}</td>
                  <td className="tabela-celula">{formatarData(l.criado_em)}</td>
                  <td className="tabela-celula" data-coluna="acao">
                    <Botao
                      variante="secundario"
                      tamanho="sm"
                      onClick={() => void copiar(l.nomenclatura_final)}
                    >
                      {copiado === l.nomenclatura_final ? 'Copiado' : 'Copiar'}
                    </Botao>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
