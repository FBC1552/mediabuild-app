# Plano de Mídia — especificação das colunas de métrica

Fechamento de escopo para a tela de Plano de Mídia, a partir de uma planilha de plano de mídia de referência (planilha de referência, raiz do repositório) e do pedido do usuário de acrescentar quartis de vídeo.

**O que a planilha de referência já mostrou:** uma linha por anúncio, com as três taxonomias lado a lado (Campanha, Grupo de Anúncios, Anúncio — cada uma já terminando no match ID: `..._C3291`, `..._G1531`, `..._A0975`), seguidas de `Investimento (R$)` e seis métricas (Impressões, Cliques, Conversões, Curtidas, Seguidores, Compartilhamentos), com uma linha `TOTAL` no pé somando cada coluna numérica. Esta especificação assume essa granularidade — **uma linha por anúncio** — e não introduz agregação por campanha ou grupo; se o produto precisar disso, é uma tela derivada (pivô sobre estas linhas), não uma mudança na estrutura da tabela.

Este documento não propõe schema, migration nem componente de UI. É a definição do domínio para quem for desenhar essas duas coisas.

---

## 1. Lista canônica de métricas

| Ordem | Código | Rótulo (UI e Excel) | Unidade | Observação |
| --- | --- | --- | --- | --- |
| 1 | `investimento` | Investimento (R$) | moeda | ver §4 sobre o nível ANÚNCIO |
| 2 | `impressoes` | Impressões | inteiro | |
| 3 | `cliques` | Cliques | inteiro | |
| 4 | `video_inicio` | Vídeo — início | inteiro | ver §2 |
| 5 | `video_25` | Vídeo — 25% | inteiro | ver §2 |
| 6 | `video_50` | Vídeo — 50% | inteiro | ver §2 |
| 7 | `video_75` | Vídeo — 75% | inteiro | ver §2 |
| 8 | `video_completo` | Vídeo — final (100%) | inteiro | ver §2 |
| 9 | `conversoes` | Conversões | inteiro | |
| 10 | `curtidas` | Curtidas | inteiro | |
| 11 | `seguidores` | Seguidores | inteiro | |
| 12 | `compartilhamentos` | Compartilhamentos | inteiro | |

**Onde os quartis entram:** logo depois de Cliques e antes de Conversões, não junto das métricas sociais. Justificativa operacional: quartil de vídeo é sinal de **atenção/exposição** — mesma família de Impressões e Cliques, meio do funil — enquanto Curtidas/Seguidores/Compartilhamentos são **engajamento social**, uma família diferente que o cliente já tinha isolado no fim da tabela. Misturar os dois blocos obrigaria o analista a pular colunas para ler qualquer um dos dois de forma coerente.

**Todas as métricas são contagem, não taxa.** `video_25` é "quantas vezes o vídeo foi visto até 25%", não "25% de quê". Isso é proposital: mantém a mesma unidade de todas as outras colunas (Impressões, Cliques também são contagens), evita decidir um denominador ambíguo por linha, e permite que a linha `TOTAL` some a coluna sem precisar virar média ponderada. **Taxa de conclusão de vídeo é uma coluna calculada de relatório (`video_completo / video_inicio`), não uma coluna do plano** — se algum dia entrar na tela, entra como derivado, exibido, nunca persistido; guardar as duas coisas duplicaria dado e criaria uma segunda fonte de verdade para o mesmo número.

Nenhuma coluna de percentual entra na lista. Não há candidato onde uma taxa precise ser digitada — CPM/CPV negociado, se entrar (§5), é moeda por mil/por view, não percentual.

---

## 2. Semântica dos quartis — explícita, com divergência por plataforma

A pergunta do enunciado é a certa: "visualizações iniciais" e "final" não são termos neutros. Cada plataforma tem uma métrica nativa diferente que parece a definição óbvia e não é.

### `video_inicio` — **não** é o "Views"/"TrueView views" que a plataforma exibe como headline

