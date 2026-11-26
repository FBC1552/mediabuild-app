# Plano de Mídia — desenho de interface

Documento de desenho, não de implementação. Lido junto de `docs/PLANO-DE-MIDIA.md` (domínio,
já travado) e do contrato real do backend: `backend/app/models/plano_midia.py`,
`backend/app/schemas.py` (seção *plano de mídia*), `backend/app/routers/planos.py`,
`backend/app/routers/metricas.py`, `backend/app/exportacao_plano.py`.

Convenção de leitura: as seis perguntas do pedido (A–F) são respondidas dentro das seções
correspondentes, não num bloco à parte — cada uma nasce da anatomia da tela que a resolve.

---

## 0 · O que o contrato já resolve por mim

Vale registrar antes do desenho, porque muda o que a interface precisa *calcular* versus só
*exibir*:

- **`valor` é a única fonte da verdade; `percentual` nunca é persistido** (`_LinhaPedido`,
  `app/routers/planos.py`). A API aceita `valor` OU `percentual` na escrita — nunca os dois,
  nunca nenhum — e devolve os dois sempre calculados a partir do que está gravado. Isso simplifica
  o controle duplo do problema C: o cliente não precisa decidir qual dos dois é "a verdade", o
  servidor já decidiu.
- **`soma_*` e `diferenca` já vêm prontos em todo nível** — `PlanoMidiaLer.soma_campanhas`/
  `diferenca`, `CampanhaDoPlanoLer.soma_grupos`/`diferenca`, `GrupoDoPlanoLer.soma_anuncios`/
  `diferenca`. A interface não recalcula rateio nem soma nada — só exibe o que a leitura devolve
  a cada resposta. Isso resolve boa parte do problema B: o dado para "mostrar o delta em R$ de
  todos os níveis" já está na árvore, uma viagem só (`_montar_plano_ler` monta tudo em lote).
- **`nomenclatura` (snapshot) e `nomenclatura_atual` (agora) já vêm separados**, com
  `nomenclatura_divergente` calculado — o problema D não precisa de lógica de comparação no
  cliente, só de decisão de exibição.
- **O que o backend NÃO resolve, e a interface não pode fingir que resolve** (ver §5, §6, §8 —
  são as lacunas que retornam nas respostas A–F abaixo, sinalizadas onde mordem):
  1. Não existe endpoint para **atualizar o snapshot** de nome/match_id de uma linha já criada —
     `CampanhaDoPlanoAtualizar`/`GrupoDoPlanoAtualizar`/`AnuncioDoPlanoAtualizar` só tocam
     valor/percentual (e flight/KPI/custo unitário/metas). "Atualizar nomenclatura" (problema D)
     não tem verbo de API hoje.
  2. Não existe, em lugar nenhum do schema, uma classificação de **qual métrica se aplica a qual
     combinação plataforma+formato** (problema E, §3 de `PLANO-DE-MIDIA.md`). O próprio documento
     de domínio já registra isso como pendente de levantamento com o cliente.
  3. `gerar_planilha_plano` não escreve nenhuma nota de desbalanço na planilha exportada — a
     recomendação do §4 do domínio ("Total alocado: R$X de R$Y — R$Z sem definir") ainda não
     está implementada no exportador.

Nenhuma dessas três é decisão de UX — são pré-requisitos de backend que a tela vai *pedir* mas não
pode fabricar sozinha. Ficam explícitas na lista final (§9).

---

## 1 · F — onde a tela mora

**Recomendação: assunto irmão, não aba nova da Taxonomia.** Rota `#/plano`.

Justificativa por arquitetura de informação, não por conveniência de código:

- `docs/DECISOES.md` D-010 e o próprio `cromo.tsx` já registram o princípio: *"sistemas de
  organização diferentes não compartilham a mesma barra"*. As abas Gerar/Dicionário/Histórico são
  um **sistema de rotulagem em torno de um único verbo**: gerar nome para uma entidade por vez,
  cascata campanha→grupo→anúncio, tela por nível. Plano de Mídia é outro verbo: **orquestrar
  entidades já nomeadas** — selecionar N campanhas existentes, ratear uma verba entre elas,
  registrar metas por anúncio, exportar um documento consolidado. O objeto de trabalho muda de
  "uma nomenclatura" para "um plano com uma árvore inteira dentro". Enfiar isso como quarta aba
  do gerador quebraria a proporção de Miller-por-grupo (regra 8 deste agente): a aba Gerar já é
  densa por nível; encaixar rateio+metas dentro dela sobrecarregaria uma tela que hoje tem um job
  único e bem cumprido.
