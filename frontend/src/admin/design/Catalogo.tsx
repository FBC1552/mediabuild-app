import { useEffect, useRef, useState } from 'react'

import { Estado } from '../../componentes/ui'
import { ROTULO_SECAO, SECOES_CATALOGO, type SecaoCatalogo } from '../../roteador'
import { CascaAdmin } from '../CascaAdmin'
import {
  ContextoPalco,
  FUNDOS,
  LARGURAS,
  MostraExemplo,
  PADRAO,
  Selecao,
  ZOOMS,
  type Preferencias,
} from './MostraExemplo'
import { EXEMPLOS_POR_SECAO } from './registro'

/**
 * Catálogo de interface (`#/admin/*`). Rótulo na UI é "Catálogo de interface"
 * — a página não administra nada, e prometer administração e não entregar é
 * pior que o nome feio na URL.
 *
 * Uma seção por rota: sete seções em rolagem única viram maratona e impedem
 * link direto para o que se quer discutir.
 */
export default function Catalogo({ secao }: { secao: SecaoCatalogo }) {
  const [global, setGlobal] = useState<Preferencias>(PADRAO)
  const [textoGrande, setTextoGrande] = useState(false)
  const conteudoRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Zoom de texto a 200% é o teste de WCAG 1.4.4 mais barato que existe.
    conteudoRef.current?.style.setProperty('font-size', textoGrande ? '200%' : '')
  }, [textoGrande])

  const exemplos = EXEMPLOS_POR_SECAO[secao]

  return (
    <CascaAdmin area="design">
      <div className="pilha" data-espaco="2">
        <h2 className="titulo-secao">Catálogo de interface</h2>
        <p className="marca-subtitulo medida">
          Referência viva do sistema visual. Não chama a API: tudo aqui sai de fixturas.
        </p>
      </div>

      <div className="catalogo">
        <nav className="catalogo-nav" aria-label="Seções do catálogo">
          {SECOES_CATALOGO.map((id) => (
            <a
              key={id}
              className="catalogo-link"
              href={`#/admin/design/${id}`}
              aria-current={id === secao ? 'page' : undefined}
            >
              {ROTULO_SECAO[id]}
            </a>
          ))}
        </nav>

        <div className="pilha" data-espaco="8" ref={conteudoRef}>
          {/* Controle global com sobrescrita local: só global impede comparar
              lado a lado; só local vira trabalho braçal. */}
          <div className="barra-controles linha" data-espaco="5">
            <Selecao
              rotulo="Largura"
              valor={global.largura}
              opcoes={LARGURAS.filter((o) => o.valor !== 'herdar')}
              aoMudar={(largura) => setGlobal((p) => ({ ...p, largura }))}
            />
            <Selecao
              rotulo="Zoom"
              valor={global.zoom}
              opcoes={ZOOMS.filter((o) => o.valor !== 'herdar')}
              aoMudar={(zoom) => setGlobal((p) => ({ ...p, zoom }))}
            />
            <Selecao
              rotulo="Fundo"
              valor={global.fundo}
              opcoes={FUNDOS.filter((o) => o.valor !== 'herdar')}
              aoMudar={(fundo) =>
                setGlobal((p) => ({ ...p, fundo: fundo as Preferencias['fundo'] }))
              }
            />
            <label className="controle-inline" htmlFor="texto-grande">
              <input
                id="texto-grande"
                type="checkbox"
                checked={textoGrande}
                onChange={(e) => setTextoGrande(e.target.checked)}
              />
              Texto grande (200%)
            </label>
          </div>

          <h3>{ROTULO_SECAO[secao]}</h3>

          <ContextoPalco.Provider value={global}>
            {exemplos.length === 0 ? (
              <Estado tipo="vazio" titulo="Nenhum exemplo cadastrado nesta seção ainda." />
            ) : (
              exemplos.map((exemplo) => <MostraExemplo key={exemplo.id} exemplo={exemplo} />)
            )}
          </ContextoPalco.Provider>
        </div>
      </div>
    </CascaAdmin>
  )
}
