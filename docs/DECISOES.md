# Registro de decisões

Decisões travadas do projeto. Uma vez aqui, não são reabertas sem motivo novo — reabrir decisão de fundação no meio da implementação é a forma mais comum de estourar prazo.

---

## D-001 · Nome do produto: **MediaBuild**
**01/08/2026 · travada**

A spec original chamava o produto de "o nome de trabalho anterior". O nome oficial é **MediaBuild**, sigla **MDBD**.

"o nome de trabalho anterior" fica registrado apenas como nome histórico em [ESPECIFICACAO.md](ESPECIFICACAO.md). Não deve aparecer na UI, no código, no `package.json` ou em qualquer texto voltado ao usuário.

> Resolve a lacuna 10 de [AVALIACAO.md](AVALIACAO.md).

---

## D-002 · Stack: Python/FastAPI + PostgreSQL + React/Vite
**01/08/2026 · travada**

| Camada | Escolha |
| --- | --- |
| Backend | Python 3.12 + FastAPI |
| Validação | Pydantic v2 |
| ORM / Migrations | SQLAlchemy 2 + Alembic |
| Banco | PostgreSQL 16 |
| Excel | `openpyxl` |
| Frontend | React + Vite + TypeScript |
| Formulários | React Hook Form + Zod |
| Infra local | Docker Compose (3 serviços) |

**Por quê:** Pydantic modela as regras de validação da taxonomia quase literalmente; OpenAPI sai de graça no FastAPI; `openpyxl` é o caminho mais maduro para `.xlsx`.

Node/NestJS era alternativa legítima e foi descartada. Não reabrir.

---

## D-003 · Autenticação: **depois** — ✅ resolvida pelo [D-014](#d-014--autenticação-por-sessão-opaca-três-papéis-e-trilha-de-acesso)
**01/08/2026 · adiada · encerrada em 07/08/2026**

Decisão original: não haveria auth no MVP, porque a aplicação era local e single-user.

Consequências práticas, na época:
- A tabela `usuarios` **não** seria criada.
- `taxonomias_geradas.usuario_id` existiria como coluna **nullable**, sem foreign key, reservando o espaço.
- Quando virasse multiusuário: criar `usuarios`, popular a coluna, só então adicionar a FK.

Isso evitou tanto uma migration destrutiva quanto construir login que ninguém usaria.

**Encerramento.** O adiamento cumpriu o papel dele e acabou. O **D-014** implementa a
autenticação. A aposta se pagou: a tabela `usuarios` nasceu com sessão, papel e trilha de
acesso pensados de uma vez, em vez de ter sido improvisada na Fase 1.

O terceiro item acima segue **pendente de propósito**: `taxonomias_geradas.usuario_id`
continua nullable e sem FK. Não é esquecimento — é o D-004/D-009. O histórico de
nomenclatura sobrevive à exclusão de quem o gerou, pelo mesmo motivo que sobrevive à
exclusão da campanha.

> Resolve a lacuna 8 de [AVALIACAO.md](AVALIACAO.md).

---

## D-004 · Taxonomia exportada é **imutável**
**01/08/2026 · travada**

Uma vez que uma nomenclatura é gerada e persistida em `taxonomias_geradas`, ela **nunca** é alterada.

Se o analista editar os campos da entidade depois, o sistema **gera uma nova taxonomia** (novo registro, novo match ID) e mantém a antiga no histórico.

**Por quê:** o nome já pode ter subido no Meta/Google. Se ele mudar retroativamente, o cruzamento com as planilhas de performance descola silenciosamente — que é exatamente o problema que os match IDs existem para resolver.

> Resolve a lacuna 6 de [AVALIACAO.md](AVALIACAO.md). Confirmada explicitamente pelo usuário em 01/08/2026.

---

## D-005 · Termo fora do dicionário é **erro**
**01/08/2026 · travada**

Quando um valor de campo não tem abreviação cadastrada, o sistema **falha** em vez de deixar passar o termo normalizado.

A mensagem de erro precisa ser acionável, dizendo as duas saídas possíveis:
1. cadastrar o termo no dicionário, ou
2. escolher uma das opções já existentes — que o erro **lista**.

**Por quê:** deixar passar geraria `CONVERSAO` onde deveria estar `CV`, silenciosamente. O nome sobe na plataforma, ninguém percebe, e o cruzamento com a planilha de performance quebra. Travar o analista por um minuto é muito mais barato que um nome errado em campanha rodando.

**Exceção:** um token de campo pode declarar `"abreviar": false` no template, para campos livres que legitimamente não têm dicionário (nome de produto, por exemplo). Aí o valor só é normalizado.

---

## D-006 · Match ID sequencial por nível
**01/08/2026 · travada**

Formato `C0001`, `G0001`, `A0001` — prefixo da inicial do nível mais 4 dígitos, gerados por sequences do Postgres (uma por nível).

Sequence garante unicidade sem race condition e mantém o código curto e legível, ao contrário de UUID. Passa de 4 dígitos naturalmente quando estourar 9999 (`C10000`), sem quebrar nada — o campo tem 20 caracteres.

---

## D-007 · Toda plataforma tem os três níveis
**01/08/2026 · travada**

Nenhuma plataforma pode existir sem **template e limite de caracteres para `CAMPANHA`, `GRUPO` e `ANUNCIO`**.

**Por quê:** uma plataforma sem template num nível é inutilizável ali — o motor não tem como montar o nome. E a falha só apareceria no pior momento: quando o analista estivesse tentando gerar.

**Como é garantido:**
- `app/plataformas.py::criar_plataforma()` cria plataforma, 3 limites e 3 templates numa operação só. **A API da Fase 3 deve usar essa função, nunca instanciar `Plataforma` direto.**
- `niveis_faltando()` diagnostica plataformas incompletas.
- O teste `test_toda_plataforma_do_banco_tem_os_tres_niveis` percorre **todas** as plataformas cadastradas, não uma lista fixa — então uma inclusão incompleta quebra a suíte.

Não há constraint no banco porque o Postgres não expressa bem "para cada linha em A, devem existir N linhas em B". A garantia é de código e de teste.

---

