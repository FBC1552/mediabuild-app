import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useState } from 'react'

import { AplicativoTaxonomia } from '../componentes/AplicativoTaxonomia'
import type { AbaTaxonomia } from '../roteador'
import { BarraTopo } from '../componentes/cromo'
import { ComSessao, renderComSessao } from './ajudaSessao'
import { camposDoTemplate, type Template, type TokenCampo } from '../tipos'

/**
 * As abas viraram rotas, então `<App />` em `#/` é a splash. Estes testes são
 * de formulário, não de navegação: renderizam o aplicativo de taxonomia
 * direto, com um dono de estado mínimo no lugar do roteador.
 */
function Taxonomia() {
  const [aba, setAba] = useState<AbaTaxonomia>('gerar')
  // Papel `pleno`: estes testes são de formulário e de aba, não de permissão.
  // Quem cobre o gating por papel é `sessao.test.tsx`.
  return (
    <ComSessao>
      <AplicativoTaxonomia aba={aba} aoTrocarAba={setAba} />
    </ComSessao>
  )
}


const META = { id: 'p-meta', nome: 'Meta', sigla: 'FB', ativo: true }

/** Rótulos vêm do servidor dentro do token, como na aplicação real. */
const ROTULOS: Record<string, string> = {
  objetivo: 'Objetivo',
  publico: 'Público',
  posicionamento: 'Posicionamento',
  formato: 'Formato',
}

const template = (
  nivel: Template['nivel'],
  campos: (string | TokenCampo)[],
): Template => ({
  id: `t-${nivel}`,
  plataforma_id: META.id,
  nivel,
  separador: '_',
  tokens: [
    { tipo: 'literal', valor: 'FB' },
    ...campos.map((c) =>
      typeof c === 'string'
        ? ({ tipo: 'campo' as const, chave: c, rotulo: ROTULOS[c] ?? c })
        : c,
    ),
    { tipo: 'match_id' },
  ],
  versao: 1,
  ativo: true,
})

const TEMPLATES = [
  template('CAMPANHA', ['objetivo']),
  template('GRUPO', ['publico', 'posicionamento']),
  template('ANUNCIO', ['formato']),
]

const DICIONARIO = [
  { id: 'a1', plataforma_id: null, categoria: 'objetivo', termo: 'Conversão', abreviacao: 'CV' },
  { id: 'a2', plataforma_id: null, categoria: 'objetivo', termo: 'Tráfego', abreviacao: 'TRF' },
  { id: 'a3', plataforma_id: null, categoria: 'publico', termo: 'Remarketing', abreviacao: 'RMKT' },
  { id: 'a4', plataforma_id: null, categoria: 'formato', termo: 'Stories', abreviacao: 'ST' },
  {
    id: 'a5',
    plataforma_id: META.id,
    categoria: 'posicionamento',
    termo: 'Instagram Stories',
    abreviacao: 'IGST',
  },
]

/** Resposta de preview equivalente à que o motor produziria. */
function previewFalso(corpo: { nivel: string; campos: Record<string, string> }) {
  const abrev = (v: string) => DICIONARIO.find((d) => d.termo === v)?.abreviacao
  const valores = Object.values(corpo.campos).map(abrev)

  if (valores.some((v) => v === undefined)) {
    const faltante = Object.entries(corpo.campos).find(([, v]) => !abrev(v))!
    return {
      ok: false,
      corpo: {
        erro: 'termo_desconhecido',
        mensagem: `O termo '${faltante[1]}' não está no dicionário de '${faltante[0]}'.`,
        campo: faltante[0],
        opcoes: ['Conversão', 'Tráfego'],
      },
    }
  }

  const sufixo = { CAMPANHA: 'C0000', GRUPO: 'G0000', ANUNCIO: 'A0000' }[corpo.nivel]
  const nomenclatura = ['FB', ...valores, sufixo].join('_')
  return {
    ok: true,
    corpo: {
      nomenclatura,
      match_id_provisorio: true,
      template_versao: 1,
      limite_caracteres: 400,
      caracteres: nomenclatura.length,
    },
  }
}

