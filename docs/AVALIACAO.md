# Avaliação da especificação

Análise crítica de [ESPECIFICACAO.md](ESPECIFICACAO.md). O objetivo aqui é separar o que já está bem resolvido do que vai custar caro se não for decidido **antes** de escrever código.

## O que está bem resolvido

| Ponto | Por quê |
| --- | --- |
| Docker desde o dia zero | Correto para o plano "local agora, nuvem depois". A migração vira troca de env vars + Postgres gerenciado. |
| Hierarquia Plataforma → Campanha → Grupo → Anúncio | Espelha o modelo real de Meta/Google/TikTok. Não force nada diferente disso. |
| JSONB para campos dinâmicos | Escolha pragmática certa. Evita uma migration por campo novo de plataforma. |
| Match IDs concatenados no nome | É a decisão mais valiosa da spec: é o que permite cruzar nomenclatura com planilha de performance depois. |
| Validação por RegEx + separador padrão | Necessário. Nome inválido só aparece quando o analista cola na plataforma — tarde demais. |

## Lacunas que precisam de decisão

Ordenadas por custo de correção tardia.

### 1. O dicionário de abreviações não existe no schema — CRÍTICO

A seção 3 descreve o "De → Para" como peça central, mas a seção 2 não tem tabela para ele. Sem isso, as abreviações viram constantes no código e cada termo novo exige deploy.

**Proposta:** tabela `dicionario_abreviacoes` com `categoria` (objetivo/publico/formato/posicionamento) + `termo` + `abreviacao`, opcionalmente escopada por plataforma (`plataforma_id` nulo = global).

### 2. O padrão de nomenclatura está hardcoded em colunas — CRÍTICO

`sigla_objetivo`, `sigla_publico`, `sigla_formato` como colunas fixas assume que **toda** plataforma usa exatamente esses campos, nessa ordem. Não usa. E cada cliente/conta costuma querer uma ordem própria.

Isso é contraditório com a própria spec, que já pede campos dinâmicos via JSONB.

**Proposta:** tabela `templates_taxonomia` que define a sequência ordenada de tokens por (plataforma, nível):

```json
{ "separador": "_",
  "tokens": [ {"tipo":"literal","valor":"FB"},
              {"tipo":"campo","chave":"objetivo"},
              {"tipo":"campo","chave":"publico"},
              {"tipo":"match_id"} ] }
```

Sem isso, mudar o padrão de nomes = migration + redeploy. Com isso, é um `UPDATE`.

### 3. `limite_caracteres` está no lugar errado

Está em `Plataformas`, mas o limite varia **por nível**: no Meta, nome de campanha e nome de anúncio têm limites diferentes; no Google idem.

**Proposta:** mover para `limites_plataforma (plataforma_id, nivel, limite_caracteres)`.

### 4. O que fazer com acentos não está definido

A RegEx `^[a-zA-Z0-9_-]+$` **rejeita** "Conversão". Mas rejeitar e devolver erro é hostil: o analista digitou certo em português.

**Proposta:** normalizar antes de validar — `NFD` → remove diacríticos → maiúsculas → espaço vira separador. "Conversão" vira `CONVERSAO` sozinho. A RegEx passa a ser rede de segurança, não porta de entrada.

### 5. Nada garante que a nomenclatura final seja única

Se duas campanhas geram o mesmo nome, o cruzamento com a planilha de performance quebra silenciosamente — que é exatamente o problema que os match IDs existem para resolver.

**Proposta:** `UNIQUE` em `taxonomias_geradas.nomenclatura_final` + erro explícito na geração. O match ID no template já torna colisão improvável, mas "improvável" não é garantia.

### 6. Não há regra de imutabilidade / reedição

Pergunta não respondida pela spec: se o analista editar o objetivo de uma campanha **depois** que o nome já foi exportado e subiu no Meta, o nome muda?

Se mudar, o histórico de performance descola. Recomendo: taxonomia exportada é imutável; edição gera nova versão com novo match ID. Precisa ser decidido antes da Fase 2.

> ✅ **Resolvido** — [D-004](DECISOES.md): imutável.

### 7. `id` vs `id_banco_match` estão ambíguos

A spec tem os dois sem distinguir claramente. Definir:
- `id` — UUID, chave primária interna, nunca aparece no nome.
- `match_id` — código curto, legível, único e **estável** (`C0001`, `G0001`, `A0001`), esse sim entra na nomenclatura.

