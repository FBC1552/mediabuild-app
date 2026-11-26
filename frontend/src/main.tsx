import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { ProvedorSessao } from './sessao'
import './index.css'
import './estilos/layout.css'
import './estilos/componentes.css'
import './estilos/gerador.css'
// Por último: a camada de telas ajusta peças das anteriores (a altura do palco
// da splash, a métrica hero do botão secundário) e precisa vencer na cascata.
import './estilos/telas.css'
// Plano de mídia é uma tela nova, não um ajuste das anteriores — mas reaproveita
// `.arvore-*`/`.selo`/`.abas` de `componentes.css` e `.titulo-tela`/`.pagina` de
// `telas.css`/`layout.css`, então precisa carregar depois das duas para as
// classes novas (`.tabela*`, `.campo-rateio*`, `.faixa-saldo`) nunca perderem
// para uma regra homônima mais antiga na cascata.
import './estilos/plano.css'
// Parte II da UX-NAVEGACAO: voltar hierárquico, casca do admin e densidade de
// dados. Por último porque AJUSTA `.tabela` (de `plano.css`) e `.card`.
import './estilos/admin.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* A sessão envolve TUDO: o portão de `#/entrar` é decidido no `App`, e
        o menu de conta vive no cromo, que aparece em quase toda rota. */}
    <ProvedorSessao>
      <App />
    </ProvedorSessao>
  </StrictMode>,
)