function mockFetch() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const resposta = (corpo: unknown, status = 200) =>
      ({ ok: status < 400, status, json: async () => corpo }) as Response

    if (url.startsWith('/api/plataformas?')) return resposta([META])
    if (url.includes('/templates')) return resposta(TEMPLATES)
    if (url.startsWith('/api/dicionario')) return resposta(DICIONARIO)

    if (url === '/api/taxonomias/preview') {
      const r = previewFalso(JSON.parse(String(init!.body)))
      return resposta(r.corpo, r.ok ? 200 : 422)
    }

    if (url === '/api/campanhas') return resposta({ id: 'c1', match_id: 'C0001', nome_interno: '' })
    if (url === '/api/grupos') return resposta({ id: 'g1', match_id: 'G0001', nome_interno: '' })
    if (url === '/api/anuncios') return resposta({ id: 'n1', match_id: 'A0001', nome_interno: '' })

    // Árvore da hierarquia, consultada depois de salvar.
    if (url === '/api/campanhas/c1/grupos') return resposta([])
    if (url.endsWith('/anuncios') && url.startsWith('/api/grupos/')) return resposta([])
    if (url === '/api/taxonomias') {
      const { nivel } = JSON.parse(String(init!.body))
      const nomes = {
        CAMPANHA: 'FB_CV_C0001',
        GRUPO: 'FB_RMKT_IGST_G0001',
        ANUNCIO: 'FB_ST_A0001',
      }
      return resposta({ id: `t-${nivel}`, nivel, nomenclatura_final: nomes[nivel as keyof typeof nomes] })
    }

    throw new Error(`URL não mockada: ${url}`)
  })
}

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch())
  vi.stubGlobal('crypto', { ...crypto, randomUUID: () => 'lote-1' })
})

async function selecionarMeta(user: ReturnType<typeof userEvent.setup>) {
  render(<Taxonomia />)
  const seletor = await screen.findByLabelText('Plataforma')
  await user.selectOptions(seletor, META.id)
  return seletor
}

const painel = (titulo: string) => screen.getByRole('heading', { name: titulo }).closest('section')!

// --------------------------------------------------------------------------

describe('extração de campos do template', () => {
  it('pega os tokens de campo na ordem em que aparecem no nome', () => {
    expect(camposDoTemplate(TEMPLATES[1]).map((c) => c.chave)).toEqual([
      'publico',
      'posicionamento',
    ])
  })

  it('lê tipo, limite e opcionalidade que o servidor manda no token', () => {
    const livre: Template = {
      ...TEMPLATES[0],
      tokens: [
        {
          tipo: 'campo',
          chave: 'nome_criativo',
          rotulo: 'Nome do criativo',
          abreviar: false,
          max_caracteres: 10,
          opcional: true,
        },
      ],
    }
    expect(camposDoTemplate(livre)).toEqual([
      {
        chave: 'nome_criativo',
        rotulo: 'Nome do criativo',
        abreviar: false,
        maxCaracteres: 10,
        opcional: true,
        categoria: 'nome_criativo',
      },
    ])
  })

  it('cai num rótulo legível quando o token é antigo e não tem um', () => {
    const antigo: Template = {
      ...TEMPLATES[0],
      tokens: [{ tipo: 'campo', chave: 'tipo_compra' }],
    }
    expect(camposDoTemplate(antigo)[0].rotulo).toBe('Tipo compra')
  })

  it('usa a categoria do token quando ela difere da chave', () => {
    const compartilhado: Template = {
      ...TEMPLATES[0],
      tokens: [{ tipo: 'campo', chave: 'interesse_2', categoria: 'interesse' }],
    }
    expect(camposDoTemplate(compartilhado)[0].categoria).toBe('interesse')
  })
})