## D-008 · A estrutura de campos vem da a planilha de taxonomia de referência
**04/08/2026 · travada**

A planilha de referência (planilha de taxonomia de referência, não incluída neste repositório) é a fonte da estrutura de campos por nível. Ela trouxe duas coisas que o MVP não tinha:

**1. Dois tipos de campo.** A aba "Taxonomia" marca cada coluna como `Drop list` ou `Campo livre N caracteres`. Isso virou atributo do token, em `templates_taxonomia.tokens`:

| Atributo | Significado |
| --- | --- |
| `abreviar: true` (padrão) | Drop list — o valor precisa existir no dicionário (D-005) |
| `abreviar: false` + `max_caracteres` | Campo livre com limite próprio |
| `rotulo` | Nome que o analista lê ("Dimensão do criativo") |
| `opcional: true` | Em branco, o token some do nome em vez de virar erro |
| `categoria` | Vocabulário consultado, quando difere da chave |

Manter isso no token e não numa tabela nova preserva a regra de que **o padrão de nomenclatura é dado, não código** — inclusive os rótulos, que por isso não existem hardcoded no frontend.

`categoria` existe por um caso concreto: `interesse_1` e `interesse_2` são posições diferentes no nome, mas o analista cadastra a lista de interesses **uma vez só**.

**2. A coluna "Plataforma" da planilha é a sigla, não um campo.** O analista já escolhe a plataforma no topo da tela; pedir de novo num dropdown seria digitar duas vezes e abriria espaço para divergência. Vira um token literal com a sigla — e as siglas adotadas são as que a planilha escreveu: `METAA`, `TIKTOK`, `DV360`.

**Acréscimos nossos** (a planilha autorizou "pode colocar mais campos"), todos opcionais para não alongar o nome de quem não usa: `funil` na campanha, `posicionamento` no Meta e `correspondencia` no Google. `interesse_2` e `secundagem` também são opcionais — exigi-los forçaria o analista a inventar um segundo interesse ou uma secundagem para criativo estático.

**Migração:** os templates novos entraram como **versão 2**, sem tocar na v1. As nomenclaturas já geradas continuam explicáveis pelo `template_versao` que guardaram (D-004). `app/seed.py::sincronizar_templates()` refaz isso sozinho sempre que `ESTRUTURA_PADRAO` mudar.

---

## D-009 · O histórico guarda plataforma e campanha denormalizadas
**04/08/2026 · travada**

`taxonomias_geradas` ganhou `plataforma_id` e `campanha_id`, gravadas na geração e **sem foreign key** — como o `entidade_id` já era.

**Por quê:** a tela de histórico filtra por elas o tempo todo. Sem as colunas, cada requisição pagaria três subconsultas polimórficas (uma por nível) e — pior — o filtro pararia de funcionar assim que a entidade fosse apagada. O histórico sobrevive à entidade de propósito (D-004); o filtro sobre ele precisa sobreviver junto.

O backfill das linhas antigas está na migration `a1c4f7e29b03`, subindo a hierarquia anúncio → grupo → campanha → plataforma.

---

## D-010 · Roteamento por hash escrito à mão
**04/08/2026 · travada**

A navegação entre tela inicial, seletor de assunto, app de taxonomia e catálogo de interface usa um roteador por hash próprio (~35 linhas em `src/roteador.ts`), sobre `useSyncExternalStore` + `hashchange`. Nada de `react-router`.

**Por quê:** endereço é estado. `#/admin` sem URL não é uma tela, é um estado escondido — e um catálogo de design system que não pode ser mandado por link perde metade do valor. O botão voltar do navegador passa a funcionar de graça, em vez de obrigar a inventar e manter um gesto de volta em cada tela. O custo é ~35 linhas e **zero dependência de runtime**, então não toca o D-002. `hashchange` é suportado em jsdom, então as rotas ficam testáveis sem browser automation, que este projeto não tem.

`useSyncExternalStore` e não `useState` + `useEffect('hashchange')`: sob StrictMode e render concorrente o segundo padrão gera tearing e lê o hash defasado no primeiro paint. Redirecionamentos (`#/taxonomia` → `#/taxonomia/gerar`) usam `history.replaceState`, nunca `location.hash =`, que empilharia entrada e faria o botão voltar entrar em loop.

**Consequência que não pode ser esquecida:** no ramo da taxonomia o roteador é um **seletor de visibilidade, não um interruptor de montagem**. `AplicativoTaxonomia` entra num condicional que só liga e nunca desliga, e some apenas por `hidden` — desmontar descartaria formulário meio preenchido e seria regressão direta do D-005. As sete invariantes e o teste de regressão estão em `docs/UX-NAVEGACAO.md`.

As três abas viram rotas (`#/taxonomia/gerar|dicionario|historico`) mas continuam `<button role="tab">`, não `<a>`: misturar semântica de link com papel de tab confunde leitor de tela e foge do padrão APG.

---

## D-011 · Campo opcional vazio grava `NA`, não some do nome
**04/08/2026 · travada**

Até aqui, um campo opcional em branco fazia o token **desaparecer** do nome (`motor.py`, o join descartava as partes vazias). Consequência: dois anúncios da mesma plataforma e do mesmo nível saíam com quantidade de campos diferente. Quem abre a planilha de performance e separa o nome pelo `_` para montar um pivô vê as **colunas deslocarem** de linha para linha — `secundagem` cai onde deveria estar `versão`. O nome continuava correto; o relatório é que não fechava.

A partir de agora, todo campo opcional em branco emite um **marcador de ausência**. O nome passa a ter posição fixa: mesma plataforma e mesmo nível ⇒ sempre a mesma quantidade de campos.

### O marcador é `NA`