- **O produto já reservou o lugar.** `SeletorDeAssunto` (`#/assunto`) tem hoje três cartões:
  Construção de taxonomia (ativo), Social (em breve), **Mídia (em breve)**. "Mídia" é
  exatamente o rótulo certo para "planejar investimento e metas por campanha" — meio do domínio
  já sinalizado como próximo assunto, não uma tela emprestada de outro. Meu desenho assume que
  este é o cartão que passa a apontar para `#/plano` (com `aoAtivar` gravando
  `CHAVE_ULTIMO_ASSUNTO`, mesmo padrão do cartão de Taxonomia).
- **Decisão de copy que devolvo ao usuário**: manter o rótulo do cartão como "Mídia" (guarda-chuva
  para o que vier depois — compra, relatório) ou trocar para "Plano de mídia" (nomeia exatamente o
  que existe hoje). Não decido sozinho porque é escopo futuro do produto, não só rótulo de tela.

### Forma da rota

```
#/plano                    → índice de planos (lista + criar)
#/plano/{id}                → tela de um plano (header + duas abas internas)
#/plano/metricas            → catálogo de métricas (CRUD), análogo ao Dicionário
```

`lerRota`/`caminhoDe` (`src/roteador.ts`) precisam de um `Rota` novo com **segmento dinâmico**
(`{ nome: 'plano'; id: string } | { nome: 'plano-lista' } | { nome: 'plano-metricas' }` — nomes
exatos ficam com quem implementar). É a primeira rota do produto que carrega um identificador na
URL; hoje só `isolado/{exemplo}` faz algo parecido, com string livre em vez de UUID. Endereçável de
propósito (mesmo racional de D-010): um plano que já foi montado tem que poder ser reaberto por
link, sem depender de clicar a partir da lista toda vez.

### Cromo

Tela própria, com o mesmo tratamento estrutural de `AplicativoTaxonomia`: `h1` "MediaBuild"
clicável para `#/` (único ponto de saída entre assuntos), e abas internas *dentro* da tela do
plano (Estrutura e verba / Metas) usando o mesmo `.abas`/`.aba` já estilizado — não a `BarraTopo`
de `cromo.tsx`, que é reservada a Guia/Cadastro por design (ver docstring do próprio arquivo).

---

## 2 · Anatomia — índice de planos (`#/plano`)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ MediaBuild                                                    Métricas → │
│ Planos de mídia                                          [+ Novo plano]  │
├──────────────────────────────────────────────────────────────────────────┤
│  Nome              Verba total   Alocado        Diferença    Atualizado  │
│  Campanha Julho     R$ 500.000   R$ 486.500  ▲ R$ 13.500      06/08      │
│  Reforço Agosto     R$ 120.000   R$ 120.000  ✓ fechado         05/08     │
│  Rascunho sem nome  R$ 0         R$ 0          —                04/08    │
└──────────────────────────────────────────────────────────────────────────┘
```

Tabela densa, mesmo padrão de `Historico.tsx` (uma linha por plano, sem paginar cedo) — mas com
uma coluna a mais que o histórico não tem: **Diferença**, com o mesmo tratamento visual de badge
que a tela do plano usa (ver §4). É a decisão do problema B aplicada também na lista: o desbalanço
tem que ser visível **antes** de abrir o plano, porque é o primeiro sinal de "este documento ainda
não está pronto para sair".

Clicar na linha abre `#/plano/{id}`. "+ Novo plano" abre um formulário mínimo inline (nome + verba
total + observações opcional — `PlanoMidiaCriar`) — não uma tela nova; é rápido demais para
merecer navegação própria.

**Estados desta tela:**
- *Vazio*: `Estado tipo="vazio"` — "Nenhum plano de mídia ainda." + botão "Novo plano".
- *Carregando*: linhas em `Esqueleto forma="texto"`, mesmo padrão de qualquer tabela do produto.
- *Erro* (falha ao listar): `Estado tipo="erro"` com o texto do backend.

---

