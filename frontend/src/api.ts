import type {
  Abreviacao,
  AnuncioDoPlano,
  CampanhaDoPlano,
  Entidade,
  ErroApi,
  EventoAcesso,
  EventoErro,
  GrupoDoPlano,
  LaudoUtm,
  LinhaHistorico,
  Metas,
  Metrica,
  Nivel,
  NoDaArvore,
  Papel,
  Plataforma,
  PlanoMidia,
  PlanoMidiaResumo,
  PreviewResposta,
  ResumoAdmin,
  SenhaProvisoria,
  Taxonomia,
  Template,
  TipoEventoAcesso,
  Usuario,
} from './tipos'

/** Filtros da tela de histórico, também aceitos pela exportação. */
export interface FiltrosHistorico {
  plataforma_id?: string
  campanha_id?: string
  nivel?: Nivel
  busca?: string
  desde?: string
  ate?: string
}

/** Descarta chaves vazias para não mandar `?busca=` e afins. */
function querystring(filtros: Record<string, string | undefined>): string {
  const params = new URLSearchParams()
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor) params.set(chave, valor)
  }
  return params.toString()
}

const BASE = '/api'

/** Erro da API já desempacotado, preservando `campo` e `opcoes` para a UI. */
export class ErroRequisicao extends Error {
  constructor(
    readonly status: number,
    readonly corpo: ErroApi,
  ) {
    super(corpo.mensagem)
  }

  get campo() {
    return this.corpo.campo ?? undefined
  }

  get opcoes() {
    return this.corpo.opcoes ?? undefined
  }
}

/**
 * Códigos estáveis de `app/erros_acesso.py`. A tela reage ao CÓDIGO, nunca ao
 * texto da mensagem — a mensagem é redação e muda; o código é contrato.
 */
export type CodigoAcesso =
  | 'nao_autenticado'
  | 'sessao_expirada'
  | 'credenciais_invalidas'
  | 'conta_desativada'
  | 'permissao_insuficiente'

type OuvinteFalha = (erro: ErroRequisicao) => void

const ouvintesDeFalhaAuth = new Set<OuvinteFalha>()

/**
 * Avisa que uma chamada QUALQUER voltou 401. Quem decide o que fazer é a
 * sessão (`src/sessao.tsx`): este módulo não navega e não desmonta nada —
 * fazer isso daqui é como se descarta um formulário meio preenchido.
 *
 * As rotas `/auth/*` ficam de fora de propósito: o 401 de
 * `credenciais_invalidas` é resposta esperada do formulário de login, e o de
 * `GET /auth/eu` é a resposta normal de quem ainda não entrou.
 */
export function observarFalhaDeAutenticacao(ouvinte: OuvinteFalha): () => void {
  ouvintesDeFalhaAuth.add(ouvinte)
  return () => {
    ouvintesDeFalhaAuth.delete(ouvinte)
  }
}

