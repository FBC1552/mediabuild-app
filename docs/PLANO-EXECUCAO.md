# Plano de execução faseado

Do zero ao sistema rodando local. Cada fase tem **critério de saída verificável** — só avança quando fecha.

Estimativa total: **12–18 dias** de trabalho focado. As fases 0–5 formam o MVP utilizável.

Premissas: decisões travadas em [DECISOES.md](DECISOES.md), correções de schema das lacunas 1–8 de [AVALIACAO.md](AVALIACAO.md) incorporadas.

---

## Fase 0 — Fundação e decisões travadas
**~1 dia** · sem dependências

Antes de qualquer código de negócio, fechar as decisões que são caras de reverter.

**Decisões — fechadas em 01/08/2026** (ver [DECISOES.md](DECISOES.md)):

- [x] Nome do produto: **MediaBuild** — D-001
- [x] Stack: Python/FastAPI + PostgreSQL 16 + React/Vite/TS — D-002
- [x] Auth: **depois**; `usuario_id` nullable sem FK — D-003
- [x] Taxonomia exportada é **imutável** — D-004 *(adotada por recomendação; confirmar antes da Fase 2)*

**Scaffolding — feito em 01/08/2026** (commit `f3dfb59`):

- [x] Estrutura do monorepo: `backend/`, `frontend/`, `docs/`
- [x] `docker-compose.yml` com 3 serviços (db, api, web), healthchecks e hot reload nos dois lados
- [x] Backend: FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic, com `GET /health` e `GET /health/ready`
- [x] Frontend: Vite + React + TypeScript, tokens do tema light
- [x] `.env.example` versionado; `.env` no `.gitignore`

**Saída:** `docker compose up` sobe tudo; `GET /health` responde 200; frontend abre sem erro de console; API conecta no Postgres.

### Status da verificação — ✅ Fase 0 concluída em 01/08/2026

| Critério | Status |
| --- | --- |
| `docker compose up` sobe os 3 serviços | ✅ `db` e `api` healthy, `web` up |
| `GET /health` → 200 | ✅ `{"status":"ok","app":"MediaBuild"}` |
| API conecta no Postgres | ✅ `/health/ready` → `{"status":"ok","database":"conectado"}` |
| Frontend responde | ✅ 200 em `localhost:5173` |
| `GET /health/ready` → 503 sem banco, com mensagem útil | ✅ verificado |
| Backend: testes passam | ✅ `pytest` 1/1 |
| Alembic carrega config e `env.py` | ✅ verificado |
| Frontend: typecheck + build | ✅ `tsc -b && vite build` limpo |

**Histórico do bloqueio do Docker** (resolvido): o engine Linux respondia HTTP 500 porque o WSL2 não estava instalado. `wsl --install --no-distribution` habilitou `VirtualMachinePlatform` e `Microsoft-Windows-Subsystem-Linux`, mas o Início Rápido do Windows fazia "desligar/ligar" virar boot híbrido (evento 27, tipo `0x1`), que não ativa componentes pendentes. Só um **Reiniciar** de verdade (tipo `0x0`) resolveu.

---

## Fase 1 — Modelo de dados e migrations
**1–2 dias** · depende de 0

- [x] Implementar o schema proposto em AVALIACAO.md, incluindo `dicionario_abreviacoes`, `templates_taxonomia` e `limites_plataforma`
- [x] Enum `nivel` (`CAMPANHA | GRUPO | ANUNCIO`)
- [x] Constraints: `UNIQUE` em `match_id` de cada nível e em `taxonomias_geradas.nomenclatura_final`
- [x] Alembic: migration inicial, testada up **e** down
- [x] Seed: Meta/Google/TikTok, seus limites por nível, um template inicial por plataforma e 32 abreviações de partida

**Saída:** migration roda limpa em banco vazio; seed popula; consulta SQL percorre a hierarquia completa; `downgrade` volta ao estado zero sem erro.

### Status da verificação — ✅ Fase 1 concluída em 01/08/2026

| Critério | Status |
| --- | --- |
| Migration roda limpa em banco vazio | ✅ `alembic upgrade head` |
| `downgrade` volta ao estado zero | ✅ ciclo `up → down → up` sem erro |
| Seed popula | ✅ 3 plataformas, 9 limites, 9 templates, 32 abreviações |
| Seed é idempotente | ✅ segunda execução cria 0 registros |
| Consulta SQL percorre a hierarquia completa | ✅ `test_consulta_percorre_a_hierarquia_completa` |
| Suíte de testes | ✅ 12/12 |

