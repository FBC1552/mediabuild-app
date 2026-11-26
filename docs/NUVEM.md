# Caminho de migração para nuvem

O MediaBuild roda local por decisão, não por limitação. Este documento
registra o que já está pronto para a mudança, o que falta, e em que ordem
fazer — para que a migração seja uma tarde de trabalho e não um projeto.

Nada aqui precisa ser feito agora. É um mapa, não um plano em execução.

---

## O que já está pronto

| Item | Onde |
| --- | --- |
| Aplicação conteinerizada | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| Configuração 100% por variável de ambiente | `backend/app/config.py` |
| Recusa a subir em produção com valores de exemplo | `Settings._recusar_defaults_de_desenvolvimento` |
| Schema versionado em migrations | `backend/alembic/versions/` |
| Logs estruturados em JSON com `request_id` | `backend/app/logs.py` |
| Liveness e readiness separados | `/health` e `/health/ready` |
| Backup e restore testados | `scripts/backup.ps1`, `scripts/restore.ps1` |
| Autenticação, papéis e trilha de acesso | `backend/app/autorizacao.py`, D-014 |
| Registro de erro consultável por API | `eventos_erro`, `GET /admin/erros` |

A separação entre `/health` e `/health/ready` importa mais na nuvem do que
aqui: orquestradores reiniciam o container quando o **liveness** falha. Se
ele dependesse do banco, uma oscilação do Postgres viraria um ciclo de
reinícios que só piora a situação.

---

## Ordem sugerida

### 1. Banco gerenciado
Trocar o container `db` por um Postgres gerenciado (RDS, Cloud SQL,
Neon, Supabase). Não há nada de exótico no schema: enum nativo, JSONB,
índices parciais e três sequences — tudo Postgres padrão.

Só é preciso definir `DATABASE_URL` com a URL do provedor; ela tem
precedência sobre as partes `POSTGRES_*`. Confirmar que a string exige TLS
(`?sslmode=require` na maioria dos provedores).

A migração dos dados é o `scripts/backup.ps1` seguido de um `pg_restore`
apontando para o novo host.

### 2. Segredos fora do arquivo
Hoje a senha vive no `.env`, que não é versionado. Na nuvem ela deve vir
do gerenciador de segredos do provedor, injetada como variável de
ambiente. Nenhuma mudança de código é necessária — é o motivo de a
configuração ser toda por env var.

Com `DEBUG=false`, esquecer de trocar a senha derruba a aplicação no boot,
com mensagem explícita. É intencional: falhar alto é melhor que subir
exposto.

### 3. Imagens num registry
Hoje as imagens são construídas na máquina. Publicar em GHCR, ECR ou
Artifact Registry, com tag por commit, e trocar `build:` por `image:` no
compose de produção.

Dois ajustes necessários nos Dockerfiles atuais, que hoje são de
desenvolvimento:

- **Backend:** tirar o `--reload` do uvicorn e o bind mount `./backend:/app`.
- **Frontend:** hoje serve pelo dev server do Vite. Em produção deve ser
  `npm run build` e servir os arquivos estáticos por nginx ou por uma CDN.

### 4. Proxy reverso e TLS
Um nginx ou Caddy na frente, terminando TLS e roteando `/api` para o
backend e o resto para os estáticos do frontend.

Ajustar `CORS_ORIGINS` para o domínio real — com `DEBUG=false`, deixar
`localhost` ali também derruba o boot.

### 5. Autenticação — ✅ feita (D-014)
Existe: sessão opaca em cookie HttpOnly, senha com `hashlib.scrypt`, três
papéis (`basico` / `pleno` / `admin`) e trilha de acesso em
`eventos_acesso`. **Deixou de ser o item bloqueante desta lista.**

Restaram três coisas presas a ela, e as três são de infraestrutura, não de
produto:

**a) HTTPS virou obrigatório, não recomendado.** O cookie de sessão sai com
`Secure` sempre que `DEBUG=false` — que é a configuração de qualquer
ambiente real. Navegador **descarta** cookie `Secure` vindo por `http://`,
então subir sem TLS não dá erro: dá um login que aparentemente funciona e
não mantém ninguém logado. Sintoma péssimo de diagnosticar. Isso amarra
esta seção ao passo 4 (proxy reverso e TLS), que passa a ser
pré-requisito e não paralelo.

