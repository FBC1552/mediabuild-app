import { SeloDesbalanco } from './SeloDesbalanco'

interface NoFoco {
  nome_interno: string
  valor: string
  diferenca: string
}

interface Props {
  plano: { nome: string; verba_total: string; diferenca: string }
  /** O nó atualmente focado/expandido na árvore — a trilha segue o foco. */
  campanha?: NoFoco | null
  grupo?: NoFoco | null
}

/**
 * Trilha de saldo (§4.2): Plano → campanha em foco → grupo em foco, sempre
 * visível — inclusive na aba Metas, onde não há edição de rateio nenhuma,
 * só o reflexo passivo do estado do plano inteiro.
 */
export function FaixaDeSaldo({ plano, campanha, grupo }: Props) {
  return (
    <div className="faixa-saldo" role="status" aria-label="Saldo do plano">
      <span className="faixa-saldo-item">
        <span className="faixa-saldo-nome">Plano · {plano.nome}</span>
        <SeloDesbalanco diferenca={plano.diferenca} base={plano.verba_total} rotulo="Plano" />
      </span>

      {campanha && (
        <>
          <span className="faixa-saldo-separador" aria-hidden="true">
            ›
          </span>
          <span className="faixa-saldo-item">
            <span className="faixa-saldo-nome">{campanha.nome_interno}</span>
            <SeloDesbalanco
              diferenca={campanha.diferenca}
              base={campanha.valor}
              rotulo={campanha.nome_interno}
            />
          </span>
        </>
      )}

      {grupo && (
        <>
          <span className="faixa-saldo-separador" aria-hidden="true">
            ›
          </span>
          <span className="faixa-saldo-item">
            <span className="faixa-saldo-nome">{grupo.nome_interno}</span>
            <SeloDesbalanco diferenca={grupo.diferenca} base={grupo.valor} rotulo={grupo.nome_interno} />
          </span>
        </>
      )}
    </div>
  )
}