**Decisões de implementação que valem registro:**

- **Enum criado uma vez só.** O autogenerate do Alembic emitia um `CREATE TYPE nivel` por tabela que usa o enum (3 tabelas), o que falharia na segunda. A migration foi ajustada à mão para criar o tipo no início com `checkfirst` e removê-lo no `downgrade` — sem isso, um novo `upgrade` após `downgrade` falharia.
- **Unicidade do dicionário via dois índices parciais.** No Postgres, `NULL` é distinto de `NULL`, então uma `UNIQUE(plataforma_id, categoria, termo)` deixaria passar duas linhas globais idênticas. Índices separados para `plataforma_id IS NULL` e `IS NOT NULL` resolvem, e ainda permitem que uma abreviação de plataforma sobrescreva a global.
- **`taxonomias_geradas.entidade_id` não tem foreign key.** É polimórfico (aponta para campanha, grupo ou anúncio conforme `nivel`) e, principalmente, apagar a entidade não pode apagar o histórico — o nome já pode estar rodando numa plataforma de anúncios (D-004). Coberto por `test_historico_sobrevive_a_exclusao_da_entidade`.
- **Limites de caracteres do seed não foram conferidos** contra a documentação atual de cada plataforma (Meta 400, Google 255, TikTok 512 são valores plausíveis de partida). Como vivem em dados, corrigir é um `UPDATE`. Vale validar antes de uso real.

---

## Fase 2 — Motor de taxonomia (núcleo)
**2–3 dias** · depende de 1 · **fase mais crítica do projeto**

Módulo puro, sem dependência de banco nem HTTP. É aqui que um bug custa verba de campanha real.

- [x] `normalizar()` — NFD, remove diacríticos, upper, espaço → separador
- [x] `abreviar()` — lookup no dicionário por (categoria, termo); termo ausente é **erro** (D-005)
- [x] `montar()` — percorre tokens do template (literal / campo / match_id)
- [x] `validar()` — `^[A-Z0-9_-]+$` + limite de caracteres do nível
- [x] `gerar_match_id()` — sequencial curto e estável (`C0001`, `G0001`, `A0001`)
- [x] Suíte de testes exaustiva: acentos, cedilha, espaços múltiplos, string vazia, termo fora do dicionário, estouro de limite, caractere especial, template com token desconhecido

**Saída:** tabela de fixtures entrada → nome esperado passando 100%; cobertura do módulo ≥ 90%; nenhum caminho do motor toca o banco.

### Status da verificação — ✅ Fase 2 concluída em 01/08/2026

| Critério | Status |
| --- | --- |
| Fixtures entrada → nome esperado | ✅ 39 testes de motor, sem banco |
| Cobertura do módulo ≥ 90% | ✅ **100%** em `app/taxonomia` (167 statements) |
| Nenhum caminho do motor toca o banco | ✅ `motor.py` não importa SQLAlchemy |
| Motor gera nomes com os dados reais do seed | ✅ 7 testes de integração |
| Ciclo de migrations com as 2 revisões | ✅ `down → up` limpo |
| Suíte completa | ✅ 62/62 |

**Arquitetura resultante:**

```
app/taxonomia/
├── normalizacao.py   NFD, remoção de acentos, RegEx        (puro)
├── erros.py          erros com dados acionáveis para a UI  (puro)
├── tipos.py          Template, tokens tipados, Dicionario  (puro)
├── motor.py          gerar_nomenclatura()                  (puro)
├── match_id.py       sequences do Postgres                 (banco)
└── repositorio.py    carrega template/dicionário/limite    (banco)
```

A separação entre os quatro módulos puros e os dois que tocam o banco é o que
mantém o critério "nenhum caminho do motor toca o banco" verificável, e é o
que vai permitir um importador em lote reusar o motor sem reescrita.

**Nomes gerados com o seed real** (verificados em teste):

| Plataforma / nível | Campos | Nome |
| --- | --- | --- |
| Meta · campanha | objetivo: Conversão | `FB_CV_C0001` |
| Meta · grupo | público: Remarketing, posicionamento: Instagram Stories | `FB_RMKT_IGST_G0001` |
| Google · grupo | público: Lookalike, correspondência: Exata | `GO_LAL_EXT_G0001` |
| TikTok · anúncio | formato: Reels | `TT_RLS_A0001` |

