import type { ErroApi, PreviewResposta } from '../tipos'
import { BotaoCopiar } from './ui'

interface Props {
  resultado: PreviewResposta | null
  erro: ErroApi | null
  carregando: boolean
  /**
   * O que o analista digitou no campo que o motor recusou. Vem do formulário,
   * não da mensagem de erro — o corpo do 422 traz `campo` e `opcoes`, e é o
   * `PainelNivel` que sabe qual valor está naquela chave.
   */
  termoRecusado?: string
}

/**
 * Preview ao vivo — o recurso que mais reduz erro do analista, porque mostra
 * o nome final antes de qualquer coisa ser salva.
 *
 * Fica ao pé do formulário, numa barra escura: é o resultado, e a inversão de
 * superfície é o que o separa dos campos sem precisar de moldura nem de cor
 * de estado. O erro NÃO usa a barra escura — não existe token de erro para
 * superfície invertida, e vermelho aproximado no escuro reprova AA.
 */
export function Preview({ resultado, erro, carregando, termoRecusado }: Props) {
  if (erro) {
    // O atalho entre o erro e o conserto (§6.5). Hoje o analista lê o erro,
    // troca de aba e redigita tudo; o link abre o Dicionário já filtrado pelo
    // termo recusado e com o campo De preenchido.
    //
    // A reação é ao CÓDIGO (`termo_desconhecido`, de `app/erros_http.py`),
    // nunca ao texto: mensagem é redação e muda, código é contrato. E o termo
    // não é extraído da mensagem — quem o conhece é o formulário, que o
    // entrega em `termoRecusado`.
    const oferecerCadastro = erro.erro === 'termo_desconhecido' && Boolean(termoRecusado)

    return (
      <div role="alert" className="laudo" data-tipo="erro">
        <p className="laudo-titulo">{erro.mensagem}</p>
        {erro.opcoes && erro.opcoes.length > 0 && (
          <p className="texto-auxiliar">
            Cadastre o termo no dicionário ou escolha um dos existentes.
          </p>
        )}
        {oferecerCadastro && (
          <p className="laudo-detalhe">
            <a
              className="botao"
              data-variante="secundario"
              data-tamanho="sm"
              href={`#/taxonomia/dicionario?q=${encodeURIComponent(termoRecusado!)}`}
            >
              <span className="botao-rotulo">Cadastrar "{termoRecusado}" no dicionário</span>
            </a>
          </p>
        )}
      </div>
    )
  }

  if (!resultado) {
    return (
      <div className="preview-barra" data-estado="vazio">
        <p className="preview-titulo">Preview da nomenclatura</p>
        <p className="preview-medida">
          {carregando ? 'Gerando…' : 'Preencha os campos para ver o nome.'}
        </p>
      </div>
    )
  }

  const { nomenclatura, caracteres, limite_caracteres, match_id_provisorio } = resultado
  const proximoDoLimite = limite_caracteres !== null && caracteres > limite_caracteres * 0.9

  return (
    <div className="preview-barra" data-estado="ok" aria-busy={carregando || undefined}>
      <p className="preview-titulo">Preview da nomenclatura</p>

      <div className="linha" data-espaco="3">
        <code className="nomenclatura">{nomenclatura}</code>
        <BotaoCopiar texto={nomenclatura} />
      </div>

      <p className="preview-medida" data-tom={proximoDoLimite ? 'alerta' : undefined}>
        {caracteres}
        {limite_caracteres !== null && ` / ${limite_caracteres}`} caracteres
        {match_id_provisorio && ' · o código final é definido ao salvar'}
      </p>
    </div>
  )
}