describe('marcador de ausência (D-011)', () => {
  const comMarcador = (token: TokenCampo, doTemplate?: string): Template => ({
    ...TEMPLATES[0],
    marcador_ausencia: doTemplate,
    tokens: [token],
  })

  it('repassa o marcador do template para o campo opcional', () => {
    const t = comMarcador({ tipo: 'campo', chave: 'funil', opcional: true }, 'NA')
    expect(camposDoTemplate(t)[0].marcadorAusencia).toBe('NA')
  })

  it('deixa o marcador do token vencer o do template', () => {
    const t = comMarcador(
      { tipo: 'campo', chave: 'funil', opcional: true, marcador_ausencia: 'SEM' },
      'NA',
    )
    expect(camposDoTemplate(t)[0].marcadorAusencia).toBe('SEM')
  })

  it('não marca campo obrigatório, que nunca fica em branco', () => {
    const t = comMarcador({ tipo: 'campo', chave: 'objetivo' }, 'NA')
    expect(camposDoTemplate(t)[0].marcadorAusencia).toBeUndefined()
  })

  it('preserva o comportamento antigo quando não há marcador nenhum', () => {
    // Retrocompatibilidade: template v1/v2 lido do banco não pode passar a
    // prometer um `NA` que o motor daquela versão não escreve.
    const t = comMarcador({ tipo: 'campo', chave: 'funil', opcional: true })
    expect(camposDoTemplate(t)[0].marcadorAusencia).toBeUndefined()
  })

  it('avisa no formulário o que o campo opcional grava se ficar em branco', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        const corpo = url.startsWith('/api/plataformas?')
          ? [META]
          : url.includes('/templates')
            ? [
                {
                  ...template('CAMPANHA', []),
                  marcador_ausencia: 'NA',
                  tokens: [
                    {
                      tipo: 'campo',
                      chave: 'funil',
                      rotulo: 'Etapa do funil',
                      opcional: true,
                    },
                  ],
                },
              ]
            : url.startsWith('/api/dicionario')
              ? DICIONARIO
              : []
        return { ok: true, status: 200, json: async () => corpo } as Response
      }),
    )

    render(<Taxonomia />)
    await user.selectOptions(await screen.findByLabelText('Plataforma'), META.id)

    const campo = await screen.findByLabelText(/Etapa do funil/)
    expect(campo).toHaveAccessibleDescription('Em branco, o nome recebe NA nesta posição.')
  })
})

describe('saída do aplicativo', () => {
  // A saída deixou de morar no `h1` desta tela: a `BarraTopo` virou cromo
  // global (o `App` a monta em toda rota do produto), e é a marca dela que
  // leva ao início. Duas marcas clicáveis na mesma tela seriam dois caminhos
  // para o mesmo lugar, com pesos diferentes.
  it('tem título próprio e um Voltar hierárquico, não a marca repetida', async () => {
    render(<Taxonomia />)
    await screen.findByLabelText('Plataforma')

    // A marca mora só na barra global (cromo). O `h1` daqui é o ASSUNTO —
    // não a marca, e não o nome da aba: aba não é tela (§2.4).
    expect(screen.queryByRole('link', { name: /MediaBuild/ })).not.toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Construção de taxonomia' }),
    ).toBeInTheDocument()

    // Voltar hierárquico, com destino verificável ANTES do clique — não
    // `history.back()`, cujo rótulo teria que mentir.
    const voltar = screen.getByRole('link', { name: /Voltar para os assuntos/ })
    expect(voltar).toHaveAttribute('href', '#/assunto')
  })

  it('o Voltar fica fora dos tabpanel e não muda ao trocar de aba', async () => {
    const user = userEvent.setup()
    render(<Taxonomia />)
    await screen.findByLabelText('Plataforma')

    const voltar = screen.getByRole('link', { name: /Voltar para os assuntos/ })
    // As abas organizam DENTRO do assunto; o Voltar opera ENTRE assuntos.
    expect(voltar.closest('[role="tabpanel"]')).toBeNull()

    await user.click(screen.getByRole('tab', { name: 'Histórico' }))
    expect(screen.getByRole('link', { name: /Voltar para os assuntos/ })).toHaveAttribute(
      'href',
      '#/assunto',
    )
  })

  it('foca o cabeçalho da tela, não o h1, para o Voltar ficar no caminho do Tab', async () => {
    render(<Taxonomia />)
    await screen.findByLabelText('Plataforma')

    const alvo = document.querySelector('[data-foco-rota]')
    expect(alvo?.tagName).toBe('HEADER')
    // Com o foco no `h1`, o link acima dele só seria alcançável por Shift+Tab.
    expect(alvo?.querySelector('a.voltar-para')).not.toBeNull()
  })

  it('a marca da barra de topo leva de volta para a tela inicial', () => {
    renderComSessao(<BarraTopo />)
    expect(screen.getByRole('link', { name: /MediaBuild/ })).toHaveAttribute('href', '#/')
  })
})

describe('cascata', () => {
  it('começa com tudo bloqueado até escolher a plataforma', async () => {
    render(<Taxonomia />)
    await screen.findByLabelText('Plataforma')
    expect(screen.getAllByText('Selecione uma plataforma para começar.')).toHaveLength(3)
  })

  it('abre a campanha e mantém grupo e anúncio bloqueados', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)

    await waitFor(() => expect(screen.getByLabelText(/Objetivo/)).toBeInTheDocument())
    expect(screen.getByText('Complete a campanha primeiro.')).toBeInTheDocument()
    expect(screen.getByText('Complete o grupo de anúncio primeiro.')).toBeInTheDocument()
  })

  it('libera o grupo quando a campanha fica válida', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)

    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')

    await waitFor(() => expect(screen.getByLabelText(/Público/)).toBeInTheDocument())
    expect(screen.queryByText('Complete a campanha primeiro.')).not.toBeInTheDocument()
  })
})