**Decisões de implementação:**

- **Busca no dicionário ignora acento e caixa.** `conversao`, `CONVERSÃO` e `  Conversao  ` encontram o termo cadastrado como `Conversão`. Exigir grafia exata seria um gerador de erro sem propósito.
- **Nada é removido silenciosamente.** Caracteres inválidos não são descartados na normalização — `validar()` reclama deles com mensagem explícita. Sumir com um `&` sem avisar produziria um nome que o analista não reconhece.
- **Colisão não é checada no motor.** Depende do banco; fica na `UNIQUE` de `taxonomias_geradas`, aplicada na persistência (Fase 3).

---

## Fase 3 — API REST
**2–3 dias** · depende de 2

- [x] CRUD: plataformas, campanhas, grupos, anúncios, dicionário, templates
- [x] `POST /taxonomias/preview` — gera **sem** persistir (alimenta o preview ao vivo da Fase 4)
- [x] `POST /taxonomias` — persiste, atribui match ID e `lote_id`
- [x] `GET /taxonomias` — lista com filtro por plataforma, nível e data
- [x] Erros de validação retornando qual campo falhou e por quê (não um 500 genérico)
- [x] OpenAPI/Swagger publicado

**Saída:** fluxo completo (criar plataforma → campanha → grupo → anúncio → gerar) executável pelo Swagger, sem tocar no banco manualmente; violação de unicidade retorna 409, não 500.

### Status da verificação — ✅ Fase 3 concluída em 01/08/2026

Verificado com 24 testes de API **e** por chamadas HTTP reais contra o container.

| Critério | Status |
| --- | --- |
| Fluxo completo pela API | ✅ campanha → `FB_CV_C0448`, grupo → `FB_RMKT_IGST_G0054`, anúncio → `FB_ST_A0026` |
| Unicidade retorna 409, não 500 | ✅ segunda geração da mesma taxonomia |
| Erro diz qual campo falhou | ✅ 422 com `erro`, `campo` e `opcoes` |
| Preview não persiste | ✅ e não consome match ID |
| OpenAPI publicado | ✅ 21 rotas em `/docs` |
| Suíte completa | ✅ 91/91 |

**Decisões de implementação:**

- **Match ID pertence à entidade, não à taxonomia.** É atribuído em `POST /campanhas` e reusado ao gerar o nome. Assim ele é estável: regerar a nomenclatura da mesma campanha não muda o código que aparece nas planilhas de performance.
- **Preview usa placeholder de mesmo tamanho** (`C0000`) quando nenhum match ID é informado. Alocar um ID de verdade a cada tecla digitada queimaria a sequência; o placeholder tem 5 caracteres como um real, então a checagem de limite continua fiel.
- **Taxonomias não têm `PATCH` nem `DELETE`.** A imutabilidade do D-004 é garantida pela ausência das rotas — as tentativas retornam 405, e há teste cobrindo isso.
- **Nova versão de template desativa a anterior, sem apagá-la.** `taxonomias_geradas.template_versao` aponta para versões antigas, e o histórico precisa continuar explicável.
- **Erros do motor viram 422 com código estável** (`termo_desconhecido`, `campo_ausente`, `limite_excedido`, …) para o cliente tratar sem parsear texto; `IntegrityError` vira 409.
- **`GET /taxonomias?plataforma_id=` filtra por subconsulta** de entidades, já que `entidade_id` é polimórfico e sem FK.

---

## Fase 4 — Frontend em cascata
**3–4 dias** · depende de 3

- [x] Design tokens do tema light: fundo `#F8F9FA`, cards `#FFFFFF`, cor de ação `#2563EB`
- [x] Formulário cascata: Plataforma → campos de Campanha → campos de Grupo → campos de Anúncio
- [x] Campos dinâmicos renderizados a partir do template da plataforma (nada hardcoded no front)
- [x] **Preview ao vivo do nome enquanto digita** — o recurso que mais reduz erro do analista
- [x] Erros de validação inline, no campo, em português
- [x] Botão copiar nome individual

**Saída:** um analista monta uma taxonomia completa e copia o nome sem abrir Swagger nem console; nome inválido é impossível de submeter.

### Status da verificação — ⚠️ Fase 4 verificada por teste, **não** no navegador

