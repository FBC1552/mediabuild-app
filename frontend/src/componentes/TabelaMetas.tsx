import { api } from '../api'
import type { CampanhaDoPlano, GrupoDoPlano, Metrica, PlanoMidia } from '../tipos'
import { CelulaMeta } from './CelulaMeta'
import { formatarMoedaComPrefixo, paraNumero } from './formatoPlano'

interface Props {
  plano: PlanoMidia
  metricas: Metrica[]
  aoAtualizarPlano: () => Promise<void>
}

interface LinhaMeta {
  campanha: CampanhaDoPlano
  grupo: GrupoDoPlano
  anuncio: GrupoDoPlano['anuncios'][number]
}

function achatarLinhas(plano: PlanoMidia): LinhaMeta[] {
  const linhas: LinhaMeta[] = []
  for (const campanha of plano.campanhas) {
    for (const grupo of campanha.grupos) {
      for (const anuncio of grupo.anuncios) {
        linhas.push({ campanha, grupo, anuncio })
      }
    }
  }
  return linhas
}

/**
 * Aba Metas (§5) — uma linha por anúncio, igual à planilha do cliente.
 * Colunas de identificação fixas (`position: sticky` horizontal) e rodapé
 * TOTAL fixo (`position: sticky` vertical), somando só o que não é nulo —
 * a mesma regra de uma `SOMA()` de Excel (branco ≠ zero).
 */
export function TabelaMetas({ plano, metricas, aoAtualizarPlano }: Props) {
  const linhas = achatarLinhas(plano)

  async function salvarMeta(linha: LinhaMeta, codigo: string, valor: number | null) {
    const metas = { ...linha.anuncio.metas }
    if (valor === null) delete metas[codigo]
    else metas[codigo] = valor
    await api.planos.atualizarAnuncio(plano.id, linha.campanha.id, linha.grupo.id, linha.anuncio.id, {
      valor: linha.anuncio.valor,
      metas,
    })
    await aoAtualizarPlano()
  }

  if (linhas.length === 0) {
    return (
      <p className="texto-auxiliar">
        Nenhum anúncio no plano ainda. Adicione a estrutura na aba "Estrutura e verba" antes de
        preencher metas.
      </p>
    )
  }

  return (
    <div className="contexto-painel">
      <p className="texto-auxiliar" id="legenda-metas">
        Cada célula é uma meta de contagem — vazio é diferente de zero.
      </p>
      <div className="tabela-rolagem">
        <table className="tabela" aria-describedby="legenda-metas">
          <thead>
            <tr>
              <th className="tabela-celula tabela-fixa" scope="col">
                Campanha › Grupo › Anúncio
              </th>
              <th className="tabela-celula tabela-fixa" scope="col">
                Investimento previsto (R$)
              </th>
              {metricas.map((m) => (
                <th key={m.id} className="tabela-celula" scope="col">
                  {m.rotulo}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((linha) => (
              <tr key={linha.anuncio.id}>
                <th className="tabela-celula tabela-fixa" scope="row">
                  <span className="texto-auxiliar mono">
                    {linha.campanha.match_id} › {linha.grupo.match_id} › {linha.anuncio.match_id}
                  </span>
                  <br />
                  {linha.anuncio.nome_interno}
                </th>
                <td className="tabela-celula tabela-fixa mono">
                  {formatarMoedaComPrefixo(paraNumero(linha.anuncio.valor))}
                </td>
                {metricas.map((m) => (
                  <td key={m.id} className="tabela-celula">
                    <CelulaMeta
                      rotulo={`${m.rotulo} de ${linha.anuncio.nome_interno}`}
                      valor={linha.anuncio.metas[m.codigo] ?? null}
                      aoSalvar={(valor) => salvarMeta(linha, m.codigo, valor)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th className="tabela-celula tabela-fixa" scope="row">
                TOTAL
              </th>
              <td className="tabela-celula tabela-fixa mono">
                {formatarMoedaComPrefixo(
                  linhas.reduce((soma, l) => soma + paraNumero(l.anuncio.valor), 0),
                )}
              </td>
              {metricas.map((m) => {
                const valores = linhas
                  .map((l) => l.anuncio.metas[m.codigo])
                  .filter((v): v is number => v !== undefined && v !== null)
                const soma = valores.reduce((acc, v) => acc + v, 0)
                return (
                  <td key={m.id} className="tabela-celula mono">
                    {valores.length > 0 ? soma : '—'}
                  </td>
                )
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
