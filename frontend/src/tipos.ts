export type Nivel = 'CAMPANHA' | 'GRUPO' | 'ANUNCIO'

export const NIVEIS: Nivel[] = ['CAMPANHA', 'GRUPO', 'ANUNCIO']

export const ROTULO_NIVEL: Record<Nivel, string> = {
  CAMPANHA: 'Campanha',
  GRUPO: 'Grupo de anúncio',
  ANUNCIO: 'Anúncio',
}

export interface Plataforma {
  id: string
  nome: string
  sigla: string
  ativo: boolean
}

export type TokenCampo = {
  tipo: 'campo'
  chave: string
  /** Drop list (true, padrão) exige termo do dicionário; false é campo livre. */
  abreviar?: boolean
  /** Rótulo do formulário. Vem do servidor — nada de tabela de rótulos aqui. */
  rotulo?: string
  /** Só para campo livre. */
  max_caracteres?: number
  opcional?: boolean
  /** Vocabulário consultado, quando difere da chave (interesse_1 → interesse). */
  categoria?: string
  /**
   * D-011: o que entra no nome quando um campo opcional fica em branco.
   * Ausente ou vazio = comportamento antigo, em que o token some do nome.
   * A decisão previa o marcador no token; o servidor entrega hoje na
   * coluna do template. Os dois são lidos, com o token vencendo.
   */
  marcador_ausencia?: string | null
}

export type Token =
  | { tipo: 'literal'; valor: string }
  | TokenCampo
  | { tipo: 'match_id' }

export interface Template {
  id: string
  plataforma_id: string
  nivel: Nivel
  separador: string
  tokens: Token[]
  /** Marcador de ausência do nível inteiro (D-011). Vazio = token some. */
  marcador_ausencia?: string | null
  versao: number
  ativo: boolean
}

export interface Abreviacao {
  id: string
  plataforma_id: string | null
  categoria: string
  termo: string
  abreviacao: string
}

export interface PreviewResposta {
  nomenclatura: string
  match_id_provisorio: boolean
  template_versao: number
  limite_caracteres: number | null
  caracteres: number
}

/** Corpo de erro da API — ver app/erros_http.py. */
export interface ErroApi {
  erro: string
  mensagem: string
  campo?: string | null
  opcoes?: string[] | null
}

export interface Entidade {
  id: string
  match_id: string
  nome_interno: string
}

/**
 * Papéis de acesso (D-014). Espelha `Papel` em `app/schemas.py` — o cliente
 * NUNCA infere papel de outra coisa: quem diz é `GET /auth/eu`.
 */
export type Papel = 'basico' | 'pleno' | 'admin'

export const ROTULO_PAPEL: Record<Papel, string> = {
  basico: 'Básico',
  pleno: 'Pleno',
  admin: 'Administrador',
}

/** Corpo de `GET /auth/eu` e de `POST /auth/login` (`UsuarioLer`). */
export interface Usuario {
  id: string
  nome: string
  /** Identidade do produto. Não é e-mail, e a interface chama isto de "Usuário". */
  login: string
  papel: Papel
  ativo: boolean
  criado_em: string
  ultimo_acesso_em?: string | null
}

/**
 * Resposta de `POST /usuarios/{id}/senha` (`SenhaProvisoriaLer`).
 *
 * A senha em claro aparece UMA VEZ. O banco guarda só o hash scrypt, então
 * nem o servidor consegue recuperá-la depois — a tela precisa dizer isso na
 * cara, e não pode ter um caminho que a mostre de novo.
 */
export interface SenhaProvisoria {
  usuario_id: string
  login: string
  senha_provisoria: string
}

/**
 * Identidade aceita pelo servidor (`Login` em `app/schemas.py`). Validar aqui
 * dá erro imediato; a autoridade continua sendo o 422 do servidor.
 */
export const REGEX_LOGIN = /^[A-Za-z0-9._-]{3,60}$/

export type TipoEventoAcesso = 'login_ok' | 'login_falha' | 'logout' | 'sessao_expirada'

