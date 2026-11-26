/**
 * Sessão, papel e permissões (D-014).
 *
 * Três coisas que este módulo garante, e que são o motivo de ele existir
 * separado das telas:
 *
 * 1. **O boot tem três estados, não dois.** Enquanto `GET /auth/eu` não
 *    responde, a fase é `verificando` — e nem a tela de login nem o produto
 *    aparecem. Tratar "ainda não sei" como "não logado" faz a tela de login
 *    piscar em toda abertura de quem já tem sessão.
 *
 * 2. **Expirar sessão não é navegar.** O 401 de uma chamada qualquer liga uma
 *    flag; quem estava trabalhando continua com a tela e o formulário
 *    montados, e resolve num diálogo por cima (UX-NAVEGACAO §4.4). Nada é
 *    desmontado, nada é limpo, nada é reenviado sozinho.
 *
 * 3. **O papel vem do servidor e nada mais.** Não se infere papel de rota, de
 *    localStorage nem da presença de um botão. E o gating daqui é COSMÉTICO:
 *    a autoridade é o backend, que devolve 403 de qualquer jeito.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { api, ErroRequisicao, observarFalhaDeAutenticacao } from './api'
import { CHAVE_ULTIMO_ASSUNTO } from './componentes/SeletorDeAssunto'
import type { Papel, Usuario } from './tipos'

export type { Papel, Usuario }

/**
 * Rascunho do gerador. A chave mora aqui porque quem a APAGA é o logout —
 * rascunho com nome de cliente sobrevivendo numa máquina compartilhada é
 * vazamento. Quem a ESCREVE é o `Gerador` (etapa 2).
 */
export const CHAVE_RASCUNHO_GERADOR = 'mdbd:rascunho-gerador'

export type FaseSessao = 'verificando' | 'anonimo' | 'autenticado'

export type EstadoSessao =
  | { fase: 'verificando' }
  | { fase: 'anonimo' }
  | { fase: 'autenticado'; usuario: Usuario }

export interface Permissoes {
  /** Aba Dicionário: cadastrar e corrigir abreviações. */
  podeVerDicionario: boolean
  /** Qualquer ação destrutiva do produto. */
  podeExcluir: boolean
  /** Área administrativa (`#/admin/*`). */
  podeAdministrar: boolean
}

/**
 * Predicados NOMEADOS PELA AÇÃO, nunca por papel. `papel === 'admin'`
 * espalhado pelo JSX é o que torna impossível responder "o que muda quando
 * criarmos um quarto papel?".
 */
export function permissoesDe(papel: Papel | null): Permissoes {
  const plenoOuAcima = papel === 'pleno' || papel === 'admin'
  return {
    podeVerDicionario: plenoOuAcima,
    podeExcluir: plenoOuAcima,
    podeAdministrar: papel === 'admin',
  }
}

export interface ContextoDeSessao {
  estado: EstadoSessao
  usuario: Usuario | null
  papel: Papel | null
  permissoes: Permissoes
  /**
   * Muda SÓ em login e logout — nunca em troca de rota, nunca na
   * reautenticação depois de expirar. É a `key` do ramo da taxonomia, e a
   * única exceção autorizada ao I-1/I-2 (UX-NAVEGACAO §5.5).
   */
  idSessao: number
  /** Havia sessão e ela venceu: o diálogo de reautenticação está devido. */
  expirada: boolean
  entrar: (login: string, senha: string) => Promise<Usuario>
  /** Mesma chamada de `entrar`, mas sem remontar nada: a pessoa é a mesma. */
  reautenticar: (login: string, senha: string) => Promise<Usuario>
  sair: () => Promise<void>
}

const Contexto = createContext<ContextoDeSessao | null>(null)

/**
 * Endereço que a pessoa tentou abrir sem sessão. Fica em memória de MÓDULO,
 * não na URL: `?next=` num roteador por hash vira string colável e apontável
 * para fora, e o login não é compartilhado por link (§5.2).
 */
let destinoPretendido: string | null = null

export function lembrarDestino(hash: string) {
  if (hash && hash !== '#/entrar' && hash !== '#/') destinoPretendido = hash
}

/** §5.2: destino pretendido → último assunto → seletor de assunto. */
export function destinoPosLogin(): string {
  const pretendido = destinoPretendido
  destinoPretendido = null
  if (pretendido) return pretendido
  try {
    const assunto = window.localStorage.getItem(CHAVE_ULTIMO_ASSUNTO)
    if (assunto === 'taxonomia') return '#/taxonomia/gerar'
    if (assunto === 'plano') return '#/plano'
  } catch {
    // Sem localStorage cai no seletor, que é o destino honesto.
  }
  return '#/assunto'
}

function limparRascunhos() {
  try {
    window.sessionStorage.removeItem(CHAVE_RASCUNHO_GERADOR)
  } catch {
    // Sem sessionStorage não há rascunho a limpar.
  }
}

