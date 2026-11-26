/**
 * Dados falsos do catálogo. O catálogo não chama a API — por isso o estado
 * "carregando" não existe aqui por regra, e por isso demonstrar um formulário
 * de dicionário não polui o banco do analista.
 */
export const NOMENCLATURA_EXEMPLO = 'ALV27_ALF_METAA_INSTA_CV_AGO_C0001'

export const LINHAS_HISTORICO = [
  {
    match_id: 'C0001',
    nomenclatura_final: NOMENCLATURA_EXEMPLO,
    plataforma: 'Meta',
    campanha: 'Black Friday',
    caracteres: 34,
  },
  {
    match_id: 'G0001',
    nomenclatura_final: 'F_25-34_BOLSA_SUD_RJ_RMKT_G0001',
    plataforma: 'Meta',
    campanha: 'Black Friday',
    caracteres: 31,
  },
]

export const TERMOS_DICIONARIO = [
  { categoria: 'objetivo', termo: 'Conversão', abreviacao: 'CV', escopo: 'Todas' },
  { categoria: 'empresa', termo: 'Loja Alfa', abreviacao: 'ALF', escopo: 'Todas' },
  { categoria: 'posicionamento', termo: 'Instagram Stories', abreviacao: 'IGST', escopo: 'Meta' },
]

export const REGRAS_DE_REDACAO: { regra: string; sim: string; nao: string }[] = [
  {
    regra: 'Rótulo de campo é substantivo curto, sem dois-pontos.',
    sim: 'Objetivo',
    nao: 'Informe o objetivo:',
  },
  {
    regra: 'Botão nomeia a ação, não confirma a pergunta.',
    sim: 'Gerar nomenclatura',
    nao: 'OK',
  },
  {
    regra: 'Erro diz o que fazer, não acusa o usuário.',
    sim: 'Cadastre "Instagram" no dicionário para usar este termo.',
    nao: 'Valor inválido.',
  },
  {
    regra: 'Estado vazio explica a próxima ação.',
    sim: 'Complete os três níveis para ver a nomenclatura.',
    nao: 'Sem dados.',
  },
  {
    regra: 'Nunca expor o UUID interno; o código visível é o match ID.',
    sim: 'C0001',
    nao: '3f2b1c8e-…',
  },
  {
    regra: 'Nomenclatura gerada é imutável (D-004): o caminho é regerar.',
    sim: 'Gerar de novo',
    nao: 'Editar nomenclatura',
  },
]
