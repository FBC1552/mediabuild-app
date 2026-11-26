import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '../App'
import { caminhoDe, lerRota, REDIRECIONAMENTOS_LEGADOS, SECOES_CATALOGO } from '../roteador'
import { renderComSessao } from './ajudaSessao'

/** Toda `Rota` carrega `params`; os testes de mapeamento olham só o alvo. */
function alvo(hash: string) {
  const { params, ...resto } = lerRota(hash)
  void params
  return resto
}

describe('lerRota', () => {
  it('mapeia as rotas conhecidas', () => {
    expect(alvo('')).toEqual({ nome: 'splash' })
    expect(alvo('#/')).toEqual({ nome: 'splash' })
    expect(alvo('#/entrar')).toEqual({ nome: 'entrar' })
    expect(alvo('#/assunto')).toEqual({ nome: 'assunto' })
    expect(alvo('#/guia')).toEqual({ nome: 'guia' })
    expect(alvo('#/cadastro')).toEqual({ nome: 'cadastro' })
    expect(alvo('#/taxonomia/historico')).toEqual({ nome: 'taxonomia', aba: 'historico' })
    // Plano de mídia: assunto irmão da taxonomia (D-010), não quarta aba.
    expect(alvo('#/plano')).toEqual({ nome: 'plano-lista' })
    expect(alvo('#/plano/metricas')).toEqual({ nome: 'plano-metricas' })
    expect(alvo('#/plano/8f14e...uuid')).toEqual({ nome: 'plano', id: '8f14e...uuid' })
    // Administração em três áreas (§3.1).
    expect(alvo('#/admin/acessos')).toEqual({ nome: 'admin-acessos' })
    expect(alvo('#/admin/monitoramento')).toEqual({ nome: 'admin-monitoramento' })
    expect(alvo('#/admin/design/movimento')).toEqual({ nome: 'catalogo', secao: 'movimento' })
    expect(alvo('#/isolado/componentes-botao')).toEqual({
      nome: 'isolado',
      exemplo: 'componentes-botao',
    })
  })

  it('canoniza os ramos sem segmento', () => {
    // O App faz o replaceState; aqui só interessa o destino calculado.
    expect(caminhoDe(lerRota('#/taxonomia'))).toBe('#/taxonomia/gerar')
    // `#/admin` cai em Acessos: é a área que responde à pergunta que traz
    // alguém aqui ("quem tem acesso"), não o catálogo de design.
    expect(caminhoDe(lerRota('#/admin'))).toBe('#/admin/acessos')
    expect(caminhoDe(lerRota('#/admin/design'))).toBe('#/admin/design/fundacao')
  })

  it('trata aba e seção inexistentes como endereço desconhecido', () => {
    expect(alvo('#/taxonomia/relatorios')).toEqual({
      nome: 'desconhecida',
      caminho: '/taxonomia/relatorios',
    })
    expect(alvo('#/admin/design/cores')).toEqual({
      nome: 'desconhecida',
      caminho: '/admin/design/cores',
    })
    expect(alvo('#/qualquer')).toEqual({ nome: 'desconhecida', caminho: '/qualquer' })
    // As telas de conteúdo são de segmento único: nada de subcapítulo
    // silenciosamente ignorado.
    expect(alvo('#/guia/match-id')).toEqual({
      nome: 'desconhecida',
      caminho: '/guia/match-id',
    })
    expect(alvo('#/cadastro/novo')).toEqual({
      nome: 'desconhecida',
      caminho: '/cadastro/novo',
    })
  })
})

