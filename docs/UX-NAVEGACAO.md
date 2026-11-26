# Navegação, sessão, papéis e distribuição de tela

Especificação de UX/AI. Duas camadas:

- **Parte I** — navegação, splash, seletor de assunto e catálogo. Escrita em 04/08/2026, **implementada** (com um desvio: o catálogo muda de endereço, ver §3).
- **Parte II** — voltar, área administrativa, papéis, login, busca no Dicionário e distribuição de tela. Escrita em 06/08/2026, **não implementada**. É o que um agente de frontend executa a seguir.

Nada da Parte II depende de biblioteca nova. Depende de **backend que ainda não existe** (autenticação — D-003 nunca foi decidido); o §10 lista o contrato mínimo.

---

# Parte II — o que falta desenhar

## 1 · Mapa de rotas × papel

Três papéis: `basico` (gera nomes), `pleno` (tudo do produto), `admin` (+ administração).

| Rota | Tela | Deslogado | `basico` | `pleno` | `admin` |
| --- | --- | --- | --- | --- | --- |
| `#/entrar` | Entrar | ✅ | → destino | → destino | → destino |
| `#/` | Splash | → `#/entrar` | ✅ | ✅ | ✅ |
| `#/assunto` | Escolher assunto | → `#/entrar` | ✅ | ✅ | ✅ |
| `#/guia` | Guia de uso | → `#/entrar` | ✅ | ✅ | ✅ |
| `#/cadastro` | Cadastro | → `#/entrar` | ✅ | ✅ | ✅ |
| `#/taxonomia/gerar` | Gerar | → `#/entrar` | ✅ | ✅ | ✅ |
| `#/taxonomia/dicionario` | Dicionário | → `#/entrar` | 🚫 painel negado | ✅ | ✅ |
| `#/taxonomia/historico` | Histórico | → `#/entrar` | ✅ (só leitura) | ✅ | ✅ |
| `#/plano` | Planos de mídia | → `#/entrar` | ✅ sem excluir | ✅ | ✅ |
| `#/plano/metricas` | Catálogo de métricas | → `#/entrar` | ✅ | ✅ | ✅ |
| `#/plano/<id>` | Plano | → `#/entrar` | ✅ sem excluir | ✅ | ✅ |
| `#/admin` | → replace → `#/admin/acessos` | → `#/entrar` | 🚫 tela negada | 🚫 tela negada | ✅ |
| `#/admin/acessos` | Gestão de acessos | → `#/entrar` | 🚫 | 🚫 | ✅ |
| `#/admin/design` | → replace → `#/admin/design/fundacao` | → `#/entrar` | 🚫 | 🚫 | ✅ |
| `#/admin/design/<secao>` | Catálogo de interface | → `#/entrar` | 🚫 | 🚫 | ✅ |
| `#/admin/monitoramento` | Monitoramento | → `#/entrar` | 🚫 | 🚫 | ✅ |
| `#/isolado/<id>` | Exemplo isolado | → `#/entrar` | 🚫 | 🚫 | ✅ |
| `#/admin/<secao antiga>` | → replace → `#/admin/design/<secao>` | → `#/entrar` | 🚫 | 🚫 | ✅ |
| (outra) | Endereço não encontrado | → `#/entrar` | ✅ | ✅ | ✅ |

Legenda: **→ destino** = já logado em `#/entrar` cai no destino pós-login (§5.2). **🚫** = tela/painel de acesso negado, com texto, **nunca** redirecionamento silencioso nem 404 (§4.3).

`basico` não vê botão de excluir em lugar nenhum do produto — o que hoje significa: aba Dicionário inteira ausente, `Excluir plano`, `Remover campanha/grupo/anúncio` do plano ausentes. O Histórico não tem exclusão para ninguém (D-004).

---

## 2 · Botão de voltar

### 2.1 A decisão

**Voltar sobe um nível na hierarquia da informação. Não é `history.back()`.**

Três razões, em ordem de peso:

1. **`history.back()` tem destino desconhecido, e um rótulo não pode mentir.** Nielsen #6 (reconhecer em vez de lembrar) e Krug: o rótulo precisa dizer para onde vai. `← Voltar` sem destino obriga o usuário a testar. `← Voltar para os assuntos` é verificável antes do clique.
2. **O histórico do navegador aqui está poluído por navegação que o usuário não considera navegação.** `trocarAba()` chama `navegar()`, que empilha. Depois de circular Gerar → Dicionário → Histórico → Gerar, `history.back()` anda **uma aba de cada vez**, quatro cliques para "sair da taxonomia". A hierarquia sai em um.
3. **Por link direto ou F5 não existe "atrás".** O produto vai ser aberto por bookmark e por link colado no chat — nesses casos `history.back()` leva o usuário para fora do MediaBuild ou não faz nada. Um controle que às vezes não faz nada é pior que controle nenhum (Norman: significante sem significado).

O botão **voltar do navegador continua funcionando e continua sendo o desfazer de navegação** — as duas coisas coexistem porque fazem coisas diferentes, e é exatamente por serem diferentes que a nossa precisa de rótulo explícito.

### 2.2 Rótulo, posição e marcação

Componente novo `VoltarPara`, um por tela, primeiro filho do `<main class="pagina">`, acima do `<h1>`. É o padrão que `SeletorDeAssunto` e `PlanoDetalhe` já usam — não se inventa nada, uniformiza-se.

```
┌─────────────────────────────────────────────────────────┐
│ ← Voltar para os assuntos                               │  ← .linha, botão fantasma sm
│                                                         │
│ Gerar nomenclatura                                      │  ← h1
│ Nomenclaturas padronizadas para campanhas de mídia paga │
└─────────────────────────────────────────────────────────┘
```

- É `<a href>`, não `<button>`: Ctrl+clique, botão do meio e "copiar endereço do link" saem de graça, e o motor de acessibilidade anuncia "link".
- Variante `fantasma`, tamanho `sm`. **Não compete com a ação primária da tela** — ela é o preview/salvar, não a saída.
- Alvo ≥ 44×44 px de área clicável (uso frequente, WCAG 2.5.8 pede 24 mínimo; 44 aqui por frequência).
- A seta `←` é texto dentro do link, não ícone solto; `aria-hidden` nela.

### 2.3 Destino por rota

| Rota | Rótulo exato | Destino |
| --- | --- | --- |
| `#/` | *sem botão* | — |
| `#/entrar` | *sem botão* | — |
| `#/assunto` | `← Voltar para o início` | `#/` |
| `#/guia` | `← Voltar para o início` | `#/` |
| `#/cadastro` | `← Voltar para o início` | `#/` |
| `#/taxonomia/gerar` \| `/dicionario` \| `/historico` | `← Voltar para os assuntos` | `#/assunto` |
| `#/plano` | `← Voltar para os assuntos` | `#/assunto` |
| `#/plano/metricas` | `← Voltar para os planos` | `#/plano` |
| `#/plano/<id>` | `← Voltar para os planos` | `#/plano` |
| `#/admin/acessos` \| `/monitoramento` | `← Voltar para os assuntos` | `#/assunto` |
| `#/admin/design/<secao>` | `← Voltar para a administração` | `#/admin/acessos` |
| `#/isolado/<id>` | `← Voltar para o catálogo` | `#/admin/design/<seção do exemplo>` |
| `desconhecida` | `← Voltar para o início` | `#/` |

O destino de `#/isolado/<id>` é **calculado**, não fixo: `EXEMPLOS_POR_SECAO` já sabe a que seção cada exemplo pertence. Voltar de um exemplo isolado para a seção errada é o tipo de detalhe que faz o usuário desconfiar da navegação inteira.

