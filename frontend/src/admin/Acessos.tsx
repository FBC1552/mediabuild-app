/**
 * Gestão de acessos (`#/admin/acessos`, UX-NAVEGACAO §3.6).
 *
 * Quatro decisões que a tela materializa:
 *
 * 1. **A senha provisória aparece UMA vez.** O banco guarda só o hash scrypt —
 *    nem o servidor a recupera. Fechar o diálogo perde o valor, e a tela diz
 *    isso na cara, com botão de copiar ao lado.
 * 2. **Papel edita inline.** É o campo que mais muda e não merece uma tela.
 *    Salva na hora, confirma em `role="status"`, sem botão de salvar por linha.
 * 3. **Desativar é a ação recomendada; excluir é a exceção.** Desativar
 *    preserva a trilha de quem gerou o quê. Excluir é a única ação
 *    verdadeiramente destrutiva do produto (taxonomia é imutável, plano tem
 *    histórico), então o diálogo exige digitar o usuário da pessoa.
 * 4. **O admin não altera a si mesmo.** É o caso legítimo de "desabilitado com
 *    motivo" (§4.1): é condição, não permissão — e o motivo é acionável (peça
 *    a outro administrador).
 *
 * A validação de `login` acontece aqui só para dar erro imediato. A autoridade
 * é o 422 do servidor, e o cliente imprime a mensagem que ele mandou.
 */
import { useCallback, useEffect, useId, useRef, useState } from 'react'

import { api, ErroRequisicao } from '../api'
import { Botao, BotaoCopiar, Esqueleto, Estado } from '../componentes/ui'
import { useSessao } from '../sessao'
import { contemBusca } from '../texto'
import { REGEX_LOGIN, ROTULO_PAPEL, type Papel, type SenhaProvisoria, type Usuario } from '../tipos'
import { CascaAdmin } from './CascaAdmin'
import { formatarQuando, gerarSenhaProvisoria } from './formato'

const PAPEIS: Papel[] = ['basico', 'pleno', 'admin']

type Carga =
  | { fase: 'carregando' }
  | { fase: 'erro'; mensagem: string }
  | { fase: 'pronto'; usuarios: Usuario[] }

type Situacao = 'todos' | 'ativos' | 'desativados'

/** `ErroRequisicao` traz `mensagem` pronta; qualquer outra coisa é rede. */
function mensagemDe(erro: unknown, padrao: string): string {
  return erro instanceof ErroRequisicao ? erro.corpo.mensagem : padrao
}