## 3 · Anatomia — tela do plano (`#/plano/{id}`)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ MediaBuild                                                                │
│ [Nome do plano — editável inline]              Verba total: R$ 500.000 ✎ │
│ ✓ salvo · atualizado há 2 min                                            │
├──────────────────────────────────────────────────────────────────────────┤
│ ▲ Plano: R$ 13.500 (2,7%) sem campanha definida     [Baixar Excel ▾]     │
├──────────────────────────────────────────────────────────────────────────┤
│  Estrutura e verba          Metas                                        │  ← abas (APG)
├──────────────────────────────────────────────────────────────────────────┤
│                        (conteúdo da aba ativa — §4 ou §5)                │
└──────────────────────────────────────────────────────────────────────────┘
```

O cabeçalho carrega três coisas que **não pertencem a nenhuma aba**, porque são fatos do plano
inteiro e o usuário não pode perder de vista trocando de aba (regra 4 deste agente — estado
preservado é respeito, e aqui isso vale para *visibilidade*, não só para dado):

1. Nome e verba total do plano — editáveis inline, mesma UX do "Nome interno" do gerador
   (`PainelNivel`): rótulo acima do campo, sem modal.
2. **A faixa de saldo do topo** (ver §4.2) — sempre visível, mesmo dentro da aba Metas. Resolve
   parte do problema B: mesmo editando uma meta de vídeo lá embaixo, o analista não perde de vista
   se o plano todo fecha.
3. "Baixar Excel" — ação secundária persistente, nunca escondida dentro de uma aba.

---

## 4 · Aba "Estrutura e verba" — A, B, C, D, F respondidos na prática

### 4.1 · Por que hierarquia expansível, e não tabela larga (problema A)

**Recomendação: duas vistas separadas dentro do plano — árvore editável para rateio, tabela plana
para metas — nunca a mesma grade.** O que sacrifico: não dá para ver a verba de um anúncio e a
meta de impressões dele lado a lado sem trocar de aba. Considero esse sacrifício aceitável porque
são duas operações cognitivamente diferentes (Hick/Miller — regra 8): rateio é *proporção dentro
de uma árvore de três níveis*, lido de cima para baixo; meta é *preenchimento em massa de uma
grade plana*, lida da esquerda para a direita, uma linha por anúncio — a própria estrutura que
uma planilha de plano de mídia de referência já usa. Forçar as duas no mesmo componente produziria uma
tabela com 3 níveis de indentação **e** 11 colunas de métrica simultaneamente — ilegível em
qualquer largura razoável, e o § A do pedido já antecipa esse risco.

Mitigação da perda: a faixa de saldo do cabeçalho (§3.2) fica visível nas duas abas, e a aba Metas
traz a coluna "Investimento previsto (R$)" do anúncio ao lado das métricas (somente leitura) —
o número de verba mais relevante para quem está preenchendo meta continua ali, sem trocar de aba.

A árvore reaproveita a estrutura de `ArvoreCampanha.tsx` (que já resolve N campanhas → N grupos →
N anúncios, expandir/recolher, ícone de nível, `match_id` visível, nunca `id`) — mas cada nó aqui é
**editável**, não só leitura, e cada campanha carrega um `+ Adicionar campanha` no topo (a árvore
de hoje assume uma campanha corrente só; a do plano precisa de várias em paralelo).

```
┌ Estrutura e verba ─────────────────────────────────────────── + Campanha ─┐
│ Trilha:  Plano R$500.000 ▲13.500  ›  (selecione uma campanha)             │
│                                                                             │
│ ▾ 🏳 Campanha de Julho · C3291           [ R$ 320.000 ][ 64,000 %] ✓ salvo│
│     AAAAA_BET_DV360_AUDNET_APP_JUL_NA_C3291  ⚠ nome desatualizado ›       │
│     Flight: [01/07/2026] a [31/07/2026]   KPI primário: [CPA ▾]           │
│     ▾ grupos: R$ 306.500 de R$ 320.000  ▲ R$ 13.500 não distribuído       │
│                                                                             │
│     ▾ 👥 F_35-44_BOLSA... · G1531        [ R$ 200.000 ][ 62,500 %]        │
│         Custo unitário negociado (CPM): [ R$ 18,50 ]                     │
│         ▾ anúncios: R$ 200.000 de R$ 200.000  ✓ fechado                  │
│         ▸ 📄 BNR_1080X1350...A · A0975   [ R$ 120.000 ][ 60,000 %]       │
│         ▸ 📄 BNR_1080X1350...B · A0976   [ R$  80.000 ][ 40,000 %]       │
│                                              + Adicionar anúncio existente│
│     ▸ 👥 M_25-34_SAPE... · G1532          [ R$ 106.500 ][ 33,281 %]      │
│                                              + Adicionar grupo existente  │
│                                                                             │
│ ▸ 🏳 Reforço institucional · C3305       [ R$ 180.000 ][ 36,000 %]       │
│                                              + Adicionar campanha existente│
└─────────────────────────────────────────────────────────────────────────┘
```

Cada linha (campanha/grupo/anúncio) é um `<li>` com: chevron de expandir, ícone de nível
(`IconeNivel`, reused), nome + `match_id`, o controle de rateio duplo (§4.3), e — só quando a linha
está expandida — os campos extras do nível (flight+KPI na campanha, custo unitário no grupo) e o
resumo dos filhos (soma + diferença, §4.2). Colapsado, uma campanha inteira cabe numa linha de
~32px; expandida, mostra só o que pertence àquele nível. Isso é *progressive disclosure com
moderação* (regra 7): os campos extras não somem — ficam a um clique, não escondidos atrás de um
menu "mais opções".

**Adicionar entidade existente**: cada nível ganha um combobox de busca (padrão APG combobox,
sem dependência nova — `<input>` + `<ul role="listbox">` escrito à mão, mesmo espírito das abas
por hash já escritas à mão neste projeto) filtrando por nome interno / match ID, escopado à
hierarquia certa — grupo só oferece grupos daquela campanha, anúncio só os daquele grupo. O
servidor já valida isso (`EntidadeForaDaHierarquia`), a busca só evita que o erro apareça na
prática.

### 4.2 · B — o desbalanço, onde mora e como se distingue

**Delta em R$, sempre, ao lado do percentual — nunca só percentual.** Cada nó com filhos mostra
`soma_filhos de valor_do_nó` mais a diferença em reais, igual ao mock acima
("R$ 306.500 de R$ 320.000 ▲ R$ 13.500 não distribuído"). O percentual bruto (`64,000 %`) fica no
campo de edição, não na frase de resumo — resolve literalmente o ponto 1 do domínio ("97,3% soa
quase fechado").

**Sub-alocado vs sobre-alocado — símbolo diferente, não só cor diferente** (requisito de
acessibilidade do pedido: perceptível sem depender de cor):

| Estado | `diferenca` | Ícone | Selo | Peso |
| --- | --- | --- | --- | --- |
| Fechado | `0` (ou abaixo de um centavo por arredondamento) | ✓ | `Selo variante="ok"` | leve — só o texto "fechado" |
| Sub-alocado | `> 0` | ▲ (seta para cima — "sobra pra alocar") | `Selo variante="alerta"` | médio |
| Sobre-alocado | `< 0` | ▼ invertida num triângulo cheio, ou `!` — precisa de forma distinta da seta de sub-alocado, não só a cor trocada | `Selo variante="erro"` | forte — o único que usa `--erro`, por ser o caso "prometendo mais mídia do que a verba cobre" (doc §4, ponto 3) |

Os dois ícones (`IconeAlerta`, ou duas variantes de seta) são **novos** em `icones.tsx` — hoje só
existe `IconeChevron`, que gira mas não muda de forma; imbalance precisa de duas formas
distintas (não duas rotações do mesmo triângulo), porque rotação sozinha falha o teste "sem
depender de cor E sem depender só de orientação" para quem tem baixa acuidade visual.

**Trilha de saldo (`FaixaDeSaldo`, componente novo):** faixa fixa no topo da aba, mostrando
Plano → campanha selecionada → grupo selecionado, cada segmento com seu próprio badge de
diferença, **mesmo quando o nível que está sendo editado é o de baixo**. É a resposta direta ao
ponto 2 do domínio: editar um grupo sem navegar teria que deixar visível se a campanha e o plano
acima continuam fechando. "Selecionada" aqui significa: o nó atualmente focado ou expandido na
árvore — a trilha segue o foco, não exige um clique à parte para "ver o caminho".

**Exportar com desbalanço — não bloqueia, mas confirma uma vez** (minha recomendação, sinalizada
como decisão do usuário no domínio, e repito o sinalizador aqui): clicar "Baixar Excel" com
`diferenca` do **plano** diferente de zero abre uma confirmação simples ("Este plano tem
R$ 13.500 não alocados. Exportar mesmo assim?" / "Exportar" / "Cancelar") — uma interrupção só, no
nível mais alto, não uma por campanha/grupo. Não bloqueia (respeita a decisão travada de não
redistribuir/não impedir); adiciona fricção mínima só no momento em que o documento sai da
ferramenta, que é exatamente onde o domínio já apontou o maior risco ("quem lê o plano fora do
app não vê o aviso da tela"). **Ponto que devolvo ao usuário**: aprovar esse gatilho de
confirmação (e se vale um limiar de tolerância, tipo ignorar diferenças abaixo de R$ 1 por
arredondamento composto — o domínio já registra que arredondamento em cascata pode produzir desvio
residual pequeno e legítimo).

### 4.3 · C — o controle de rateio duplo (`CampoRateio`, componente novo)

```
   [ R$ 200.000,00 ]  [ 62,500 % ]
     ─┬─                 ─┬─
      └── campo em foco   └── deriva ao vivo, cinza enquanto o outro edita
