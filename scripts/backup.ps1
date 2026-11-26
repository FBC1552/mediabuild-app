<#
.SYNOPSIS
    Backup do banco do MediaBuild.

.DESCRIPTION
    Roda `pg_dump` dentro do container do Postgres e grava um arquivo
    comprimido em backups/. Usa o formato custom (-Fc) e não SQL puro:
    é menor, e o `pg_restore` consegue restaurar em paralelo e recriar o
    schema do zero.

    Faz o dump do banco lógico, não uma cópia do volume. Copiar o
    diretório de dados com o Postgres rodando produz um backup que às
    vezes restaura e às vezes não.

.PARAMETER Destino
    Pasta onde gravar. Padrão: backups/ na raiz do repositório.

.PARAMETER Manter
    Quantos backups preservar; os mais antigos são apagados. Padrão: 10.

.EXAMPLE
    .\scripts\backup.ps1
    .\scripts\backup.ps1 -Destino D:\backups -Manter 30
#>
[CmdletBinding()]
param(
    [string]$Destino,
    [int]$Manter = 10
)

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
if (-not $Destino) { $Destino = Join-Path $raiz "backups" }

# Mesmos defaults do docker-compose.yml.
$usuario = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "mdbd" }
$banco = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "mediabuild" }

if (-not (Test-Path $Destino)) {
    New-Item -ItemType Directory -Path $Destino -Force | Out-Null
}

Push-Location $raiz
try {
    $estado = docker compose ps --status running --services 2>$null
    if ($estado -notcontains "db") {
        throw "O container 'db' nao esta rodando. Suba com: docker compose up -d db"
    }

    $carimbo = Get-Date -Format "yyyyMMdd-HHmmss"
    $arquivo = Join-Path $Destino "mediabuild-$carimbo.dump"
    $noContainer = "/tmp/mediabuild-$carimbo.dump"

    Write-Host "Gerando backup de '$banco'..."
    # Grava dentro do container e copia depois, em vez de canalizar a saida
    # binaria: o pipeline do PowerShell decodifica stdout como texto e
    # corromperia o dump.
    docker compose exec -T db pg_dump -U $usuario -d $banco -Fc -f $noContainer
    if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou com codigo $LASTEXITCODE" }

    try {
        docker compose cp "db:$noContainer" $arquivo
        if ($LASTEXITCODE -ne 0) { throw "falha ao copiar o dump do container" }
    }
    finally {
        docker compose exec -T db rm -f $noContainer 2>$null | Out-Null
    }

    $tamanho = (Get-Item $arquivo).Length
    if ($tamanho -lt 1024) {
        Remove-Item $arquivo
        throw "Backup saiu com $tamanho bytes - pequeno demais para ser valido. Arquivo descartado."
    }

    "{0}  ({1:N0} KB)" -f $arquivo, ($tamanho / 1KB) | Write-Host -ForegroundColor Green

    $antigos = Get-ChildItem $Destino -Filter "mediabuild-*.dump" |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip $Manter
    foreach ($velho in $antigos) {
        Write-Host "removendo backup antigo: $($velho.Name)"
        Remove-Item $velho.FullName
    }
}
finally {
    Pop-Location
}