| Plataforma | Métrica nativa mais próxima | Por que não é "Views" |
| --- | --- | --- |
| Meta | `video_play_actions` (vídeo começou a tocar, exclui replay) | O "Views" que aparece na UI do Meta costuma ser `video_3_sec_watched` (3 segundos) — já é um filtro, não o início puro |
| Google/YouTube | Player start (base do `VideoQuartileP0Rate`, "impressões que iniciaram o player") | "Views"/"TrueView views" (renomeado para isso em 2025) é uma **view paga**: 30s assistidos ou o vídeo inteiro, o que vier primeiro — é quase o quartil 100% de vídeos curtos, não o início |
| DV360 | "Starts" | Consistente com o início — este é o caso mais direto |
| TikTok | `video_watched_2s` ou o "Views" padrão (que já conta a partir de qualquer exibição) | TikTok tende a contar "view" com um limiar mínimo mais baixo, mas ainda é um limiar, não zero |

**Definição adotada pelo produto:** `video_inicio` = a contagem de **início de reprodução (0%)**, o equivalente a `video_play_actions` (Meta) / "Starts" (DV360) / player start (Google) / `video_watched_2s` como melhor proxy disponível no TikTok. **Nunca** o "Views"/"TrueView views" que a plataforma expõe como métrica de destaque — esse número já embute uma definição de "view válida" que difere por plataforma e por duração de vídeo, e se o analista copiar o "Views" da UI para este campo, o número não vai bater com o quartil 25% de baixo dele em nenhum relatório futuro.

### `video_completo` — **não** é ThruPlay/view paga, é o quartil 100%

Meta tem uma segunda métrica de "conclusão" (`video_p100_watched_actions`, contagem de chegou a 100%) que é diferente de ThruPlay (visualização completa **ou** 15 segundos, o que vier primeiro — métrica de otimização de objetivo, não de quartil). `video_completo` neste produto é sempre o quartil 100%, nunca ThruPlay.

| Plataforma | Métrica nativa |
| --- | --- |
| Meta | `video_p100_watched_actions` |
| Google/YouTube | Quartil 100% ("Video played to: 100%") |
| DV360 | "Completions" |
| TikTok | `video_views_p100` |

### Quartis 25/50/75 — a definição em si é razoavelmente consistente; a **base de cálculo** não é

"Chegou a 25% do vídeo" quer dizer a mesma coisa nas quatro plataformas. O que diverge é o denominador que cada uma usa para expressar isso como **taxa**: Google normaliza pela contagem de quem **iniciou o player** ("viewers who initiated the player", não pelas impressões); Meta e DV360 reportam a contagem bruta. Como este produto guarda **contagem, não taxa** (decisão do §1), essa divergência de denominador não contamina o dado armazenado — ela só importa se, no futuro, o produto calcular uma taxa de conclusão e comparar entre plataformas. Registre a ressalva ali quando esse dia chegar: taxa de Google e taxa de Meta/DV360 no mesmo relatório não são a mesma grandeza sem normalizar o denominador.

### O que a interface deve fazer com a divergência

Não pedir para o analista escolher a definição por plataforma — isso reabriria a ambiguidade que a padronização existe para fechar. A interface adota **uma** definição fixa por campo (a da tabela acima), documentada num texto de ajuda ao lado do campo ("início de reprodução, equivalente a Starts/Video Plays — não é o \"Views\" de destaque da plataforma"), e não tenta imitar a métrica de mais alto nível de cada UI de anúncios. Isso é a mesma lógica do dicionário de abreviações (D-005): o vocabulário do produto é fixo e estável, mesmo quando a plataforma renomeia ou reagrupa a métrica dela.