| Critério | Status |
| --- | --- |
| Cascata: nível abre só quando o anterior fica válido | ✅ teste |
| Campos vêm do template, não hardcoded | ✅ teste |
| Campo com dicionário vira select mostrando De → Para | ✅ teste |
| Preview ao vivo com debounce | ✅ teste |
| Erro do servidor exibido e campo marcado `aria-invalid` | ✅ teste |
| Copiar nome individual e os três juntos | ✅ teste |
| Salvar só habilita com os três níveis válidos | ✅ teste |
| Typecheck + build de produção | ✅ `tsc -b && vite build` |
| Vite serve todos os módulos no container | ✅ HTTP 200 em cada um |
| **Renderização e interação num navegador real** | ✅ conferida pelo usuário em 04/08/2026 |

**Sobre a verificação visual:** nenhuma sessão teve ferramenta de automação de navegador, então os testes com jsdom cobrem a lógica de cascata, os campos dinâmicos, o preview e o tratamento de erro, mas **não** layout, contraste nem responsividade. Isso ficou pendente até 04/08/2026, quando o usuário abriu `http://localhost:5173` já com a Fase 6 no ar e aprovou. Mexidas grandes na camada visual devem ser conferidas por ele de novo, não declaradas verificadas.

**Decisões de implementação:**

- **Desvio consciente do D-002: sem React Hook Form + Zod.** A autoridade de validação é o motor no servidor, e os campos são dinâmicos (derivados do template). Montar schemas Zod em runtime a partir dos templates duplicaria as regras do motor no cliente — exatamente o que as mensagens de erro do D-005 existem para evitar. O formulário usa estado controlado simples, e o servidor continua sendo a única fonte de verdade. Se o formulário crescer em complexidade local, reavaliar.
- **Preview com debounce de 300 ms** e cancelamento da resposta anterior, para não disparar uma requisição por tecla.
- **Campos com dicionário viram `<select>`**, não texto livre: assim o analista não consegue digitar um termo inexistente, e o erro do D-005 vira exceção em vez de rotina.
- **Trocar de plataforma reinicia o formulário**, porque templates e dicionário mudam junto.

---

## Fase 5 — Exportação Excel
**~1 dia** · depende de 4 · **fecha o MVP**

- [x] `GET /taxonomias/export` gerando `.xlsx` via `openpyxl`
- [x] Colunas separadas (plataforma, nível, match ID, cada campo) **mais** a coluna com a nomenclatura final concatenada
- [x] Exportar por lote/sessão ou por filtro
- [x] Cabeçalho congelado e larguras de coluna ajustadas

**Saída:** arquivo abre no Excel sem aviso de corrupção; a coluna de nomenclatura cola direto na plataforma de anúncios.

### Status da verificação — ✅ Fase 5 concluída em 01/08/2026 · **MVP fechado**

| Critério | Status |
| --- | --- |
| Arquivo abre sem corrupção | ✅ baixado da API real e reaberto com `openpyxl` |
| Assinatura de zip válida (`PK`) | ✅ |
| Nomenclatura na **primeira** coluna | ✅ é a que o analista cola |
| Campos dinâmicos em colunas separadas | ✅ Objetivo, Publico, Formato, Posicionamento |
| Filtro por lote e por nível | ✅ |
| Cabeçalho congelado + autofiltro + larguras | ✅ `freeze_panes=A2` |
| Botão "Baixar Excel" na interface | ✅ |
| Suíte | ✅ 103 backend + 12 frontend |

Arquivo real gerado (12 colunas):

```
Nomenclatura | Plataforma | Nível | Nome interno | Match ID | Caracteres
             | Objetivo | Publico | Formato | Posicionamento | Criado em | Lote
FB_CV_C0448        Meta   Campanha          Smoke   C0448   11
FB_RMKT_IGST_G0054 Meta   Grupo de anúncio  G       G0054   18
FB_ST_A0026        Meta   Anúncio           A       A0026   11
```

**Decisões de implementação:**

- **Nomenclatura é a primeira coluna**, antes dos campos que a compõem. É a coluna mais usada; deixá-la no fim obrigaria a rolar horizontalmente a cada cópia.
- **Colunas de campo são descobertas dos dados**, não fixas: a união das chaves de `campos` de todas as linhas, com os campos conhecidos em ordem de prioridade e o resto em ordem alfabética. Uma plataforma nova com campo novo aparece sozinha na planilha.
- **Entidades resolvidas em lote por nível.** `entidade_id` é polimórfico e sem FK, então a junção é feita em código — uma consulta por nível presente, não uma por taxonomia. Há teste contando as consultas para travar isso.
- **Entidade apagada não quebra a exportação:** a linha sai com `(entidade removida)` e a nomenclatura preservada, coerente com o D-004.
- **`/taxonomias/export` é declarada antes de `/taxonomias/{id}`**, senão o FastAPI tentaria interpretar `export` como UUID e devolveria 422.