### 2.4 As três armadilhas

**Aba não é tela.** As três abas da taxonomia mostram o **mesmo** `← Voltar para os assuntos`. Sair da aba Dicionário não é "voltar" para Gerar — as abas são um sistema de organização *dentro* do assunto (Rosenfeld/Morville), e o Voltar opera *entre* assuntos. Consequência prática: o `VoltarPara` mora no `AplicativoTaxonomia`, fora dos `tabpanel`, e não muda quando a aba muda.

**Sair da taxonomia não descarta nada.** Clicar `← Voltar para os assuntos` com o formulário meio preenchido segue a rota normal: o ramo é escondido com `hidden`, nunca desmontado (I-1). O botão não pede confirmação, porque não há nada a perder. Se algum dia passar a haver, o diálogo é a solução errada — o certo é não perder.

**Tela raiz não tem botão desabilitado.** Em `#/` e `#/entrar` o `VoltarPara` **não é renderizado** e nenhum espaço é reservado. Um controle permanentemente desabilitado ensina o usuário a ignorar a região onde ele mora, e o layout não pode saltar entre telas — por isso a altura do bloco vem do `.pilha`, não do botão.

**Foco.** Hoje `App.tsx` foca `[data-foco-rota]`, que é o `<h1>`. Com o link acima do `h1`, o link fica fora do caminho do Tab (só alcançável por Shift+Tab). Correção: `data-foco-rota` e `tabIndex={-1}` migram para um `<header class="cabecalho-tela">` que envolve o `VoltarPara` **e** o `h1`. O leitor de tela continua anunciando o título (o `role="status"` do `App` já anuncia `document.title`), e o primeiro Tab passa a cair no Voltar — que é a ordem visual.

---

## 3 · Área administrativa

### 3.1 Rotas

```
#/admin                    → replace → #/admin/acessos
#/admin/acessos            Gestão de acessos   (listar, criar, editar papel, desativar/excluir)
#/admin/design             → replace → #/admin/design/fundacao
#/admin/design/<secao>     Catálogo de interface (7 seções, as de hoje)
#/admin/monitoramento      Monitoramento       (acessos e erros)
```

`SecaoCatalogo` não muda de valores; muda de lugar na URL.

### 3.2 URLs antigas: **redirecionam**, não 404

`#/admin/fundacao` … `#/admin/redacao` viram `substituir('#/admin/design/<secao>')`.

Isso parece contradizer a regra da Parte I ("não redirecionar em silêncio, Nielsen #9"). Não contradiz: aquela regra vale para endereço **desconhecido**, onde o silêncio esconde um erro do usuário. Aqui o endereço é conhecido e mudou de lugar — é semântica de 301, e quem publicou o link antigo fomos nós (`cromo.tsx` linha 84, rodapé de toda tela de entrada). 404 num link que o próprio produto distribuiu é dano autoinfligido.

Implementação: uma tabela `REDIRECIONAMENTOS_LEGADOS` em `roteador.ts`, com comentário datado, para poder ser apagada quando não houver mais bookmark vivo.

### 3.3 Como se chega lá

**Pelo menu de conta**, item `Administração` (§5.4). Não pela barra de navegação principal e não pelo rodapé.

Razão: administração é atributo de **quem você é**, não de **o que você está fazendo** (Arango — a estrutura ensina o modelo mental). Pôr `Administração` ao lado de `Guia de uso` na barra sugere que é mais um assunto do produto, e obrigaria a esconder um item da barra por papel, que é a maior fonte de "a barra muda de tamanho dependendo de quem loga".

O link `Catálogo de interface` do rodapé (`cromo.tsx`) **sai para todo mundo**. Para `admin` ele reaparece apontando para `#/admin/design/fundacao`.

### 3.4 Navegação interna

Três áreas, nível único, como **links** com `aria-current="page"` — **não** `role="tab"`. São telas distintas com URL própria; o padrão APG de tabs descreve painéis dentro de uma tela e brigaria com a nav lateral de seções que o catálogo já tem (dois `tablist` aninhados é ruído de leitor de tela garantido).

```
┌───────────────────────────────────────────────────────────────────────────┐
│ ▌MDBuilder                                        Guia de uso   [◯ Ana S…]│  barra global
├───────────────────────────────────────────────────────────────────────────┤
│ Administração · você está fora do produto                                 │  faixa de contexto
└───────────────────────────────────────────────────────────────────────────┘
  ← Voltar para os assuntos

  Administração
  ┌──────────┬────────┬────────────────┐
  │ Acessos  │ Design │ Monitoramento  │        ← nav secundária, <a>, aria-current
  └──────────┴────────┴────────────────┘
  ────────────────────────────────────────────────────────────────────────────
  (conteúdo da área; em Design entra a nav lateral de seções que já existe)
```

Em `Design`, o layout é o de hoje: `216px` de nav lateral + conteúdo, via `@container pagina (min-width: 900px)`.

### 3.5 Como se distingue do produto sem virar outro aplicativo

**Um sinal só, forte, e fora do conteúdo**: a *faixa de contexto* logo abaixo da barra global, superfície invertida (`--fundo-inverso` / `--texto-inverso`, tokens que já existem), altura de uma linha, texto `Administração`.

O que **não** fazer, e por quê:

- **Não trocar a paleta da área.** O catálogo de design existe para mostrar as cores do produto. Recolorir a casca do admin faria o palco mentir — o mesmo erro que a Parte I evitou ao proibir `@media`.
- **Não usar outra barra de topo, outra tipografia ou outro layout de página.** Seria um segundo aplicativo: o usuário perderia o caminho de volta e o custo de manutenção dobraria (Refactoring UI: um sinal forte vale mais que cinco fracos).
- **Não usar cor de estado (`--erro`/`--alerta`) na faixa.** Estar no admin não é erro nem risco.

Além da faixa: `document.title` ganha o prefixo `Administração · `, e o `h1` de toda tela do admin é `Administração` com a área no `h2` — assim o anúncio de rota já diz onde a pessoa está.

### 3.6 `#/admin/acessos` — gestão de usuários

Uma tela, uma tabela, um formulário de criação em diálogo. Largura `--largura-ampla` (§7).

```
Administração
[Acessos] Design  Monitoramento
─────────────────────────────────────────────────────────────────────────────
Buscar pessoa [ nome ou usuário         ]   Papel [Todos ▾]  Situação [Ativos ▾]
                                                             [ + Novo acesso ]
─────────────────────────────────────────────────────────────────────────────
 Nome              Usuário         Papel      Situação     Último acesso
─────────────────────────────────────────────────────────────────────────────
 Ana Souza    ana.souza        Admin      Ativo        hoje, 09:12     ⋯
 Marina Alves      marina.alves    Pleno      Ativo        ontem, 18:40    ⋯
 João Pedro        joao.pedro      Básico     Desativado   12/07, 11:02    ⋯
─────────────────────────────────────────────────────────────────────────────
```

**`+ Novo acesso`** abre `<dialog>` com `Nome`, `Usuário`, `Papel` e `Senha provisória`. A senha provisória é **gerada pelo sistema e exibida uma vez**, com botão copiar e o aviso `Anote agora: esta senha não será mostrada de novo.` — o administrador a entrega pessoalmente. Não há e-mail para enviá-la, e inventar um campo de e-mail só para isso seria mentir sobre a existência de um canal.

