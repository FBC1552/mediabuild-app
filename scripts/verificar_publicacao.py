#!/usr/bin/env python3
"""Trava de publicação: falha se o repositório contiver algo que não deve ficar público.

Uso:
    python scripts/verificar_publicacao.py [pasta]          # pasta padrão: raiz do repo
    PUBLICACAO_BLOQUEIO=/caminho/termos.txt python scripts/verificar_publicacao.py

Três camadas:
  1. Arquivos que nunca entram: artefatos do dbt, dados tabulares, dumps, segredos.
  2. Padrões de conteúdo: chaves, credenciais em URL, CPF/CNPJ, hosts internos, SQL do dbt.
  3. Termos locais (empresa, clientes, schemas) lidos de um arquivo FORA do repositório,
     um termo por linha, para que a própria lista de bloqueio não vaze o que protege.
     Procura em $PUBLICACAO_BLOQUEIO e, se ausente, em ../.bloqueio-local.txt.

Nunca imprime o valor encontrado — só arquivo, linha e regra. Sai com código 1 se achar algo.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PASTAS_IGNORADAS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}

# (1) Nomes e extensões que nunca entram.
NOMES_PROIBIDOS = {
    "dbt_project.yml", "profiles.yml", "manifest.json", "run_results.json",
    "catalog.json", "sources.json", "semantic_manifest.json", "packages.yml",
    "package-lock.yml", "dbt.log", "credentials.json", "service-account.json",
}
PASTAS_PROIBIDAS = {"target", "dbt_packages", "dbt_modules", "seeds", "snapshots", "analyses", "macros"}
EXTENSOES_PROIBIDAS = {
    ".csv", ".tsv", ".parquet", ".avro", ".feather", ".xlsx", ".xls", ".xlsm",
    ".dump", ".bak", ".7z", ".zip", ".gz", ".tar", ".sqlite", ".sqlite3", ".db",
    ".duckdb", ".hc", ".pem", ".key", ".pfx", ".p12", ".docx", ".pdf", ".ofx",
}
# Permitidos mesmo com extensão ou nome acima.
PERMITIDOS = {".env.example"}

# (2) Padrões de conteúdo.
REGRAS = [
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("chave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("chave de API", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[A-Za-z0-9-]{10,})\b")),
    ("credencial em URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:(?!\$|\{|<|%|senha|password|exemplo|example|mdbd\b)[^\s@'\"/]{4,}@[^\s'\"]+")),
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
    ("IP interno", re.compile(r"\b(10\.\d{1,3}|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")),
    ("host de banco gerenciado", re.compile(r"\b[\w.-]+\.(database\.windows\.net|rds\.amazonaws\.com|redshift\.amazonaws\.com|snowflakecomputing\.com|bigquery\.googleapis\.com)\b")),
    ("jinja do dbt", re.compile(r"\{\{\s*(ref|source|config|var)\s*\(")),
    ("schema de camada analítica", re.compile(r"\banalytics_(gold|silver|bronze|staging|marts?)\b|\b(gold|silver|bronze|staging|marts?)\.(fct|dim|stg|int)_\w+")),
    ("modelo dbt (fct_/dim_/stg_)", re.compile(r"\b(fct|dim|stg|int)_[a-z][a-z0-9_]{3,}\b")),
    ("caminho local de usuário", re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s]+|/(Users|home)/[a-z][\w.-]+/")),
]
EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+\.)+[a-z]{2,}\b", re.IGNORECASE)
DOMINIOS_EMAIL_OK = {"exemplo.com", "example.com", "exemplo.com.br", "noreply@anthropic.com", "users.noreply.github.com"}
TAMANHO_MAX = 2_000_000


def carregar_termos_locais(raiz: Path) -> list[re.Pattern[str]]:
    caminho = os.environ.get("PUBLICACAO_BLOQUEIO")
    candidatos = [Path(caminho)] if caminho else [raiz.resolve().parent / ".bloqueio-local.txt"]
    for c in candidatos:
        if c.is_file():
            termos = [t.strip() for t in c.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
            return [re.compile(re.escape(t), re.IGNORECASE) for t in termos]
    return []


def arquivos(raiz: Path):
    for atual, pastas, nomes in os.walk(raiz):
        pastas[:] = [p for p in pastas if p not in PASTAS_IGNORADAS]
        for nome in nomes:
            yield Path(atual) / nome


def main() -> int:
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
    termos = carregar_termos_locais(raiz)
    excecoes = raiz / ".publicacao-permitidos"
    sql_permitidos = (
        {l.strip() for l in excecoes.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
        if excecoes.is_file() else set()
    )
    achados: list[str] = []

    este = Path(__file__).resolve()
    for arq in arquivos(raiz):
        if arq.resolve() == este:
            continue
        rel = arq.relative_to(raiz).as_posix()
        nome, ext = arq.name, arq.suffix.lower()
        if nome in PERMITIDOS:
            continue
        partes = set(arq.relative_to(raiz).parts[:-1])
        if nome.lower() in NOMES_PROIBIDOS:
            achados.append(f"{rel}: arquivo proibido (artefato dbt/credencial)")
            continue
        if partes & PASTAS_PROIBIDAS:
            achados.append(f"{rel}: pasta proibida ({', '.join(sorted(partes & PASTAS_PROIBIDAS))})")
            continue
        if ext in EXTENSOES_PROIBIDAS or (nome == ".env" or (nome.startswith(".env.") and nome != ".env.example")):
            achados.append(f"{rel}: tipo de arquivo proibido ({ext or nome})")
            continue
        if ext == ".sql" and rel not in sql_permitidos:
            achados.append(f"{rel}: arquivo .sql — revise à mão e, se for público, liste o caminho em .publicacao-permitidos")
            continue
        if arq.stat().st_size > TAMANHO_MAX or arq.name == "package-lock.json":
            continue
        try:
            texto = arq.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, linha in enumerate(texto.splitlines(), 1):
            for rotulo, padrao in REGRAS:
                m = padrao.search(linha)
                # ${VAR:-padrao} é interpolação de compose/shell, não credencial literal
                if m and not (rotulo == "credencial em URL" and "{" in m.group(0)):
                    achados.append(f"{rel}:{n}: {rotulo}")
            for m in EMAIL.finditer(linha):
                if not any(m.group(0).lower().endswith(d) for d in DOMINIOS_EMAIL_OK):
                    achados.append(f"{rel}:{n}: e-mail")
            for t in termos:
                if t.search(linha):
                    achados.append(f"{rel}:{n}: termo bloqueado localmente")

    if achados:
        print(f"BLOQUEADO: {len(achados)} achado(s). Nada foi impresso além de arquivo:linha:regra.")
        for a in achados[:200]:
            print("  " + a)
        if len(achados) > 200:
            print(f"  ... e mais {len(achados) - 200}")
        return 1
    aviso = "" if termos else " (sem lista local de termos: só as regras genéricas rodaram)"
    print(f"OK: nenhum achado em {raiz}{aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