**Fontes:** [Meta — Video Plays](https://www.facebook.com/business/help/592054664510127), [Meta — Video Plays at 25%](https://www.facebook.com/business/help/279891745529019), [Google Ads — About YouTube ads and view metrics](https://support.google.com/google-ads/answer/2375431?hl=en), [Google Ads Help — discrepância entre `video_quartile_*_rate` e a UI](https://groups.google.com/g/adwords-api/c/CR2RAUoPxbY), [DV360 — Report on video campaigns](https://support.google.com/displayvideo/answer/3521206?hl=en), [TikTok Ads — Video play metrics](https://ads.tiktok.com/help/article/video-play?lang=en).

---

## 3. Métricas que não fazem sentido em toda combinação de plataforma/formato

Casos reais, do enunciado e além:
- Seguidores em DV360 (display/vídeo programático não tem página social associada)
- Quartil de vídeo numa linha de banner estático (formato `BNR` já aparece na planilha de referência ao lado de `VID`)
- Conversões numa campanha de objetivo Alcance/Reconhecimento
- Curtidas/Compartilhamentos fora de Meta/TikTok (Google Search e DV360 não têm)

**Recomendação: colunas sempre visíveis; célula desabilitada (cinza, com tooltip) quando a combinação plataforma+formato não suporta a métrica; em branco = não se aplica, `0` = aplica-se e o resultado foi zero.**

Por quê, e não as outras duas opções:

- **Esconder coluna por linha** quebra a tabela — cada linha é um anúncio, potencialmente de plataforma e formato diferentes (a própria planilha de referência mistura `BNR` e `VID` nas linhas 5-7). Uma tabela com colunas que aparecem e somem linha a linha não é lida, é decifrada. E colunas mudando de posição é exatamente o problema que o D-011 já resolveu do lado da taxonomia (posição fixa, marcador de ausência) — a tela de plano herda a mesma lógica de estabilidade posicional, agora sobre dado numérico em vez de nome.
- **Deixar tudo sempre editável sem sinalização** deixa a porta aberta para o erro mais caro: alguém preenche Curtidas numa linha de Google Search porque a célula estava lá, disponível, e ninguém questiona. O plano vira uma planilha livre de novo — exatamente o que a taxonomia inteira existe para evitar do lado do nome.
- **Desabilitar com explicação** é o meio-termo que preserva a leitura tabular (mesma largura de linha, export Excel com colunas fixas, comparável entre plataformas de uma olhada) e ainda impede a entrada de dado sem sentido, sem fazer a tela desaparecer sob os pés de quem está preenchendo.

A distinção branco/zero importa porque são fatos diferentes: "não medi/não se aplica" e "medi e deu zero" (uma campanha nova sem verba liberada ainda tem impressões = 0 e é uma linha legítima; uma linha de banner estático tem `video_inicio` = não aplicável, nunca zero). A coluna numérica no banco deve ser **nullable**, e a linha `TOTAL` soma ignorando nulos — a mesma regra que uma planilha do Excel já aplica com `SOMA()`.

---

## 4. Revisão crítica do rateio em cascata

A decisão de não redistribuir automaticamente e apenas avisar a diferença está travada e não é questionada aqui. O que muda com a operação real:

### Onde isso morde

- **O aviso em percentual esconde o tamanho real do problema.** "97,3% alocado" soa quase fechado; em um plano de R$ 500.000 isso são R$ 13.500 sem campanha, grupo ou anúncio dono — dinheiro que ninguém vai saber que existe até o financeiro perguntar por que o total gasto não bate com o total aprovado.
- **Arredondamento composto em três níveis.** 33%/33%/34% numa campanha, repetido dentro de cada grupo, repetido dentro de cada anúncio — o desvio de cada nível é pequeno isoladamente e não seria motivo de alarme sozinho, mas três níveis de arredondamento na mesma direção (sempre para baixo, por exemplo) somam um desvio real no fundo da árvore.
- **Edição parcial em plano vivo.** O analista ajusta o percentual de uma campanha depois que os grupos abaixo dela já estavam com sua própria soma fechada em 100% — a soma de baixo continua "fechada" localmente, mas relativa a uma base que mudou. O aviso de 100% no nível do grupo não capta isso; só o aviso do nível da campanha captaria, e só se o analista voltar lá para conferir.
- **Múltiplos editores em ramos diferentes da árvore.** Cenário realista de agência: uma pessoa monta os grupos da campanha A, outra monta os da campanha B, cada uma fecha 100% no próprio pedaço. Ninguém necessariamente abre a visão do plano inteiro para ver se o topo fecha — o desbalanço se torna um problema de coordenação, não só de aritmética.

### O que a interface precisa mostrar para isso ser útil

1. **Mostrar o delta em R$, não só em %.** "Faltam 2,7% (R$ 13.500) não alocados" é acionável; "soma: 97,3%" obriga o analista a fazer a conta de cabeça toda vez.
2. **Mostrar o delta de todos os níveis acima simultaneamente, não só o que está sendo editado.** Editar a distribuição de um grupo deveria deixar visível, sem navegar, se a campanha acima e o plano no topo continuam fechando — um resumo fixo (breadcrumb ou barra lateral) com o delta de cada nível da hierarquia atual.
3. **Distinguir sub-alocado de sobre-alocado visualmente, com pesos diferentes.** Sub-alocado (< 100%) é verba disponível não distribuída — inconveniente. Sobre-alocado (> 100%) é comprometimento além do aprovado — mais grave, porque nesse caso alguém já está prometendo mais mídia do que a verba cobre. Sobre-alocação merece o estado visual mais forte (vermelho vs âmbar).
4. **Levar o aviso para o Excel exportado.** Quem lê o plano fora do app (cliente, financeiro) não vê o aviso da tela. Uma linha ou nota no export ("Total alocado: R$ 486.500 de R$ 500.000 — R$ 13.500 sem campanha/grupo/anúncio definido") transporta o mesmo sinal para fora da ferramenta, do mesmo jeito que a linha `TOTAL` da planilha de referência já soma as colunas.

Bloquear a exportação em caso de desbalanço grande seria mudar a decisão já travada de não redistribuir/não impedir — não estou propondo isso. Sinalizo como ponto que o usuário pode querer decidir separadamente: se um desbalanço acima de algum limiar deveria pelo menos exigir confirmação explícita antes de exportar, em vez de só aparecer como aviso passivo na tela.

### Investimento no nível do ANÚNCIO — realista ou ficção de planilha

**Parcialmente ficção, e a tela deveria dizer isso na própria etiqueta do campo.**

Como a compra funciona de fato:
- No **grupo** (Conjunto de anúncios no Meta, Grupo de anúncios no Google/TikTok, Line Item no DV360), o orçamento **é** um valor real configurável na plataforma (ABO no Meta, orçamento de line item no DV360) — a coluna de investimento aqui corresponde a algo que existe de verdade do outro lado.
- Na **campanha**, também pode ser real quando a otimização de orçamento está no nível da campanha (CBO no Meta) — a plataforma decide sozinha como distribuir entre os grupos abaixo, então o valor por campanha é real, mas a distribuição interna que o analista digitar por grupo pode não ser a que o algoritmo de fato executa.
- No **anúncio**, não existe orçamento configurável nas plataformas de mídia — os anúncios dentro de um grupo competem pelo orçamento do grupo via leilão/otimização de entrega, não por uma fatia fixa que alguém reservou. O que a planilha de referência chama de "Investimento" na linha do anúncio é uma **meta de planejamento/proposta**, não um dial que existe em nenhuma plataforma.

**Onde isso ainda tem valor real**, apesar de não ser configurável:
1. **Planejamento pré-veiculação** — dividir a verba do grupo entre conceitos criativos ajuda a vender o plano ao cliente e a prever performance esperada por variante, antes de a campanha existir.
2. **Comparação planejado vs. realizado, depois que a campanha já rodou** — as plataformas de fato reportam gasto por anúncio individual no relatório de performance (é dado real, só não é configurável antes). O `match_id` do anúncio é exatamente a chave que permite comparar a linha do plano (meta) contra a linha do relatório exportado (real) sem depender de nome — o caso de uso central do produto.

**Recomendação de rótulo:** trocar "Investimento" por **"Investimento previsto (R$)"** no nível do anúncio (e considerar o mesmo na campanha, quando ela não estiver com CBO), para não deixar um analista júnior ou um cliente lendo o export pensar que aquele número é um orçamento configurado na plataforma. Isso é mudança de copy, sinalizo para o usuário aprovar — não é decisão técnica minha.

---

## 5. Colunas que faltam — as que eu defenderia, e só essas

O produto gera nomes, não compra mídia. As três abaixo passam no teste "alguém vai filtrar/agrupar por isso no reporting" sem abrir espaço para o app virar ferramenta de compra:

1. **Período do flight (data início / data fim), no nível da campanha.** A campanha já carrega `mes` no nome (`JUL`), e o próprio D-008/DECISOES.md já registra a limitação de mês sem ano ficar ambíguo depois de 12 meses. Duas datas resolvem isso sem tocar o token de nome (que fica como está — o nome não muda), dão ao plano uma visão de calendário/Gantt básica, e são o campo mais óbvio que falta num "plano de mídia" que hoje não tem nenhuma noção de tempo além de um mês abreviado dentro do nome.

2. **KPI primário, no nível da campanha.** Drop list pequena (CPA, CPC, CPM, CPV, CTR, Taxa de engajamento, Alcance) declarando qual das doze métricas da tabela é a que importa para aquela campanha especificamente. Sem isso, quem revisa o plano tem que adivinhar se uma campanha de Reconhecimento deveria ser lida pela coluna Impressões ou pela coluna Cliques. É exatamente o campo que um gestor escaneia primeiro — passa no teste do princípio 5.

3. **Custo unitário negociado (CPM/CPV, conforme `tipo_compra`), no nível do grupo.** O campo `tipo_compra` já existe na taxonomia do anúncio (CPM/CPC/CPV/CPA/oCPM) — falta o valor numérico contratado. Com ele, o plano permite uma conferência simples e real (`investimento_previsto / impressoes_previstas * 1000` vs. o CPM negociado) sem esperar o relatório de performance voltar. Diferente de investimento — que é meta de gasto —, isto é o preço unitário acordado, informação que hoje não existe em lugar nenhum da planilha.

**O que eu não defenderia**, para deixar explícito o limite: praça/mercado (já coberto por `regiao`/`cidade` no nível de grupo — proposta redundante), viewability, brand lift, taxa de veiculação/ad-serving fee, e qualquer coisa que dependa de configuração real na plataforma (CBO ligado/desligado, lances automáticos) — isso é operação de compra, fora do escopo declarado do produto.

---

## Pontos que precisam de decisão do usuário, não minha

- **Confirmar o mapeamento exato de `video_inicio`/`video_completo` para a métrica nativa de cada plataforma** (tabela do §2) contra os exports reais que a operação do cliente usa hoje — a definição que proponho é defensável, mas "o que bate com o relatório do cliente" é fato de campo, não de doutrina.
- **Unidade dos quartis: contagem (proposto) vs. taxa.** Recomendo contagem por consistência com as demais métricas e por evitar denominador ambíguo por linha; se o cliente reporta taxas diretamente (comum em export de vídeo), vale confirmar antes de fechar o schema.
- **Tratamento de célula desabilitada por combinação plataforma+formato (§3)** — a lista de quais combinações desabilitam quais métricas é uma tabela de regras que precisa ser levantada com o cliente real (que plataformas/formatos ele de fato usa), não inventada aqui.
- **Rótulo "Investimento previsto" no nível do anúncio (e possivelmente campanha)** — é mudança de copy que muda a leitura que um cliente faz do plano; peço aprovação antes de qualquer implementação a levar isso para código.
- **As três colunas novas do §5** (flight, KPI primário, custo unitário negociado) são candidatas que eu defenderia; ainda são escopo novo e cabe ao usuário decidir se entram nesta fase ou ficam para depois.
- **Limiar de desbalanço que mereça confirmação explícita antes de exportar** (mencionado no fim do §4) — não é uma mudança na decisão já travada de não redistribuir; é uma pergunta em aberto sobre se vale um segundo nível de fricção além do aviso passivo.