export const ROTULO_EVENTO_ACESSO: Record<TipoEventoAcesso, string> = {
  login_ok: 'Entrada',
  login_falha: 'Falha de login',
  logout: 'Saída',
  sessao_expirada: 'Sessão expirada',
}

export interface EventoAcesso {
  id: string
  ocorrido_em: string
  tipo: TipoEventoAcesso
  login_tentado: string | null
  usuario_id: string | null
  /** Nulo quando a conta já foi excluída — o evento sobrevive a ela (D-014). */
  usuario_login: string | null
  ip: string | null
  agente: string | null
  detalhe: string | null
}

export interface EventoErro {
  id: string
  ocorrido_em: string
  /** A coluna que justifica a tela: liga a reclamação do analista à linha de log. */
  request_id: string | null
  metodo: string
  caminho: string
  status: number
  codigo_erro: string | null
  mensagem: string | null
  usuario_id: string | null
  usuario_login: string | null
  duracao_ms: number | null
}

export interface LoginsDoDia {
  dia: string
  ok: number
  falha: number
}

export interface CaminhoComErro {
  caminho: string
  total: number
}

/** Agregados de `GET /admin/resumo` — calculados em SQL, não no cliente. */
export interface ResumoAdmin {
  dias: number
  desde: string
  logins_por_dia: LoginsDoDia[]
  /** Proporção entre 0 e 1. `0` quando não houve tentativa nenhuma. */
  taxa_falha_login: number
  total_logins_ok: number
  total_logins_falha: number
  top_caminhos_com_erro: CaminhoComErro[]
  erros_4xx: number
  erros_5xx: number
  sessoes_ativas: number
  usuarios_por_papel: Record<string, number>
}

export interface Taxonomia {
  id: string
  nivel: Nivel
  nomenclatura_final: string
}

/**
 * Filho de uma campanha (grupo) ou de um grupo (anúncio), já com a
 * nomenclatura mais recente resolvida pelo servidor — ver `NoDaArvore`
 * em `app/schemas.py`. `nomenclatura` nula é estado normal: a entidade
 * existe e ainda não teve nome gerado.
 */
export interface NoDaArvore {
  id: string
  pai_id: string
  nome_interno: string
  match_id: string
  nomenclatura: string | null
  taxonomia_id: string | null
  gerado_em: string | null
  criado_em: string
}

/** Um item do laudo de UTM — erro ou aviso, mesma forma (D-012). */
export interface ItemLaudoUtm {
  codigo: string
  parametro: string | null
  mensagem: string
  encontrado?: string | null
  esperado?: string | null
}

/**
 * Resposta de `POST /utm/validar`. A rota responde **sempre 200**: URL
 * problemática não é requisição malformada, é laudo (D-012).
 */
export interface LaudoUtm {
  valido: boolean
  erros: ItemLaudoUtm[]
  avisos: ItemLaudoUtm[]
  parametros: Record<string, string>
  sugestao: Record<string, string>
  /** Vazia quando não há o que sugerir — o servidor não manda nulo. */
  url_sugerida: string
}

/** Linha do histórico, com plataforma e campanha já resolvidas pelo servidor. */
export interface LinhaHistorico {
  id: string
  nivel: Nivel
  nomenclatura_final: string
  plataforma: string
  campanha: string
  nome_interno: string
  match_id: string
  caracteres: number
  template_versao: number
  campos: Record<string, string>
  lote_id: string | null
  criado_em: string
}

/** Um campo do formulário, já com tudo o que a UI precisa para renderizá-lo. */
export interface CampoDoTemplate {
  chave: string
  rotulo: string
  abreviar: boolean
  maxCaracteres?: number
  opcional: boolean
  /** Categoria do dicionário — igual à chave quando o servidor não manda outra. */
  categoria: string
  /**
   * Só em campo opcional, e só quando o servidor manda um marcador não
   * vazio: o texto que ocupa a posição no nome se o campo ficar em branco.
   * `undefined` significa que o token some, como antes do D-011.
   */
  marcadorAusencia?: string
}

