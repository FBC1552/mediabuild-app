import type { Abreviacao, CampoDoTemplate } from '../tipos'

interface Props {
  campo: CampoDoTemplate
  valor: string
  opcoes: Abreviacao[]
  invalido: boolean
  onChange: (valor: string) => void
}

/**
 * Campo renderizado a partir do template — nada aqui é hardcoded por
 * plataforma, nem o rótulo. Os dois tipos vêm da planilha do cliente:
 * "Drop list" vira `select` (o analista não deveria conseguir digitar um
 * termo que não existe) e "Campo livre N caracteres" vira `input` com
 * limite. O limite é reforçado no servidor; aqui ele só evita a digitação
 * inútil.
 */
export function CampoDinamico({ campo, valor, opcoes, invalido, onChange }: Props) {
  const id = `campo-${campo.chave}`
  const idDica = `${id}-dica`
  const dropList = campo.abreviar
  const excedeu = campo.maxCaracteres !== undefined && valor.length > campo.maxCaracteres

  // D-011: campo opcional em branco não some mais do nome — grava o marcador
  // e a posição fica fixa. Quem preenche precisa saber disso antes de deixar
  // em branco, não depois de ler a nomenclatura.
  const vazio = valor.trim() === ''
  const dica =
    campo.opcional && campo.marcadorAusencia
      ? vazio
        ? `Em branco, o nome recebe ${campo.marcadorAusencia} nesta posição.`
        : `Se ficar em branco, o nome recebe ${campo.marcadorAusencia} nesta posição.`
      : undefined

  return (
    <div>
      <label htmlFor={id}>
        {campo.rotulo}
        {campo.opcional && <span className="rotulo-anexo"> · opcional</span>}
        {!campo.opcional && dropList && opcoes.length === 0 && (
          <span className="rotulo-anexo" data-tom="alerta">
            {' '}
            · sem opções no dicionário
          </span>
        )}
        {campo.maxCaracteres !== undefined && (
          <span className="rotulo-anexo" data-tom={excedeu ? 'erro' : undefined}>
            {' '}
            · {valor.length}/{campo.maxCaracteres}
          </span>
        )}
      </label>

      {dropList ? (
        <select
          id={id}
          value={valor}
          aria-invalid={invalido}
          aria-describedby={dica ? idDica : undefined}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">
            {campo.opcional
              ? campo.marcadorAusencia
                ? `— nenhum (${campo.marcadorAusencia}) —`
                : '— nenhum —'
              : 'Selecione…'}
          </option>
          {opcoes.map((o) => (
            <option key={o.id} value={o.termo}>
              {o.termo} → {o.abreviacao}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          value={valor}
          aria-invalid={invalido || excedeu}
          aria-describedby={dica ? idDica : undefined}
          maxLength={campo.maxCaracteres}
          placeholder={
            campo.maxCaracteres !== undefined
              ? `Até ${campo.maxCaracteres} caracteres`
              : 'Texto livre'
          }
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {dica && (
        <p id={idDica} className="dica-campo">
          {dica}
        </p>
      )}
    </div>
  )
}