| Candidato | Por que não |
| --- | --- |
| `NAO` | Significa "não" em português. Num campo binário (`inclui_frete`, `usa_cupom`) ninguém distingue "não preenchi" de "o valor é não". |
| `X` | Já aparece dentro de 8 abreviações de `dimensao` (`1080X1080`) e de `EXT`/`LUXO`. Colisão exata não há, mas quem lê `..._X_...` no meio de `1080X1920` erra. |
| `0` | O Excel converte para número, some o zero à esquerda de campos vizinhos numa colagem, e colide com `secundagem`/`idade`, que são numéricos de verdade. |
| `__` (vazio preservado) | Separador duplo. O "Texto para colunas" do Excel tem a caixa *"Considerar delimitadores consecutivos como um só"*, e várias rotinas de split colapsam por padrão — o problema volta exatamente onde ele dói. E `A__B` parece erro de digitação para quem abre o Gerenciador de Anúncios. |
| `NA` | **Escolhido.** 2 caracteres (o mais barato que não é degenerado), convenção que qualquer analista já lê como "não se aplica", e sem colisão. |

**Ressalva registrada:** em `pandas` e em R, `NA` está na lista padrão de valores nulos ao ler CSV. O texto vira `NaN`, e `groupby()` **descarta** essas linhas por padrão. Semanticamente até faz sentido, mas some com dado sem avisar. Quem for analisar fora do Excel lê com `keep_default_na=False` (ou `dtype=str`), ou agrupa com `dropna=False`. No Excel e no Google Sheets, `NA` digitado numa célula continua sendo o texto `NA` — só a função `=NA()` produz `#N/D`. Como o consumo previsto é planilha, o custo é aceitável.

### Reserva: `NA` não pode ser abreviação de nada

Se um termo real abreviar para `NA`, o nome fica ambíguo e não há como distinguir ausência de valor. E o caso não é hipotético: `Nacional` em `regiao` é a abreviação preguiçosa óbvia.

**A trava é na escrita do dicionário**, em `POST /dicionario` e `PATCH /dicionario/{id}`: `normalizar(abreviacao)` não pode ser igual a nenhum marcador em uso. Erro novo `AbreviacaoReservada(ErroTaxonomia)`, registrado em `erros_http.py` com o código `abreviacao_reservada` → 422, no mesmo formato dos outros. Não é regex nem lista negra genérica: é igualdade exata contra o conjunto `{MARCADOR_AUSENCIA_PADRAO} ∪ {marcadores dos templates ativos}`. Conter `NA` continua permitido (`NOR`, `NOV`, e qualquer `NATAL` futuro) — só ser `NA` é proibido.

**Colisão existente: não há.** Conferido nas 109 abreviações de `app/seed.py` e nas 116 linhas do banco de desenvolvimento — zero contra `NA`, `NAO`, `X`, `0`, `SEM`, `NULL` e `-`. Nada a corrigir. A garantia futura é o teste `test_dicionario_nao_colide_com_marcador_de_ausencia`, que percorre a tabela inteira (mesmo padrão do D-007: a garantia é de código e de teste, não de constraint).

### Custo de caractere: nenhum, no pior caso

O marcador tem 2 caracteres e **nenhum** campo opcional tem abreviação mais curta que isso. Então o pior caso de tamanho do nome **não muda** — antes o pior caso já era o campo preenchido com seu maior valor.

| Plataforma | Nível | Limite (seed) | Pior caso | Folga |
| --- | --- | --- | --- | --- |
| Meta | CAMPANHA / GRUPO / ANUNCIO | 400 | 43 / 52 / 41 | ≥ 348 |
| TikTok | CAMPANHA / GRUPO / ANUNCIO | 512 | 44 / 45 / 41 | ≥ 467 |
| DV360 | CAMPANHA / GRUPO / ANUNCIO | 255 | 43 / 45 / 41 | ≥ 210 |
| Google | CAMPANHA / GRUPO / ANUNCIO | 255 | 44 / 49 / 41 | ≥ 206 |

Nada estoura, e a margem é de ~5x mesmo no nível mais apertado. O que cresce é o nome **mínimo**: +3 caracteres (`_NA`) por opcional vazio — +3 em quase todos os casos, +6 em Meta/GRUPO e Google/GRUPO, que têm dois opcionais.

Os limites do seed seguem sendo valores de partida. Conferido nesta decisão apenas o Google: a documentação oficial da Google Ads API dá **256** para nome de campanha e **256** para nome de grupo de anúncios, então o `255` do seed está certo e conservador. Meta/TikTok/DV360 continuam na lista de pendentes — irrelevante para esta decisão dada a margem, relevante antes de uso real.

### O marcador mora em coluna do template, com a comparação de versão estendida

`templates_taxonomia.marcador_ausencia` (`String(10)`), ao lado de `separador`, que é o vizinho natural — os dois são propriedades de montagem do nome inteiro, não de um campo. O default do produto é `NA`, na constante `MARCADOR_AUSENCIA_PADRAO` em `app/plataformas.py`. O motor o recebe por `Template.marcador_ausencia`, então continua puro: o marcador chega pelo tipo que ele já recebia.

**Esta seção foi reconciliada em 05/08/2026.** A decisão original mandava o marcador para dentro do token, por um motivo correto: `sincronizar_templates()` comparava **só `tokens`**, então marcador em coluna mudaria a saída do motor **sem** trocar de versão, e `template_versao` deixaria de explicar o nome — regressão direta do D-004. A implementação foi por coluna e resolveu a mesma objeção por outro caminho: `sincronizar_templates()` **passou a comparar também o marcador**, e o bump de versão voltou a acontecer sozinho. O seed real produziu +12 versões (4 plataformas × 3 níveis).

A objeção do D-004 continua valendo como invariante, e agora tem um dono explícito: **quem mexer em `sincronizar_templates()` precisa manter o marcador dentro da comparação.** Se um dia ele sair de lá, o marcador vira exatamente o vetor de regressão que a decisão original descrevia.

**Retrocompatibilidade:** a migration `c3f81a6b47d9` adiciona a coluna com default `''` e só depois troca o default para `'NA'`. Vazio = comportamento antigo (o token some), que é o significado correto para os templates que já existiam — sem isso, v1 e v2 lidos do banco passariam a reproduzir o comportamento novo e os nomes antigos ficariam inexplicáveis. Quem promove um template para `NA` é o seed. `''` segue válido como válvula de escape para template que precise economizar caracteres.