type Props = {
  children: ReactNode
  /**
   * Costura de teste: com ela o provedor não chama `GET /auth/eu` e já nasce
   * resolvido. `undefined` = comportamento de produção.
   */
  sessaoInicial?: Usuario | null
}

export function ProvedorSessao({ children, sessaoInicial }: Props) {
  const [estado, setEstado] = useState<EstadoSessao>(() =>
    sessaoInicial === undefined
      ? { fase: 'verificando' }
      : sessaoInicial === null
        ? { fase: 'anonimo' }
        : { fase: 'autenticado', usuario: sessaoInicial },
  )
  const [idSessao, setIdSessao] = useState(1)
  const [expirada, setExpirada] = useState(false)

  // A fase é lida por um ouvinte de módulo (o de 401), que não pode fechar
  // sobre um valor velho — daí o ref ao lado do estado.
  const faseRef = useRef<FaseSessao>(estado.fase)
  faseRef.current = estado.fase

  useEffect(() => {
    if (sessaoInicial !== undefined) return
    const controle = new AbortController()
    api.auth
      .eu(controle.signal)
      .then((usuario) => setEstado({ fase: 'autenticado', usuario }))
      .catch((erro: unknown) => {
        if (erro instanceof DOMException && erro.name === 'AbortError') return
        // Qualquer falha no boot — 401, servidor fora, rede — cai em anônimo.
        // A tela de login é o único lugar em que a pessoa pode fazer algo a
        // respeito, e ela mostra o erro real quando o `Entrar` também falhar.
        setEstado({ fase: 'anonimo' })
      })
    return () => controle.abort()
  }, [sessaoInicial])

  // Interceptação global do 401 (§4.4). Ver o comentário longo: a reação
  // depende de haver ou não sessão estabelecida, não só do código.
  useEffect(() => {
    return observarFalhaDeAutenticacao((erro: ErroRequisicao) => {
      if (faseRef.current === 'autenticado') {
        // Estava trabalhando. NUNCA desmontar: é regressão do D-005 tanto
        // quanto trocar a `key` do gerador. Vale para `sessao_expirada` e
        // também para `nao_autenticado` — o cookie pode ter sido apagado por
        // fora, e o desfecho para quem está na tela é o mesmo: entrar de novo
        // e continuar de onde parou.
        setExpirada(true)
        return
      }
      // Sem sessão estabelecida (boot, ou já deslogado): não há formulário a
      // preservar, e o lugar certo é a tela de login.
      if (erro.corpo.erro === 'nao_autenticado' || erro.corpo.erro === 'sessao_expirada') {
        setEstado({ fase: 'anonimo' })
      }
    })
  }, [])

  const entrar = useCallback(async (login: string, senha: string) => {
    const usuario = await api.auth.entrar(login, senha)
    setEstado({ fase: 'autenticado', usuario })
    setExpirada(false)
    // Sessão NOVA: outra pessoa pode ter sentado na máquina, então o ramo da
    // taxonomia remonta e nada da sessão anterior é herdado.
    setIdSessao((n) => n + 1)
    return usuario
  }, [])

  const reautenticar = useCallback(async (login: string, senha: string) => {
    const usuario = await api.auth.entrar(login, senha)
    setEstado({ fase: 'autenticado', usuario })
    setExpirada(false)
    // `idSessao` NÃO muda: é a mesma pessoa continuando o mesmo trabalho, e
    // remontar aqui apagaria exatamente o formulário que o diálogo prometeu
    // preservar. Nada é reenviado — o usuário aperta o botão de novo.
    return usuario
  }, [])

  const sair = useCallback(async () => {
    try {
      await api.auth.sair()
    } catch {
      // 204 sempre, mas rede cai. Sair localmente mesmo assim: insistir numa
      // sessão que o usuário pediu para encerrar é pior que a chamada perdida.
    }
    limparRascunhos()
    setExpirada(false)
    setEstado({ fase: 'anonimo' })
    setIdSessao((n) => n + 1)
  }, [])

  const valor = useMemo<ContextoDeSessao>(() => {
    const usuario = estado.fase === 'autenticado' ? estado.usuario : null
    const papel = usuario?.papel ?? null
    return {
      estado,
      usuario,
      papel,
      permissoes: permissoesDe(papel),
      idSessao,
      expirada,
      entrar,
      reautenticar,
      sair,
    }
  }, [estado, idSessao, expirada, entrar, reautenticar, sair])

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useSessao(): ContextoDeSessao {
  const valor = useContext(Contexto)
  if (!valor) throw new Error('useSessao() exige <ProvedorSessao> acima na árvore.')
  return valor
}

export function usePermissao(): Permissoes {
  return useSessao().permissoes
}