- **Papel edita inline**, num `<select>` na própria célula: é o campo que mais muda e não merece uma tela. Ao mudar, salva na hora e confirma com `role="status"`: `Papel de Marina Alves alterado para Admin.` Sem botão de salvar por linha.
- **Coluna `⋯`** abre menu com `Desativar acesso` / `Redefinir senha` / `Excluir`.
- **`Redefinir senha` é a única forma de recuperação que existe no produto** — não há "esqueci minha senha" na tela de login (§5.3). Abre `<dialog>` que gera uma senha provisória, mostra uma vez com botão copiar, e marca a conta para trocar a senha no próximo login. Redação: `Senha provisória de Marina Alves` · `Anote agora: esta senha não será mostrada de novo.`
- **Desativar é a ação recomendada; excluir é a exceção.** Desativar preserva a trilha de quem gerou o quê; excluir some com ela. O menu deixa `Excluir` por último, separado, em `--erro`, e o diálogo de confirmação exige digitar o usuário da pessoa. Justificativa: é a única ação verdadeiramente destrutiva de todo o produto (a taxonomia é imutável, o plano tem histórico).
- **O admin não consegue rebaixar nem excluir a si mesmo.** Esse é o caso legítimo de *desabilitado com motivo* (§4.1): é estado, não permissão. Motivo: `Você não pode alterar o próprio acesso.`
- Estados: vazio (`Nenhum acesso cadastrado.` — na prática impossível, mas existe), filtro sem resultado (`Ninguém encontrado com esses filtros.` + `Limpar filtros`), carregando (esqueleto de 5 linhas), erro de carga (`Não foi possível carregar os acessos.` + `Tentar de novo`).

### 3.7 `#/admin/monitoramento` — acessos e erros

Duas seções na mesma tela, separadas por espaço (não por linha divisória), com um seletor de período único no topo (`Hoje` · `7 dias` · `30 dias`), porque as duas respondem à mesma pergunta temporal.

```
Período  ( Hoje )( 7 dias )( 30 dias )

Acessos
┌───────────────┬───────────────┬───────────────┐
│ 12            │ 5             │ 1             │
│ entradas      │ pessoas       │ falhas de     │
│               │ distintas     │ login         │
└───────────────┴───────────────┴───────────────┘
 Quando            Pessoa              Origem        Resultado
 hoje, 09:12       ana.souza@…          127.0.0.1     Sucesso
 hoje, 08:58       joao@…              127.0.0.1     Senha incorreta

Erros
┌───────────────┬───────────────┐
│ 3             │ 0             │
│ erros de      │ falhas do     │
│ validação     │ servidor      │
└───────────────┴───────────────┘
 Quando       Código                 Rota                 Request ID
 hoje, 10:40  termo_nao_cadastrado   POST /taxonomias/…   3f9c…  [copiar]
```

- O **`request_id`** é a coluna que justifica a tela: `app/logs.py` já o devolve em `X-Request-ID`, e é ele que liga a reclamação do analista à linha de log. Monoespaçado, com botão copiar.
- Erro de validação (422 do motor) e erro de servidor (5xx) são **contadores separados**. Juntar os dois faz "3 erros hoje" parecer alarme quando é só alguém digitando um termo fora do dicionário.
- Não usar gráfico nesta fase. Três números e duas tabelas respondem à pergunta; gráfico sem série histórica é decoração.
- Estados: vazio (`Nenhum acesso no período.` / `Nenhum erro no período.` — este último com tom neutro, é boa notícia), carregando, erro.

---

## 4 · Visibilidade por papel

### 4.1 A regra de ouro

> **Ausência de permissão esconde. Ausência de condição desabilita com motivo.**

- **Papel não permite** → o controle **não existe** na árvore. Sem `disabled`, sem tooltip, sem cadeado.
- **Papel permite, mas agora não dá** (formulário incompleto, plano sem linhas, você é o próprio usuário) → controle **desabilitado, com o motivo visível em texto ao lado** — o padrão que o `Gerador` já usa (`Complete os três níveis para salvar.`).

Justificativa: um controle desabilitado só é útil quando o usuário pode agir sobre o motivo. "Você não tem permissão" não é acionável — o analista `basico` veria a mesma frase dezenas de vezes por dia, todo dia, para sempre. Isso é ruído permanente (Krug: retire as palavras que não trabalham) e ainda anuncia uma capacidade que ele nunca terá, o que gera pedido e frustração, não aprendizado.

O contra-argumento honesto — esconder prejudica a descoberta e cria o "sumiu o botão" entre papéis — é resolvido em **um lugar canônico** em vez de N inline: o menu de conta mostra o papel e uma linha de verdade.

```
Perfil: Básico
Seu perfil gera nomenclaturas e consulta o histórico.
Dicionário e exclusões precisam de um perfil Pleno.
```

Uma frase, num lugar previsível, contra dezenas de controles mortos na tela. É a troca certa.

### 4.2 Onde isso muda o código

- `ABAS_TAXONOMIA` deixa de ser constante e vira `abasVisiveis(papel)`. O roving tabindex do APG passa a percorrer 2 ou 3 abas conforme o papel — a implementação atual já é genérica sobre o array, só não pode continuar lendo a constante global.
- Todo botão de excluir passa por um único portão: `podeExcluir(papel)`.
- **Nunca** condicionar visibilidade a `papel === 'admin'` espalhado pelo JSX. Um módulo `src/sessao.tsx` exporta `usePermissao()` com predicados nomeados (`podeVerDicionario`, `podeExcluir`, `podeAdministrar`). Regra de manutenção: se o nome do predicado não descreve a *ação*, ele está errado.

### 4.3 `basico` digitando `#/taxonomia/dicionario`

Nem redirecionamento silencioso, nem 404.

A tela de taxonomia renderiza normalmente (com as duas abas que ele tem), e no lugar do painel aparece:

```
┌───────────────────────────────────────────────────────────┐
│  Você não tem acesso ao Dicionário                        │
│                                                           │
│  Seu perfil é Básico. Peça a um administrador para        │
│  liberar o acesso, ou volte para Gerar.                   │
│                                                           │
│  [ Ir para Gerar ]                                        │
└───────────────────────────────────────────────────────────┘
```

