import { useEffect, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import type { Metrica } from '../tipos'
import { Esqueleto, Estado } from './ui'
import { VoltarPara } from './VoltarPara'

/**
 * Catálogo de métricas (`#/plano/metricas`) — SÓ LEITURA nesta fase (decisão
 * explícita da tarefa: a edição descrita em §6 do desenho fica para depois).
 * Consome `GET /metricas` e nada mais; nenhum POST/PATCH/DELETE aqui.
 */
export function CatalogoMetricas() {
  const [metricas, setMetricas] = useState<Metrica[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    api
      .metricas.listar(true)
      .then(setMetricas)
      .catch((e) =>
        setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível carregar as métricas.'),
      )
  }, [])

  return (
    <main className="pagina contexto-pagina pilha" data-espaco="6">
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara de="planos" />
        <h1 className="titulo-tela">Catálogo de métricas</h1>
        <p className="marca-subtitulo medida">
          Vocabulário de metas compartilhado por todos os planos — só leitura nesta versão.
        </p>
      </header>

      {erro && <Estado tipo="erro" titulo="Não foi possível carregar as métricas" texto={erro} />}

      {!erro && metricas === null && (
        <div className="pilha" data-espaco="2">
          <Esqueleto forma="texto" />
          <Esqueleto forma="texto" />
          <Esqueleto forma="texto" final />
        </div>
      )}

      {!erro && metricas !== null && metricas.length === 0 && (
        <Estado tipo="vazio" titulo="Nenhuma métrica cadastrada ainda." />
      )}

      {!erro && metricas !== null && metricas.length > 0 && (
        <div className="contexto-painel">
          <table className="tabela">
            <thead>
              <tr>
                <th className="tabela-celula" scope="col">
                  Código
                </th>
                <th className="tabela-celula" scope="col">
                  Rótulo
                </th>
                <th className="tabela-celula" scope="col">
                  Ordem
                </th>
                <th className="tabela-celula" scope="col">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {metricas.map((m) => (
                <tr key={m.id}>
                  <td className="tabela-celula mono">{m.codigo}</td>
                  <td className="tabela-celula">{m.rotulo}</td>
                  <td className="tabela-celula texto-auxiliar">{m.ordem}</td>
                  <td className="tabela-celula texto-auxiliar">{m.ativo ? 'Ativa' : 'Inativa'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}

export default CatalogoMetricas