```

Comportamento, decidido pelo próprio formato do contrato (`_LinhaPedido` aceita só um dos dois):

1. **Dois inputs lado a lado**, R$ primeiro (mais peso — é o valor que a plataforma de mídia
   realmente move) e % ao lado, menor, tipografia mais leve (`--texto-suave`).
2. **Durante a digitação**: só o campo com foco guarda o texto bruto que a pessoa está digitando —
   nunca reformatado a cada tecla (perderia o cursor, WCAG e Wroblewski concordam aqui). O campo
   irmão (sem foco) é recalculado ao vivo **em memória, sem chamada de rede** — é aritmética local
   (`percentual = valor / valor_do_pai * 100`, arredondado a 3 casas para exibição), e fica com
   `data-derivado` — texto em `--texto-suave` em vez de `--texto`, sinal visual de "isto é
   calculado a partir do outro campo, não o que você digitou". Some no blur: depois de salvo, os
   dois números são igualmente fatos, não há razão para manter a distinção.
3. **No blur** (ou Enter): dispara o PATCH real, mandando **só** o campo editado
   (`valor` OU `percentual`, nunca os dois — mesmo contrato do backend). Enquanto a resposta não
   volta, o campo mostra um `Giro` pequeno inline; ao voltar, os dois campos são substituídos pelos
   valores que o servidor devolveu (fonte da verdade), e um "✓ salvo" transitório aparece por
   ~1,5s (mesmo padrão de `BotaoCopiar`), anunciado por live region.
4. **Erro de validação** (ex. negativo, acima de 100%, ou `EntidadeForaDaHierarquia` num caso mais
   raro de corrida): o campo que falhou ganha `aria-invalid`, borda em `--erro`, e uma linha de
   erro abaixo dele com o texto que o backend devolveu — nunca "validation failed" (regra 5).
5. **Teclado**: Enter confirma e move o foco para o próximo campo de rateio da árvore (padrão de
   planilha — Tab já faz isso nativamente entre inputs, Enter é o atalho extra que quem preenche
   dezenas de linhas vai usar).

### 4.4 · D — nomenclatura defasada

Cada linha com `nomenclatura_divergente = true` ganha, ao lado do nome, um
`Selo variante="alerta"` com texto curto ("nome desatualizado") — nunca escondido atrás de hover,
porque é informação que muda a leitura do plano, não um detalhe. Ativar o selo (clique/Enter)
expande uma revelação inline (`<details>`, sem JS de posicionamento, sem modal) mostrando as duas
strings lado a lado:

```
⚠ nome desatualizado                                            [fechar]
  No plano:  AAAAA_BET_DV360_AUDNET_APP_JUL_NA_C3291
  Agora:     AAAAA_BET_DV360_AUDNET_APP_JUL_VID_C3291
  [ Atualizar snapshot do plano ]
