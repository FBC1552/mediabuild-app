/**
 * Monitoramento de acessos e erros (`#/admin/monitoramento`, §3.7).
 *
 * Duas seções na mesma tela, separadas por espaço e não por linha divisória,
 * com **um** seletor de período no topo: as duas respondem à mesma pergunta
 * temporal, e dois seletores criariam o estado em que os números da tela são
 * de janelas diferentes.
 *
 * Três decisões que a tela materializa:
 *
 * · **`request_id` é a coluna que justifica a tela.** `app/logs.py` já o
 *   devolve em `X-Request-ID` e carrega em toda linha de log; é ele que liga a
 *   reclamação do analista à linha do log. Monoespaçado, com botão copiar.
 * · **422 do motor e 5xx são contadores SEPARADOS.** Somá-los faz "3 erros
 *   hoje" parecer alarme quando é só alguém digitando um termo fora do
 *   dicionário.
 * · **Sem gráfico.** A série existe (`logins_por_dia`), mas ela responde a uma
 *   pergunta de tendência que ninguém faz numa ferramenta interna de uso
 *   local; a tabela diz o mesmo, é legível por leitor de tela e não inventa
 *   escala. Se a pergunta mudar, o dado já está aqui.
 */
import { useCallback, useEffect, useId, useState } from 'react'

import { api, ErroRequisicao } from '../api'
import { BotaoCopiar, Esqueleto, Estado } from '../componentes/ui'
import {
  ROTULO_EVENTO_ACESSO,
  type EventoAcesso,
  type EventoErro,
  type ResumoAdmin,
} from '../tipos'
import { CascaAdmin } from './CascaAdmin'
import { formatarQuando } from './formato'

/** Períodos em DIAS. `Hoje` é 1 — a janela do backend é deslizante. */
const PERIODOS = [
  { dias: 1, rotulo: 'Hoje' },
  { dias: 7, rotulo: '7 dias' },
  { dias: 30, rotulo: '30 dias' },
] as const

/** Teto do servidor é 500; a tela nunca precisa de mais que isto. */
const LIMITE = 100

type Dados = { resumo: ResumoAdmin; acessos: EventoAcesso[]; erros: EventoErro[] }

type Carga =
  | { fase: 'carregando' }
  | { fase: 'erro'; mensagem: string }
  | { fase: 'pronto'; dados: Dados }

export default function Monitoramento() {
  const [dias, setDias] = useState<number>(7)
  const [carga, setCarga] = useState<Carga>({ fase: 'carregando' })
  // `useId()` e não id literal: o mesmo id serve de `name`, que é o que agrupa
  // os rádios — literal, dois grupos na mesma página viram um só.
  const idPeriodo = useId()

  const buscar = useCallback(async (janela: number, signal: AbortSignal) => {
    setCarga({ fase: 'carregando' })
    const desde = new Date(Date.now() - janela * 86_400_000).toISOString()
    try {
      const [resumo, acessos, erros] = await Promise.all([
        api.admin.resumo(janela, signal),
        api.admin.acessos({ desde, limite: LIMITE }, signal),
        api.admin.erros({ desde, limite: LIMITE }, signal),
      ])
      if (signal.aborted) return
      setCarga({ fase: 'pronto', dados: { resumo, acessos, erros } })
    } catch (erro) {
      if (signal.aborted) return
      setCarga({
        fase: 'erro',
        mensagem:
          erro instanceof ErroRequisicao
            ? erro.corpo.mensagem
            : 'Não foi possível carregar o monitoramento.',
      })
    }
  }, [])

  // AbortController porque o período é trocado em sequência: resposta atrasada
  // da janela anterior não pode sobrescrever a nova.
  useEffect(() => {
    const controle = new AbortController()
    void buscar(dias, controle.signal)
    return () => controle.abort()
  }, [dias, buscar])

  return (
    <CascaAdmin area="monitoramento">
      <div className="pilha" data-espaco="2">
        <h2 className="titulo-secao">Monitoramento</h2>
        <p className="texto-auxiliar medida">
          Quem entrou, quem tentou e o que falhou. O <span className="mono">request id</span> é o
          que liga uma reclamação à linha de log.
        </p>
      </div>

      <fieldset className="segmentos" aria-label="Período">
        {PERIODOS.map((periodo) => (
          <span key={periodo.dias} className="segmento">
            <input
              className="apenas-leitor"
              type="radio"
              id={`${idPeriodo}-${periodo.dias}`}
              name={idPeriodo}
              checked={dias === periodo.dias}
              onChange={() => setDias(periodo.dias)}
            />
            <label htmlFor={`${idPeriodo}-${periodo.dias}`}>{periodo.rotulo}</label>
          </span>
        ))}
      </fieldset>

      {carga.fase === 'carregando' && (
        <div className="pilha" data-espaco="3" aria-busy="true">
          <Esqueleto forma="cartao" />
          <Esqueleto forma="texto" />
          <Esqueleto forma="texto" final />
        </div>
      )}

      {carga.fase === 'erro' && (
        <Estado
          tipo="erro"
          titulo="Não foi possível carregar o monitoramento."
          texto={carga.mensagem}
        />
      )}

      {carga.fase === 'pronto' && <Conteudo dados={carga.dados} />}
    </CascaAdmin>
  )
}