---

## Fase 6 — Estrutura de campos, histórico e administração
**1–2 dias** · depende de 5

- [x] Estrutura de campos da a planilha de taxonomia de referência: drop list × campo livre, rótulos, opcionais (D-008)
- [x] Tela de histórico: filtro por data de criação, plataforma, campanha, nível e busca no nome
- [x] Reexportar lote anterior (o link de Excel carrega os filtros da tela)
- [x] CRUD do dicionário de abreviações pela UI (sem SQL manual)
- [x] Aplicar a regra de imutabilidade decidida na Fase 0

**Saída:** trabalho de semanas atrás é localizável e reexportável; adicionar abreviação nova não exige desenvolvedor.

### Status da verificação — ✅ Fase 6 concluída em 04/08/2026

| Critério | Status |
| --- | --- |
| Campos por nível conforme a planilha | ✅ 6 na campanha, 7 no grupo, 6 no anúncio |
| Drop list × campo livre com limite próprio | ✅ erro `campo_longo_demais` (422) apontando o campo |
| Campo opcional em branco some do nome | ✅ sem separador duplicado |
| Rótulos vêm do servidor, não do frontend | ✅ `rotulo` no token |
| `interesse_1` e `interesse_2` compartilham vocabulário | ✅ via `categoria` |
| Templates migrados sem tocar no histórico | ✅ v2; 9 versões novas criadas pelo seed |
| Filtro por data / plataforma / campanha | ✅ testado na API real |
| Filtro sobrevive à exclusão da campanha | ✅ colunas denormalizadas (D-009) |
| Histórico sem PATCH nem DELETE | ✅ 405 nas duas |
| Aba de dicionário com criar/editar/remover | ✅ |
| Suíte | ✅ 134 backend + 29 frontend; motor em 100% |

Nomenclaturas geradas pela API real com os dados da planilha:

```
BF26_ALF_METAA_INSTA_CV_AGO_C0969       campanha
F_25-34_BOLSA_MODA_SUD_RJ_RMKT_G0282    grupo de anúncio
VID_1080X1920_CPC_FIVELA_15S_A_A0199    anúncio
```

Planilha exportada: 27 colunas, uma por campo, com rótulos legíveis (`Dimensão do criativo`, `Tipo de compra`) e a nova coluna `Campanha`.

**Decisões de implementação:**

- **O tipo de campo mora no token**, não numa tabela nova. Rótulo, limite, opcionalidade e categoria vieram junto — assim o frontend não precisa de uma tabela de rótulos hardcoded, que era o começo de um acoplamento por plataforma.
- **A sigla da plataforma substitui a coluna "Plataforma" da planilha.** Pedir a plataforma duas vezes na mesma tela permitiria divergir do que o sistema já sabe.
- **Templates novos são versão 2.** É o primeiro uso real do versionamento previsto na Fase 1: o histórico antigo continua explicável, e `sincronizar_templates()` repete a operação sempre que a estrutura mudar.
- **`plataforma_id`/`campanha_id` denormalizados no histórico** (D-009), pelos mesmos dois motivos: custo de consulta e sobrevivência à exclusão da entidade.
- **O gerador fica montado ao trocar de aba.** O fluxo do D-005 é exatamente "erro manda cadastrar termo → vou ao dicionário → volto"; perder o formulário nesse caminho anularia a orientação do erro. Ao sair da aba de dicionário, o gerador recarrega só as drop lists.
- **`ate` vira fim do dia.** A tela manda `2026-08-04`, que o FastAPI lê como meia-noite; sem o ajuste, filtrar "até hoje" esconderia tudo o que foi gerado hoje.
- **A aba de histórico não tem editar nem excluir**, pelo mesmo motivo que a API não tem: é assim que o D-004 é aplicado na interface.

---

## Fase 7 — Robustez e preparo para nuvem
**1–2 dias** · depende de 6