```

**Recomendação: avisa sempre, oferece atualizar, nunca atualiza sozinho.** Nunca silencioso —
regenerar a taxonomia sem tocar no plano é comportamento normal e esperado (D-004), então o plano
*vai* ficar defasado com frequência; um aviso que ninguém nota é pior que não ter aviso. Nunca
automático — o texto do próprio pedido já aponta o motivo: **o plano pode já ter sido enviado ao
cliente**, e trocar o nome sozinho nesse momento seria exatamente o tipo de mudança silenciosa que
D-004 existe para proibir do lado da taxonomia. O botão "Atualizar snapshot" é uma ação explícita,
por linha (não em lote no plano inteiro — cada linha pode ter sido escrita num momento diferente,
lote esconderia qual delas realmente mudou).

**Bloqueio que devolvo, porque é de backend, não de desenho**: hoje **não existe** o verbo de API
para essa ação. `CampanhaDoPlanoAtualizar`/`GrupoDoPlanoAtualizar`/`AnuncioDoPlanoAtualizar` só
cobrem valor/percentual e os campos extras de cada nível — nenhum deles toca `nome_interno`,
`match_id` ou `nomenclatura`. Implementar "Atualizar snapshot" no front pressupõe um campo/rota
novo no backend (ex. `PATCH .../campanhas/{id}` aceitar um `sincronizar_nomenclatura: true`, ou uma
rota de ação dedicada). Não decido a forma aqui — é para quem for implementar levar ao usuário
antes de tocar em `app/routers/planos.py`.

---

## 5 · Aba "Metas" — E respondido na prática

```
┌ Metas ────────────────────────────────────────────────────────────────────┐
│ ℹ Células cinza: a métrica não se aplica a este anúncio. Vazio ≠ zero.    │
├───────────────┬────────────┬────────┬──────────┬─────┬─────┬─────┬───────┤
│ Campanha ›     │ Investim.  │ Impres-│ Cliques  │Víd. │Víd. │ ... │ Comp. │
│ Grupo › Anúncio│ previsto   │ sões   │          │início│25% │     │       │
├───────────────┼────────────┼────────┼──────────┼─────┼─────┼─────┼───────┤
│ C3291›G1531›   │ R$ 120.000 │[4.000000]│[17.000]│[ 500]│[900]│ ... │ [50]  │
│  A0975 (BNR)   │            │        │          │▨ n/a │▨ n/a│     │       │
├───────────────┼────────────┼────────┼──────────┼─────┼─────┼─────┼───────┤
│ C3291›G1531›   │ R$  80.000 │[2.000000]│[16.000]│[ 500]│[500]│ ... │ [50]  │
│  A0976 (BNR)   │            │        │          │▨ n/a │▨ n/a│     │       │
├───────────────┴────────────┴────────┴──────────┴─────┴─────┴─────┴───────┤
│ TOTAL          │ R$ 200.000 │ 6.000.000│ 33.000 │  —   │  —  │ ... │ 100  │
└─────────────────────────────────────────────────────────────────────────┘
```

Uma linha por anúncio (leaf), igual à planilha de referência — resolve a metade "tabular" do problema
A. Colunas fixas à esquerda (breadcrumb + investimento, somente leitura — editar valor é trabalho
da outra aba, regra de não duplicar o mesmo dado editável em dois lugares) com `position: sticky`
horizontal, para não perder o contexto da linha ao rolar para a coluna 11. Rolagem **horizontal**
dentro do `.contexto-painel` da tabela (não vertical em cascata) — a única rolagem que este produto
aceita para dado tabular denso, e mesmo assim com as colunas de identificação fixas.

### 5.1 · E — mecânica da célula desabilitada

Decisão já travada em `PLANO-DE-MIDIA.md` §3: sempre visível, célula desabilitada com motivo,
branco ≠ zero. A pergunta aqui é só **como o analista entende isso sem passar o mouse
célula por célula** — três camadas, nenhuma delas por hover isolado:

1. **Legenda única, uma vez, no topo da tabela** (mostrado no mock acima): "Células cinza: a
   métrica não se aplica a este anúncio. Vazio ≠ zero." — ensina o vocabulário uma vez
   (Covert: linguagem é a interface), não repete em cada célula.
2. **Tratamento visual consistente e reconhecível**: fundo `--desabilitado-fundo`, texto
   `--desabilitado-texto`, e um glifo fixo dentro da célula (ex. "n/a", não vazio-vazio) — assim
   uma célula "não se aplica" nunca é visualmente idêntica a uma célula em branco que o analista
   ainda não preencheu. É a mesma disciplina do marcador `NA` da taxonomia (D-011): ausência tem
   marcador, não é espaço vazio adivinhado.
3. **Motivo sob foco, não sob hover**: a célula usa `aria-disabled="true"` + `readOnly` (nunca
   `disabled` puro) — o mesmo padrão que `CartaoOpcao` já estabelece em `ui.tsx`, justamente para
   continuar alcançável por Tab. Ao focar (teclado ou clique), uma linha de status fixa abaixo da
   tabela mostra o motivo específico: *"Vídeo — início não se aplica a A0975 (formato Banner)."* —
   isso serve tanto quem navega por mouse (hover ainda mostra `title`) quanto quem navega por
   teclado (foco é obrigatório para descobrir *qualquer* informação nesta interface, hover não).

**Bloqueio que devolvo, de novo por ser lacuna de dado e não de desenho**: a mecânica acima
pressupõe que exista, para cada anúncio, uma lista de "métricas aplicáveis" ou "métricas
bloqueadas + motivo". **Isso não existe hoje em nenhum schema.** `PLANO-DE-MIDIA.md` §3 já
registra a tabela de regras (que combinação plataforma+formato desabilita qual métrica) como
"levantamento pendente com o cliente" — não é uma omissão minha, é um dado que ainda não foi
coletado. Recomendo dois caminhos possíveis para quando o levantamento existir, sem escolher por
conta própria:
- **(a)** um campo calculado na leitura (`AnuncioDoPlanoLer.metricas_bloqueadas: dict[str, str]`,
  código da métrica → motivo), resolvido no servidor a partir do `canal`/`formato` que a
  taxonomia do anúncio já guarda em `campos` JSONB (mesmo caminho que `app/utm/repositorio.py` já
  usa para montar contexto);
- **(b)** uma tabela de regra nova (`metricas_bloqueios` ou token no template), no mesmo espírito
  de "regra é dado, não código" que rege todo o resto do produto (D-008).
Até essa lacuna fechar, a aba Metas nasce **sem** nenhuma célula desabilitada — todas as 11
colunas editáveis para todo anúncio, sem julgamento de aplicabilidade. É um estado inicial honesto
(o produto ainda não sabe distinguir), não uma simplificação permanente — quando a regra existir,
a mecânica acima já está desenhada para recebê-la sem redesenho de tabela.

### 5.2 · Entrada de meta e total

Célula numérica simples (`type="number"`, `inputMode="numeric"`, sem casas decimais — todas as
onze métricas são contagem, D do domínio §1), salva no blur com o mesmo padrão de confirmação
transitória do `CampoRateio`. Uma linha `TOTAL` fixa no rodapé da tabela (`position: sticky`
vertical), somando só as colunas visíveis, ignorando nulos — espelha exatamente o rodapé que
`gerar_planilha_plano` já produz no Excel, então a leitura na tela e a leitura do arquivo baixado
batem.

---

## 6 · Catálogo de métricas (`#/plano/metricas`)