function Conteudo({ dados }: { dados: Dados }) {
  const { resumo, acessos, erros } = dados
  const percentualFalha = Math.round(resumo.taxa_falha_login * 100)

  return (
    <>
      <section className="pilha" data-espaco="5">
        <h3 className="rotulo-secao">Acessos</h3>

        <div className="cartoes-numero">
          <CartaoNumero valor={resumo.total_logins_ok} rotulo="entradas" />
          <CartaoNumero valor={resumo.sessoes_ativas} rotulo="sessões ativas agora" />
          <CartaoNumero
            valor={resumo.total_logins_falha}
            rotulo={`falhas de login · ${percentualFalha}% das tentativas`}
          />
        </div>

        {resumo.logins_por_dia.length > 0 && (
          <div className="tabela-rolagem">
            <table className="tabela" data-densidade="alta">
              <caption className="apenas-leitor">Entradas e falhas por dia</caption>
              <thead>
                <tr>
                  <th className="tabela-celula" data-coluna="principal" scope="col">
                    Dia
                  </th>
                  <th className="tabela-celula" scope="col">
                    Entradas
                  </th>
                  <th className="tabela-celula" scope="col">
                    Falhas
                  </th>
                </tr>
              </thead>
              <tbody>
                {resumo.logins_por_dia.map((linha) => (
                  <tr key={linha.dia}>
                    <td className="tabela-celula" data-coluna="principal">
                      {linha.dia}
                    </td>
                    <td className="tabela-celula">{linha.ok}</td>
                    <td className="tabela-celula">{linha.falha}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {acessos.length === 0 ? (
          <Estado tipo="vazio" titulo="Nenhum acesso no período." />
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela" data-densidade="alta">
              <caption className="apenas-leitor">Eventos de acesso, mais recentes primeiro</caption>
              <thead>
                <tr>
                  <th className="tabela-celula" scope="col">
                    Quando
                  </th>
                  <th className="tabela-celula" data-coluna="principal" scope="col">
                    Pessoa
                  </th>
                  <th className="tabela-celula" scope="col">
                    Origem
                  </th>
                  <th className="tabela-celula" scope="col">
                    Resultado
                  </th>
                </tr>
              </thead>
              <tbody>
                {acessos.map((evento) => (
                  <tr key={evento.id}>
                    <td className="tabela-celula">{formatarQuando(evento.ocorrido_em)}</td>
                    {/* `usuario_login` vem nulo quando a conta já foi excluída;
                        `login_tentado` continua preenchido, então a linha nunca
                        fica anônima. */}
                    <td className="tabela-celula mono" data-coluna="principal">
                      {evento.usuario_login ?? evento.login_tentado ?? '—'}
                    </td>
                    <td className="tabela-celula mono">{evento.ip ?? '—'}</td>
                    <td className="tabela-celula">{ROTULO_EVENTO_ACESSO[evento.tipo]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="pilha" data-espaco="5">
        <h3 className="rotulo-secao">Erros</h3>

        <div className="cartoes-numero">
          <CartaoNumero valor={resumo.erros_4xx} rotulo="erros de validação (4xx)" />
          <CartaoNumero valor={resumo.erros_5xx} rotulo="falhas do servidor (5xx)" />
        </div>

        {resumo.top_caminhos_com_erro.length > 0 && (
          <p className="texto-auxiliar">
            Rotas com mais erro:{' '}
            {resumo.top_caminhos_com_erro
              .map((item) => `${item.caminho} (${item.total})`)
              .join(' · ')}
          </p>
        )}

        {erros.length === 0 ? (
          // Tom neutro: nenhum erro no período é boa notícia, não estado vazio
          // que precisa de conserto.
          <Estado tipo="vazio" titulo="Nenhum erro no período." />
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela" data-densidade="alta">
              <caption className="apenas-leitor">Respostas com erro, mais recentes primeiro</caption>
              <thead>
                <tr>
                  <th className="tabela-celula" scope="col">
                    Quando
                  </th>
                  <th className="tabela-celula" scope="col">
                    Código
                  </th>
                  <th className="tabela-celula" data-coluna="principal" scope="col">
                    Rota
                  </th>
                  <th className="tabela-celula" scope="col">
                    Request ID
                  </th>
                </tr>
              </thead>
              <tbody>
                {erros.map((evento) => (
                  <tr key={evento.id}>
                    <td className="tabela-celula">{formatarQuando(evento.ocorrido_em)}</td>
                    <td className="tabela-celula mono">
                      {evento.codigo_erro ?? evento.status}
                      <div className="tabela-nota">HTTP {evento.status}</div>
                    </td>
                    <td className="tabela-celula mono" data-coluna="principal">
                      {evento.metodo} {evento.caminho}
                    </td>
                    <td className="tabela-celula">
                      {evento.request_id ? (
                        <span className="linha" data-espaco="2">
                          <span className="mono">{evento.request_id.slice(0, 8)}…</span>
                          <BotaoCopiar
                            texto={evento.request_id}
                            tamanho="sm"
                            rotulo="Copiar"
                          />
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}

function CartaoNumero({ valor, rotulo }: { valor: number; rotulo: string }) {
  return (
    <div className="cartao-numero">
      <span className="cartao-numero-valor">{valor}</span>
      <span className="cartao-numero-rotulo">{rotulo}</span>
    </div>
  )
}