/** Rótulo de emergência para tokens antigos, salvos antes do campo `rotulo`. */
function rotularChave(chave: string): string {
  const texto = chave.replace(/_/g, ' ')
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

/* ===========================================================================
 * Plano de mídia — espelha `app/schemas.py` (seção "plano de mídia").
 * Campos Decimal do backend chegam como STRING no JSON (ver
 * `tests/test_plano_midia.py::_d`, que faz `Decimal(str(valor))`), nunca
 * number: a serialização preserva casas decimais sem perder precisão de
 * ponto flutuante. Todo `valor`/`percentual`/`diferenca`/`soma_*` aqui é
 * string por esse motivo — nunca number.
 * =========================================================================== */

export interface Metrica {
  id: string
  codigo: string
  rotulo: string
  ordem: number
  ativo: boolean
}

/** Código da métrica → meta (contagem). Nenhuma métrica de trabalho é monetária. */
export type Metas = Record<string, number>

export interface AnuncioDoPlano {
  id: string
  anuncio_id: string
  nome_interno: string
  match_id: string
  /** Snapshot gravado quando a linha entrou no plano (D-004: nunca muda sozinho). */
  nomenclatura: string | null
  /** Nomenclatura mais recente do anúncio, agora — resolvida na leitura. */
  nomenclatura_atual: string | null
  nomenclatura_divergente: boolean
  valor: string
  /** Nulo quando o grupo pai tem valor zero — a divisão não tem sentido. */
  percentual: string | null
  metas: Metas
  criado_em: string
  atualizado_em: string
}

export interface GrupoDoPlano {
  id: string
  grupo_id: string
  nome_interno: string
  match_id: string
  nomenclatura: string | null
  nomenclatura_atual: string | null
  nomenclatura_divergente: boolean
  valor: string
  percentual: string | null
  /** Informativo — não alimenta cálculo nenhum. */
  custo_unitario_negociado: string | null
  soma_anuncios: string
  diferenca: string
  anuncios: AnuncioDoPlano[]
}

export interface CampanhaDoPlano {
  id: string
  campanha_id: string
  plataforma_id: string | null
  nome_interno: string
  match_id: string
  nomenclatura: string | null
  nomenclatura_atual: string | null
  nomenclatura_divergente: boolean
  valor: string
  percentual: string | null
  flight_inicio: string | null
  flight_fim: string | null
  kpi_primario_id: string | null
  kpi_primario_codigo: string | null
  kpi_primario_rotulo: string | null
  kpi_primario_ativo: boolean | null
  soma_grupos: string
  diferenca: string
  grupos: GrupoDoPlano[]
}

export interface PlanoMidia {
  id: string
  nome: string
  verba_total: string
  observacoes: string | null
  soma_campanhas: string
  diferenca: string
  campanhas: CampanhaDoPlano[]
  criado_em: string
  atualizado_em: string
}

/** Linha do índice de planos — sem a árvore inteira. */
export interface PlanoMidiaResumo {
  id: string
  nome: string
  verba_total: string
  soma_campanhas: string
  diferenca: string
  quantidade_campanhas: number
  criado_em: string
  atualizado_em: string
}

/** Campos que o rateio duplo (`CampoRateio`) pode enviar — exatamente um. */
export type CampoRateioNome = 'valor' | 'percentual'

/** Campos que o template do nível exige, na ordem em que aparecem no nome. */
export function camposDoTemplate(template: Template): CampoDoTemplate[] {
  return template.tokens
    .filter((t): t is TokenCampo => t.tipo === 'campo')
    .map((t) => {
      const opcional = t.opcional === true
      // O token manda; o marcador do template é o padrão do nível. Nenhum
      // dos dois presente = comportamento antigo, e nada a avisar.
      const marcador = t.marcador_ausencia ?? template.marcador_ausencia ?? ''
      return {
        chave: t.chave,
        rotulo: t.rotulo ?? rotularChave(t.chave),
        abreviar: t.abreviar !== false,
        maxCaracteres: t.max_caracteres,
        opcional,
        categoria: t.categoria ?? t.chave,
        marcadorAusencia: opcional && marcador ? marcador : undefined,
      }
    })
}