- [x] Config 100% por env var; nenhum segredo no código
- [x] Script de backup/restore do banco Postgres
- [x] README com runbook: subir, resetar seed, rodar testes, fazer backup
- [x] Logging estruturado no backend
- [ ] ~~Auth simples~~ — a Fase 0 decidiu **sem auth no MVP** (D-003); fora do escopo
- [x] Documentar o caminho de migração para nuvem

**Saída:** clone novo → rodando com um comando; restore de backup testado de verdade, não só escrito.

### Status da verificação — ✅ Fase 7 concluída em 04/08/2026

| Critério | Status |
| --- | --- |
| Nenhum segredo no código | ✅ tudo por env var; defaults são de dev |
| Produção recusa valores de exemplo | ✅ falha no boot, inclusive se a senha vier escondida num `DATABASE_URL` inteiro |
| Logs estruturados em JSON | ✅ uma linha por evento, parseável |
| `request_id` correlacionando as linhas | ✅ devolvido em `X-Request-ID`; aceita id vindo de fora |
| Backup gerado | ✅ `pg_dump -Fc`, 26 KB |
| **Restore testado de verdade** | ✅ ver abaixo |
| Runbook no README | ✅ subir, testar, migrar, seed, backup, logs, config |
| Caminho de nuvem documentado | ✅ `docs/NUVEM.md` |
| Suíte | ✅ 163 backend + 29 frontend |

**O restore foi validado de duas formas**, ambas sem tocar no banco de trabalho — restaurando num banco descartável (`mediabuild_restore_test`):

1. **Banco vazio.** Todas as 9 tabelas com contagem idêntica à origem, mais o enum `nivel`, as 3 sequences de match ID, os 2 índices parciais e a versão do Alembic (`a1c4f7e29b03`).
2. **Banco populado** (o caminho `--clean`). Uma linha de lixo foi inserida antes; depois do restore ela sumiu e a contagem voltou a bater com a origem — provando que o restore substitui, não mescla.

**Decisões de implementação:**

- **Config em partes + `DATABASE_URL` opcional com precedência.** O compose já monta as variáveis em partes e um Postgres gerenciado entrega os mesmos campos separados; aceitar a URL inteira cobre o caso da nuvem sem obrigar ninguém a montá-la.
- **A checagem de produção olha o DSN efetivo, não as partes.** Passar `DATABASE_URL=...mdbd:mdbd@...` seria o jeito fácil de furar uma checagem que só olhasse `POSTGRES_PASSWORD`. Há teste para isso.
- **`backend/conftest.py` na raiz define `DEBUG=true`.** Rodar a suíte é desenvolvimento por definição; sem isso, `pytest` num clone sem `.env` bateria na proteção de produção. É `setdefault`, então quem quiser testar contra configuração real só exporta as variáveis.
- **String vazia conta como não definida.** `${LOG_JSON:-}` no compose expande para `""`, que quebraria o parse de `bool | None` e impediria o container de subir.
- **`/health/ready` não devolve mais a exceção crua.** A mensagem do psycopg cita host, porta e usuário, e a rota não tem autenticação. Vai para o log; só aparece na resposta com `DEBUG=true`.
- **Erro de taxonomia é logado em INFO, não ERROR.** O 422 do D-005 é o caminho previsto quando falta termo no dicionário, não falha do sistema — mas fica registrado, porque a frequência por categoria diz quais termos faltam.
- **Backup copia o arquivo em vez de canalizar.** O pipeline do PowerShell decodifica stdout como texto e corromperia o dump binário; o script gera dentro do container e usa `docker compose cp`.
- **O log de acesso do uvicorn é desligado.** O middleware já registra método, rota, status e duração — com o `request_id` junto, que é o que falta no do uvicorn.

---

## Caminho crítico

```
Fase 0 ─→ 1 ─→ 2 ─→ 3 ─→ 4 ─→ 5 ─┬─→ 6 ─→ 7
                                  └─ MVP utilizável aqui
```

A Fase 2 é o gargalo de qualidade: tudo depois dela confia que o motor gera nomes corretos. Não comprima essa fase para ganhar tempo — comprima a 6.

## Fora de escopo (explicitamente)

Registrado para evitar inflação de escopo — o produto **gera nomenclaturas**:

- Integração com API do Meta/Google/TikTok (criar campanha de fato)
- Importação em lote de planilha — mas o motor da Fase 2 já é escrito para suportar isso depois sem reescrita (lacuna 9)
- Dashboard de performance de mídia
- Multi-tenant / múltiplos clientes isolados