- **Não redirecionar**: o usuário digitou um endereço; ser teleportado sem explicação se lê como bug (Nielsen #1).
- **Não 404**: "não existe" é mentira. Existe, não é para ele. Rótulo mentiroso é dívida de arquitetura de informação (Covert).
- `Ir para Gerar` usa `substituir()` (replaceState), para o botão voltar do navegador não devolver a pessoa à tela negada.
- Mesmo componente, mesma redação, para `#/admin/*` com papel não-admin — ali como tela cheia, `h1` = `Você não tem acesso à administração`.
- Isso é **cosmético**: a autoridade é o servidor. Qualquer 403 vindo da API renderiza o mesmo componente, no mesmo lugar.

### 4.4 Sessão expirada no meio de um formulário

**Requisito duro: expirar sessão não navega, não desmonta, não limpa nada.** Sessão não é rota. Violar isso é regressão do D-005, exatamente como desmontar o gerador.

Fluxo:

1. `api.ts` intercepta `401` e liga a flag global `sessaoExpirada`. **Não** navega.
2. `App.tsx` renderiza um `<dialog>` modal por cima do que estiver na tela — o conteúdo abaixo continua montado e preenchido.

```
┌──────────────────────────────────────────────┐
│  Sua sessão expirou                          │
│                                              │
│  Entre de novo para continuar.               │
│  Nada do que você preencheu foi perdido.     │
│                                              │
│  Usuário                                     │
│  ┌──────────────────────────────────────┐    │
│  │ ana.souza                             │    │  (somente leitura)
│  └──────────────────────────────────────┘    │
│  Senha                                       │
│  ┌──────────────────────────────────────┐    │
│  │                                      │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  [ Entrar ]                    Sair da conta │
└──────────────────────────────────────────────┘
```

3. `<dialog>` nativo com `showModal()`. **Não escrever focus trap à mão** — é onde nascem os bugs de acessibilidade. `Esc` não fecha (`cancel` prevenido): fechar sem resolver deixaria a tela numa mentira, com controles que não funcionam.
4. Ao autenticar: fecha, devolve o foco ao elemento que o tinha antes, e **não reexecuta nada automaticamente**. O usuário aperta o botão de novo.
   Motivo: repetir sozinho um `POST /taxonomias` pode consumir um `match_id` a mais e gravar um nome que ninguém pediu. **Reexecução automática é permitida só para o `GET` idempotente que disparou o 401** (recarregar plataformas, histórico), nunca para POST/PATCH/DELETE.
5. `Sair da conta` descarta tudo e vai para `#/entrar` — só chega aqui quem escolheu explicitamente.

**Rede de segurança independente da sessão:** o `Gerador` serializa seu formulário em `sessionStorage['mdbd:rascunho-gerador']` (debounce 500 ms) e restaura ao montar. Isso cobre F5, queda do navegador e fechar a aba sem querer — casos que o diálogo não cobre. Limpar o rascunho ao salvar com sucesso e ao sair da conta: rascunho com nome de cliente sobrevivendo numa máquina compartilhada é vazamento. `sessionStorage`, não `localStorage`, pela mesma razão.

---

## 5 · Login

### 5.1 Onde entra no fluxo

Hoje: `#/` (splash) → `#/assunto` → assunto.
Passa a ser: **`#/entrar` → `#/` (splash) → `#/assunto` → assunto**, com o atalho de sempre por cima.

A splash continua **depois** do login, e continua sendo pulada por quem já escolheu assunto (`localStorage['mdbd:ultimo-assunto']`, constante `SEMPRE_MOSTRAR_SPLASH`). A splash é marca e recomendação, não portão; o portão que decide todo o resto tem que vir antes.

### 5.2 Destino pós-login

1. Se havia um endereço pretendido (a pessoa abriu `#/plano/abc` sem sessão), volta para ele.
2. Senão, `localStorage['mdbd:ultimo-assunto']` → `#/taxonomia/gerar` ou `#/plano`.
3. Senão, `#/assunto`.

O endereço pretendido fica em **memória do módulo**, não na URL. Sem `?next=` — num roteador por hash isso vira string colável e apontável para fora, e não há benefício: o login não é compartilhado por link.

Redirecionar para `#/entrar` usa `substituir()`: `location.hash =` empilharia entrada e o botão voltar entraria em loop com o portão.

### 5.3 A tela

Coluna única centrada, cartão em `--largura-estreita`, sem barra de topo e sem rodapé de links (não há para onde ir).

```
                    ▌ MDBuilder

        ┌───────────────────────────────────────┐
        │  Entrar                               │
        │  Nomenclaturas padronizadas para      │
        │  campanhas de mídia paga              │
        │                                       │
        │  Usuário                              │
        │  ┌─────────────────────────────────┐  │
        │  │                                 │  │
        │  └─────────────────────────────────┘  │
        │                                       │
        │  Senha                                │
        │  ┌─────────────────────────────────┐  │
        │  │                            👁    │  │
        │  └─────────────────────────────────┘  │
        │                                       │
        │  ┌─────────────────────────────────┐  │
        │  │            Entrar               │  │
        │  └─────────────────────────────────┘  │
        │                                       │
        │  Esqueceu a senha? Só um              │
        │  administrador pode redefinir.        │
        └───────────────────────────────────────┘

                MediaBuild · uso local
```

**A identidade é `usuario`, não e-mail.** Decisão que fecha uma alternativa razoável, então fica registrada: não existe envio de e-mail neste produto (uso local, sem SMTP), então e-mail seria um identificador cujo único poder — recuperar acesso sozinho — não existe. Login por `usuario` diz a verdade sobre o que o sistema faz. Consequência obrigatória: **toda a interface chama isso de `Usuário`**, nunca "login", "e-mail" ou "conta". Um objeto, um nome (Covert).

- Rótulo **acima** do campo (Wroblewski): rótulo ao lado quebra em zoom de 200% e é mais lento de escanear.
- `type="text"`, `autocomplete="username"` no primeiro campo e `autocomplete="current-password"` no segundo. **Sem `type="email"` e sem `inputMode="email"`** — no celular isso traria o teclado com `@` e `.com` para um campo que não é endereço, e no desktop ligaria a validação nativa de e-mail, que rejeitaria `ana.souza` antes de qualquer requisição.
- `spellCheck={false}`, `autoCapitalize="none"` no campo de usuário. Autocorreção transformando o usuário digitado é falha silenciosa: a pessoa jura que digitou certo.
- Botão `Entrar` ocupa a largura do cartão — é a única ação, não precisa disputar espaço (Fitts).
- **Mostrar senha** é `<button>` com `aria-pressed`, nome acessível `Mostrar senha` / `Ocultar senha`. Ajuda mais do que atrapalha numa ferramenta interna.
- **Sem "lembrar de mim"** — a duração da sessão é decisão de backend, e um checkbox que não muda nada é mentira.
- **Sem "esqueci minha senha" clicável.** Redefinir senha é ação de administrador (§3.6), não fluxo de autoatendimento. A frase estática é a resposta correta e completa: ela diz o que fazer (procurar um administrador) sem oferecer um caminho que não existe. Link que não leva a lugar nenhum custa mais que a frase.
- Enter no campo de senha envia (é um `<form>` de verdade, com `onSubmit`).
- Foco inicial: campo de usuário. Esta é a **única** tela do produto com foco automático em campo — é a única em que a primeira ação do usuário é digitar, sem exceção.

### 5.4 Estados

| Estado | Elemento | Texto |
| --- | --- | --- |
| Enviando | Botão com `carregando` + `aria-busy`, campos em `readonly` (não `disabled`: `disabled` rouba o foco e o leitor de tela perde o contexto) | `Entrar` |
| Credencial inválida | `role="alert"` acima dos campos; ambos com `aria-invalid="true"`; **senha limpa, usuário preservado**; foco vai para a senha | `Usuário ou senha incorretos.` |
| Conta desativada | `role="alert"` | `Esta conta está desativada. Fale com um administrador.` |
| Sessão expirada (chegou aqui por expiração) | `role="status"` acima do formulário, tom neutro | `Sua sessão expirou. Entre de novo.` |
| Servidor inacessível | `role="alert"` + botão `Tentar de novo` | `Não foi possível falar com o servidor. Tente de novo em instantes.` |
| Muitas tentativas (429) | `role="alert"` | `Muitas tentativas. Espere um minuto e tente de novo.` |

**Vazamento de existência de conta.** A regra é do backend, e o front não pode enfraquecê-la:

- O cliente **imprime a mensagem que a API mandou**, com um único fallback local. Nunca escolhe texto por status, nunca deriva "usuário não cadastrado" de nada.
- O cliente **não** valida existência de usuário antes de enviar, **não** faz `GET /usuarios?usuario=` e **não** muda o foco/estado de forma diferente conforme o motivo — a diferença de comportamento também é um canal de enumeração.
- `Usuário ou senha incorretos.` cobre os dois casos numa frase só, e é por isso que essa frase existe. Nunca `Usuário não encontrado.`
- `Conta desativada` **admite** que a conta existe. É trade-off consciente: é o único jeito de o usuário parar de tentar e procurar um administrador. **Se o backend preferir não distinguir, ele simplesmente devolve a mensagem genérica e este estado nunca aparece** — o front não precisa mudar. Ponto a confirmar com quem implementar o `/auth/entrar` (§10).

### 5.5 Identidade, sair e tema — o menu de conta

Consequência estrutural: **a `BarraTopo` passa a ser cromo global**, renderizada pelo `App` em todas as rotas menos `#/`, `#/entrar` e `#/isolado/*`.

Hoje ela só aparece nas telas de entrada, e cada tela grande (`AplicativoTaxonomia`, `PlanoIndice`, `PlanoDetalhe`, `Catalogo`) inventou o próprio cabeçalho com um `titulo-tela-link` apontando para `#/`. Identidade e `Sair` precisam estar sempre no mesmo lugar (Nielsen #4, consistência), e não dá para repetir isso em cinco cabeçalhos. Os `titulo-tela-link` são removidos: a marca da barra vira o único caminho para o início, que é a convenção que todo mundo já conhece (Jakob).

```
┌────────────────────────────────────────────────────────────────────────┐
│ ▌MDBuilder            Guia de uso   Cadastro          [◯ Ana ▾]  │
└────────────────────────────────────────────────────────────────────────┘
                                                        ┌───────────────────────────┐
                                                        │ Ana Souza            │
                                                        │ @ana.souza                 │
                                                        │ Perfil: Pleno             │
                                                        │ ───────────────────────── │
                                                        │ Tema                      │
                                                        │ (Claro)(Escuro)(Sistema)  │
                                                        │ ───────────────────────── │
                                                        │ Administração        (adm)│
                                                        │ ───────────────────────── │
                                                        │ Sair                      │
                                                        └───────────────────────────┘
```

- Gatilho: `<button>` com `IconeConta` + primeiro nome, `aria-haspopup="menu"`, `aria-expanded`. Segue o padrão APG de menu button: Esc fecha e devolve o foco ao gatilho, setas percorrem, clique fora fecha.
- **Papel visível no menu** — é o lugar canônico da §4.1. Para `basico`, entra ali a frase que explica o que ele não vê.
- **Tema é controle de três estados** (`Claro` / `Escuro` / `Sistema`), padrão `Sistema`, persistido em `localStorage['mdbd:tema']` e aplicado em `document.documentElement.dataset.tema` — exatamente o gancho já reservado em `index.css:413`. Não usar ícone sol/lua solto na barra: ícone único é ambíguo entre "estado atual" e "o que vai virar", e essa ambiguidade é um bug recorrente em toda interface que a adota.
  **O controle de tema só entra junto com o bloco `:root[data-tema='escuro']`.** Antes disso não se renderiza — não é caso de desabilitar.
- `Sair` é o último item, separado, alvo de 44 px. Sem confirmação: sair não destrói nada (o rascunho é limpo de propósito, e nomenclatura salva é imutável).
- Ao sair: `POST /auth/sair`, limpa sessão, limpa `mdbd:rascunho-gerador`, `substituir('#/entrar')` e **remonta o ramo da taxonomia**.

> **Exceção explícita ao I-2.** Sair é o único momento em que desmontar o gerador é correto — outra pessoa pode sentar na máquina e não pode herdar o formulário da anterior. Implementar como `key={idSessao}` no ramo, onde `idSessao` muda **apenas** em login/logout, jamais em troca de rota. Qualquer outra coisa entrando nessa `key` é o bug que o I-2 descreve.

---

## 6 · Busca no Dicionário

### 6.1 Cliente, não servidor

A busca é **local**. `api.dicionarioCompleto()` já carrega tudo na montagem, o dicionário tem ordem de centenas de linhas, e o filtro roda em fração de milissegundo.

Ida ao servidor custaria latência a cada tecla e obrigaria a **duplicar a regra de acento em SQL**, que é onde moram os bugs de `unaccent`/collation. Gatilho para revisar: se `entradas.length` passar de ~2000, a busca migra para o servidor mantendo o mesmo contrato de URL.

Contraste deliberado com o **Histórico**, que filtra no servidor e deve continuar assim: ele é ilimitado e recortado por data.

### 6.2 O que entra na busca

`termo` (De) · `abreviacao` (Para) · `categoria`.

A categoria entra porque a pergunta real do analista é frequentemente "que abreviações existem em objetivo?", e digitar `objetivo` numa caixa é mais rápido que caçar o valor num `<select>`. O `<select>` de categoria **continua existindo** e combina com a busca por **E**, não por OU: filtro é recorte, busca é procura.

### 6.3 Acento, caixa e forma de casar

O produto inteiro dobra acento — e o motivo da busca existir é justamente o analista ter recebido `termo_nao_cadastrado` e vir conferir. Digitar `conversao` **tem** que achar `Conversão`.

```ts
// src/texto.ts
export function normalizarBusca(s: string): string {
  return s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toUpperCase()
}
```

- Aplicado dos **dois lados** (consulta e campo), a cada comparação.
- **Substring**, não prefixo e não difuso. Numa ferramenta cujo produto é exatidão, resultado aproximado obriga a reconferir tudo — custa mais do que rende.
- Não remover `_` nem `-`: são significativos na coluna Para.
- Uma linha de comentário obrigatória no arquivo: **isto normaliza para *achar*, nunca para *gerar***. A normalização que produz nomenclatura é do servidor (`app/taxonomia/normalizacao.py`) e não tem cópia no cliente.

### 6.4 Debounce

**Nenhum no filtro.** Filtrar um array local é instantâneo, e atrasar de propósito o que é imediato só produz sensação de travamento (Doherty threshold).

300 ms de debounce só para dois efeitos colaterais:
1. gravar `?q=` na URL;
2. anunciar a contagem no `role="status"` — sem debounce o leitor de tela é metralhado a cada tecla.

### 6.5 URL

Sim: `#/taxonomia/dicionario?q=conversao&cat=objetivo`.

Ganho concreto: o erro do Preview (`Termo "X" não cadastrado`) passa a oferecer **`Cadastrar "X" no dicionário`** apontando para `#/taxonomia/dicionario?q=X`, que já abre filtrado e com o campo De preenchido. É o atalho entre o erro e o conserto — hoje o analista lê o erro, troca de aba e digita tudo de novo.

Exige mudança no roteador: `lerRota` corta em `?` **antes** de dividir por `/`, e a rota passa a carregar `params: URLSearchParams`. Sem isso, `dicionario?q=x` cai em `desconhecida`.

Escrita com `substituir()` (replaceState) enquanto digita — senão cada tecla vira uma entrada no histórico e o botão voltar do navegador fica inútil.

### 6.6 Anatomia e estados vazios

A busca fica no **cabeçalho da seção da lista**, não perto do formulário `Adicionar termo`. Misturar filtro com criação é o erro de agrupamento clássico: são conversas diferentes (Jarrett & Gaffney).

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Adicionar termo                                                          │
│ Categoria [Objetivo ▾]  ou nova [        ]  De [        ]  Para [     ]  │
│ Vale para [Todas ▾]                                        [ Adicionar ] │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ Termos                                    Objetivo · 12 de 84 termos     │
│ Buscar termo [ conversão, CV, objetivo    ✕ ]   Categoria [Objetivo ▾]   │
│ ──────────────────────────────────────────────────────────────────────── │
│ Categoria    De                Para      Vale para        │             │
│ Objetivo     Conversão         CV        Todas            Editar Remover│
│ Objetivo     Reconhecimento    RCN       Todas            Editar Remover│
└──────────────────────────────────────────────────────────────────────────┘
```

- `type="search"`, `<label>` real `Buscar termo`, botão `✕` (`Limpar busca`) só quando há texto.
- Contador ao lado do título: `12 de 84 termos` quando filtrado; `84 termos` quando não.

Três vazios distintos — a diferença entre eles é a informação:

| Situação | Título | Complemento |
| --- | --- | --- |
| Dicionário sem nenhum termo | `Nenhum termo cadastrado ainda.` | `O gerador recusa termos que não estão aqui. Comece cadastrando o primeiro acima.` |
| Busca sem resultado | `Nenhum termo com "conversao".` | `[ Limpar busca ]` · `[ Cadastrar "conversao" ]` (preenche o campo De e foca o Para) |
| Categoria sem termos | `Nenhum termo em "Objetivo".` | `[ Ver todas as categorias ]` |

`Cadastrar "conversao"` é o item de maior valor da tela: fecha o ciclo erro → busca → cadastro sem redigitar.

### 6.7 Dois consertos que vêm junto

- `window.prompt` para editar e `window.confirm` para remover **saem**. Editar vira edição inline na linha (o único campo editável é `abreviacao`, igual à API); remover vira `<dialog>` nomeando o termo: `Remover "Conversão" de Objetivo?` / `Termos já usados em nomenclaturas geradas não são afetados — elas são imutáveis.`
- `Dicionario.tsx` e `Historico.tsx` ainda carregam objetos de estilo literais (`CELULA`, `LINK_BOTAO`, `padding: '1.25rem'`, `borderColor: '#fecaca'`). Isso viola a regra de tokens do `CLAUDE.md` e é pré-requisito de §7 — as duas telas não conseguem mudar de densidade enquanto a densidade estiver escrita em `.tsx`.

---

## 7 · Distribuição na tela

### 7.1 O diagnóstico

`--largura-conteudo: 1040px` é aplicado igualmente a todas as telas. Num monitor de 2560 px, o Histórico — que é uma tabela de seis colunas — fica numa coluna de 1040 no meio do deserto, enquanto o Guia — que é texto corrido — fica com a mesma largura, que para texto já é larga demais.

O erro não é o valor. É haver **um valor só**.

### 7.2 A regra

> **A página não tem uma largura máxima. Cada tela recebe a largura que o seu conteúdo justifica.**

Três classes (valores exatos são do agente de design system; aqui vale a intenção):

| Token | Ordem de grandeza | Para quê |
| --- | --- | --- |
| `--largura-leitura` | ~72ch | Texto corrido: Guia, Cadastro, tela de erro, login |
| `--largura-conteudo` | ~1120px | Telas dominadas por um formulário |
| `--largura-ampla` | ~1600px (teto) | Telas dominadas por dados: Histórico, Dicionário, Planos, Plano, Acessos, Monitoramento |

**Teto, nunca 100%.** Uma linha de tabela de 2400 px destrói o retorno do olho entre a primeira e a última coluna (Müller-Brockmann: a grade serve à leitura). "Aproveitar a tela" não é encostar na borda; é dar colunas a quem tem o que pôr nelas.

Aplicação: `.pagina[data-largura='leitura' | 'ampla']`, mesma mecânica do `data-largura='estreita'` que já existe.

### 7.3 Tela por tela

**Gerar** — hoje: uma coluna abaixo de 880px, duas acima (`contexto 320` + `formulário`). O Preview mora no pé de cada `PainelNivel`, ou seja, num monitor de 1080p o analista digita em cima e a resposta fica abaixo da dobra. O preview é o produto (princípio 2); ficar fora da vista é o defeito mais caro da tela.

Duas etapas, nesta ordem:

*Etapa 1 (barata, faça primeiro):* limitar a coluna do formulário a ~68ch. Campo de texto de 900 px de largura não ajuda ninguém a preencher 30 caracteres, e o rótulo fica longe do valor.

*Etapa 2 (a que resolve):* terceira coluna acima de ~1400 px de contêiner.

```
< 880px                880–1400px                        > 1400px
┌──────────────┐   ┌──────────┬───────────────┐   ┌────────┬───────────┬──────────┐
│ Plataforma   │   │Plataforma│  Formulário   │   │Platafor│Formulário │ Resultado│
│ Estrutura    │   ├──────────┤  do nível     │   ├────────┤ do nível  │ ┌──────┐ │
│ Formulário   │   │Estrutura │               │   │Estrutu-│           │ │NOME  │ │
│  Preview     │   │ (sticky) │  [Preview]    │   │ra      │           │ │[copi]│ │
│  [Salvar]    │   │          │  [Salvar]     │   │(sticky)│           │ └──────┘ │
└──────────────┘   └──────────┴───────────────┘   │        │ [Salvar]  │ 42/400   │
                                                   └────────┴───────────┴──────────┘
                                                                        └ sticky ┘
```

Na etapa 2 o Preview do nível em edição sobe para a coluna `Resultado`, sticky, junto com os nomes já salvos e o `Copiar os três nomes`. Os previews dentro dos painéis somem **apenas** nesse formato — abaixo de 1400 px continuam onde estão. Isso é mudança estrutural no `Gerador`/`PainelNivel`: se o tempo for curto, entregue só a etapa 1 e registre a 2.

Tudo por `@container gerar`, nunca `@media` (regra do topo de `layout.css`).

**Dicionário e Histórico** — `--largura-ampla`. O ganho maior não é a largura, é a **altura recuperada**:

- O cartão de filtros vira uma linha de controles sem cartão e **sem o `<h2>Filtros`** — os rótulos dos campos já dizem o que são (Krug: retire a palavra que não trabalha). Recupera ~120 px verticais.
- Célula de tabela em `--tipo-md`, padding de `--esp-2`/`--esp-3`.
- **Meta observável: ≥ 18 linhas visíveis sem rolar em 1920×1080.** Se der menos que isso, a densidade não foi resolvida. Esse número é o critério de aceite, não o CSS.
- Colunas do Histórico com largura proporcional: `Nomenclatura` toma o `1fr` (é o que se lê), `Criado em` e o botão `Copiar` ficam com largura fixa à direita.

**Planos e Plano** — `--largura-ampla`. Já são hierarquia/tabela; a árvore do plano é o principal beneficiado por espaço horizontal (mais colunas de meta visíveis sem rolagem lateral).

**Guia, Cadastro, Entrar, Endereço não encontrado** — `--largura-leitura`. São as únicas telas em que crescer é **erro**: linha de 140 caracteres é o defeito de legibilidade mais comum em tela grande.

**Escolher assunto** — `--largura-conteudo`. Três cartões; a grade `auto-fit` já resolve.

**Admin · Design** — `--largura-ampla`: o palco precisa de espaço para o exemplo de 1440 px caber sem rolagem lateral.

### 7.4 Texto maior em tela grande

É entrega do agente de design system. O requisito daqui:

- `--tipo-base` deve chegar a ~16 px em viewport ≥ 1600 px, interpolado por `clamp()` com `vw` **no `:root` apenas**.
- Isso não é `@media` e não é consulta; é a única exceção legítima à regra de viewport-unit do projeto.
- **Ressalva a registrar**: dentro do palco do catálogo a tipografia continuará seguindo a *janela*, não o palco — então um palco de 360 px num monitor grande mostrará o layout de celular com o texto de desktop. O controle `Texto grande (200%)` já cobre o eixo tipográfico do catálogo, então o custo é aceitável, mas ninguém pode ler o palco como prova de tipografia.

---

## 8 · Mudanças por arquivo

Ordem sugerida de execução. Cada item é independente o bastante para virar um commit.

### Roteamento e sessão

1. **`src/roteador.ts`**
   - `lerRota` corta a hash em `?` antes de dividir por `/`; toda `Rota` passa a carregar `params: URLSearchParams`.
   - Novas rotas: `{ nome: 'entrar' }`, `{ nome: 'admin-acessos' }`, `{ nome: 'admin-monitoramento' }`, `{ nome: 'catalogo'; secao }` agora em `#/admin/design/<secao>`.
   - `#/admin` → `#/admin/acessos`; `#/admin/design` → `#/admin/design/fundacao`.
   - `REDIRECIONAMENTOS_LEGADOS`: as 7 seções antigas → `#/admin/design/<secao>`.
   - `abasVisiveis(papel)` substitui o uso direto de `ABAS_TAXONOMIA` na UI (a constante continua existindo para os testes de rota).
   - `caminhoDe` atualizado para todas as novas rotas.
2. **`src/sessao.tsx`** (novo) — `ContextoSessao`, `useSessao()`, `usePermissao()` com `podeVerDicionario` / `podeExcluir` / `podeAdministrar`, estado `sessaoExpirada`, `idSessao`.
3. **`src/api.ts`** — `auth.entrar` / `auth.sair` / `auth.eu`; `usuarios.*`; `monitoramento.*`; interceptação de `401` (liga `sessaoExpirada`, **não** navega) e de `403` (erro tipado que a tela traduz no componente de acesso negado).
4. **`src/App.tsx`** — portão de sessão antes de tudo; `BarraTopo` global (exceto `#/`, `#/entrar`, `#/isolado/*`); diálogo de reautenticação; `key={idSessao}` **só** no ramo da taxonomia; `TITULO` estendido; título prefixado com `Administração · ` nas rotas de admin.

### Cromo e navegação

5. **`src/componentes/VoltarPara.tsx`** (novo) — `<a>` com rótulo e destino explícitos; tabela de destinos do §2.3 num único mapa.
6. **`src/componentes/cromo.tsx`** — `BarraTopo` vira cromo global; ganha `MenuConta` (padrão APG de menu button); rodapé perde `Catálogo de interface` para não-admin; nova `FaixaAdmin`.
7. **`src/componentes/Entrar.tsx`** (novo) — tela do §5.3 com os seis estados do §5.4.
8. **`src/componentes/AcessoNegado.tsx`** (novo) — usado como painel (dentro da taxonomia) e como tela cheia (admin), mesma redação.
9. **Cabeçalhos das telas** — `AplicativoTaxonomia.tsx`, `PlanoIndice.tsx`, `PlanoDetalhe.tsx`, `Catalogo.tsx`, `Guia.tsx`, `Cadastro.tsx`, `SeletorDeAssunto.tsx`: remover o `titulo-tela-link` para `#/`, inserir `VoltarPara`, mover `data-foco-rota`/`tabIndex={-1}` do `h1` para o `<header class="cabecalho-tela">`.

### Taxonomia

10. **`src/componentes/AplicativoTaxonomia.tsx`** — abas por papel; `VoltarPara` fora dos `tabpanel`; painel de acesso negado quando `basico` cai no Dicionário.
11. **`src/componentes/Dicionario.tsx`** — campo de busca; filtro local com `normalizarBusca`; sincronia com `?q=`/`?cat=`; três estados vazios; edição inline; `<dialog>` de remoção; ações de exclusão sob `podeExcluir`; **todos os estilos literais para CSS**.
12. **`src/componentes/Historico.tsx`** — filtros em linha sem cartão e sem `<h2>Filtros`; densidade de tabela; **estilos literais para CSS**.
13. **`src/componentes/Gerador.tsx`** — rascunho em `sessionStorage` (debounce 500 ms, limpo ao salvar e ao sair); coluna do formulário limitada (etapa 1); coluna `Resultado` acima de 1400 px (etapa 2); erro de termo não cadastrado passa a linkar `#/taxonomia/dicionario?q=<termo>`.
14. **`src/texto.ts`** (novo) — `normalizarBusca`, com o comentário de que serve para achar, nunca para gerar.

### Administração

15. **`src/admin/`** — `Catalogo.tsx`, `ExemploIsolado.tsx`, `MostraExemplo.tsx`, `registro.ts`, `fixturas.ts`, `secoes/` migram para `src/admin/design/`; ajustar os `href` da nav de seções para `#/admin/design/<id>`.
16. **`src/admin/CascaAdmin.tsx`** (novo) — faixa de contexto + `h1 Administração` + nav secundária das três áreas.
17. **`src/admin/Acessos.tsx`** (novo) — §3.6.
18. **`src/admin/Monitoramento.tsx`** (novo) — §3.7.
19. **Regra mantida**: `src/admin/design/**` continua proibido de importar `src/api.ts`. `Acessos` e `Monitoramento` **podem** — eles administram de verdade. A proibição vale para o catálogo, não para a área.

### Estilo

20. **`src/index.css`** — `--largura-leitura` e `--largura-ampla`; `clamp()` de tipografia no `:root`; bloco `:root[data-tema='escuro']` (dependência do agente de design system).
21. **`src/estilos/layout.css`** — `.pagina[data-largura='leitura'|'ampla']`; `.cabecalho-tela`.
22. **`src/estilos/componentes.css`** — `.menu-conta`, `.faixa-admin`, `.nav-admin`, `.campo-busca`, `<dialog>`, densidade de `.tabela`.
23. **`src/estilos/gerador.css`** — terceira coluna em `@container gerar (min-width: 1400px)`.

### Testes (`src/testes/`)

24. `roteador.test.tsx` — query string na hash; redirecionamentos legados; novas rotas.
25. `sessao.test.tsx` (novo) — abas por papel; `basico` em `#/taxonomia/dicionario` vê acesso negado e **não** é redirecionado; nenhum botão de excluir para `basico`.
26. `permanencia.test.tsx` — **novo caso, o mais importante do lote**: com o formulário preenchido, forçar 401 → o diálogo aparece, o sentinela continua na árvore, autenticar → o sentinela continua lá e nada foi reenviado sozinho.
27. `Dicionario.test.tsx` (novo) — `conversao` acha `Conversão`; três vazios distintos; `?q=` sincroniza.
28. Testes existentes que renderizam `<App />` precisam de um provedor de sessão falso. **Escopar as consultas** — com a `BarraTopo` global montada, `getByRole('button', { name: /…/ })` passa a casar com o menu de conta também.

---

## 9 · Prioridade

**Quebra a tarefa** — sessão expirada descartando formulário (§4.4) · `key` de sessão vazando para troca de rota e remontando o gerador (§5.5) · `basico` conseguindo chamar rota negada e recebendo 500 em vez de negativa legível · redirecionamento de login empilhando histórico e prendendo o botão voltar.

**Custa tempo todo dia** — ausência do Voltar (§2) · busca no Dicionário e o atalho erro → cadastro (§6.5) · densidade do Histórico e do Dicionário (§7.3) · preview fora da vista em monitor grande (§7.3, etapa 2) · `window.prompt`/`window.confirm` no Dicionário (§6.7).

**Polimento** — faixa de contexto do admin · controle de tema · números do Monitoramento · migração das URLs antigas do catálogo.

---

## 10 · Dependências fora do frontend

**Backend — nada da Parte II §4/§5 funciona sem isto.** D-003 ("autenticação: depois") precisa finalmente ser decidido.

| Necessário | Observação |
| --- | --- |
| `POST /auth/entrar` | Mensagem genérica para credencial inválida, definida **no servidor**. Decidir se `conta_desativada` é distinguível (§5.4). |
| `POST /auth/sair` | |
| `GET /auth/eu` | Devolve nome, `usuario` e papel. É a fonte do papel — o cliente nunca infere papel de outra coisa. **Sem coluna de e-mail no modelo**: não há canal de e-mail (§5.3). |
| `POST /usuarios/<id>/senha` | Redefinição por administrador. Devolve a senha provisória **uma vez**. Único caminho de recuperação que existe. |
| `401` com corpo estável | Dispara o diálogo de reautenticação. |
| `403` com corpo estável | Renderiza `AcessoNegado`. |
| `GET/POST/PATCH/DELETE /usuarios` | Tela de Acessos. `DELETE` só para admin, e não pode apagar a si mesmo. |
| `GET /monitoramento/acessos` e `/erros` | Já existe substrato: `app/logs.py` carrega `request_id` em toda linha. |
| `usuario_id` deixa de ser sempre nulo | Coluna já existe (D-003), sem FK. |

**Design system** — `--largura-leitura`, `--largura-ampla`, `clamp()` tipográfico e o bloco `:root[data-tema='escuro']`. O controle de tema não entra antes do bloco escuro.

**Decisões a registrar em `docs/DECISOES.md`** (numeração livre a partir de D-014):

- Papéis `basico`/`pleno`/`admin` e a regra "permissão esconde, condição desabilita" (§4.1).
- Voltar é hierárquico, não `history.back()` (§2.1).
- Administração em três áreas, com o catálogo movido para `#/admin/design/*` e redirecionamento das URLs antigas (§3.1–3.2).
- Sessão expirada nunca desmonta o gerador; `key={idSessao}` é a única exceção ao I-2 (§5.5).
- Identidade é `usuario`, não e-mail; não existe recuperação de senha por autoatendimento — redefinir é ação de administrador (§3.6, §5.3).

---

## 11 · Verificação visual pendente

Não há automação de browser neste projeto; os testes jsdom cobrem lógica, não layout nem contraste. Depois de implementado, o usuário precisa abrir e **olhar**:

1. Em 1920×1080, no Histórico: dá para contar **18 linhas** sem rolar?
2. Em monitor largo, na aba Gerar: o preview fica visível **sem rolar** enquanto se digita o último campo?
3. O `← Voltar` está sempre no mesmo pixel entre telas diferentes, ou a página salta ao navegar?
4. A faixa `Administração` se lê como contexto ou como alerta?
5. Com o formulário preenchido, derrubando a sessão: o diálogo aparece **por cima** e o formulário continua atrás, intacto?
6. O menu de conta abre para dentro da tela nas duas pontas, sem cortar em monitor pequeno?

---
---

# Parte I — implementado em 04/08/2026

Mantida na íntegra no que ainda governa comportamento. A única alteração é o endereço do catálogo (§3.1 da Parte II).

## Preservação do D-005 — a parte que não pode ser lida por alto

```
<App>                                    ← dono do roteador; useRota()
  ├─ 'splash'       → <Splash />
  ├─ 'assunto'      → <SeletorDeAssunto />
  ├─ 'catalogo'     → <Catalogo />        (React.lazy)
  ├─ 'isolado'      → <ExemploIsolado />  (React.lazy)
  ├─ 'desconhecida' → <RotaNaoEncontrada />
  └─ {taxonomiaJaVisitada && (
       <div hidden={rota.nome !== 'taxonomia'}>
         <AplicativoTaxonomia aba={…} />
       </div>
     )}                                  ← NUNCA desmonta depois do primeiro mount
```

| # | Invariante | Por quê |
| --- | --- | --- |
| I-1 | O ramo só **liga**, nunca desliga. Visibilidade só por `hidden`. | Desmontar descarta formulário meio preenchido — regressão do D-005. |
| I-2 | A rota **nunca** entra como `key` de ancestral do ramo. | Forma mais comum de remount acidental; o React destrói a subárvore em silêncio. **Única exceção autorizada: `idSessao` (Parte II §5.5).** |
| I-3 | Dentro de `AplicativoTaxonomia`, o `Gerador` mantém `<div hidden={aba !== 'gerar'}>`. | Preserva o comportamento já testado. |
| I-4 | Nada de `React.lazy`/`Suspense` envolvendo `AplicativoTaxonomia`. | Elimina chance de a fronteira de Suspense re-suspender. |
| I-5 | Esconder só com `hidden` — nunca `display:none` por classe, `visibility` ou `opacity`. | `hidden` remove da árvore de acessibilidade e do foco; os outros não. |
| I-6 | O bump de `versaoDicionario` sai de `trocarAba` e vira `useEffect` comparando `aba` com um `useRef`. | A troca de aba pode vir da URL ou do botão voltar, não só do clique. |
| I-7 | Sair de `#/taxonomia/*` e voltar preserva aba ativa e formulário. | Critério de aceite observável do D-005 sob roteamento. |

Duas escolhas técnicas que não são estilo, documentadas no topo de `roteador.ts`: `useSyncExternalStore` (não `useState` + `hashchange`) e `history.replaceState` para canonização (não `location.hash =`). Há ainda um terceiro achado, registrado no comentário longo de `App.tsx`: os memorandos de rota são `useRef`, não `useState` — `setState` durante o render congela a cópia interna do `useSyncExternalStore` e mata toda navegação de volta.

**Foco e rolagem:** muda a tela → foco em `[data-foco-rota]`, rola ao topo, `document.title` atualizado, anúncio polite. Muda só a aba → **não mexer no foco nem rolar**.

## Splash (`#/`)

Monograma quicando; bloco central é **zona morta geométrica** (o retângulo + `--esp-6` é a parede em que a marca reflete), então o movimento nunca cobre a ação primária — por geometria, não por `z-index`. Hover pausa e fixa o cartão de recomendação em vez de tooltip. Sorteio por baralho Fisher-Yates. Abaixo de 720×560 cai no layout estático.

Acessibilidade dura: WCAG 2.2.2 exige o botão de pausa visível; `prefers-reduced-motion` tem variante estática completa; a marca é `<button>` com nome acessível e alvo ≥ 44×44; troca de cor só na colisão. Movimento por `requestAnimationFrame` com delta de tempo e `translate3d`, limites por `ResizeObserver`, pausa em `visibilitychange`.

Splash pulada para quem já escolheu assunto (`localStorage['mdbd:ultimo-assunto']`), revertível pela constante `SEMPRE_MOSTRAR_SPLASH`.

## Seletor de assunto (`#/assunto`)

Rota própria em tela cheia, não modal — é nó de navegação, não tarefa interruptiva; sem modal não há focus trap escrito à mão. Cartões indisponíveis usam `aria-disabled` (não `disabled` nativo, que os tiraria do Tab), `cursor: default` (não `not-allowed`, que acusa o usuário de um erro que ele não cometeu), sem hover, sem toast ao ativar, e **sem `opacity: 0.5`** (derrubaria o texto abaixo de 4.5:1).

## Catálogo de interface (`#/admin/design/*`)

Rótulo na UI é `Catálogo de interface` — a página não administra nada. Uma seção por rota. Nav lateral sticky com `aria-current="page"`.

`<MostraExemplo>`: controles `Largura / Zoom / Fundo / Abrir ⧉`, régua de largura ao vivo, nota de "o que observar". Controle global com sobrescrita local. `ErrorBoundary` por exemplo, para que um exemplo quebrado não apague a página. `src/admin/design/**` não pode importar `src/api.ts`.

> A ressalva que decide a honestidade da página: um `<div>` de largura fixa **não é um viewport**. Por isso o design system usa `@container` e layout intrínseco, e `@media` fica reservado a `prefers-reduced-motion`, `prefers-contrast`, `forced-colors` e print.

Badge de contraste calculado na seção `Fundação`. A suspeita registrada na época se confirmou: `--texto-fraco: #9ca3af` sobre `--card` dava 2.54:1. Corrigido **no token**, não nos componentes — `--texto-suave` foi para `#5b6270` (6.05:1) e `--texto-fraco` para `#6b7280` (4.82:1).