### 8. `usuario_id` aponta para uma tabela que não existe

Sendo local e (aparentemente) single-user no início, a decisão razoável é **não** construir auth agora e deixar a coluna nula, criando `usuarios` só quando for multiusuário. Mas isso deve ser uma escolha consciente, não um esquecimento.

> ✅ **Resolvido** — [D-003](DECISOES.md): auth depois; coluna nullable sem FK.

### 9. Exportação é só de ida

Analista de mídia vive em planilha. Mais cedo ou mais tarde vai querer **importar** um lote em vez de digitar campanha por campanha. Não é escopo do MVP, mas o motor deve ser escrito como função pura (entrada → nome) para que o import reuse a mesma lógica depois, sem reescrita.

### 10. Nome do produto está inconsistente

A spec chama de **"o nome de trabalho anterior"**; o projeto foi criado como **MediaBuild (MDBD)**. Decidir qual é o nome do produto na UI antes da Fase 4.

> ✅ **Resolvido** — [D-001](DECISOES.md): o nome é **MediaBuild**.

## Schema proposto (consolidando as correções)

```
plataformas            id, nome, sigla, ativo
limites_plataforma     id, plataforma_id → plataformas, nivel, limite_caracteres
                       UNIQUE (plataforma_id, nivel)
templates_taxonomia    id, plataforma_id, nivel, separador, tokens JSONB, versao, ativo
                       UNIQUE (plataforma_id, nivel, versao)
dicionario_abreviacoes id, plataforma_id NULL, categoria, termo, abreviacao
                       UNIQUE (plataforma_id, categoria, termo)

campanhas              id, plataforma_id, nome_interno, match_id UNIQUE, campos JSONB, criado_em
grupos_anuncio         id, campanha_id, nome_interno, match_id UNIQUE, campos JSONB, criado_em
anuncios               id, grupo_anuncio_id, nome_interno, match_id UNIQUE, campos JSONB, criado_em

taxonomias_geradas     id, nivel, entidade_id, nomenclatura_final UNIQUE,
                       template_versao, lote_id, usuario_id NULL, criado_em
```

`nivel` é um enum: `CAMPANHA | GRUPO | ANUNCIO`.

## Pipeline do motor de taxonomia

```
campos brutos
  → 1. resolve template (plataforma + nivel)
  → 2. percorre tokens ordenados (literal | campo | match_id)
  → 3. abrevia via dicionário (categoria + termo → sigla)
  → 4. normaliza (NFD, remove acentos, upper, espaço → separador)
  → 5. monta (join com separador)
  → 6. valida (^[A-Z0-9_-]+$ e limite do nível)
  → 7. checa colisão
  → nomenclatura_final
```

Os passos 1–6 devem ser **função pura**, sem dependência de banco nem de HTTP. É o que torna o motor testável de forma exaustiva e reutilizável por um futuro importador em lote.

## Recomendação de stack

> ✅ **Aceita e travada** — [D-002](DECISOES.md). A tabela abaixo é o registro do raciocínio; a versão canônica está em DECISOES.md.

A spec deixou em aberto. Recomendação:

| Camada | Escolha | Motivo |
| --- | --- | --- |
| Backend | **Python + FastAPI** | Pydantic modela as regras de validação da taxonomia quase literalmente; OpenAPI sai de graça; `openpyxl` é o caminho mais maduro para `.xlsx`. |
| ORM/Migrations | SQLAlchemy + Alembic | Migrations versionadas desde a Fase 1. |
| Banco | PostgreSQL 16 | Já definido na spec; JSONB é requisito. |
| Frontend | React + Vite + TypeScript | Formulário em cascata com validação é o caso de uso central; React Hook Form + Zod resolvem bem. |

Node/NestJS era alternativa legítima — foi descartada em D-002 e não deve ser reaberta.

## Riscos

| Risco | Mitigação |
| --- | --- |
| Nome errado sobe em campanha real e queima verba | Fase 2 (motor) com cobertura de teste alta antes de existir UI. Preview ao vivo na Fase 4. |
| Padrão de nomenclatura muda depois do go-live | Templates versionados em tabela (lacuna 2), não em código. |
| Limites de caracteres das plataformas mudam | Estão em dados (`limites_plataforma`), não em constantes. |
| Escopo inflar para "gerenciador de campanhas" | O produto gera **nomes**. Não integra com API de anúncios. Manter isso explícito. |
