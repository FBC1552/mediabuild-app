<#
.SYNOPSIS
    Restaura um backup do MediaBuild.

.DESCRIPTION
    Recria o schema a partir de um arquivo gerado pelo backup.ps1.

    ATENCAO: e destrutivo. O --clean do pg_restore derruba os objetos
    existentes antes de recriar. Pede confirmacao, a menos que -Force.

.PARAMETER Arquivo
    Caminho do .dump. Sem isso, usa o mais recente de backups/.

.PARAMETER Force
    Pula a confirmacao. Para uso em script.

.EXAMPLE
    .\scripts\restore.ps1
    .\scripts\restore.ps1 -Arquivo backups\mediabuild-20260804-231500.dump -Force
#>
[CmdletBinding()]
param(
    [string]$Arquivo,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$usuario = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "mdbd" }
$banco = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "mediabuild" }

if (-not $Arquivo) {
    $recente = Get-ChildItem (Join-Path $raiz "backups") -Filter "mediabuild-*.dump" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $recente) { throw "Nenhum backup encontrado em backups/. Informe -Arquivo." }
    $Arquivo = $recente.FullName
}

if (-not (Test-Path $Arquivo)) { throw "Arquivo nao encontrado: $Arquivo" }
$Arquivo = (Resolve-Path $Arquivo).Path

Push-Location $raiz
try {
    $estado = docker compose ps --status running --services 2>$null
    if ($estado -notcontains "db") {
        throw "O container 'db' nao esta rodando. Suba com: docker compose up -d db"
    }

    Write-Host "Restaurar '$banco' a partir de:" -ForegroundColor Yellow
    Write-Host "  $Arquivo"
    Write-Host "Isso APAGA os dados atuais do banco." -ForegroundColor Yellow

    if (-not $Force) {
        $resposta = Read-Host "Digite 'restaurar' para confirmar"
        if ($resposta -ne "restaurar") { Write-Host "Cancelado."; return }
    }

    # Copia para dentro do container em vez de canalizar: o pipeline do
    # PowerShell trata stdin como texto e corromperia o dump binario.
    $noContainer = "/tmp/restore-" + [guid]::NewGuid().ToString("N") + ".dump"
    docker compose cp $Arquivo "db:$noContainer"
    if ($LASTEXITCODE -ne 0) { throw "falha ao copiar o dump para o container" }

    try {
        # --clean --if-exists: derruba o que existe sem falhar quando nao
        # existe (banco vazio). --no-owner: o dono no destino pode diferir.
        docker compose exec -T db pg_restore -U $usuario -d $banco `
            --clean --if-exists --no-owner $noContainer
    }
    finally {
        docker compose exec -T db rm -f $noContainer 2>$null | Out-Null
    }

    # pg_restore devolve 1 tambem por avisos benignos ("nao existe" no
    # --clean de um banco vazio). A validacao real e a consulta abaixo.
    $contagem = docker compose exec -T db psql -U $usuario -d $banco -tAc `
        "SELECT count(*) FROM taxonomias_geradas"
    if ($LASTEXITCODE -ne 0) { throw "Banco inacessivel apos o restore." }

    Write-Host "Restaurado. $($contagem.Trim()) taxonomias no historico." -ForegroundColor Green
    Write-Host "Confira tambem: docker compose exec api python -m alembic current"
}
finally {
    Pop-Location
}
