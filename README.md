# MediaBuild (MDBD)

Gerador de taxonomias (nomenclaturas padronizadas) para campanhas de mídia paga.

Analista escolhe a plataforma, preenche um formulário em cascata (Campanha → Grupo de Anúncio → Anúncio) e o sistema devolve o nome já normalizado, abreviado, validado e com um **match ID** embutido — o código que permite cruzar a nomenclatura com as planilhas de performance de mídia depois.

Aplicação web, **local por enquanto**, conteinerizada desde o início para facilitar a migração futura para nuvem.

## Status

**Todas as fases concluídas** (Fase 7 em 04/08/2026) — stack no Docker, schema com migrations e seed, motor de taxonomia com 100% de cobertura, API REST, interface em três abas, exportação Excel, logs estruturados e backup/restore testados. 163 testes de backend + 29 de frontend.

Falta apenas autenticação, deixada fora do MVP de propósito (D-003) — ver [docs/NUVEM.md](docs/NUVEM.md).

A interface tem três abas:

| Aba | O que faz |
| --- | --- |
| **Gerar** | Formulário em cascata (campanha → grupo → anúncio) com preview ao vivo e download do `.xlsx` |
| **Dicionário** | Cadastro das drop lists — o De → Para de cada categoria |
| **Histórico** | Nomenclaturas geradas, com filtro por data de criação, plataforma, campanha e nível |

- Interface: http://localhost:5173
- API documentada: http://localhost:8000/docs

Interface conferida num navegador real em 04/08/2026.

Nomenclaturas geradas pela API com os dados do seed:

| Nível | Campos | Nome |
| --- | --- | --- |
| Campanha | BF26 · Loja Alfa · Instagram · Conversão · Agosto | `BF26_ALF_METAA_INSTA_CV_AGO_C0969` |
| Grupo | Feminino · 25-34 · Bolsas · Moda · Sudeste · RJ · Remarketing | `F_25-34_BOLSA_MODA_SUD_RJ_RMKT_G0282` |
| Anúncio | Vídeo · 1080x1920 · CPC · fivela · 15s · A | `VID_1080X1920_CPC_FIVELA_15S_A_A0199` |

Cada campo é **drop list** (o valor precisa existir no dicionário) ou **campo livre** com limite próprio de caracteres — exatamente como a planilha de referência define. Alguns são opcionais e simplesmente somem do nome quando ficam em branco.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [docs/DECISOES.md](docs/DECISOES.md) | **Decisões travadas** (nome, stack, auth, imutabilidade, estrutura de campos) |
| [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md) | Spec original |
| [docs/AVALIACAO.md](docs/AVALIACAO.md) | Análise crítica, lacunas e schema proposto |
| [docs/PLANO-EXECUCAO.md](docs/PLANO-EXECUCAO.md) | Plano faseado (Fases 0–7) com critérios de saída |
| [docs/NUVEM.md](docs/NUVEM.md) | Caminho de migração para nuvem e armadilhas conhecidas |

## Stack

| Camada | Escolha |
| --- | --- |
| Backend | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic |
| Banco | PostgreSQL 16 |
| Frontend | React · Vite · TypeScript · React Hook Form + Zod |
| Excel | `openpyxl` |
| Infra local | Docker Compose |

## Arquitetura pretendida

Três contêineres: **PostgreSQL** · **API REST** (FastAPI) · **Frontend** (React + Vite).

O núcleo do sistema é o motor de taxonomia: uma função pura que recebe campos brutos e um template, e devolve a nomenclatura final.

```
campos brutos → template → abreviação → normalização → montagem → validação → nome final
```

## Estrutura

```
MediaBuild/
├── README.md
├── backend/       # FastAPI, motor de taxonomia, migrations
├── frontend/      # React + Vite
├── scripts/       # backup e restore do banco
└── docs/          # decisões, avaliação, plano e caminho de nuvem
```

---

# Runbook

## Subir

```bash
cp .env.example .env
docker compose up --build
```

- Web: http://localhost:5173
- API: http://localhost:8000 — documentação interativa em `/docs`

Se o daemon não responder, o Docker Desktop provavelmente não iniciou junto com o Windows — abra-o antes e dê ~20s.

Conferir que está de pé:

```bash
curl http://localhost:8000/health        # o processo responde
curl http://localhost:8000/health/ready  # a API fala com o Postgres
```

Os dois são separados de propósito: `/health` não depende do banco, para que uma oscilação do Postgres não vire um ciclo de reinícios do container.

## Rodar os testes

```powershell
docker compose exec api python -m pytest tests -q
docker compose exec api python -m pytest tests -q --cov=app.taxonomia --cov-report=term-missing

cd frontend; npm test
```

## Migrations e seed

```bash
docker compose exec api python -m alembic current      # versão aplicada
docker compose exec api python -m alembic upgrade head # aplicar pendentes
docker compose exec api python -m app.seed             # popular o que faltar
docker compose exec api python -m app.seed --reset     # APAGA tudo e repopula
```

O seed é idempotente e **não sobrescreve** termos do dicionário já existentes — o analista pode tê-los ajustado. Quando a estrutura de campos muda, ele cria uma **versão nova** de template em vez de editar a atual, para que o histórico continue explicável (D-004).

## Primeiro acesso (D-014)

A partir do D-014 a API exige login. O **primeiro administrador é criado pelo seed**, a partir de duas variáveis de ambiente:

```bash
ADMIN_LOGIN_INICIAL=admin.mediabuilder   # login, não e-mail
ADMIN_SENHA_INICIAL=<escolha a sua>
```