O marcador é validado em `Template.__post_init__`: precisa casar com `PADRAO_VALIDO` e **não pode conter o separador** — senão ele mesmo deslocaria as colunas que veio consertar. Falha vira `TemplateInvalido`. `POST /plataformas/{id}/templates/{nivel}` aceita e valida o campo, devolvendo 422 e não 500.

### Histórico

`app/seed.py::sincronizar_templates()` vê o marcador diferente, cria a **versão 3** e desativa a 2. As nomenclaturas já geradas continuam explicáveis pelo `template_versao` que guardaram (D-004), e nenhuma delas é reescrita — nem poderia. `taxonomias_geradas` não é tocada: a migration mexe apenas em `templates_taxonomia`.

**Operacional:** quem der pull precisa de `alembic upgrade head` **seguido de** `python -m app.seed`. Só a migration deixa os templates com marcador vazio, e o comportamento novo não aparece.

O que **não** pode acontecer: regenerar em massa os nomes antigos para "uniformizar". Eles já podem estar rodando em plataforma; reescrever descola o cruzamento com a planilha, que é o problema que os match IDs existem para resolver.

Consequência operacional a comunicar: nomes gerados a partir de agora não são comparáveis por posição com os gerados antes. Quem cruzar histórico atravessando a virada usa o **match ID**, nunca o split por `_` — que é a regra que já valia.

---

## D-012 · Validador de UTM: o app **confere**, não gera
**04/08/2026 · travada**

A aba Gerar ganha um campo onde o analista **cola a URL de destino** e o MediaBuild responde se os parâmetros batem com a taxonomia gerada. Não é montador de UTM: gerar a URL exigiria conhecer regra de landing page, redirecionador e macro de cada plataforma, e o produto gera nomes.

O valor está no laudo, e o item mais caro que ele pega é a URL copiada de outra campanha — o link funciona, o site abre, e o custo é atribuído no lugar errado por semanas.

### Arquitetura

Mesma separação do motor: `app/utm/validador.py` **puro** (`validar_utm(url, contexto) -> ResultadoUtm`, sem SQLAlchemy e sem HTTP) e `app/utm/repositorio.py` montando o contexto. Reaproveita `remover_acentos` de `app/taxonomia/normalizacao.py`.

`POST /utm/validar`, corpo `{"url": str, "taxonomia_id": UUID}`. O servidor resolve o contexto pela linha de `taxonomias_geradas` (nível, `entidade_id`, e `plataforma_id`/`campanha_id`, que o D-009 já denormalizou), sobe a hierarquia anúncio → grupo → campanha para os match IDs e as nomenclaturas disponíveis, e lê `tipo_compra` e `canal` dos `campos` JSONB.

**Resposta é sempre 200**, com `{"valido": bool, "erros": [...], "avisos": [...], "parametros": {...}, "sugestao": {...}, "url_sugerida": str}`. `valido = erros == []`. URL problemática não é requisição malformada: o pedido foi processado e a resposta é o laudo. 422 fica para corpo inválido. Cada item é `{"codigo", "parametro", "mensagem", "encontrado", "esperado"}` — código estável, como no `erros_http.py`.

**Nada é persistido.** Conferir URL não gera taxonomia nem altera a existente (D-004).

Regra que depende de um nível ausente do contexto é **pulada**, nunca reprovada.

### Qual parâmetro casa com o quê

| Parâmetro | Casa com | Severidade |
| --- | --- | --- |
| `utm_id` | match ID da **campanha** (`c0001`) | ausente = aviso · divergente = **erro** |
| `utm_campaign` | precisa **conter** o match ID da campanha | ausente = **erro** · divergente = **erro** · ≠ nomenclatura completa = aviso |
| `utm_source` | vocabulário `utm_source` da plataforma | fora do vocabulário cadastrado = **erro** · sem vocabulário e ≠ sigla = aviso |
| `utm_medium` | vocabulário `utm_medium`, senão o `tipo_compra` do anúncio | idem |
| `utm_content` | match ID do **anúncio** (`a0001`) | ausente = **erro** · divergente = **erro** · ≠ nomenclatura do anúncio = aviso |
| `utm_term` | match ID do **grupo** (`g0001`) | ver abaixo |

**Conter, não ser igual.** O match ID é a chave; o nome é o rótulo. Exigir que `utm_campaign` seja a nomenclatura inteira reprovaria quem encurta o rótulo ou usa uma variante legítima, sem ganhar nada no cruzamento. A igualdade vira **aviso**, com o valor sugerido pronto.

A comparação é **case-insensitive** e o match ID precisa aparecer **delimitado** — `(?<![a-z0-9])c0001(?![a-z0-9])` sobre o valor em minúsculas. Sem a delimitação, `c0001` casaria dentro de `c00010`.

**Nível trocado é erro:** `a0001` em `utm_campaign`, ou `c0001` em `utm_content`, significa que os níveis foram invertidos — o dado de anúncio vai ser somado como campanha.

**`utm_id` importa mais do que parece.** É por ele que o GA4 junta o custo importado com a sessão na importação de dados de custo; sem ele o relatório de ROAS não fecha, mesmo com as outras cinco UTMs perfeitas. Por isso a ausência é aviso ativo, com a sugestão pronta (`utm_id=c0001`), e a divergência é erro.

**`utm_term` é o slot sem consenso.** Em Search ele é a palavra-chave (`{keyword}`), e disputar essa posição quebraria uma convenção que funciona. Regra final: o match ID do grupo precisa aparecer em `utm_term` **ou** em `utm_content`; ausente dos dois = **aviso**; presente com o `g` **errado** = **erro**. Palavra-chave ou macro em `utm_term` passa sem reclamação.

**`utm_source`/`utm_medium` seguem o dicionário.** Duas categorias novas, `utm_source` e `utm_medium` (por plataforma), no `dicionario_abreviacoes` — sem mudança de schema, e nenhum token as consulta, então a geração de nomes não é afetada. Cadastrado o vocabulário, ficar fora dele é **erro**, com a mesma saída dupla do D-005 ("use uma destas ou cadastre a sua"). Sem vocabulário cadastrado, a divergência contra a sigla (ou contra o `tipo_compra`) é só **aviso**: não dá para tratar como autoridade um vocabulário que ninguém registrou. Isso mantém a decisão em dados — o time que usa `paid_social` cadastra `paid_social` e para de ser avisado.