CRUD simples, mesmo padrão de `Dicionario.tsx` (tabela + formulário de inclusão): código
(travado após criado — `MetricaAtualizar` não aceita mudar `codigo`, por isso o campo fica
somente-leitura na edição, com nota explicando por quê), rótulo, ordem, ativo/inativo. Sem botão
de excluir em destaque — `DELETE /metricas/{id}` existe no backend mas é destrutivo de verdade
(sem FK, mas some das metas antigas na exibição por rótulo — vira `_rotulo_de_fallback` no
export); a ação recomendada na interface é **desativar** (`ativo=false`), com "excluir
definitivamente" como ação secundária de menor peso, não a primária — mesmo espírito do D-004 de
preferir estados que preservam histórico a apagar.

Fica fora das duas abas do plano porque não é dado de UM plano — é vocabulário compartilhado por
todos, como o Dicionário é para toda a Taxonomia. Link de acesso: um item utilitário no cabeçalho
do índice de planos (§2), não uma aba do plano individual.

---

## 7 · Componentes — novos vs. reaproveitados

### Reaproveitados sem alteração
- `Botao`, `BotaoCopiar`, `Selo`, `Estado`, `Giro`, `Esqueleto` (`ui.tsx`)
- `IconeNivel`, `IconeChevron`, `IconeMais` (`icones.tsx`)
- Classes de layout: `.pilha`, `.linha`, `.grade.campos`, `.campo-largo`, `.card`, `.bloco`,
  `.contexto-painel`, `.abas`/`.aba`, `.arvore-lista`/`.arvore-no`/`.arvore-nome`/
  `.arvore-codigo`/`.arvore-nomenclatura` (estas últimas de `ArvoreCampanha`, generalizadas para
  nós editáveis), `.mono`, `.texto-auxiliar`
