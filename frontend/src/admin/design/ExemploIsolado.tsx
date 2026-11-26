import { Estado } from '../../componentes/ui'
import { destinoDoExemplo, VoltarPara } from '../../componentes/VoltarPara'
import { acharExemplo, secaoDoExemplo } from './registro'

/**
 * `#/isolado/<id>`: o exemplo sozinho, sem cromo de catálogo.
 *
 * Redimensionar a janela real aqui é o único teste 100% honesto de
 * responsividade — um palco de largura fixa continua sendo um `<div>`.
 */
export default function ExemploIsolado({ exemplo: id }: { exemplo: string }) {
  const exemplo = acharExemplo(id)

  if (!exemplo) {
    return (
      <main className="pagina contexto-pagina">
        <Estado
          tipo="rota"
          tituloComo="h1"
          titulo="Exemplo não encontrado"
          texto="Nenhum exemplo do catálogo corresponde a este identificador."
          identificador={id}
        >
          <a className="botao" href="#/admin/design/fundacao">
            Voltar ao catálogo
          </a>
        </Estado>
      </main>
    )
  }

  return (
    <main className="pagina contexto-pagina pilha" data-espaco="6">
      {/* O destino é CALCULADO a partir da seção do exemplo, não fixo. */}
      <header className="cabecalho-tela" tabIndex={-1} data-foco-rota>
        <VoltarPara {...destinoDoExemplo(secaoDoExemplo(id) ?? 'fundacao')} />
        <h1 className="apenas-leitor">{exemplo.titulo}</h1>
      </header>
      <div className="contexto">{exemplo.render()}</div>
    </main>
  )
}