### Erro versus aviso

**Erro** é o que faz o dado chegar errado ou não chegar:

| Código | Quando |
| --- | --- |
| `url_invalida` | não parseia, ou sem domínio |
| `url_sem_esquema` | falta `http://` / `https://` |
| `query_dentro_da_ancora` | o `#` vem **antes** do `?` — a query fica dentro do fragmento, não é enviada, e as UTMs somem (armadilha clássica de SPA) |
| `sem_utm` | nenhum parâmetro `utm_*` |
| `utm_obrigatoria_ausente` | falta `utm_source`, `utm_medium` ou `utm_campaign` |
| `utm_vazia` | parâmetro presente com valor vazio |
| `parametro_duplicado` | o mesmo `utm_*` aparece duas vezes — qual vale é indefinido |
| `utm_desconhecida` | nome a distância de edição ≤ 2 de um dos cinco (`utm_campaing`, `utm_mediun`): é ignorado em silêncio, que é o pior desfecho possível |
| `match_id_ausente` / `match_id_divergente` / `match_id_nivel_trocado` | ver tabela acima |
| `utm_id_divergente` | `utm_id` aponta para outra campanha |
| `utm_source_invalida` / `utm_medium_invalida` | fora do vocabulário cadastrado |
| `espaco_no_valor` | espaço literal em qualquer parâmetro; `%20` em `utm_source/medium/campaign/content` |
| `acento_no_valor` | qualquer caractere não-ASCII |
| `caractere_invalido_no_valor` | ASCII fora de `[A-Za-z0-9._~+-]` (mais `{}`/`%%` de macro) |
| `encoding_invalido` | `%` sem dois dígitos hexadecimais depois |

**Aviso** é o que funciona mas envelhece mal: `utm_id_ausente`, `caixa_mista`, `nomenclatura_divergente`, `grupo_sem_rastreio`, `utm_source_fora_da_convencao`, `utm_medium_fora_da_convencao`, `sem_https`, `encoding_duplo`, `mais_e_espaco`, `macro_na_url`, `parametro_utm_nao_conferido`, `ancora_com_utm`, `utm_campaign_longa`.

Três chamadas de julgamento que valem registrar:

- **Maiúscula é aviso, não erro.** O GA4 diferencia caixa e `Facebook`/`facebook` viram duas linhas — é o problema real que a taxonomia inteira existe para evitar. Mas o motor gera nome **maiúsculo**, e reprovar a própria saída do produto seria absurdo. Resolução: comparação sempre case-insensitive (o match ID nunca falha por caixa), aviso `caixa_mista` quando o valor não é todo minúsculo, e a `sugestao` que o app devolve já vem em minúsculas — seguir a sugestão do próprio app limpa o aviso.
- **Espaço em `utm_term` é aviso**, nos outros quatro é erro. Palavra-chave de Search tem espaço legitimamente.
- **Âncora *depois* da query é aviso, não erro** (`?utm_source=x#secao` funciona) — e só vira aviso se o fragmento contiver `utm_`. É a âncora *antes* da query que é erro. Macro de plataforma (`{lpurl}`, `{{campaign.name}}`, `%%DEST_URL%%`) é aviso: o valor final só existe depois da plataforma resolver, e não há o que conferir aqui.

### Texto das mensagens

Tom do `app/taxonomia/erros.py`: diz o que está errado, e o que fazer.

```
url_sem_esquema      A URL não começa com http:// ou https://. Sem esquema a plataforma pode
                     montar o link errado — escreva a URL completa.
url_invalida         Não consegui ler esta URL. Confira se ela está completa, com domínio e
                     sem espaços.
query_dentro_da_ancora
                     Os parâmetros estão depois do '#', dentro da âncora. O navegador não
                     envia essa parte e as UTMs se perdem. Mova a query para antes do '#'.
sem_utm              A URL não tem nenhum parâmetro utm_. Sem eles não há como cruzar o dado
                     do GA4 com o da plataforma.
utm_obrigatoria_ausente
                     Falta o parâmetro '{p}'. utm_source, utm_medium e utm_campaign são
                     obrigatórios.
utm_vazia            O parâmetro '{p}' está na URL mas sem valor. Preencha ou remova.
parametro_duplicado  O parâmetro '{p}' aparece {n} vezes na URL. Qual valor vale fica
                     indefinido — deixe só um.
utm_desconhecida     '{p}' não é um parâmetro válido; você quis dizer '{sugestao}'? Escrito
                     assim ele é ignorado em silêncio e o dado se perde.
match_id_ausente     O '{p}' não traz o match ID '{esperado}'. Sem ele não dá para juntar
                     est{e|a} {nivel} com a planilha de performance.
match_id_divergente  O '{p}' aponta para '{encontrado}', mas est{e|a} {nivel} é '{esperado}'.
                     Provavelmente a URL foi copiada de outr{o|a} {nivel} — o custo vai ser
                     atribuído no lugar errado.
match_id_nivel_trocado
                     O '{p}' traz '{encontrado}', que é match ID de {nivel_encontrado}. Neste
                     parâmetro entra o de {nivel_esperado} ('{esperado}').
utm_id_ausente       Sem utm_id. É por ele que o GA4 junta o custo importado com a sessão —
                     inclua 'utm_id={c}'.
utm_id_divergente    O utm_id é '{encontrado}' e a campanha é '{esperado}'. O custo importado
                     vai casar com a campanha errada.
utm_source_invalida  '{v}' não está cadastrado em 'utm_source' para {plataforma}. Use uma das
                     opções: {opcoes}. Ou cadastre '{v}' no dicionário.
utm_medium_invalida  '{v}' não está cadastrado em 'utm_medium' para {plataforma}. Use uma das
                     opções: {opcoes}. Ou cadastre '{v}' no dicionário.
utm_source_fora_da_convencao
                     '{v}' não corresponde à plataforma escolhida ({sigla}). Se for
                     proposital, cadastre em 'utm_source' no dicionário para parar de avisar.
utm_medium_fora_da_convencao
                     '{v}' não corresponde ao tipo de compra do anúncio ({tipo_compra}).
                     utm_medium é o que separa CPC de CPM no relatório.
grupo_sem_rastreio   Nem utm_term nem utm_content trazem o match ID do grupo ('{g}'). Você não
                     vai conseguir separar conjunto de anúncios no GA4.
nomenclatura_divergente
                     O '{p}' tem o match ID certo, mas não é a nomenclatura gerada. Esperado:
                     '{esperado}'. Encontrado: '{encontrado}'. O cruzamento funciona; a
                     leitura do relatório fica pior.
caixa_mista          O '{p}' está como '{v}'. O GA4 diferencia maiúscula de minúscula: '{v}' e
                     '{minusculo}' viram duas linhas no relatório. Sugestão: '{minusculo}'.
espaco_no_valor      O '{p}' tem espaço no valor ('{v}'). Espaço quebra o link e vira duas
                     linhas diferentes no relatório. Troque por '-'.
acento_no_valor      O '{p}' tem acento no valor ('{v}'). Use '{sugestao}' — acento em UTM vira
                     codificação diferente em cada ferramenta e o cruzamento não fecha.
caractere_invalido_no_valor
                     O '{p}' tem o caractere '{c}' no valor ('{v}'). Em UTM use só letras,
                     números, '.', '_' e '-'.
encoding_invalido    O '{p}' tem uma sequência de escape inválida ('{trecho}'). A URL não vai
                     ser lida como você espera.
encoding_duplo       O valor de '{p}' parece codificado duas vezes ('{v}'). Confira se a
                     ferramenta que montou o link não escapou o que já estava escapado.
mais_e_espaco        O '+' em '{p}' é lido como espaço pelo GA4. Se a intenção era juntar
                     palavras, use '-'.
sem_https            A URL usa http://. Se o site redirecionar para https, alguns servidores
                     descartam a query e as UTMs somem.
macro_na_url         A URL contém a macro '{m}', que só é resolvida pela plataforma. Não dá
                     para conferir o valor final aqui.
parametro_utm_nao_conferido
                     '{p}' é um parâmetro válido do GA4, mas o MediaBuild não confere o
                     conteúdo dele.
ancora_com_utm       A âncora depois da query contém 'utm_'. Ela não é enviada como parâmetro
                     — confira se não é um link montado errado.
utm_campaign_longa   utm_campaign tem {n} caracteres. Nada quebra, mas relatório com nome
                     desse tamanho é difícil de ler.
```

