import { useEffect, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import { caminhoDe, navegar } from '../roteador'
import type { PlanoMidiaResumo } from '../tipos'
import { formatarMoedaComPrefixo, paraNumero } from './formatoPlano'
import { SeloDesbalanco } from './SeloDesbalanco'
import { Botao, Esqueleto, Estado } from './ui'
import { VoltarPara } from './VoltarPara'

function formatarData(iso: string): string {
  const data = new Date(iso)
  return Number.isNaN(data.valueOf()) ? iso : data.toLocaleDateString('pt-BR')
}

/**
 * Índice de planos (`#/plano`) — mesmo padrão denso de `Historico.tsx`, uma
 * linha por plano, sem paginar cedo. A coluna Diferença usa o mesmo selo de
 * desbalanço da tela do plano: o sinal precisa aparecer ANTES de abrir,
 * porque é o primeiro indício de "este documento ainda não está pronto".
 */
export function PlanoIndice() {
  const [planos, setPlanos] = useState<PlanoMidiaResumo[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [criando, setCriando] = useState(false)
  const [nome, setNome] = useState('')
  const [verba, setVerba] = useState('')
  const [erroForm, setErroForm] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  function carregar() {
    setErro(null)
    api
      .planos.listar()
      .then(setPlanos)
      .catch((e) => setErro(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível carregar os planos.'))
  }

  useEffect(carregar, [])

  async function criar(evento: React.FormEvent) {
    evento.preventDefault()
    setErroForm(null)
    setSalvando(true)
    try {
      const criado = await api.planos.criar({
        nome: nome.trim(),
        verba_total: verba.trim() === '' ? '0' : verba.trim().replace(',', '.'),
      })
      navegar(caminhoDe({ nome: 'plano', id: criado.id }))
    } catch (e) {
      setErroForm(e instanceof ErroRequisicao ? e.corpo.mensagem : 'Não foi possível criar o plano.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    // Tela dominada por dados (§7.3): largura densa.
    <main className="pagina contexto-pagina pilha" data-largura="densa" data-espaco="6">
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara de="assuntos" />
        <h1 className="titulo-tela">Planos de mídia</h1>
      </header>

      <div className="linha" data-alinhar="entre">
        <a className="botao" data-variante="fantasma" data-tamanho="sm" href="#/plano/metricas">
          Métricas →
        </a>
        <Botao tamanho="sm" onClick={() => setCriando((v) => !v)}>
          + Novo plano
        </Botao>
      </div>

      {criando && (
        <form className="card bloco grade campos" onSubmit={(e) => void criar(e)}>
          <div>
            <label htmlFor="plano-nome">Nome</label>
            <input id="plano-nome" value={nome} onChange={(e) => setNome(e.target.value)} required />
          </div>
          <div>
            <label htmlFor="plano-verba">Verba total (R$)</label>
            <input
              id="plano-verba"
              inputMode="decimal"
              value={verba}
              onChange={(e) => setVerba(e.target.value)}
            />
          </div>
          <div className="campo-largo linha" data-alinhar="fim">
            {erroForm && (
              <p className="texto-auxiliar" data-tom="alerta" role="alert">
                {erroForm}
              </p>
            )}
            <Botao type="submit" tamanho="sm" carregando={salvando}>
              Criar plano
            </Botao>
          </div>
        </form>
      )}

      {erro && (
        <Estado tipo="erro" titulo="Não foi possível carregar os planos" texto={erro} />
      )}

      {!erro && planos === null && (
        <div className="pilha" data-espaco="2">
          <Esqueleto forma="texto" />
          <Esqueleto forma="texto" />
          <Esqueleto forma="texto" final />
        </div>
      )}

      {!erro && planos !== null && planos.length === 0 && (
        <Estado tipo="vazio" titulo="Nenhum plano de mídia ainda." />
      )}

      {!erro && planos !== null && planos.length > 0 && (
        <div className="contexto-painel">
          <table className="tabela">
            <thead>
              <tr>
                <th className="tabela-celula" scope="col">
                  Nome
                </th>
                <th className="tabela-celula" scope="col">
                  Verba total
                </th>
                <th className="tabela-celula" scope="col">
                  Alocado
                </th>
                <th className="tabela-celula" scope="col">
                  Diferença
                </th>
                <th className="tabela-celula" scope="col">
                  Atualizado
                </th>
              </tr>
            </thead>
            <tbody>
              {planos.map((p) => (
                <tr key={p.id}>
                  <td className="tabela-celula">
                    <a href={caminhoDe({ nome: 'plano', id: p.id })}>{p.nome || 'Rascunho sem nome'}</a>
                  </td>
                  <td className="tabela-celula mono">{formatarMoedaComPrefixo(paraNumero(p.verba_total))}</td>
                  <td className="tabela-celula mono">{formatarMoedaComPrefixo(paraNumero(p.soma_campanhas))}</td>
                  <td className="tabela-celula">
                    <SeloDesbalanco diferenca={p.diferenca} base={p.verba_total} rotulo={p.nome} />
                  </td>
                  <td className="tabela-celula texto-auxiliar">{formatarData(p.atualizado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}

export default PlanoIndice
