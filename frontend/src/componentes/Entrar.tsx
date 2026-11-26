/**
 * Tela de entrada (`#/entrar`) e o formulário que ela compartilha com o
 * diálogo de sessão expirada (UX-NAVEGACAO §5.3–§5.4).
 *
 * A regra que governa a redação daqui é de segurança, não de estilo:
 * **falhar não pode dizer quem existe**. O componente imprime a mensagem que
 * a API mandou, com um único fallback local, e nunca escolhe texto por
 * status. Nunca consulta se um usuário existe antes de enviar, e o
 * comportamento pós-falha é o mesmo para todos os motivos de credencial —
 * diferença de comportamento também é canal de enumeração.
 *
 * Não há "esqueci minha senha": redefinir é ação de administrador. A frase
 * estática diz o que fazer sem oferecer um caminho que não existe.
 */
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'

import { ErroRequisicao } from '../api'
import marcaSimbolo from '../ativos/marca.png'
import { useSessao } from '../sessao'
import type { Usuario } from '../tipos'
import { Botao } from './ui'

const FALLBACK = 'Não foi possível entrar. Tente de novo.'
const SEM_SERVIDOR = 'Não foi possível falar com o servidor. Tente de novo em instantes.'
const MUITAS_TENTATIVAS = 'Muitas tentativas. Espere um minuto e tente de novo.'

type Falha = { texto: string; codigo: string | null }

function traduzir(erro: unknown): Falha {
  if (erro instanceof ErroRequisicao) {
    const daApi = erro.corpo.mensagem?.trim()
    if (daApi) return { texto: daApi, codigo: erro.corpo.erro }
    return {
      texto: erro.status === 429 ? MUITAS_TENTATIVAS : FALLBACK,
      codigo: erro.corpo.erro ?? null,
    }
  }
  // `fetch` só rejeita quando a requisição nem chegou: rede, DNS, servidor
  // fora. É o único caso em que o cliente escreve o texto sozinho.
  return { texto: SEM_SERVIDOR, codigo: null }
}

type PropsFormulario = {
  /**
   * Usuário já conhecido (diálogo de reautenticação): vira campo somente
   * leitura. `readOnly`, não `disabled` — `disabled` rouba o foco e some do
   * leitor de tela, e o valor precisa continuar legível.
   */
  loginFixo?: string
  autenticar: (login: string, senha: string) => Promise<Usuario>
  rotuloBotao?: string
  /** Só a tela cheia foca sozinha; no diálogo o foco inicial é a senha. */
  focoInicial?: 'usuario' | 'senha'
  aoEntrar?: (usuario: Usuario) => void
}

export function FormularioEntrar({
  loginFixo,
  autenticar,
  rotuloBotao = 'Entrar',
  focoInicial = 'usuario',
  aoEntrar,
}: PropsFormulario) {
  const id = useId()
  const [login, setLogin] = useState(loginFixo ?? '')
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [falha, setFalha] = useState<Falha | null>(null)

  const campoUsuario = useRef<HTMLInputElement>(null)
  const campoSenha = useRef<HTMLInputElement>(null)

  // Única tela do produto com foco automático em campo: é a única em que a
  // primeira ação é digitar, sem exceção.
  useEffect(() => {
    if (focoInicial === 'senha') campoSenha.current?.focus()
    else campoUsuario.current?.focus()
  }, [focoInicial])

  const credencialInvalida = falha?.codigo === 'credenciais_invalidas'
  const idErro = `${id}-erro`

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    if (enviando) return
    setEnviando(true)
    setFalha(null)
    try {
      const usuario = await autenticar(loginFixo ?? login, senha)
      setSenha('')
      aoEntrar?.(usuario)
    } catch (erro) {
      const traduzida = traduzir(erro)
      setFalha(traduzida)
      // Senha limpa, usuário preservado: a pessoa erra a senha muito mais
      // vezes do que o usuário, e redigitar os dois é punição desnecessária.
      setSenha('')
      campoSenha.current?.focus()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="pilha" data-espaco="5" onSubmit={enviar} noValidate>
      {falha && (
        <p className="aviso-erro" role="alert" id={idErro}>
          {falha.texto}
        </p>
      )}

      <div>
        <label htmlFor={`${id}-usuario`}>Usuário</label>
        <input
          id={`${id}-usuario`}
          ref={campoUsuario}
          type="text"
          name="username"
          value={login}
          // Sem `type="email"` e sem `inputMode="email"`: a identidade não é
          // endereço, e o teclado com `@` seria mentira sobre o campo.
          autoComplete="username"
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
          readOnly={loginFixo !== undefined || enviando}
          aria-invalid={credencialInvalida || undefined}
          aria-describedby={falha ? idErro : undefined}
          onChange={(e) => setLogin(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor={`${id}-senha`}>Senha</label>
        <div className="campo-senha">
          <input
            id={`${id}-senha`}
            ref={campoSenha}
            type={mostrarSenha ? 'text' : 'password'}
            name="password"
            value={senha}
            autoComplete="current-password"
            readOnly={enviando}
            aria-invalid={credencialInvalida || undefined}
            aria-describedby={falha ? idErro : undefined}
            onChange={(e) => setSenha(e.target.value)}
          />
          <button
            type="button"
            className="botao"
            data-variante="fantasma"
            data-tamanho="sm"
            aria-pressed={mostrarSenha}
            onClick={() => setMostrarSenha((v) => !v)}
          >
            <span className="botao-rotulo">
              {mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
            </span>
          </button>
        </div>
      </div>

      <Botao type="submit" tamanho="lg" carregando={enviando}>
        {rotuloBotao}
      </Botao>
    </form>
  )
}

export function Entrar() {
  const { entrar, expirada } = useSessao()

  return (
    <div className="casca-conteudo entrar-casca">
      {/* Sem barra de topo e sem rodapé de links: não há para onde ir a
          partir daqui, e um menu de conta sem conta seria decoração. */}
      <p className="entrar-marca">
        <img
          className="simbolo-topo"
          src={marcaSimbolo}
          alt=""
          aria-hidden="true"
          width={256}
          height={256}
          decoding="async"
        />
        <span className="marca marca-logotipo" data-tamanho="sm">
          MDBuilder
        </span>
      </p>

      <main
        className="pagina contexto-pagina pilha entrar"
        data-largura="estreita"
        data-espaco="6"
      >
        <div className="card entrar-cartao pilha" data-espaco="6">
          <header className="pilha" data-espaco="2">
            {/* Sem `data-foco-rota` de propósito: esta é a única tela do
                produto cujo foco inicial é um CAMPO, e o efeito de rota do
                `App` roda depois do efeito de montagem do formulário — com o
                atributo aqui, o `h1` roubaria o foco do campo de usuário. */}
            <h1 className="titulo-tela">Entrar</h1>
            <p className="marca-subtitulo">
              Nomenclaturas padronizadas para campanhas de mídia paga
            </p>
          </header>

          {/* Tom neutro, `status` e não `alert`: expirar não é erro de quem
              está entrando agora. */}
          {expirada && (
            <p className="texto-auxiliar" role="status">
              Sua sessão expirou. Entre de novo.
            </p>
          )}

          <FormularioEntrar autenticar={entrar} />

          <p className="texto-auxiliar">
            Esqueceu a senha? Só um administrador pode redefinir.
          </p>
        </div>
      </main>

      <p className="entrar-nota">MediaBuild · uso local</p>
    </div>
  )
}

export default Entrar