Escreva a senha real no **`.env`**, que não é versionado. O `.env.example` traz só um placeholder — e com `DEBUG=false` esse placeholder **derruba a aplicação no boot**, de propósito, igual já acontece com a senha de exemplo do banco.

```bash
docker compose exec api python -m app.seed   # cria o admin se ainda não existir
```

O seed **nunca sobrescreve a senha de um usuário que já existe**, nem o papel, nem o `ativo`. Trocar as variáveis depois do primeiro boot não faz nada: rodar o seed é operação corriqueira, e se ele redefinisse a senha, qualquer `python -m app.seed` devolveria o acesso a quem conhecesse o valor antigo. Para trocar a senha, use a API (`PATCH /usuarios/{id}`) ou gere uma provisória (`POST /usuarios/{id}/senha`).

> Depois do primeiro seed, **remova `ADMIN_SENHA_INICIAL` do ambiente**. Ela vira dado morto que dá acesso total — exatamente o tipo de coisa que fica esquecida num arquivo.

Entrar:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"admin.mediabuilder","senha":"..."}' -c cookies.txt
curl http://localhost:8000/auth/eu -b cookies.txt
```

Perdeu o acesso e não sobrou nenhum admin? O sistema impede chegar nesse estado (guarda de último admin), mas se acontecer por edição manual no banco, o caminho é apagar a linha do admin em `usuarios` e rodar o seed de novo.

### Papéis

| Papel | Pode |
| --- | --- |
| `basico` | Gerar taxonomia, ver histórico, usar planos. **Não** vê o dicionário e **não** faz DELETE em lugar nenhum |
| `pleno` | Tudo do produto, incluindo dicionário e remoções |
| `admin` | Tudo, mais `/usuarios` e `/admin/*` |

`/health`, `/health/ready`, `/docs` e `/openapi.json` seguem sem autenticação.

## Backup e restore

```powershell
.\scripts\backup.ps1                    # grava em backups/
.\scripts\backup.ps1 -Manter 30         # preserva os 30 mais recentes

.\scripts\restore.ps1                   # restaura o backup mais recente
.\scripts\restore.ps1 -Arquivo backups\mediabuild-20260804-002342.dump
```

O backup usa `pg_dump -Fc` do banco lógico, não uma cópia do volume: copiar o diretório de dados com o Postgres rodando produz um arquivo que às vezes restaura e às vezes não.

**O restore é destrutivo** — derruba os objetos existentes antes de recriar. Pede confirmação por digitação, a menos que `-Force`.

Testar um restore sem tocar no banco de trabalho, que é como o procedimento foi validado:

```powershell
docker compose exec -T db createdb -U mdbd mediabuild_teste
$env:POSTGRES_DB = "mediabuild_teste"; .\scripts\restore.ps1 -Force
docker compose exec -T db psql -U mdbd -d mediabuild_teste -tAc "SELECT count(*) FROM taxonomias_geradas"
docker compose exec -T db dropdb -U mdbd mediabuild_teste
```

## Logs

```bash
docker compose logs -f api
```

Toda requisição recebe um `request_id`, devolvido no cabeçalho `X-Request-ID` e presente em todas as linhas de log daquela requisição — inclusive nos erros de domínio. Para investigar uma falha relatada por um analista, peça o cabeçalho e filtre por ele.

Em desenvolvimento o formato é texto legível; com `DEBUG=false` vira uma linha JSON por evento. Forçar um ou outro: `LOG_JSON=true|false`.

## Sem Docker

Útil para ciclos rápidos de teste:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# fora do Docker o hostname `db` não resolve — aponte para a porta publicada
$env:DATABASE_URL = "postgresql+psycopg://mdbd:mdbd@localhost:5432/mediabuild"

.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

cd ..\frontend
npm install
npm run dev
```

Sem um Postgres acessível, `/health` responde 200 mas `/health/ready` responde 503 — comportamento esperado, e os testes de banco são pulados.

## Configuração

Tudo por variável de ambiente; ver [.env.example](.env.example) para a lista comentada.

Com `DEBUG=false`, a aplicação **recusa subir** se a senha do banco ainda for a de exemplo, se o CORS apontar para `localhost` ou se `ADMIN_SENHA_INICIAL` ainda for o placeholder do `.env.example`. A falha é no boot, com mensagem explícita, e não em runtime — é o que impede levar configuração de desenvolvimento para um ambiente real sem perceber.

`SESSAO_DURACAO_HORAS` (padrão 12) é o teto da sessão de quem ninguém revogou; a revogação imediata existe à parte, pela administração de usuários (D-014).

`FUSO_HORARIO` (padrão `America/Sao_Paulo`) é o fuso em que os filtros de data do histórico são interpretados. Não é o fuso do servidor: `criado_em` é gravado em UTC e, na nuvem, o servidor tende a estar em UTC — ler o relógio da máquina daria o resultado certo no notebook do analista e errado em produção. Fuso desconhecido também derruba a aplicação no boot.

## Ir para a nuvem

Ver [docs/NUVEM.md](docs/NUVEM.md). A autenticação, que era o item bloqueante, foi resolvida pelo D-014. O que resta antes de expor na internet: **HTTPS obrigatório** (o cookie de sessão sai com `Secure`, e sem TLS o login falha em silêncio), **rate limiting no `/auth/login`** (não existe) e remover `ADMIN_SENHA_INICIAL` do ambiente depois do primeiro seed.