- Padrão de "campo com rótulo acima + contador/estado abaixo" de `PainelNivel`/`CampoDinamico`

### Novos
| Componente | Onde | Resolve |
| --- | --- | --- |
| `CampoRateio` | árvore da aba Estrutura e verba | C — controle duplo %/R$ |
| `ArvorePlano` | aba Estrutura e verba | generaliza `ArvoreCampanha` para N campanhas e edição |
| `FaixaDeSaldo` | topo da tela do plano + topo da aba Estrutura e verba | B2 — trilha de níveis |
| `SeloDesbalanco` | linhas da árvore e da lista de planos | B3 — sub vs sobre-alocado com forma, não só cor |
| `SeletorEntidadeExistente` | "+ Adicionar campanha/grupo/anúncio existente" | seleção de entidades já cadastradas (combobox APG) |
| `DivergenciaNome` | ao lado de qualquer nome com `nomenclatura_divergente` | D — revelação inline snapshot vs atual |
| `TabelaMetas` | aba Metas | E — grade densa, colunas fixas, rodapé TOTAL |
| `CelulaMeta` | dentro de `TabelaMetas` | E — célula editável/desabilitada com motivo sob foco |
| Ícones novos em `icones.tsx` | `IconeSubalocado`, `IconeSobrealocado` (ou `IconeAlerta` + variante) | B3 — forma distinta, não rotação da mesma forma |
| `.tabela`/`.tabela-cabecalho`/`.tabela-celula`/`.tabela-fixa` (CSS) | `componentes.css` | ver nota abaixo |

