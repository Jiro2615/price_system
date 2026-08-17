param(
    [string]$PythonCommand = "py",
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return Split-Path -Parent $PSScriptRoot
}

$repoRoot = Get-RepoRoot
$venvPath = Join-Path $repoRoot $VenvDir
$requirementsPath = Join-Path $repoRoot "requirements.txt"
$envPath = Join-Path (Split-Path -Parent $repoRoot) ".env"

if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "requirements.txt not found: $requirementsPath"
}

Write-Host "Worker PC setup guide"
Write-Host "  repo_root         : $repoRoot"
Write-Host "  python_command    : $PythonCommand"
Write-Host "  venv_path         : $venvPath"
Write-Host ""
Write-Host "Run the following commands in PowerShell:"
Write-Host ""
Write-Host "cd $repoRoot"
Write-Host "$PythonCommand -m venv $VenvDir"
Write-Host ".\$VenvDir\Scripts\Activate.ps1"
Write-Host "python -m pip install --upgrade pip"
Write-Host "python -m pip install -r requirements.txt"
Write-Host "playwright install chromium"
Write-Host ""

if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Host "Create the shared configuration file:"
    Write-Host "New-Item -ItemType File -Path $envPath"
    Write-Host ""
}

Write-Host "Then edit $envPath and set at least:"
Write-Host "  PRICE_SYSTEM_DB_HOST"
Write-Host "  PRICE_SYSTEM_DB_PORT"
Write-Host "  PRICE_SYSTEM_DB_NAME"
Write-Host "  PRICE_SYSTEM_DB_USER"
Write-Host "  PRICE_SYSTEM_DB_PASSWORD"
Write-Host ""
Write-Host "Initial verification commands:"
Write-Host "cd $repoRoot\scripts"
Write-Host "python test_db_connection.py"
Write-Host "python price_check_from_db.py --limit 1 --summary --use-stats --worker-id worker-pc-test"
