import { useId, useMemo, useState } from 'react'

import type { Entidade } from '../tipos'
import { Botao } from './ui'

interface Props {
  /** Rótulo do nível sendo adicionado — "campanha", "grupo", "anúncio". */
  rotulo: string
  candidatos: Entidade[]
  carregando?: boolean
  desabilitado?: boolean
  motivoDesabilitado?: string
  aoSelecionar: (entidade: Entidade) => void
}

/**
 * Combobox de busca por nome interno / match ID, escopado à hierarquia
 * certa pelo `candidatos` que o chamador já filtrou (grupo só oferece
 * grupos da campanha, anúncio só os do grupo — o servidor valida de novo,
 * a busca só evita que o erro apareça na prática).
 *
 * Padrão APG combobox escrito à mão — `<input>` + `<ul role="listbox">`,
 * sem dependência nova, mesmo espírito das abas por hash deste projeto.
 */
export function SeletorEntidadeExistente({
  rotulo,
  candidatos,
  carregando = false,
  desabilitado = false,
  motivoDesabilitado,
  aoSelecionar,
}: Props) {
  const idBase = useId()
  const idLista = `${idBase}-lista`
  const [aberto, setAberto] = useState(false)
  const [busca, setBusca] = useState('')

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase()
    if (termo === '') return candidatos
    return candidatos.filter(
      (c) =>
        c.nome_interno.toLowerCase().includes(termo) || c.match_id.toLowerCase().includes(termo),
    )
  }, [busca, candidatos])

  function escolher(entidade: Entidade) {
    aoSelecionar(entidade)
    setBusca('')
    setAberto(false)
  }

  if (desabilitado) {
    return <p className="texto-auxiliar">{motivoDesabilitado}</p>
  }

  return (
    <div className="seletor-entidade">
      <label htmlFor={idBase} className="apenas-leitor">
        Buscar {rotulo} existente por nome ou código
      </label>
      <input
        id={idBase}
        role="combobox"
        aria-expanded={aberto}
        aria-controls={idLista}
        aria-autocomplete="list"
        placeholder={`Adicionar ${rotulo} existente…`}
        value={busca}
        onFocus={() => setAberto(true)}
        onChange={(e) => {
          setBusca(e.target.value)
          setAberto(true)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setAberto(false)
        }}
        onBlur={() => {
          // Timeout curto: dá tempo do clique num item da lista registrar
          // antes do blur fechar a lista embaixo dele.
          setTimeout(() => setAberto(false), 150)
        }}
      />
      {aberto && (
        <ul id={idLista} role="listbox" className="seletor-entidade-lista" aria-label={`Resultados de ${rotulo}`}>
          {carregando && <li className="texto-auxiliar">Carregando…</li>}
          {!carregando && filtrados.length === 0 && (
            <li className="texto-auxiliar">Nenhum {rotulo} encontrado.</li>
          )}
          {!carregando &&
            filtrados.map((c) => (
              <li key={c.id} role="option" aria-selected={false}>
                <Botao
                  tamanho="sm"
                  variante="fantasma"
                  onClick={() => escolher(c)}
                >
                  {c.nome_interno} <span className="mono texto-auxiliar">{c.match_id}</span>
                </Botao>
              </li>
            ))}
        </ul>
      )}
    </div>
  )
}