export default function Acessos() {
  const { usuario: eu } = useSessao()
  const [carga, setCarga] = useState<Carga>({ fase: 'carregando' })
  const [busca, setBusca] = useState('')
  const [papelFiltro, setPapelFiltro] = useState<Papel | ''>('')
  const [situacao, setSituacao] = useState<Situacao>('todos')
  const [aviso, setAviso] = useState('')
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  const [criando, setCriando] = useState(false)
  const [senhaExibida, setSenhaExibida] = useState<SenhaProvisoria | null>(null)
  const [aExcluir, setAExcluir] = useState<Usuario | null>(null)

  const idBusca = useId()
  const idPapel = useId()
  const idSituacao = useId()

  const carregar = useCallback(async (signal?: AbortSignal) => {
    setCarga({ fase: 'carregando' })
    try {
      const usuarios = await api.usuarios.listar(signal)
      if (signal?.aborted) return
      setCarga({ fase: 'pronto', usuarios })
    } catch (erro) {
      if (signal?.aborted) return
      setCarga({ fase: 'erro', mensagem: mensagemDe(erro, 'Não foi possível carregar os acessos.') })
    }
  }, [])

  useEffect(() => {
    const controle = new AbortController()
    void carregar(controle.signal)
    return () => controle.abort()
  }, [carregar])

  const usuarios = carga.fase === 'pronto' ? carga.usuarios : []

  // Derivado no corpo do render: filtrar um array de dezenas de itens é mais
  // barato que comparar dependências de um useMemo.
  const visiveis = usuarios.filter((u) => {
    if (papelFiltro && u.papel !== papelFiltro) return false
    if (situacao === 'ativos' && !u.ativo) return false
    if (situacao === 'desativados' && u.ativo) return false
    if (!busca.trim()) return true
    return contemBusca(u.nome, busca) || contemBusca(u.login, busca)
  })

  /** Toda mutação segue o mesmo roteiro: age, anuncia, recarrega. */
  async function agir(acao: () => Promise<void>, sucesso: string, falha: string) {
    setErroAcao(null)
    try {
      await acao()
      setAviso(sucesso)
      await carregar()
    } catch (erro) {
      // `ultimo_admin` e `auto_exclusao` chegam como 409 com mensagem pronta.
      // Mostrar a mensagem do servidor, nunca um genérico que apaga o motivo.
      setErroAcao(mensagemDe(erro, falha))
    }
  }

  function trocarPapel(alvo: Usuario, papel: Papel) {
    void agir(
      async () => {
        await api.usuarios.atualizar(alvo.id, { papel })
      },
      `Papel de ${alvo.nome} alterado para ${ROTULO_PAPEL[papel]}.`,
      'Não foi possível alterar o papel.',
    )
  }

  function alternarAtivo(alvo: Usuario) {
    void agir(
      async () => {
        await api.usuarios.atualizar(alvo.id, { ativo: !alvo.ativo })
      },
      alvo.ativo ? `Acesso de ${alvo.nome} desativado.` : `Acesso de ${alvo.nome} reativado.`,
      'Não foi possível alterar a situação do acesso.',
    )
  }

  async function redefinirSenha(alvo: Usuario) {
    setErroAcao(null)
    try {
      setSenhaExibida(await api.usuarios.redefinirSenha(alvo.id))
      setAviso(`Senha provisória de ${alvo.nome} gerada.`)
    } catch (erro) {
      setErroAcao(mensagemDe(erro, 'Não foi possível redefinir a senha.'))
    }
  }

  return (
    <CascaAdmin area="acessos">
      <div className="pilha" data-espaco="2">
        <h2 className="titulo-secao">Gestão de acessos</h2>
        <p className="texto-auxiliar medida">
          Desativar preserva a trilha de quem gerou cada nomenclatura. Excluir apaga essa
          ligação e não tem volta.
        </p>
      </div>

      <span className="apenas-leitor" role="status" aria-live="polite">
        {aviso}
      </span>

      <div className="filtros">
        <div>
          <label htmlFor={idBusca}>Buscar pessoa</label>
          <input
            id={idBusca}
            type="search"
            value={busca}
            placeholder="nome ou usuário"
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor={idPapel}>Papel</label>
          <select
            id={idPapel}
            value={papelFiltro}
            onChange={(e) => setPapelFiltro(e.target.value as Papel | '')}
          >
            <option value="">Todos</option>
            {PAPEIS.map((p) => (
              <option key={p} value={p}>
                {ROTULO_PAPEL[p]}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={idSituacao}>Situação</label>
          <select
            id={idSituacao}
            value={situacao}
            onChange={(e) => setSituacao(e.target.value as Situacao)}
          >
            <option value="todos">Todas</option>
            <option value="ativos">Ativos</option>
            <option value="desativados">Desativados</option>
          </select>
        </div>

        <div className="filtros-acoes">
          <Botao onClick={() => setCriando(true)}>+ Novo acesso</Botao>
        </div>
      </div>

      {erroAcao && (
        <div role="alert" className="aviso-erro">
          {erroAcao}
        </div>
      )}

      {carga.fase === 'carregando' && (
        <div className="pilha" data-espaco="3" aria-busy="true">
          {[0, 1, 2, 3, 4].map((n) => (
            <Esqueleto key={n} forma="texto" final={n === 4} />
          ))}
        </div>
      )}

      {carga.fase === 'erro' && (
        <Estado tipo="erro" titulo="Não foi possível carregar os acessos." texto={carga.mensagem}>
          <div className="linha">
            <Botao variante="secundario" onClick={() => void carregar()}>
              Tentar de novo
            </Botao>
          </div>
        </Estado>
      )}

      {carga.fase === 'pronto' && usuarios.length === 0 && (
        <Estado tipo="vazio" titulo="Nenhum acesso cadastrado." />
      )}

      {carga.fase === 'pronto' && usuarios.length > 0 && visiveis.length === 0 && (
        <Estado tipo="sem-resultado" titulo="Ninguém encontrado com esses filtros.">
          <div className="linha">
            <Botao
              variante="secundario"
              onClick={() => {
                setBusca('')
                setPapelFiltro('')
                setSituacao('todos')
              }}
            >
              Limpar filtros
            </Botao>
          </div>
        </Estado>
      )}

      {carga.fase === 'pronto' && visiveis.length > 0 && (
        <div className="tabela-rolagem">
          <table className="tabela" data-densidade="alta">
            <caption className="apenas-leitor">Pessoas com acesso ao MediaBuild</caption>
            <thead>
              <tr>
                <th className="tabela-celula" data-coluna="principal" scope="col">
                  Nome
                </th>
                <th className="tabela-celula" scope="col">
                  Usuário
                </th>
                <th className="tabela-celula" scope="col">
                  Papel
                </th>
                <th className="tabela-celula" scope="col">
                  Situação
                </th>
                <th className="tabela-celula" scope="col">
                  Último acesso
                </th>
                <th className="tabela-celula" data-coluna="acao" scope="col">
                  <span className="apenas-leitor">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((u) => {
                const souEu = eu?.id === u.id
                return (
                  <tr key={u.id}>
                    <td className="tabela-celula" data-coluna="principal">
                      {u.nome}
                    </td>
                    <td className="tabela-celula mono">{u.login}</td>
                    <td className="tabela-celula">
                      <SeletorPapel usuario={u} bloqueado={souEu} aoMudar={trocarPapel} />
                    </td>
                    <td className="tabela-celula">{u.ativo ? 'Ativo' : 'Desativado'}</td>
                    <td className="tabela-celula">{formatarQuando(u.ultimo_acesso_em)}</td>
                    <td className="tabela-celula" data-coluna="acao">
                      <MenuAcoes
                        usuario={u}
                        souEu={souEu}
                        aoAlternarAtivo={() => alternarAtivo(u)}
                        aoRedefinirSenha={() => void redefinirSenha(u)}
                        aoExcluir={() => setAExcluir(u)}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <DialogoNovoAcesso
        aberto={criando}
        aoFechar={() => setCriando(false)}
        aoCriar={(criado, senha) => {
          setCriando(false)
          setSenhaExibida({ usuario_id: criado.id, login: criado.login, senha_provisoria: senha })
          setAviso(`Acesso de ${criado.nome} criado.`)
          void carregar()
        }}
      />

      <DialogoSenhaProvisoria dados={senhaExibida} aoFechar={() => setSenhaExibida(null)} />

      <DialogoExcluir
        usuario={aExcluir}
        aoFechar={() => setAExcluir(null)}
        aoConfirmar={(alvo) => {
          setAExcluir(null)
          void agir(
            async () => {
              await api.usuarios.remover(alvo.id)
            },
            `Acesso de ${alvo.nome} excluído.`,
            'Não foi possível excluir o acesso.',
          )
        }}
      />
    </CascaAdmin>
  )
}

/* ---------------------------------------------------------------------------
 * Papel inline
 * ------------------------------------------------------------------------- */

function SeletorPapel({
  usuario,
  bloqueado,
  aoMudar,
}: {
  usuario: Usuario
  bloqueado: boolean
  aoMudar: (usuario: Usuario, papel: Papel) => void
}) {
  const id = useId()
  return (
    <>
      <label className="apenas-leitor" htmlFor={id}>
        Papel de {usuario.nome}
      </label>
      <select
        id={id}
        value={usuario.papel}
        disabled={bloqueado}
        aria-describedby={bloqueado ? `${id}-motivo` : undefined}
        onChange={(e) => aoMudar(usuario, e.target.value as Papel)}
      >
        {PAPEIS.map((p) => (
          <option key={p} value={p}>
            {ROTULO_PAPEL[p]}
          </option>
        ))}
      </select>
      {/* Desabilitado COM MOTIVO (§4.1): é condição, não permissão. */}
      {bloqueado && (
        <span className="texto-auxiliar" id={`${id}-motivo`}>
          Você não pode alterar o próprio acesso.
        </span>
      )}
    </>
  )
}

/* ---------------------------------------------------------------------------
 * Menu de ações da linha
 * ------------------------------------------------------------------------- */

function MenuAcoes({
  usuario,
  souEu,
  aoAlternarAtivo,
  aoRedefinirSenha,
  aoExcluir,
}: {
  usuario: Usuario
  souEu: boolean
  aoAlternarAtivo: () => void
  aoRedefinirSenha: () => void
  aoExcluir: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const idPainel = useId()
  const gatilho = useRef<HTMLButtonElement>(null)
  const painel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!aberto) return
    function aoApontar(evento: PointerEvent) {
      const alvo = evento.target as Node
      if (painel.current?.contains(alvo) || gatilho.current?.contains(alvo)) return
      setAberto(false)
    }
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key !== 'Escape') return
      setAberto(false)
      gatilho.current?.focus()
    }
    document.addEventListener('pointerdown', aoApontar)
    document.addEventListener('keydown', aoTeclar)
    return () => {
      document.removeEventListener('pointerdown', aoApontar)
      document.removeEventListener('keydown', aoTeclar)
    }
  }, [aberto])

  function executar(acao: () => void) {
    setAberto(false)
    acao()
  }

  return (
    <div className="menu-conta">
      <button
        type="button"
        className="menu-conta-gatilho"
        ref={gatilho}
        aria-expanded={aberto}
        aria-controls={idPainel}
        onClick={() => setAberto((v) => !v)}
      >
        <span aria-hidden="true">⋯</span>
        <span className="apenas-leitor">Ações de {usuario.nome}</span>
      </button>

      {aberto && (
        <div className="menu-conta-painel card pilha" data-espaco="2" id={idPainel} ref={painel}>
          <button
            type="button"
            className="menu-conta-item"
            onClick={() => executar(aoAlternarAtivo)}
          >
            {usuario.ativo ? 'Desativar acesso' : 'Reativar acesso'}
          </button>
          <button
            type="button"
            className="menu-conta-item"
            onClick={() => executar(aoRedefinirSenha)}
          >
            Redefinir senha
          </button>

          <hr className="menu-conta-divisor" />

          {/* Último e separado: é a única ação verdadeiramente destrutiva do
              produto. Sobre si mesmo é desabilitado com motivo, não escondido. */}
          <button
            type="button"
            className="menu-conta-item menu-acao-perigo"
            disabled={souEu}
            onClick={() => executar(aoExcluir)}
          >
            Excluir
          </button>
          {souEu && (
            <span className="texto-auxiliar">Você não pode alterar o próprio acesso.</span>
          )}
        </div>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------------------
 * Diálogos
 * ------------------------------------------------------------------------- */

/** `<dialog>` nativo: fundo, trap de foco e `inert` vêm do navegador. */
function useDialogo(aberto: boolean) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const elemento = ref.current
    if (!elemento) return
    if (aberto && !elemento.open) {
      if (typeof elemento.showModal === 'function') elemento.showModal()
      else elemento.setAttribute('open', '')
    }
    if (!aberto && elemento.open) {
      if (typeof elemento.close === 'function') elemento.close()
      else elemento.removeAttribute('open')
    }
  }, [aberto])
  return ref
}

function DialogoNovoAcesso({
  aberto,
  aoFechar,
  aoCriar,
}: {
  aberto: boolean
  aoFechar: () => void
  aoCriar: (usuario: Usuario, senha: string) => void
}) {
  const ref = useDialogo(aberto)
  const [nome, setNome] = useState('')
  const [login, setLogin] = useState('')
  const [papel, setPapel] = useState<Papel>('basico')
  const [erro, setErro] = useState<string | null>(null)
  const [campoInvalido, setCampoInvalido] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)
  const idNome = useId()
  const idLogin = useId()
  const idPapel = useId()

  useEffect(() => {
    if (!aberto) return
    setNome('')
    setLogin('')
    setPapel('basico')
    setErro(null)
    setCampoInvalido(null)
  }, [aberto])

  const loginValido = REGEX_LOGIN.test(login)

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault()
    // Erro imediato no cliente; a autoridade continua sendo o 422 do servidor.
    if (!loginValido) {
      setCampoInvalido('login')
      setErro('O usuário aceita letras, números, ponto, hífen e sublinhado — de 3 a 60.')
      return
    }
    setSalvando(true)
    setErro(null)
    setCampoInvalido(null)
    const senha = gerarSenhaProvisoria()
    try {
      const criado = await api.usuarios.criar({ nome: nome.trim(), login, senha, papel })
      aoCriar(criado, senha)
    } catch (e) {
      setErro(mensagemDe(e, 'Não foi possível criar o acesso.'))
      if (e instanceof ErroRequisicao && e.campo) setCampoInvalido(e.campo)
      else if (e instanceof ErroRequisicao && e.status === 409) setCampoInvalido('login')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <dialog
      className="dialogo"
      data-tamanho="lg"
      ref={ref}
      aria-label="Novo acesso"
      onCancel={(e) => {
        e.preventDefault()
        aoFechar()
      }}
    >
      {aberto && (
        <form className="pilha" data-espaco="5" onSubmit={(e) => void enviar(e)}>
          <h2 className="painel-titulo">Novo acesso</h2>

          {erro && (
            <div role="alert" className="aviso-erro">
              {erro}
            </div>
          )}

          <div>
            <label htmlFor={idNome}>Nome</label>
            <input id={idNome} value={nome} required onChange={(e) => setNome(e.target.value)} />
          </div>

          <div>
            <label htmlFor={idLogin}>Usuário</label>
            <input
              id={idLogin}
              value={login}
              required
              spellCheck={false}
              autoCapitalize="none"
              autoComplete="off"
              aria-invalid={campoInvalido === 'login' || undefined}
              aria-describedby={`${idLogin}-dica`}
              onChange={(e) => setLogin(e.target.value)}
            />
            <span className="texto-auxiliar" id={`${idLogin}-dica`}>
              Letras, números, ponto, hífen e sublinhado. Sem espaço e sem arroba.
            </span>
          </div>

          <div>
            <label htmlFor={idPapel}>Papel</label>
            <select id={idPapel} value={papel} onChange={(e) => setPapel(e.target.value as Papel)}>
              {PAPEIS.map((p) => (
                <option key={p} value={p}>
                  {ROTULO_PAPEL[p]}
                </option>
              ))}
            </select>
          </div>

          <p className="texto-auxiliar">
            A senha provisória é gerada pelo sistema e mostrada uma única vez depois de criar.
          </p>

          <div className="linha" data-alinhar="fim">
            <Botao variante="fantasma" onClick={aoFechar}>
              Cancelar
            </Botao>
            <Botao type="submit" carregando={salvando} disabled={salvando || nome.trim() === ''}>
              Criar acesso
            </Botao>
          </div>
        </form>
      )}
    </dialog>
  )
}

function DialogoSenhaProvisoria({
  dados,
  aoFechar,
}: {
  dados: SenhaProvisoria | null
  aoFechar: () => void
}) {
  const ref = useDialogo(dados !== null)
  return (
    <dialog
      className="dialogo"
      ref={ref}
      aria-label="Senha provisória"
      onCancel={(e) => {
        e.preventDefault()
        aoFechar()
      }}
    >
      {dados && (
        <div className="pilha" data-espaco="5">
          <h2 className="painel-titulo">Senha provisória de {dados.login}</h2>

          {/* O aviso é parte do bloco, não nota de rodapé: fechar aqui perde
              o valor para sempre — nem o servidor consegue recuperá-lo. */}
          <p className="texto-auxiliar">
            <strong>Anote agora: esta senha não será mostrada de novo.</strong> Entregue-a
            pessoalmente — o MediaBuild não envia e-mail.
          </p>

          <div className="senha-provisoria">
            <code>{dados.senha_provisoria}</code>
            <BotaoCopiar texto={dados.senha_provisoria} tamanho="sm" />
          </div>

          <div className="linha" data-alinhar="fim">
            <Botao onClick={aoFechar}>Anotei</Botao>
          </div>
        </div>
      )}
    </dialog>
  )
}

function DialogoExcluir({
  usuario,
  aoFechar,
  aoConfirmar,
}: {
  usuario: Usuario | null
  aoFechar: () => void
  aoConfirmar: (usuario: Usuario) => void
}) {
  const ref = useDialogo(usuario !== null)
  const [digitado, setDigitado] = useState('')
  const id = useId()

  useEffect(() => {
    setDigitado('')
  }, [usuario])

  return (
    <dialog
      className="dialogo"
      ref={ref}
      aria-label="Excluir acesso"
      onCancel={(e) => {
        e.preventDefault()
        aoFechar()
      }}
    >
      {usuario && (
        <div className="pilha" data-espaco="5">
          <h2 className="painel-titulo">Excluir o acesso de {usuario.nome}?</h2>
          <p className="texto-auxiliar">
            Excluir apaga a ligação entre esta pessoa e o que ela gerou. Se a intenção é só
            tirar o acesso, <strong>desative</strong> — a trilha continua legível.
          </p>

          <div>
            <label htmlFor={id}>
              Digite <span className="mono">{usuario.login}</span> para confirmar
            </label>
            <input
              id={id}
              value={digitado}
              spellCheck={false}
              autoCapitalize="none"
              autoComplete="off"
              onChange={(e) => setDigitado(e.target.value)}
            />
          </div>

          <div className="linha" data-alinhar="fim">
            <Botao variante="fantasma" onClick={aoFechar}>
              Cancelar
            </Botao>
            <Botao
              variante="perigo"
              disabled={digitado !== usuario.login}
              onClick={() => aoConfirmar(usuario)}
            >
              Excluir acesso
            </Botao>
          </div>
        </div>
      )}
    </dialog>
  )
}
