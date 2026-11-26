import { useCallback, useEffect, useRef, useState } from 'react'

import { ErroRequisicao, api } from '../api'
import {
  type Abreviacao,
  NIVEIS,
  type Nivel,
  type NoDaArvore,
  type Plataforma,
  ROTULO_NIVEL,
  type Taxonomia,
  type Template,
} from '../tipos'
import { CHAVE_RASCUNHO_GERADOR } from '../sessao'
import { ArvoreCampanha, type CampanhaCorrente } from './ArvoreCampanha'
import { LogoPlataforma } from './icones'
import { PainelNivel } from './PainelNivel'
import { Botao, LinkBotao } from './ui'
import { ValidadorUtm, type AlvoUtm } from './ValidadorUtm'

type PorNivel<T> = Record<Nivel, T>

const vazio = <T,>(valor: () => T): PorNivel<T> => ({
  CAMPANHA: valor(),
  GRUPO: valor(),
  ANUNCIO: valor(),
})

/**
 * O que está sendo criado agora.
 *
 * `completo` é o caminho comum, e continua sendo a cascata de três painéis:
 * é o que o analista faz o dia inteiro. Os outros dois existem porque a
 * hierarquia é 1→N — a campanha já existe e o que falta é mais um filho.
 */
type Modo = 'completo' | 'grupo' | 'anuncio'

const NIVEIS_DO_MODO: Record<Modo, Nivel[]> = {
  completo: NIVEIS,
  grupo: ['GRUPO'],
  anuncio: ['ANUNCIO'],
}

const ROTULO_SALVAR: Record<Modo, string> = {
  completo: 'Salvar e gerar nomenclaturas',
  grupo: 'Salvar grupo e gerar nomenclatura',
  anuncio: 'Salvar anúncio e gerar nomenclatura',
}

/**
 * O que sobrevive a um F5 (UX-NAVEGACAO §4.4).
 *
 * Só o que a pessoa DIGITOU. Nada de `salvos`, `lote` ou da árvore da
 * campanha: aquilo é resultado do servidor, e restaurá-lo de um armazenamento
 * do navegador faria a tela afirmar que algo foi salvo sem que o servidor
 * concorde.
 */
interface Rascunho {
  plataformaId: string
  nomes: PorNivel<string>
  campos: PorNivel<Record<string, string>>
}

/**
 * Rede de segurança INDEPENDENTE da sessão: cobre F5, queda do navegador e
 * fechar a aba sem querer — casos que o diálogo de reautenticação não cobre.
 *
 * `sessionStorage`, nunca `localStorage`: rascunho com nome de cliente
 * sobrevivendo numa máquina compartilhada é vazamento. Pela mesma razão o
 * `sair()` apaga a chave (ver `sessao.tsx`), e salvar com sucesso também.
 */
function lerRascunho(): Rascunho | null {
  try {
    const bruto = window.sessionStorage.getItem(CHAVE_RASCUNHO_GERADOR)
    if (!bruto) return null
    const dados = JSON.parse(bruto) as Partial<Rascunho>
    if (typeof dados?.plataformaId !== 'string' || !dados.nomes || !dados.campos) return null
    return dados as Rascunho
  } catch {
    // Rascunho corrompido ou sessionStorage indisponível: começar limpo é
    // sempre melhor que quebrar a tela por causa da rede de segurança.
    return null
  }
}

function apagarRascunho() {
  try {
    window.sessionStorage.removeItem(CHAVE_RASCUNHO_GERADOR)
  } catch {
    // Sem sessionStorage não há rascunho a limpar.
  }
}

interface Props {
  plataformas: Plataforma[]
  /** Muda quando o dicionário é editado em outra aba, forçando o recarregamento. */
  versaoDicionario: number
}