async function pedir<T>(caminho: string, init?: RequestInit): Promise<T> {
  const resposta = await fetch(`${BASE}${caminho}`, {
    ...init,
    // O cookie de sessão é HttpOnly (D-014): sem `include` ele simplesmente
    // não sobe, e toda chamada autenticada volta 401.
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!resposta.ok) {
    let corpo: ErroApi
    try {
      const json = await resposta.json()
      corpo =
        typeof json?.erro === 'string'
          ? json
          : { erro: 'erro', mensagem: json?.detail ?? 'Falha inesperada na requisição.' }
    } catch {
      corpo = { erro: 'erro', mensagem: `Falha na requisição (HTTP ${resposta.status}).` }
    }
    const erro = new ErroRequisicao(resposta.status, corpo)
    if (resposta.status === 401 && !caminho.startsWith('/auth/')) {
      for (const ouvinte of ouvintesDeFalhaAuth) ouvinte(erro)
    }
    throw erro
  }

  return resposta.status === 204 ? (undefined as T) : resposta.json()
}

const post = <T,>(caminho: string, corpo: unknown) =>
  pedir<T>(caminho, { method: 'POST', body: JSON.stringify(corpo) })

const patch = <T,>(caminho: string, corpo: unknown) =>
  pedir<T>(caminho, { method: 'PATCH', body: JSON.stringify(corpo) })

const remover = (caminho: string) => pedir<void>(caminho, { method: 'DELETE' })

/** Um dos dois, nunca os dois — mesmo contrato do backend (`_LinhaPedido`). */
export type CorpoRateio = { valor: string } | { percentual: string }

export const api = {
  /**
   * Autenticação por cookie de sessão opaco (D-014). Não há token no
   * JavaScript para guardar: o cookie é HttpOnly, então a única forma
   * honesta de saber quem está logado é perguntar em `/auth/eu`.
   */
  auth: {
    entrar: (login: string, senha: string) => post<Usuario>('/auth/login', { login, senha }),

    /** 204 mesmo sem sessão — sair de onde não se está não é erro. */
    sair: () => pedir<void>('/auth/logout', { method: 'POST' }),

    eu: (signal?: AbortSignal) => pedir<Usuario>('/auth/eu', { signal }),
  },

  /**
   * Gestão de acessos (`#/admin/acessos`). `login` não tem PATCH de propósito:
   * é a identidade que aparece na trilha de acesso, e renomeá-lo tornaria os
   * eventos antigos ilegíveis. Trocar de dono é criar outro usuário.
   */
  usuarios: {
    listar: (signal?: AbortSignal) => pedir<Usuario[]>('/usuarios', { signal }),

    criar: (corpo: { nome: string; login: string; senha: string; papel: Papel }) =>
      post<Usuario>('/usuarios', corpo),

    atualizar: (
      id: string,
      corpo: { nome?: string; papel?: Papel; senha?: string; ativo?: boolean },
    ) => patch<Usuario>(`/usuarios/${id}`, corpo),

    remover: (id: string) => remover(`/usuarios/${id}`),

    /**
     * Redefinição por administrador — único caminho de recuperação que existe
     * no produto. A senha volta em claro UMA VEZ e não é recuperável.
     */
    redefinirSenha: (id: string) => post<SenhaProvisoria>(`/usuarios/${id}/senha`, {}),
  },

  /** Monitoramento (`#/admin/monitoramento`). Tudo aqui exige papel admin. */
  admin: {
    resumo: (dias: number, signal?: AbortSignal) =>
      pedir<ResumoAdmin>(`/admin/resumo?dias=${dias}`, { signal }),

    // `limite` acima de 500 volta 422 — o teto é do servidor, e o cliente não
    // tenta contorná-lo pedindo em páginas.
    acessos: (
      filtros: { desde?: string; ate?: string; tipo?: TipoEventoAcesso; limite?: number } = {},
      signal?: AbortSignal,
    ) =>
      pedir<EventoAcesso[]>(
        `/admin/acessos?${querystring({
          desde: filtros.desde,
          ate: filtros.ate,
          tipo: filtros.tipo,
          limite: filtros.limite ? String(filtros.limite) : undefined,
        })}`,
        { signal },
      ),

    erros: (
      filtros: { desde?: string; ate?: string; status?: number; limite?: number } = {},
      signal?: AbortSignal,
    ) =>
      pedir<EventoErro[]>(
        `/admin/erros?${querystring({
          desde: filtros.desde,
          ate: filtros.ate,
          status: filtros.status ? String(filtros.status) : undefined,
          limite: filtros.limite ? String(filtros.limite) : undefined,
        })}`,
        { signal },
      ),
  },

  plataformas: () => pedir<Plataforma[]>('/plataformas?apenas_ativas=true'),

  templates: (plataformaId: string) =>
    pedir<Template[]>(`/plataformas/${plataformaId}/templates`),

  dicionario: (plataformaId: string) =>
    pedir<Abreviacao[]>(`/dicionario?plataforma_id=${plataformaId}`),

  /** Todo o dicionário, para a tela de administração. */
  dicionarioCompleto: () => pedir<Abreviacao[]>('/dicionario'),

  campanhas: (plataformaId?: string) =>
    pedir<Entidade[]>(`/campanhas?${querystring({ plataforma_id: plataformaId })}`),

  /** Grupos de uma campanha, com a nomenclatura mais recente de cada um. */
  gruposDaCampanha: (campanhaId: string, signal?: AbortSignal) =>
    pedir<NoDaArvore[]>(`/campanhas/${campanhaId}/grupos`, { signal }),

  /** Anúncios de um grupo, com a nomenclatura mais recente de cada um. */
  anunciosDoGrupo: (grupoId: string, signal?: AbortSignal) =>
    pedir<NoDaArvore[]>(`/grupos/${grupoId}/anuncios`, { signal }),

  historico: (filtros: FiltrosHistorico = {}) =>
    pedir<LinhaHistorico[]>(`/taxonomias/historico?${querystring({ ...filtros })}`),

  preview: (corpo: { plataforma_id: string; nivel: Nivel; campos: Record<string, string> }) =>
    post<PreviewResposta>('/taxonomias/preview', corpo),

  criarCampanha: (corpo: {
    plataforma_id: string
    nome_interno: string
    campos: Record<string, string>
  }) => post<Entidade>('/campanhas', corpo),

  criarGrupo: (corpo: {
    campanha_id: string
    nome_interno: string
    campos: Record<string, string>
  }) => post<Entidade>('/grupos', corpo),

  criarAnuncio: (corpo: {
    grupo_anuncio_id: string
    nome_interno: string
    campos: Record<string, string>
  }) => post<Entidade>('/anuncios', corpo),

  gerarTaxonomia: (corpo: { nivel: Nivel; entidade_id: string; lote_id?: string }) =>
    post<Taxonomia>('/taxonomias', corpo),

  /**
   * Confere a URL de destino contra uma nomenclatura já gerada (D-012).
   * Responde 200 mesmo com a URL toda errada — o laudo é o resultado, não
   * o erro, então nada aqui passa por `ErroRequisicao` no caminho normal.
   */
  validarUtm: (corpo: { url: string; taxonomia_id: string }, signal?: AbortSignal) =>
    pedir<LaudoUtm>('/utm/validar', {
      method: 'POST',
      body: JSON.stringify(corpo),
      signal,
    }),

  criarAbreviacao: (corpo: {
    categoria: string
    termo: string
    abreviacao: string
    plataforma_id?: string
  }) => post<Abreviacao>('/dicionario', corpo),

  atualizarAbreviacao: (id: string, abreviacao: string) =>
    patch<Abreviacao>(`/dicionario/${id}`, { abreviacao }),

  removerAbreviacao: (id: string) => pedir<void>(`/dicionario/${id}`, { method: 'DELETE' }),

  /** URL do .xlsx — usada direto num link, para o browser cuidar do download. */
  urlExport: (filtros: Record<string, string | undefined> = {}) =>
    `${BASE}/taxonomias/export?${querystring(filtros)}`,

  /** Catálogo de métricas — só leitura nesta fase (ver docs/PLANO-DE-MIDIA-UI.md §6). */
  metricas: {
    listar: (incluirInativas = false) =>
      pedir<Metrica[]>(`/metricas?${querystring({ incluir_inativas: incluirInativas ? 'true' : undefined })}`),
  },

  /**
   * Plano de mídia (D-A/D-B): rateio de verba em cascata e metas por
   * anúncio. Diferente da taxonomia, o plano TEM PATCH/DELETE em todo
   * nível — é um documento de trabalho mutável, não nomenclatura gerada.
   */
  planos: {
    listar: () => pedir<PlanoMidiaResumo[]>('/planos'),

    criar: (corpo: { nome: string; verba_total: string; observacoes?: string }) =>
      post<PlanoMidia>('/planos', corpo),

    obter: (planoId: string, signal?: AbortSignal) =>
      pedir<PlanoMidia>(`/planos/${planoId}`, { signal }),

    atualizar: (planoId: string, corpo: { nome?: string; verba_total?: string; observacoes?: string | null }) =>
      patch<PlanoMidia>(`/planos/${planoId}`, corpo),

    remover: (planoId: string) => remover(`/planos/${planoId}`),

    adicionarCampanha: (
      planoId: string,
      corpo: CorpoRateio & {
        campanha_id: string
        flight_inicio?: string | null
        flight_fim?: string | null
        kpi_primario_id?: string | null
      },
    ) => post<CampanhaDoPlano>(`/planos/${planoId}/campanhas`, corpo),

    // `CorpoRateio` (não `Partial`) porque `_LinhaPedido` — herdada por TODO
    // PATCH de linha do plano — exige exatamente um de valor/percentual em
    // TODA chamada, mesmo quando só flight/KPI/custo/metas estão mudando
    // (ver `tests/test_plano_midia.py`, que sempre reenvia `valor` junto).
    atualizarCampanha: (
      planoId: string,
      linhaId: string,
      corpo: CorpoRateio & {
        flight_inicio?: string | null
        flight_fim?: string | null
        kpi_primario_id?: string | null
        /** Contrato do adendo em curso no backend (ver relatório da tarefa). */
        sincronizar_nomenclatura?: true
      },
    ) => patch<CampanhaDoPlano>(`/planos/${planoId}/campanhas/${linhaId}`, corpo),

    removerCampanha: (planoId: string, linhaId: string) =>
      remover(`/planos/${planoId}/campanhas/${linhaId}`),

    adicionarGrupo: (
      planoId: string,
      linhaCampanhaId: string,
      corpo: CorpoRateio & { grupo_id: string; custo_unitario_negociado?: string | null },
    ) => post<GrupoDoPlano>(`/planos/${planoId}/campanhas/${linhaCampanhaId}/grupos`, corpo),

    atualizarGrupo: (
      planoId: string,
      linhaCampanhaId: string,
      linhaGrupoId: string,
      corpo: CorpoRateio & {
        custo_unitario_negociado?: string | null
        sincronizar_nomenclatura?: true
      },
    ) => patch<GrupoDoPlano>(`/planos/${planoId}/campanhas/${linhaCampanhaId}/grupos/${linhaGrupoId}`, corpo),

    removerGrupo: (planoId: string, linhaCampanhaId: string, linhaGrupoId: string) =>
      remover(`/planos/${planoId}/campanhas/${linhaCampanhaId}/grupos/${linhaGrupoId}`),

    adicionarAnuncio: (
      planoId: string,
      linhaCampanhaId: string,
      linhaGrupoId: string,
      corpo: CorpoRateio & { anuncio_id: string; metas?: Metas },
    ) =>
      post<AnuncioDoPlano>(
        `/planos/${planoId}/campanhas/${linhaCampanhaId}/grupos/${linhaGrupoId}/anuncios`,
        corpo,
      ),

    atualizarAnuncio: (
      planoId: string,
      linhaCampanhaId: string,
      linhaGrupoId: string,
      linhaAnuncioId: string,
      corpo: CorpoRateio & { metas?: Metas; sincronizar_nomenclatura?: true },
    ) =>
      patch<AnuncioDoPlano>(
        `/planos/${planoId}/campanhas/${linhaCampanhaId}/grupos/${linhaGrupoId}/anuncios/${linhaAnuncioId}`,
        corpo,
      ),

    removerAnuncio: (
      planoId: string,
      linhaCampanhaId: string,
      linhaGrupoId: string,
      linhaAnuncioId: string,
    ) =>
      remover(
        `/planos/${planoId}/campanhas/${linhaCampanhaId}/grupos/${linhaGrupoId}/anuncios/${linhaAnuncioId}`,
      ),

    /** URL do .xlsx do plano — usada direto num link/confirmação de download. */
    urlExport: (planoId: string) => `${BASE}/planos/export?plano_id=${planoId}`,
  },
}
