import { useEffect, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import {
  type Abreviacao,
  type ErroApi,
  type Nivel,
  type PreviewResposta,
  ROTULO_NIVEL,
  type Template,
  camposDoTemplate,
} from '../tipos'
import { CampoDinamico } from './CampoDinamico'
import { Preview } from './Preview'

interface Props {
  nivel: Nivel
  plataformaId: string
  template: Template
  dicionario: Abreviacao[]
  nomeInterno: string
  campos: Record<string, string>
  bloqueado: boolean
  motivoBloqueio?: string
  salvo?: string
  onNomeInterno: (v: string) => void
  onCampo: (chave: string, valor: string) => void
  onValidade: (valido: boolean) => void
}

export function PainelNivel({
  nivel,
  plataformaId,
  template,
  dicionario,
  nomeInterno,
  campos,
  bloqueado,
  motivoBloqueio,
  salvo,
  onNomeInterno,
  onCampo,
  onValidade,
}: Props) {
  const [resultado, setResultado] = useState<PreviewResposta | null>(null)
  const [erro, setErro] = useState<ErroApi | null>(null)
  const [carregando, setCarregando] = useState(false)

  const doTemplate = camposDoTemplate(template)
  // Campo opcional em branco não impede o preview — o motor grava o
  // marcador de ausência na posição dele (D-011).
  const completo = doTemplate.every(
    (c) => c.opcional || (campos[c.chave] ?? '').trim() !== '',
  )

  // Preview ao vivo, com debounce para não disparar a cada tecla.
  useEffect(() => {
    if (bloqueado || !completo) {
      setResultado(null)
      setErro(null)
      onValidade(false)
      return
    }

    let cancelado = false
    setCarregando(true)

    const timer = setTimeout(async () => {
      try {
        const r = await api.preview({ plataforma_id: plataformaId, nivel, campos })
        if (cancelado) return
        setResultado(r)
        setErro(null)
        onValidade(true)
      } catch (e) {
        if (cancelado) return
        setResultado(null)
        setErro(e instanceof ErroRequisicao ? e.corpo : { erro: 'erro', mensagem: String(e) })
        onValidade(false)
      } finally {
        if (!cancelado) setCarregando(false)
      }
    }, 300)

    return () => {
      cancelado = true
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bloqueado, completo, plataformaId, nivel, JSON.stringify(campos)])

  const opcoesDe = (categoria: string) => dicionario.filter((a) => a.categoria === categoria)

  return (
    <section
      className="card bloco pilha contexto"
      data-espaco="4"
      data-bloqueado={bloqueado || undefined}
      aria-disabled={bloqueado}
    >
      <header className="linha" data-alinhar="entre">
        {/* `tabIndex={-1}`: quando a árvore troca o modo do gerador, o foco
            vem para o título do painel que passou a valer — sem isso, num
            contêiner estreito o formulário fica acima da ação clicada e o
            usuário de teclado não é levado a lugar nenhum. */}
        <h2 className="painel-titulo" id={`titulo-nivel-${nivel}`} tabIndex={-1}>
          {ROTULO_NIVEL[nivel]}
        </h2>
        {salvo ? (
          <span className="painel-salvo">✓ {salvo}</span>
        ) : (
          <span className="rotulo-secao">v{template.versao}</span>
        )}
      </header>

      {bloqueado ? (
        <p className="texto-auxiliar">{motivoBloqueio}</p>
      ) : (
        <>
          {/* Com 6-7 campos por nível, uma coluna só vira uma tira longa
              demais; a grade quebra sozinha em contêiner estreito, sem
              consulta nenhuma — na coluna larga dá 2-3 colunas de campo. */}
          <div className="grade campos">
            <div className="campo-largo">
              <label htmlFor={`nome-${nivel}`}>Nome interno</label>
              <input
                id={`nome-${nivel}`}
                value={nomeInterno}
                placeholder="Como você chama isso internamente"
                onChange={(e) => onNomeInterno(e.target.value)}
              />
            </div>

            {doTemplate.map((campo) => (
              <CampoDinamico
                key={campo.chave}
                campo={campo}
                valor={campos[campo.chave] ?? ''}
                opcoes={opcoesDe(campo.categoria)}
                invalido={erro?.campo === campo.chave}
                onChange={(v) => onCampo(campo.chave, v)}
              />
            ))}
          </div>

          {/* O resultado ao pé do formulário, não ao lado: é o que se lê
              depois de preencher, e a barra escura já é o próprio rótulo. */}
          {/* O valor que o motor recusou sai do próprio formulário: `campo` é
              a chave da posição (`interesse_2`), e o `Preview` só precisa do
              texto para montar o `?q=` do Dicionário. */}
          <Preview
            resultado={resultado}
            erro={erro}
            carregando={carregando}
            termoRecusado={erro?.campo ? (campos[erro.campo] ?? '').trim() || undefined : undefined}
          />
        </>
      )}
    </section>
  )
}