export function Gerador({ plataformas, versaoDicionario }: Props) {
  // Lido UMA vez, como valor inicial de estado — sem efeito de restauração,
  // que sobrescreveria o que a pessoa já tivesse começado a digitar.
  const rascunhoInicial = useRef(lerRascunho()).current

  const [plataformaId, setPlataformaId] = useState(rascunhoInicial?.plataformaId ?? '')
  const [templates, setTemplates] = useState<Template[]>([])
  const [dicionario, setDicionario] = useState<Abreviacao[]>([])

  const [nomes, setNomes] = useState<PorNivel<string>>(
    () => rascunhoInicial?.nomes ?? vazio(() => ''),
  )
  const [campos, setCampos] = useState<PorNivel<Record<string, string>>>(
    () => rascunhoInicial?.campos ?? vazio(() => ({})),
  )
  const [validos, setValidos] = useState<PorNivel<boolean>>(vazio(() => false))

  const [salvos, setSalvos] = useState<PorNivel<string | undefined>>(vazio(() => undefined))
  const [lote, setLote] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [erroGeral, setErroGeral] = useState<string | null>(null)
  const [carregandoPlataforma, setCarregandoPlataforma] = useState(false)

  // --- hierarquia da campanha corrente ------------------------------------
  const [modo, setModo] = useState<Modo>('completo')
  const [campanha, setCampanha] = useState<CampanhaCorrente | null>(null)
  const [grupos, setGrupos] = useState<NoDaArvore[]>([])
  const [anunciosPorGrupo, setAnunciosPorGrupo] = useState<Record<string, NoDaArvore[]>>({})
  const [grupoAlvo, setGrupoAlvo] = useState('')
  const [arvoreCarregando, setArvoreCarregando] = useState(false)
  const [arvoreErro, setArvoreErro] = useState<string | null>(null)
  const arvoreEmVoo = useRef<AbortController | null>(null)

  // Nomenclaturas geradas nesta sessão, mais recente primeiro — é a lista
  // que o validador de UTM oferece para conferir.
  const [alvosUtm, setAlvosUtm] = useState<AlvoUtm[]>([])

  const [aviso, setAviso] = useState('')

  // Pedido de foco para o título do nível que passou a valer. Um contador,
  // não um booleano: clicar duas vezes no mesmo "+" precisa mover o foco as
  // duas vezes. Ver o efeito logo abaixo.
  const [pedidoDeFoco, setPedidoDeFoco] = useState<{ nivel: Nivel; n: number } | null>(null)

  function reiniciarSessao() {
    setNomes(vazio(() => ''))
    setCampos(vazio(() => ({})))
    setValidos(vazio(() => false))
    setSalvos(vazio(() => undefined))
    setLote(null)
    setErroGeral(null)
    setModo('completo')
    setCampanha(null)
    setGrupos([])
    setAnunciosPorGrupo({})
    setGrupoAlvo('')
    setArvoreErro(null)
    setAlvosUtm([])
  }

  // Trocar de plataforma reinicia tudo: os templates e o dicionário mudam.
  //
  // EXCEÇÃO na primeira execução com rascunho restaurado: ali a plataforma não
  // foi "trocada", ela já era essa. Sem esta guarda, o efeito de montagem
  // apagaria exatamente o formulário que o rascunho acabou de devolver — o F5
  // pareceria não ter preservado nada.
  const primeiraCargaDePlataforma = useRef(Boolean(rascunhoInicial?.plataformaId))
  useEffect(() => {
    if (!plataformaId) {
      setTemplates([])
      setDicionario([])
      return
    }

    setCarregandoPlataforma(true)
    if (primeiraCargaDePlataforma.current) primeiraCargaDePlataforma.current = false
    else reiniciarSessao()

    Promise.all([api.templates(plataformaId), api.dicionario(plataformaId)])
      .then(([ts, dic]) => {
        setTemplates(ts.filter((t) => t.ativo))
        setDicionario(dic)
      })
      .catch((e) => setErroGeral(`Não foi possível carregar a plataforma: ${e.message}`))
      .finally(() => setCarregandoPlataforma(false))
  }, [plataformaId])

  // Recarrega só o dicionário quando ele muda na aba de administração —
  // sem limpar o formulário, que é justamente o que o analista veio
  // preservar ao sair para cadastrar um termo que faltava (D-005).
  useEffect(() => {
    if (!plataformaId || versaoDicionario === 0) return
    api.dicionario(plataformaId).then(setDicionario).catch(() => undefined)
  }, [versaoDicionario, plataformaId])

  useEffect(() => () => arvoreEmVoo.current?.abort(), [])

  /* Gravação do rascunho, 500 ms depois da última tecla (§4.4).
     Debounce e não gravação por tecla: `JSON.stringify` de três níveis a cada
     caractere é trabalho jogado fora, e `sessionStorage` é síncrono — escreve
     na thread que está desenhando.

     Formulário vazio APAGA a chave em vez de gravar um objeto vazio: assim
     "não há rascunho" e "há um rascunho em branco" não são o mesmo byte, e
     limpar a plataforma limpa o vestígio. */
  useEffect(() => {
    const timer = setTimeout(() => {
      const algoPreenchido =
        plataformaId !== '' ||
        NIVEIS.some((n) => nomes[n] !== '' || Object.values(campos[n]).some(Boolean))
      if (!algoPreenchido) {
        apagarRascunho()
        return
      }
      try {
        window.sessionStorage.setItem(
          CHAVE_RASCUNHO_GERADOR,
          JSON.stringify({ plataformaId, nomes, campos } satisfies Rascunho),
        )
      } catch {
        // Cota estourada ou modo restrito: o rascunho é rede de segurança,
        // não requisito. Falhar aqui não pode derrubar o formulário.
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [plataformaId, nomes, campos])

  // Sincronização com o mundo externo (o foco do documento): as ações da
  // árvore mudam qual formulário vale, e num contêiner estreito esse
  // formulário está longe do botão que foi clicado.
  useEffect(() => {
    if (!pedidoDeFoco) return
    document.getElementById(`titulo-nivel-${pedidoDeFoco.nivel}`)?.focus()
  }, [pedidoDeFoco])

  // Derivado no corpo do render: um `useMemo` aqui trocaria uma varredura de
  // três itens por uma comparação de dependências.
  const templatePor = {} as PorNivel<Template | undefined>
  for (const t of templates) templatePor[t.nivel] = t

  const plataformaAtual = plataformas.find((p) => p.id === plataformaId)

  const definirCampo = useCallback((nivel: Nivel, chave: string, valor: string) => {
    setCampos((atual) => ({ ...atual, [nivel]: { ...atual[nivel], [chave]: valor } }))
  }, [])

  const definirValidade = useCallback((nivel: Nivel, valido: boolean) => {
    setValidos((atual) => (atual[nivel] === valido ? atual : { ...atual, [nivel]: valido }))
  }, [])

  const niveisAtivos = NIVEIS_DO_MODO[modo]

  /** Cascata: um nível só abre quando o anterior está válido. */
  function bloqueio(nivel: Nivel): string | undefined {
    if (!plataformaId) return 'Selecione uma plataforma para começar.'
    // Fora do modo completo o pai já existe e já tem nome — não há cascata
    // a percorrer, só o nível que está sendo criado.
    if (modo !== 'completo') return undefined
    if (nivel === 'CAMPANHA') return undefined
    if (nivel === 'GRUPO' && !validos.CAMPANHA) return 'Complete a campanha primeiro.'
    if (nivel === 'ANUNCIO' && !validos.GRUPO) return 'Complete o grupo de anúncio primeiro.'
    return undefined
  }

  const tudoValido = niveisAtivos.every((n) => validos[n])
  const jaSalvo = niveisAtivos.every((n) => Boolean(salvos[n]))

  /** Recarrega a árvore inteira da campanha, do servidor. */
  async function recarregarArvore(campanhaId: string) {
    arvoreEmVoo.current?.abort()
    const controlador = new AbortController()
    arvoreEmVoo.current = controlador
    setArvoreCarregando(true)
    setArvoreErro(null)

    try {
      const lista = await api.gruposDaCampanha(campanhaId, controlador.signal)
      const anuncios = await Promise.all(
        lista.map((g) => api.anunciosDoGrupo(g.id, controlador.signal)),
      )
      if (controlador.signal.aborted) return

      const mapa: Record<string, NoDaArvore[]> = {}
      lista.forEach((g, i) => {
        mapa[g.id] = anuncios[i]
      })
      setGrupos(lista)
      setAnunciosPorGrupo(mapa)
      if (lista.length > 0) setGrupoAlvo((atual) => atual || lista[lista.length - 1].id)
    } catch {
      if (controlador.signal.aborted) return
      // Falha aqui não invalida o que acabou de ser salvo — a nomenclatura
      // já existe no servidor. Só a árvore fica desatualizada.
      setArvoreErro('Não foi possível atualizar a estrutura da campanha.')
    } finally {
      if (!controlador.signal.aborted) setArvoreCarregando(false)
    }
  }

  function registrarAlvos(gerados: Taxonomia[]) {
    setAlvosUtm((atual) => [
      ...gerados.map((t) => ({
        taxonomia_id: t.id,
        rotulo: `${ROTULO_NIVEL[t.nivel]} · ${t.nomenclatura_final}`,
      })),
      ...atual,
    ])
  }

  async function salvarTudo() {
    setSalvando(true)
    setErroGeral(null)
    // Salvou, o rascunho perdeu a razão de existir: o que estava em risco
    // agora está no servidor, e nomenclatura gerada é imutável (D-004).
    // Apagar no COMEÇO seria errado — se o POST falhar, o rascunho ainda é a
    // rede; por isso a limpeza fica no caminho de sucesso, logo abaixo.
    // O lote agrupa tudo o que sai desta campanha, para o Excel sair inteiro.
    const loteAtual = lote ?? crypto.randomUUID()

    try {
      if (modo === 'completo') {
        const nova = await api.criarCampanha({
          plataforma_id: plataformaId,
          nome_interno: nomes.CAMPANHA || 'Campanha sem nome',
          campos: campos.CAMPANHA,
        })
        const grupo = await api.criarGrupo({
          campanha_id: nova.id,
          nome_interno: nomes.GRUPO || 'Grupo sem nome',
          campos: campos.GRUPO,
        })
        const anuncio = await api.criarAnuncio({
          grupo_anuncio_id: grupo.id,
          nome_interno: nomes.ANUNCIO || 'Anúncio sem nome',
          campos: campos.ANUNCIO,
        })

        const gerados: Taxonomia[] = []
        for (const [nivel, entidade] of [
          ['CAMPANHA', nova],
          ['GRUPO', grupo],
          ['ANUNCIO', anuncio],
        ] as const) {
          gerados.push(
            await api.gerarTaxonomia({ nivel, entidade_id: entidade.id, lote_id: loteAtual }),
          )
        }

        setSalvos({
          CAMPANHA: gerados[0].nomenclatura_final,
          GRUPO: gerados[1].nomenclatura_final,
          ANUNCIO: gerados[2].nomenclatura_final,
        })
        setCampanha({
          id: nova.id,
          match_id: nova.match_id,
          nome_interno: nomes.CAMPANHA || 'Campanha sem nome',
        })
        setGrupoAlvo(grupo.id)
        registrarAlvos(gerados)
        setAviso('Campanha, grupo e anúncio salvos.')
        apagarRascunho()
        setLote(loteAtual)
        await recarregarArvore(nova.id)
        return
      }

      if (modo === 'grupo') {
        if (!campanha) return
        const grupo = await api.criarGrupo({
          campanha_id: campanha.id,
          nome_interno: nomes.GRUPO || 'Grupo sem nome',
          campos: campos.GRUPO,
        })
        const gerado = await api.gerarTaxonomia({
          nivel: 'GRUPO',
          entidade_id: grupo.id,
          lote_id: loteAtual,
        })
        setSalvos((a) => ({ ...a, GRUPO: gerado.nomenclatura_final }))
        setGrupoAlvo(grupo.id)
        registrarAlvos([gerado])
        setAviso(`Grupo ${grupo.match_id} salvo nesta campanha.`)
        apagarRascunho()
        setLote(loteAtual)
        await recarregarArvore(campanha.id)
        return
      }

      if (!campanha || !grupoAlvo) return
      const anuncio = await api.criarAnuncio({
        grupo_anuncio_id: grupoAlvo,
        nome_interno: nomes.ANUNCIO || 'Anúncio sem nome',
        campos: campos.ANUNCIO,
      })
      const gerado = await api.gerarTaxonomia({
        nivel: 'ANUNCIO',
        entidade_id: anuncio.id,
        lote_id: loteAtual,
      })
      setSalvos((a) => ({ ...a, ANUNCIO: gerado.nomenclatura_final }))
      registrarAlvos([gerado])
      setAviso(`Anúncio ${anuncio.match_id} salvo neste grupo.`)
      apagarRascunho()
      setLote(loteAtual)
      await recarregarArvore(campanha.id)
    } catch (e) {
      setErroGeral(
        e instanceof ErroRequisicao ? e.corpo.mensagem : `Falha ao salvar: ${String(e)}`,
      )
    } finally {
      setSalvando(false)
    }
  }

  /** Limpa o que ficou órfão ao começar outro filho da mesma campanha. */
  function limpar(niveis: Nivel[]) {
    setNomes((a) => ({ ...a, ...Object.fromEntries(niveis.map((n) => [n, ''])) }))
    setCampos((a) => ({ ...a, ...Object.fromEntries(niveis.map((n) => [n, {}])) }))
    setValidos((a) => ({ ...a, ...Object.fromEntries(niveis.map((n) => [n, false])) }))
    setSalvos((a) => ({ ...a, ...Object.fromEntries(niveis.map((n) => [n, undefined])) }))
    setErroGeral(null)
  }

  function pedirFoco(nivel: Nivel) {
    setPedidoDeFoco((atual) => ({ nivel, n: (atual?.n ?? 0) + 1 }))
  }

  function novoGrupo() {
    limpar(['GRUPO', 'ANUNCIO'])
    setModo('grupo')
    setAviso('Novo grupo de anúncio nesta campanha.')
    pedirFoco('GRUPO')
  }

  function novoAnuncio(grupoId: string) {
    limpar(['ANUNCIO'])
    setGrupoAlvo(grupoId)
    setModo('anuncio')
    const alvo = grupos.find((g) => g.id === grupoId)
    setAviso(`Novo anúncio em ${alvo?.nome_interno ?? 'grupo selecionado'}.`)
    pedirFoco('ANUNCIO')
  }

  async function copiarTodos() {
    const texto = NIVEIS.map((n) => salvos[n]).filter(Boolean).join('\n')
    await navigator.clipboard.writeText(texto)
  }

  return (
    <div className="pilha gerar-palco" data-espaco="5">
      <span className="apenas-leitor" role="status" aria-live="polite">
        {aviso}
      </span>

      {erroGeral && (
        <div role="alert" className="aviso-erro">
          {erroGeral}
        </div>
      )}

      {/* Duas colunas: contexto à esquerda (plataforma + estrutura), trabalho
          à direita (formulário do nível corrente + ação primária). A ordem do
          DOM é a mesma da leitura nos dois formatos — em contêiner estreito as
          colunas viram uma pilha, e nada é reordenado por CSS, para o foco não
          descolar do que está na tela. */}
      <div className="gerar-colunas">
        <section className="card bloco gerar-plataforma">
          <label htmlFor="plataforma">Plataforma</label>
          {/* O logo é decorativo: quem nomeia a plataforma é o próprio
              seletor, e repetir o nome numa imagem só duplicaria a leitura. */}
          <div className="linha" data-espaco="3">
            {plataformaAtual && <LogoPlataforma sigla={plataformaAtual.sigla} tamanho="md" />}
            <select
              id="plataforma"
              value={plataformaId}
              onChange={(e) => setPlataformaId(e.target.value)}
            >
              <option value="">Selecione…</option>
              {plataformas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nome} ({p.sigla})
                </option>
              ))}
            </select>
          </div>
        </section>

        <div className="gerar-coluna" data-lado="contexto">
          <ArvoreCampanha
            campanha={campanha}
            grupos={grupos}
            anunciosPorGrupo={anunciosPorGrupo}
            carregando={arvoreCarregando}
            erro={arvoreErro}
            aoNovoGrupo={novoGrupo}
            aoNovoAnuncio={novoAnuncio}
          />
        </div>

        <div className="gerar-coluna pilha" data-lado="formulario" data-espaco="4">
          {/* Escolher o pai existe só no modo anúncio. Grupo não tem seletor
              de vínculo nenhum: ele pertence à campanha corrente e pronto.
              Aqui o seletor aparece mesmo com um grupo só — além de permitir
              a troca, é ele que diz em qual grupo o anúncio vai cair. */}
          {modo === 'anuncio' && grupos.length > 0 && (
            <section className="card bloco">
              <label htmlFor="grupo-alvo">Vincular ao grupo</label>
              <select
                id="grupo-alvo"
                value={grupoAlvo}
                onChange={(e) => setGrupoAlvo(e.target.value)}
              >
                {grupos.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.nome_interno} ({g.match_id})
                  </option>
                ))}
              </select>
            </section>
          )}

          {niveisAtivos.map((nivel) => {
            const template = templatePor[nivel]
            const motivo = bloqueio(nivel)

            if (!plataformaId || !template) {
              return (
                <section key={nivel} className="card bloco pilha" data-espaco="2" aria-disabled>
                  <h2 className="rotulo-secao">{ROTULO_NIVEL[nivel]}</h2>
                  <p className="texto-auxiliar">
                    {carregandoPlataforma
                      ? 'Carregando…'
                      : (motivo ?? 'Esta plataforma não tem template para este nível.')}
                  </p>
                </section>
              )
            }

            return (
              <PainelNivel
                key={nivel}
                nivel={nivel}
                plataformaId={plataformaId}
                template={template}
                dicionario={dicionario}
                nomeInterno={nomes[nivel]}
                campos={campos[nivel]}
                bloqueado={Boolean(motivo)}
                motivoBloqueio={motivo}
                salvo={salvos[nivel]}
                onNomeInterno={(v) => setNomes((a) => ({ ...a, [nivel]: v }))}
                onCampo={(chave, valor) => definirCampo(nivel, chave, valor)}
                onValidade={(valido) => definirValidade(nivel, valido)}
              />
            )
          })}

          {/* A ação primária ancora o pé da coluna do formulário. As ações de
              estrutura (novo grupo, novo anúncio) moram na árvore, e não se
              repetem aqui: dois caminhos para a mesma coisa na mesma tela
              custam mais do que rendem. */}
          <footer className="linha gerar-rodape" data-alinhar="entre">
            {!tudoValido && !jaSalvo ? (
              <span className="texto-auxiliar">
                {modo === 'completo'
                  ? 'Complete os três níveis para salvar.'
                  : `Complete ${ROTULO_NIVEL[niveisAtivos[0]].toLowerCase()} para salvar.`}
              </span>
            ) : (
              <span />
            )}

            <span className="linha" data-espaco="3">
              {modo === 'completo' && jaSalvo && (
                <>
                  <Botao variante="secundario" onClick={copiarTodos}>
                    Copiar os três nomes
                  </Botao>
                  <LinkBotao
                    variante="secundario"
                    href={api.urlExport(lote ? { lote_id: lote } : {})}
                    download
                  >
                    Baixar Excel
                  </LinkBotao>
                </>
              )}

              <Botao
                disabled={!tudoValido || jaSalvo || salvando}
                carregando={salvando}
                onClick={salvarTudo}
              >
                {jaSalvo ? 'Salvo' : ROTULO_SALVAR[modo]}
              </Botao>
            </span>
          </footer>
        </div>
      </div>

      <ValidadorUtm alvos={alvosUtm} />
    </div>
  )
}