describe('campos dinâmicos', () => {
  it('renderiza os campos que o template do nível pede', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)
    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')

    // O heading existe mesmo bloqueado, então espera-se pelo campo em si.
    await waitFor(() => expect(screen.getByLabelText(/Público/)).toBeInTheDocument())

    const grupo = painel('Grupo de anúncio')
    expect(within(grupo).getByLabelText(/Público/)).toBeInTheDocument()
    expect(within(grupo).getByLabelText(/Posicionamento/)).toBeInTheDocument()
  })

  it('vira select quando há dicionário, mostrando o De → Para', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)

    const campo = await screen.findByLabelText(/Objetivo/)
    expect(campo.tagName).toBe('SELECT')
    expect(within(campo).getByRole('option', { name: 'Conversão → CV' })).toBeInTheDocument()
  })
})

describe('preview ao vivo', () => {
  it('mostra a nomenclatura assim que os campos ficam completos', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)
    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')

    expect(await screen.findByText('FB_CV_C0000')).toBeInTheDocument()
    expect(screen.getByText(/11 \/ 400 caracteres/)).toBeInTheDocument()
  })

  it('copia o nome para a área de transferência', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)
    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')
    await screen.findByText('FB_CV_C0000')

    await user.click(within(painel('Campanha')).getByRole('button', { name: 'Copiar' }))
    expect(await navigator.clipboard.readText()).toBe('FB_CV_C0000')
  })

  it('exibe o erro do servidor e marca o campo culpado', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)

    // Campo livre para conseguir digitar um termo fora do dicionário.
    const campo = await screen.findByLabelText(/Objetivo/)
    await user.selectOptions(campo, 'Conversão')
    await screen.findByText('FB_CV_C0000')

    vi.mocked(fetch).mockImplementationOnce(
      async () =>
        ({
          ok: false,
          status: 422,
          json: async () => ({
            erro: 'termo_desconhecido',
            mensagem: "O termo 'Awareness' não está no dicionário de 'objetivo'.",
            campo: 'objetivo',
            opcoes: ['Conversão', 'Tráfego'],
          }),
        }) as Response,
    )
    await user.selectOptions(campo, 'Tráfego')

    expect(await screen.findByRole('alert')).toHaveTextContent(/não está no dicionário/)
    expect(
      screen.getByText('Cadastre o termo no dicionário ou escolha um dos existentes.'),
    ).toBeInTheDocument()
    expect(campo).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('salvar', () => {
  it('só habilita o botão quando os três níveis estão válidos', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)

    const botao = screen.getByRole('button', { name: /Salvar e gerar/ })
    expect(botao).toBeDisabled()

    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')
    await user.selectOptions(await screen.findByLabelText(/Público/), 'Remarketing')
    await user.selectOptions(await screen.findByLabelText(/Posicionamento/), 'Instagram Stories')
    await user.selectOptions(await screen.findByLabelText(/Formato/), 'Stories')

    await waitFor(() => expect(botao).toBeEnabled())
  })

  it('grava os três níveis e mostra as nomenclaturas finais', async () => {
    const user = userEvent.setup()
    await selecionarMeta(user)

    await user.selectOptions(await screen.findByLabelText(/Objetivo/), 'Conversão')
    await user.selectOptions(await screen.findByLabelText(/Público/), 'Remarketing')
    await user.selectOptions(await screen.findByLabelText(/Posicionamento/), 'Instagram Stories')
    await user.selectOptions(await screen.findByLabelText(/Formato/), 'Stories')

    const botao = screen.getByRole('button', { name: /Salvar e gerar/ })
    await waitFor(() => expect(botao).toBeEnabled())
    await user.click(botao)

    expect(await screen.findByText('✓ FB_CV_C0001')).toBeInTheDocument()
    expect(screen.getByText('✓ FB_RMKT_IGST_G0001')).toBeInTheDocument()
    expect(screen.getByText('✓ FB_ST_A0001')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Copiar os três nomes' }))
    expect(await navigator.clipboard.readText()).toBe(
      'FB_CV_C0001\nFB_RMKT_IGST_G0001\nFB_ST_A0001',
    )
  })
})