describe('query string na hash (§6.5)', () => {
  it('corta em `?` antes de dividir por `/`', () => {
    // Sem o corte, `dicionario?q=x` cairia em `desconhecida` e o atalho
    // erro → cadastro do Preview não existiria.
    const rota = lerRota('#/taxonomia/dicionario?q=conversao&cat=objetivo')
    expect(rota.nome).toBe('taxonomia')
    expect(rota.nome === 'taxonomia' && rota.aba).toBe('dicionario')
    expect(rota.params.get('q')).toBe('conversao')
    expect(rota.params.get('cat')).toBe('objetivo')
  })

  it('devolve parâmetros vazios quando não há query', () => {
    expect([...lerRota('#/taxonomia/gerar').params.keys()]).toEqual([])
  })

  it('preserva a query ao recompor o caminho', () => {
    // É o que impede a canonização do App de engolir o `?q=` na volta.
    expect(caminhoDe(lerRota('#/taxonomia/dicionario?q=conversao'))).toBe(
      '#/taxonomia/dicionario?q=conversao',
    )
  })

  it('decodifica valor com acento e espaço', () => {
    expect(lerRota('#/taxonomia/dicionario?q=Convers%C3%A3o+direta').params.get('q')).toBe(
      'Conversão direta',
    )
  })
})

describe('URLs antigas do catálogo (§3.2)', () => {
  it('redireciona as sete seções, em vez de 404', () => {
    // Semântica de 301: o endereço é CONHECIDO e mudou de lugar — e quem
    // publicou o link antigo (rodapé de `cromo.tsx`) fomos nós. 404 num link
    // que o próprio produto distribuiu é dano autoinfligido.
    for (const secao of SECOES_CATALOGO) {
      const rota = lerRota(`#/admin/${secao}`)
      expect(rota.nome).toBe('catalogo')
      expect(caminhoDe(rota)).toBe(`#/admin/design/${secao}`)
    }
  })

  it('tem uma entrada de tabela por seção, para poder ser apagada de uma vez', () => {
    expect(Object.keys(REDIRECIONAMENTOS_LEGADOS)).toHaveLength(SECOES_CATALOGO.length)
  })

  it('leva a query junto no redirecionamento', () => {
    expect(caminhoDe(lerRota('#/admin/fundacao?x=1'))).toBe('#/admin/design/fundacao?x=1')
  })
})

describe('telas de conteúdo montadas pelo App', () => {
  /** Nenhuma das duas chama a API — se chamar, o `fetch` não mockado estoura. */
  function abrir(hash: string) {
    window.history.replaceState(null, '', hash)
    renderComSessao(<App />)
  }

  it('monta o guia de uso em #/guia', () => {
    abrir('#/guia')
    expect(screen.getByRole('heading', { level: 1, name: 'Guia de uso' })).toBeInTheDocument()
    expect(document.title).toBe('Guia de uso · MediaBuild')
    // O foco precisa acompanhar a rota: sem isso o teclado recomeça do <body>.
    expect(document.querySelector('[data-foco-rota]')).toHaveFocus()
  })

  it('monta o acesso em #/cadastro sem prometer um cadastro que não existe', () => {
    abrir('#/cadastro')
    expect(
      screen.getByRole('heading', { level: 1, name: 'Acesso ao MediaBuild' }),
    ).toBeInTheDocument()

    // A tela não afirma mais que "o MediaBuild não tem autenticação" — tem,
    // desde o D-014. E não há formulário, campo nem botão que finja enviar:
    // contas são criadas por um administrador (§3.6).
    expect(document.querySelector('form')).toBeNull()
    expect(document.querySelector('input')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Criar conta' })).not.toBeInTheDocument()
    expect(screen.getByText(/Não há autocadastro/)).toBeInTheDocument()
  })
})

describe('caminhoDe', () => {
  it('é o inverso de lerRota para toda rota conhecida', () => {
    for (const hash of [
      '#/',
      '#/entrar',
      '#/assunto',
      '#/guia',
      '#/cadastro',
      '#/taxonomia/gerar',
      '#/taxonomia/dicionario',
      '#/plano',
      '#/plano/metricas',
      '#/plano/123e4567-e89b-12d3-a456-426614174000',
      '#/admin/acessos',
      '#/admin/monitoramento',
      '#/admin/design/fundacao',
      '#/isolado/estados-erro',
      '#/nao-existe',
    ]) {
      expect(caminhoDe(lerRota(hash))).toBe(hash)
    }
  })
})