**Nota sobre a tabela**: hoje `Dicionario.tsx` e `Historico.tsx` montam `<table>` com **estilo
inline** (`style={{ width: '100%', ... }}`, objetos `CELULA`/`LINK_BOTAO` locais) — isso é dívida
anterior a este desenho e viola a regra de "nada de cor solta fora de `index.css`" que passou a
valer depois. A tabela de Metas *precisa* de células fixas, larguras controladas e um rodapé
sticky — não dá para desenhar isso limpo em cima do padrão inline atual. Recomendo introduzir
classes tokenizadas (`.tabela*`) em `componentes.css` como parte desta implementação, e migrar
`Dicionario`/`Historico` para elas quando convier — não é obrigatório fazer a migração agora, mas
sinalizo para quem implementar não copiar o padrão inline para uma tabela nova.

---

## 8 · Estados — vazio, carregando, erro, desbalanceado, salvo

| Estado | Índice de planos | Árvore (Estrutura e verba) | Metas |
| --- | --- | --- | --- |
| **Vazio** | `Estado tipo="vazio"` + "Novo plano" | Plano sem campanha: "Adicione uma campanha para começar a ratear a verba." + `+ Adicionar campanha` em destaque | Sem anúncio no plano ainda: mesma mensagem, aponta para a outra aba |
| **Carregando** | linhas `Esqueleto forma="texto"` | árvore com `Esqueleto forma="controle"` nos campos de rateio, nós existentes visíveis (não pisca a árvore inteira) | linhas `Esqueleto`, cabeçalho fixo já visível |
| **Erro** | `Estado tipo="erro"` | erro por linha (mesmo padrão `erro?.campo` de `PainelNivel`) — nunca perde o que já estava editável nas outras linhas | erro por célula, mesma disciplina; erro de rede geral vira `.aviso-erro` fixo no topo da aba |
| **Desbalanceado** | badge `SeloDesbalanco` na coluna Diferença | `FaixaDeSaldo` + badge por nó com filhos (§4.2); não bloqueia edição em nenhum nível | reflexo passivo só na `FaixaDeSaldo` do cabeçalho — a aba Metas não tem "filhos" para desbalancear |
| **Salvo** | — (não há edição inline na lista) | "✓ salvo" transitório por campo (§4.3), 1,5s, live region | mesmo padrão por célula |

---

## 9 · O que fica para o usuário decidir

1. **Rótulo do cartão em `#/assunto`**: manter "Mídia" (guarda-chuva) ou trocar para "Plano de
   mídia" (nomeia exatamente o que existe agora). Copy, não arquitetura — mas muda a leitura do
   próximo assunto que entrar ali depois.
2. **Confirmação de exportação com plano desbalanceado** (§4.2): aprovar o gatilho de
   confirmação única no nível do plano, e decidir se vale um limiar de tolerância (ex. ignorar
   diferença abaixo de R$ 1, resíduo esperado de arredondamento em cascata) ou se qualquer valor
   diferente de zero deve confirmar.
3. **Regra de aplicabilidade de métrica por plataforma+formato** (§5.1, E): não é decisão de
   desenho, é levantamento de domínio ainda pendente (já registrado assim em
   `PLANO-DE-MIDIA.md`). A tela nasce sem essa restrição até o levantamento existir.
4. **Backend: endpoint para atualizar snapshot de nome/match_id numa linha do plano** (§4.4, D) —
   não existe hoje; a interface pressupõe que vai existir, mas a forma (rota nova? campo no
   PATCH atual?) é decisão de quem projetar essa API, não deste documento.
5. **Backend: nota de desbalanço no Excel exportado** (§0, item 3) — recomendada pelo domínio,
   ainda não implementada em `exportacao_plano.py`. Ligado ao ponto 2 acima: se a exportação vai
   pedir confirmação na tela, o mesmo número devia aparecer no arquivo, para quem só olha o Excel
   fora da ferramenta ver o mesmo aviso.
6. **Catálogo de métricas acessível ao analista** (§6): recomendo abrir a edição para quem usa o
   produto no dia a dia (mesmo padrão do Dicionário, que já é editável pelo analista) — mas é
   escopo novo e cabe confirmar se entra nesta fase ou fica atrás de alguma barreira futura
   (quando existir autenticação, D-003).
7. **Migração de `Dicionario`/`Historico` para as classes `.tabela*` novas** (§7) — não bloqueia a
   entrega do Plano de Mídia, mas é uma limpeza que faz sentido decidir junto, já que a tabela nova
   nasce tokenizada e as duas antigas não.
