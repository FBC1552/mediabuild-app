import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ArvoreCampanha, type CampanhaCorrente } from '../componentes/ArvoreCampanha'
import type { NoDaArvore } from '../tipos'

/**
 * `ArvoreCampanha` precisa sobreviver a mais de uma instância na mesma
 * página — é exatamente o que o catálogo de componentes faz ao renderizar
 * vários exemplos de uma seção simultaneamente. Um id literal no `<h2>` ou
 * derivado só do `match_id` (que se repete entre instâncias diferentes,
 * como "grupo A" em duas campanhas de exemplo) quebraria o rótulo
 * acessível: o `aria-labelledby` da segunda seção apontaria para o `<h2>`
 * da primeira.
 */

function grupo(match: string, campanhaId: string): NoDaArvore {
  return {
    id: `g-${campanhaId}-${match}`,
    pai_id: campanhaId,
    nome_interno: `Grupo ${match}`,
    match_id: match,
    nomenclatura: null,
    taxonomia_id: null,
    gerado_em: null,
    criado_em: '2026-08-06T12:00:00Z',
  }
}

describe('ArvoreCampanha com múltiplas instâncias na mesma página', () => {
  it('rotula cada seção pelo próprio título, mesmo com match_id repetido entre instâncias', () => {
    const campanhaA: CampanhaCorrente = { id: 'ca', match_id: 'C0001', nome_interno: 'Campanha A' }
    const campanhaB: CampanhaCorrente = { id: 'cb', match_id: 'C0002', nome_interno: 'Campanha B' }
    // Mesmo match_id de grupo ("G0001") em ambas — é o caso que quebraria um
    // id derivado só do match_id, sem prefixo de instância.
    const grupoA = grupo('G0001', 'ca')
    const grupoB = grupo('G0001', 'cb')

    render(
      <>
        <ArvoreCampanha
          campanha={campanhaA}
          grupos={[grupoA]}
          anunciosPorGrupo={{}}
          carregando={false}
          erro={null}
          aoNovoGrupo={() => {}}
          aoNovoAnuncio={() => {}}
        />
        <ArvoreCampanha
          campanha={campanhaB}
          grupos={[grupoB]}
          anunciosPorGrupo={{}}
          carregando={false}
          erro={null}
          aoNovoGrupo={() => {}}
          aoNovoAnuncio={() => {}}
        />
      </>,
    )

    const titulos = screen.getAllByRole('heading', { name: 'Estrutura da campanha' })
    expect(titulos).toHaveLength(2)

    const [secaoA, secaoB] = titulos.map((h2) => h2.closest('section')!)

    // Cada section é acessivelmente nomeada pelo PRÓPRIO h2, não pelo
    // primeiro do documento: o texto do nome acessível casa com o conteúdo
    // daquela seção específica.
    expect(secaoA).toHaveAccessibleName('Estrutura da campanha')
    expect(secaoB).toHaveAccessibleName('Estrutura da campanha')

    expect(within(secaoA).getByText('Campanha A')).toBeInTheDocument()
    expect(within(secaoA).queryByText('Campanha B')).not.toBeInTheDocument()
    expect(within(secaoB).getByText('Campanha B')).toBeInTheDocument()
    expect(within(secaoB).queryByText('Campanha A')).not.toBeInTheDocument()

    // Ids de fato distintos entre as duas seções (não duplicados no DOM).
    const idA = secaoA.getAttribute('aria-labelledby')
    const idB = secaoB.getAttribute('aria-labelledby')
    expect(idA).toBeTruthy()
    expect(idB).toBeTruthy()
    expect(idA).not.toBe(idB)
  })

  it('mantém aria-controls e o id do <ul> de anúncios únicos por instância, mesmo com match_id de grupo repetido', () => {
    const campanhaA: CampanhaCorrente = { id: 'ca', match_id: 'C0001', nome_interno: 'Campanha A' }
    const campanhaB: CampanhaCorrente = { id: 'cb', match_id: 'C0002', nome_interno: 'Campanha B' }
    // Mesmo match_id de grupo ("G0001") nas duas instâncias — antes da
    // correção, `idFilhos` era só `anuncios-de-${grupo.match_id}`, então as
    // duas instâncias gerariam o MESMO id de `<ul>`, e o `aria-controls` do
    // botão de uma instância poderia acabar apontando para a lista da outra.
    const grupoA = grupo('G0001', 'ca')
    const grupoB = grupo('G0001', 'cb')
    const anuncioA: NoDaArvore = {
      id: 'an-a',
      pai_id: grupoA.id,
      nome_interno: 'Anúncio A',
      match_id: 'A0001',
      nomenclatura: null,
      taxonomia_id: null,
      gerado_em: null,
      criado_em: '2026-08-06T12:00:00Z',
    }
    const anuncioB: NoDaArvore = {
      id: 'an-b',
      pai_id: grupoB.id,
      nome_interno: 'Anúncio B',
      match_id: 'A0001',
      nomenclatura: null,
      taxonomia_id: null,
      gerado_em: null,
      criado_em: '2026-08-06T12:00:00Z',
    }

    render(
      <>
        <ArvoreCampanha
          campanha={campanhaA}
          grupos={[grupoA]}
          anunciosPorGrupo={{ [grupoA.id]: [anuncioA] }}
          carregando={false}
          erro={null}
          aoNovoGrupo={() => {}}
          aoNovoAnuncio={() => {}}
        />
        <ArvoreCampanha
          campanha={campanhaB}
          grupos={[grupoB]}
          anunciosPorGrupo={{ [grupoB.id]: [anuncioB] }}
          carregando={false}
          erro={null}
          aoNovoGrupo={() => {}}
          aoNovoAnuncio={() => {}}
        />
      </>,
    )

    const botoes = screen.getAllByRole('button', { name: /Recolher anúncios de Grupo G0001/ })
    expect(botoes).toHaveLength(2)
    const controlsA = botoes[0].getAttribute('aria-controls')
    const controlsB = botoes[1].getAttribute('aria-controls')

    expect(controlsA).toBeTruthy()
    expect(controlsB).toBeTruthy()
    // O ponto central da correção: os dois ids não colidem mais.
    expect(controlsA).not.toBe(controlsB)

    // E cada botão controla de fato a lista dentro da SUA própria seção.
    const secaoA = botoes[0].closest('section')!
    const secaoB = botoes[1].closest('section')!
    expect(within(secaoA).getByText('Anúncio A').closest('ul')).toHaveAttribute('id', controlsA)
    expect(within(secaoB).getByText('Anúncio B').closest('ul')).toHaveAttribute('id', controlsB)
    expect(document.getElementById(controlsA!)).toBe(document.getElementById(controlsA!))
  })
})