**b) Rate limiting no login não existe.** Localmente é irrelevante — quem
está na máquina já está dentro. Exposto na internet, é o buraco óbvio:
`POST /auth/login` aceita tentativas ilimitadas, e os ~47 ms de scrypt por
tentativa são o único freio. Isso é atrito, não defesa.

O caminho mais barato é o proxy reverso do passo 4 (nginx `limit_req` ou o
equivalente do Caddy), por IP, no caminho `/auth/login`. Fazer no
aplicativo exigiria estado compartilhado entre réplicas — problema que o
proxy já resolve. A trilha para calibrar o limite já está pronta:
`GET /admin/resumo` devolve a taxa de falha de login por dia, e
`eventos_acesso` guarda IP e user-agent de cada tentativa.

Bloqueio progressivo por conta (após N falhas) foi considerado e **não**
implementado: sem rate limiting por IP antes, ele vira negação de serviço
contra usuário legítimo — basta errar a senha de alguém de propósito para
trancá-lo fora.

**c) Rotação de segredo.** Não há segredo de assinatura a rotacionar — é o
efeito colateral bom de sessão opaca em vez de JWT (D-014): não existe
chave que, vazada, forje sessões. O que existe para rotacionar é:

- **`ADMIN_SENHA_INICIAL`**, que só é lida pelo `python -m app.seed` na
  criação do primeiro admin. Depois disso ela é dado morto na configuração
  — e dado morto que dá acesso total é exatamente o que fica esquecido num
  arquivo. **Remova a variável do ambiente depois do primeiro seed.** O seed
  nunca sobrescreve a senha de um admin existente, então tirá-la não quebra
  nada.
- **As sessões**, cujo teto é `SESSAO_DURACAO_HORAS` (12 por padrão).
  Revogação imediata já existe pela tela de administração.
- **A senha do banco**, junto do passo 2.

### 6. Backup automático
Os scripts atuais são manuais. Na nuvem, usar o snapshot automático do
banco gerenciado — e **testar o restore**, que é a parte que costuma não
existir. O `restore.ps1` documenta o procedimento; a versão gerenciada
muda a origem do arquivo, não o resto.

---

## O que **não** muda

- O motor de taxonomia é função pura, sem I/O. Não tem consciência de onde
  roda.
- Templates e dicionário vivem em dados. Mudar padrão de nomenclatura
  continua sendo `UPDATE`, não deploy.
- As migrations sobem o schema do zero num banco vazio, o que torna
  provisionar um ambiente novo um comando só.

---

## Armadilhas conhecidas

- **O enum `nivel` e o autogenerate do Alembic.** O autogenerate emite um
  `CREATE TYPE` por tabela que usa o enum e nunca o remove no downgrade.
  Toda migration que mexer nele precisa do mesmo conserto manual de
  `84339e0f86c0`. Revisar migration autogerada antes de aplicar — isso
  fica mais caro num ambiente onde não dá para simplesmente recriar o banco.
- **Sequences de match ID não são reiniciáveis à toa.** Restaurar um backup
  antigo por cima de um banco atual pode fazer a sequence repetir códigos
  já usados numa plataforma de anúncios. O `pg_restore` traz o valor da
  sequence junto com o dump, o que resolve o caso normal — mas vale
  conferir `SELECT last_value FROM seq_match_campanha` depois de um
  restore parcial.
- **`taxonomias_geradas` não tem FK de propósito** (D-004, D-009). Nenhuma
  ferramenta de "limpeza de órfãos" deve ser apontada para essa tabela:
  linha sem entidade correspondente é o comportamento correto, não sujeira.
  **`eventos_acesso` e `eventos_erro` estão na mesma situação** (D-014): a
  trilha de acesso sobrevive à exclusão do usuário de propósito, e apagar
  "órfãos" ali é apagar exatamente o rastro de quem foi removido.
- **Cookie `Secure` e TLS.** Ver o passo 5b: sem HTTPS o login falha em
  silêncio, sem mensagem de erro nenhuma. É a armadilha mais provável de
  toda esta lista.