`{nivel}` sai como *campanha*, *grupo* e *anúncio*. Trocar pelo vocabulário de cada plataforma (*conjunto de anúncios* no Meta, *line item* no DV360) é refinamento posterior — está na lista de pendentes.

---

## D-013 · Plano de mídia: o valor em reais é a fonte da verdade
**06/08/2026 · travada**

O plano seleciona campanhas já existentes, distribui uma verba em cascata (plano → campanha → grupo → anúncio) e guarda metas de métrica por linha. Detalhamento em `docs/PLANO-DE-MIDIA.md` (domínio) e `docs/PLANO-DE-MIDIA-UI.md` (interface).

**A porcentagem nunca é persistida.** O usuário decidiu que a soma dos filhos **pode não fechar** e que nada é redistribuído automaticamente (só sinalizado). Isso elimina a % como fonte da verdade: 33,333% × 3 não devolve a verba inteira, e um total que depende de arredondamento não é um total. O banco guarda `NUMERIC(14,2)` em reais; a % é calculada na leitura a partir do valor do pai, e é aceita na escrita como *forma de entrada* — o PATCH exige exatamente um dos dois campos, nunca os dois.

**Desbalanço é estado válido de rascunho, não erro de validação.** Nenhuma rota rejeita um plano que não fecha. A leitura devolve `soma_*` e `diferenca` por nível, e quem decide o que fazer com isso é a interface.

**Investimento no nível do anúncio é projeção, não configuração.** Não existe orçamento por anúncio em nenhuma das quatro plataformas — anúncios competem pelo orçamento do grupo via leilão. A coluna existe porque a planilha de referência a tem e o planejamento precisa dela; o rótulo é **"Investimento previsto (R$)"** nesse nível, e "Investimento (R$)" nos de cima.

**Métricas vivem em dados**, na tabela-catálogo `metricas` (`codigo`, `rotulo`, `ordem`, `ativo`), com as metas em JSONB por linha. Acrescentar, renomear ou desativar métrica é `UPDATE`, nunca migration — mesmo princípio do `dicionario_abreviacoes`. Código desativado continua legível no histórico. O catálogo é **só leitura na interface** por enquanto; as rotas de escrita existem.

**O snapshot de nomenclatura não se atualiza sozinho.** A linha guarda `nome_interno`, `match_id` e `nomenclatura` capturados na inserção, sem FK para a entidade — o plano sobrevive à remoção dela, mesmo raciocínio do D-009. A leitura sinaliza `nomenclatura_divergente`; atualizar é ação explícita por linha (`sincronizar_nomenclatura: true` no PATCH), nunca em lote e nunca automática: o plano pode já ter sido enviado ao cliente. Só a `nomenclatura` é recopiada — `match_id` é estável por toda a vida da entidade (D-006) e é a chave de junção com as planilhas de performance.

**Tolerância de desbalanço na exportação: 2% relativos** da verba total, não um valor absoluto. Decisão do usuário, com a consequência explícita: 2% de R$ 50.000 são R$ 1.000, ou seja, é folga de planejamento deliberada, não margem de arredondamento. A nota sai **abaixo da linha TOTAL, na mesma aba**, e reporta o topo **e cada nó interno** fora da tolerância — dois ramos com desbalanço de sinal oposto se cancelam na soma do topo enquanto os dois estão quebrados.

**Nenhuma métrica é projetada automaticamente.** O custo unitário negociado (CPM/CPV) é guardado no nível do grupo — onde o orçamento é de fato configurável — mas nada é derivado dele. Metas são digitadas à mão.

---

## D-014 · Autenticação por sessão opaca, três papéis e trilha de acesso
**07/08/2026 · travada**

