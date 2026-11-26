/**
 * Acesso negado (UX-NAVEGACAO §4.3).
 *
 * Nem redirecionamento silencioso, nem 404:
 *
 * · redirecionar teleporta quem digitou um endereço, e isso se lê como bug;
 * · 404 é mentira — a tela existe, só não é para este perfil.
 *
 * O mesmo componente serve de painel (dentro da taxonomia) e de tela cheia
 * (administração), com a mesma redação. E vale para os dois lados: qualquer
 * 403 vindo da API renderiza isto, porque a autoridade é o servidor — o
 * esconder-por-papel do cliente é só cortesia.
 */
import { ROTULO_PAPEL, type Papel } from '../tipos'
import { substituir } from '../roteador'
import { Botao, Estado } from './ui'

type Props = {
  /** `Você não tem acesso ao Dicionário` / `… à administração`. */
  titulo: string
  papel: Papel | null
  /** Destino da saída. `replaceState` para o voltar do navegador não devolver aqui. */
  saidaHref?: string
  saidaRotulo?: string
  /** Tela cheia usa `h1`; painel dentro de outra tela usa parágrafo. */
  tituloComo?: 'p' | 'h1'
}

export function AcessoNegado({
  titulo,
  papel,
  saidaHref = '#/taxonomia/gerar',
  saidaRotulo = 'Ir para Gerar',
  tituloComo = 'p',
}: Props) {
  const perfil = papel ? ROTULO_PAPEL[papel] : 'sem perfil definido'
  return (
    <Estado
      tipo="sem-resultado"
      titulo={titulo}
      tituloComo={tituloComo}
      texto={`Seu perfil é ${perfil}. Peça a um administrador para liberar o acesso, ou volte para o que você já usa.`}
    >
      <div className="linha">
        <Botao variante="secundario" onClick={() => substituir(saidaHref)}>
          {saidaRotulo}
        </Botao>
      </div>
    </Estado>
  )
}