Resolve o [D-003](#d-003--autenticação-depois--resolvida-pelo-d-014), aberto desde o
primeiro dia do projeto e o único item bloqueante de [NUVEM.md](NUVEM.md).

### Sessão opaca em cookie HttpOnly, não JWT

O cookie `mdbd_sessao` carrega um token aleatório de 32 bytes; o banco guarda apenas o
**SHA-256** dele, em `sessoes.token_hash`. Dump vazado não vira sessão viva.

**O requisito que decidiu foi a revogação.** O admin precisa poder excluir um acesso e
derrubar a sessão *agora*. JWT não revoga: ele vale porque a assinatura confere, e
continuaria valendo até expirar — "excluí o usuário mas ele segue dentro por mais 8 horas"
é precisamente o desfecho que a tela de acessos não pode admitir. Fazer JWT revogar exige
uma lista de revogados consultada a cada requisição, que é uma tabela de sessões com
passos a mais e nenhuma vantagem.

O preço é uma consulta por requisição autenticada. Num sistema local, com um índice único
sobre `token_hash`, é irrelevante — e é o tipo de custo que se paga de bom grado por
poder desligar alguém.

O `token_hash` usa SHA-256 e **não** um KDF caro: diferente de senha, o token já tem 256
bits de entropia, então não há dicionário a tentar. E ele é calculado em toda requisição
autenticada — scrypt ali custaria 16 MB por request sem comprar segurança nenhuma.

### `hashlib.scrypt` da stdlib, sem dependência nova

Nada de passlib, bcrypt, argon2 ou python-jose. A stack é travada (D-002) e o scrypt está
na biblioteca padrão desde o Python 3.6, com custo de **memória** configurável — que é
justamente a propriedade que derruba ataque em GPU. Parâmetros: `n=2**14`, `r=8`, `p=1`,
`dklen=64`, ~16 MB e ~47 ms por verificação. Salt de 16 bytes por usuário, de
`secrets.token_bytes`: sem ele, duas pessoas com a mesma senha teriam o mesmo hash, e
quebrar um quebraria todos.

Uma dependência nova aqui traria superfície de supply chain para resolver um problema que
a stdlib já resolve. Se um dia os parâmetros subirem, o caminho é gravá-los junto do hash
— trocar o número no código invalidaria todas as senhas em silêncio.

### Identidade é **login**, não e-mail

`usuarios.login`, `^[A-Za-z0-9._-]{3,60}$`, normalizado para minúsculas na escrita. O
produto não envia e-mail e não tem recuperação de senha por link, então uma coluna de
e-mail seria um campo que ninguém preenche e ninguém usa. Arroba fica fora do padrão de
propósito: aceitá-la induziria a tratar o campo como endereço.

Redefinição de senha é ato do admin: `POST /usuarios/{id}/senha` gera uma **senha
provisória** exibida uma única vez e nunca mais recuperável — o banco guarda só o hash. O
alfabeto exclui os caracteres que se confundem ao serem transcritos à mão (`0/O`, `1/l/I`,
`5/S`, `2/Z`), porque essa senha *vai* ser copiada da tela para outro lugar pelo menos uma
vez.

### Três papéis

| Papel | Alcance |
| --- | --- |
| `basico` | Lê plataformas/hierarquia/métricas, gera taxonomia, vê histórico, usa planos. **Nenhuma** rota de `/dicionario` — nem GET — e **nenhum DELETE em lugar nenhum**. |
| `pleno` | O produto inteiro, incluindo dicionário e remoções. Sem `/usuarios` e sem `/admin/*`. |
| `admin` | Tudo, mais administração de usuários e observabilidade. |

O dicionário some inteiro para o `basico`, inclusive na leitura, porque a aba inteira
desaparece para ele — e uma aba que abre vazia por 403 é pior que uma que não existe. Ele
é quem opera sem poder alterar o vocabulário que sustenta a nomenclatura (D-005).

**A proibição de DELETE é por método HTTP, não por rota.** É o que faz a próxima rota de
remoção que alguém escrever já nascer fora do alcance do `basico`, sem depender de
ninguém lembrar. A autorização é pendurada no `include_router` em `app/main.py`, pelo
mesmo motivo: rota nova dentro de um router protegido nasce protegida.

A escada de papéis tem ordem explícita (`Papel.poder`). Sem ela, "rebaixou?" seria
`papel != ADMIN`, e promover de `basico` para `pleno` satisfaria a condição — derrubando
a sessão de quem *ganhou* acesso. O bug existiu e foi pego por teste.

`/health`, `/health/ready`, `/docs` e `/openapi.json` seguem abertos. Liveness precisa
responder ao orquestrador, que não tem cookie.

### Os dois 401 são distintos, e a falha de login não é

Todo 401/403 sai pelo `erros_http.py`, no mesmo formato do resto do projeto
(`{"erro", "mensagem"}`), com código estável:

| Código | Status | Quando |
| --- | --- | --- |
| `nao_autenticado` | 401 | Não há sessão — sem cookie, ou cookie que não corresponde a nada |
| `sessao_expirada` | 401 | Havia sessão; venceu ou foi revogada |
| `credenciais_invalidas` | 401 | Login inexistente **ou** senha errada |
| `conta_desativada` | 401 | Senha correta, `ativo=false` |
| `permissao_insuficiente` | 403 | Autenticado, sem autorização |

**`sessao_expirada` precisa ser distinguível de `nao_autenticado`** porque a tela reage
diferente: a primeira abre um diálogo por cima do formulário preenchido, a segunda manda
para o login. Sem códigos separados, um dos dois comportamentos é impossível de
implementar — e descartar o formulário de quem estava trabalhando é regressão direta do
mesmo raciocínio do D-010.

**Login inexistente e senha errada devolvem resposta idêntica** — mesmo status, mesmo
código, mesma mensagem. Qualquer diferença entrega de graça a lista de quem tem conta. A
versão sutil do vazamento também é tratada: quando o login não existe, o servidor confere
a senha contra um hash descartável, para gastar o mesmo tempo de scrypt. Sem isso, a
latência (~47 ms contra ~0) enumeraria a base mesmo com a mensagem idêntica.

**Conta desativada é a exceção deliberada.** Ela só é alcançável *depois* de a senha
conferir — quem chega lá já provou saber a senha e não está descobrindo nada. Em troca, o
usuário legítimo descobre que o problema é a conta e não os dedos, em vez de repetir a
mesma senha até abrir chamado.

> **A ordem desse bloco é regra de segurança, não estilo.** Conferir `ativo` **antes** da
> senha transformaria `conta_desativada` num oráculo de enumeração: bastaria mandar
> qualquer senha e olhar se a resposta muda. Há teste dedicado a essa regressão.

### `eventos_acesso` não tem foreign key para `usuarios`

Mesmo raciocínio de `taxonomias_geradas.entidade_id` (D-004) e das colunas denormalizadas
do D-009: **a trilha de quem entrou onde sobrevive à exclusão da conta**. Com FK CASCADE,
apagar o usuário apagaria o rastro dele junto — que é o oposto do que uma trilha de acesso
serve, e a forma mais fácil que existe de sumir com o próprio histórico. `login_tentado`
fica preenchido mesmo quando o login não existe, então a linha nunca fica anônima.

`sessoes.usuario_id`, ao contrário, **tem** FK com `ON DELETE CASCADE`, e a assimetria é
intencional: sessão não é histórico, é credencial viva. Excluir o usuário precisa derrubá-la
no mesmo instante.

Toda mudança que **reduz** o poder de alguém — senha nova, desativação, rebaixamento —
revoga as sessões vivas dele na hora. Promover não revoga: ganhar poder não invalida o que
a pessoa já podia fazer.

### `eventos_erro`: uma linha por resposta ≥ 400

Gravada pelo middleware de `app/logs.py`, reaproveitando o `request_id` que já sai no
cabeçalho `X-Request-ID` — a linha da tela de monitoramento e a linha do log são o mesmo
evento visto de dois lugares. Guarda também o `codigo_erro` estável: sem ele a tela só
saberia contar 422; com ele, dá para responder *quais termos estão faltando no dicionário*
sem abrir o log.

Duas regras duras:

1. **Falhar ao gravar o evento nunca derruba a requisição do usuário.** Tudo em
   `try/except`, e o problema vira uma linha de log. O inverso transformaria a
   observabilidade em ponto único de falha do produto inteiro.
2. **A gravação usa sessão própria**, nunca a da requisição — que pode estar em estado de
   rollback *por causa* do erro que se está tentando registrar. Reaproveitá-la perderia o
   registro justamente nos casos mais interessantes.

Os agregados de `/admin/resumo` são calculados **em SQL**. Contar em Python funciona hoje,
com a tabela vazia, e vira timeout silencioso quando `eventos_erro` — a que mais cresce no
sistema — passar de algumas centenas de milhares de linhas. Que é exatamente quando alguém
abre a tela para entender o que está acontecendo. O agrupamento por dia usa o fuso da
aplicação, não UTC, pelo mesmo motivo do `app/tempo.py`.

### O que ficou de fora, e por quê

- **Rate limiting no login.** Não há. Localmente não muda nada; **antes de expor na
  internet é obrigatório**, e está registrado em [NUVEM.md](NUVEM.md).
- **Forçar troca da senha provisória no primeiro acesso.** Precisa de coluna nova e de
  fluxo de tela; não foi pedido.
- **`taxonomias_geradas.usuario_id` continua sem FK.** Ver o encerramento do D-003.

### Operacional

Quem der pull precisa de `alembic upgrade head` **seguido de** `python -m app.seed`, que
cria o primeiro admin a partir de `ADMIN_LOGIN_INICIAL` / `ADMIN_SENHA_INICIAL`. O seed
**nunca** sobrescreve a senha de um usuário existente — mesmo princípio do dicionário, que
não desfaz o ajuste do analista, mas aqui o motivo é mais forte: rodar o seed é operação
corriqueira, e se ele redefinisse a senha, qualquer `python -m app.seed` devolveria o
acesso a quem conhecesse o valor antigo da variável de ambiente.

A senha real nunca é versionada: mora no `.env`, que o `.gitignore` cobre. O
`.env.example` traz um placeholder, e com `DEBUG=false` esse placeholder **derruba o boot**,
igual já acontece com a senha de exemplo do banco.

---

## Pendentes

| Tema | Quando decidir |
| --- | --- |
| Conferir os limites de caracteres reais de Meta, TikTok e DV360 (o seed usa valores plausíveis não verificados). **Google conferido em 04/08/2026**: a Google Ads API dá 256 para nome de campanha e 256 para grupo de anúncios, então o `255` do seed está correto e conservador | antes de uso real |
| Vocabulário inicial de `utm_source` e `utm_medium` por plataforma, para o D-012 poder tratar divergência como erro em vez de aviso | ao implementar o validador de UTM |
| Mensagens do validador de UTM usarem o vocabulário de cada plataforma (*conjunto de anúncios*, *line item*) em vez de grupo/anúncio | pós-MVP, junto do refino visual |
| Objetivo e mês estavam **em branco** na planilha; o seed usa listas plausíveis (`Conversão → CV`, `Agosto → AGO`) | confirmar com o cliente |
| Refinar a modelagem da taxonomia e o visual | pós-MVP, a pedido do usuário |
| Quais métricas não se aplicam a cada combinação plataforma+formato (D-013). Não existe em schema nenhum; a aba Metas nasce com todas as células editáveis | levantamento de domínio, antes de uso real |
| Status do plano de mídia (rascunho / aprovado / fechado). Não pedido, mas comum no artefato | quando o plano começar a circular fora da ferramenta |
| Aviso de coerência entre CPM negociado e metas digitadas ("com este CPM, esta verba daria ~X impressões, você digitou Y"). Puro display, nada persistido — o oposto da projeção automática que foi descartada | pós-entrega da tela |
| Migrar `Dicionario.tsx` e `Historico.tsx` para as classes `.tabela*` tokenizadas que nasceram com o plano de mídia. As duas usam estilo inline | limpeza, sem urgência |
| Rótulo da página interna, reaparecimento da splash e descoberta do catálogo (detalhe em `docs/UX-NAVEGACAO.md`) | antes de implementar a tela inicial |
