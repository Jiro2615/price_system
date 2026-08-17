param(
    [string]$DbName = "",
    [string]$PsqlPath = "psql",
    [string]$DbHost = "",
    [string]$DbPort = "",
    [string]$DbUser = "",
    [string]$DbPassword = ""
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Read-DotEnvFile {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed) { continue }
        if ($trimmed.StartsWith("#")) { continue }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) { continue }
        $values[$parts[0].Trim()] = $parts[1].Trim()
    }

    return $values
}

function Get-EnvFirst {
    param(
        [hashtable]$DotEnv,
        [string[]]$Names
    )

    foreach ($name in $Names) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value.Trim()
        }
        if ($DotEnv.ContainsKey($name) -and -not [string]::IsNullOrWhiteSpace($DotEnv[$name])) {
            return $DotEnv[$name].Trim()
        }
    }

    return ""
}

function Read-PasswordIfNeeded {
    param([string]$CurrentPassword)

    if (-not [string]::IsNullOrWhiteSpace($CurrentPassword)) {
        return $CurrentPassword
    }

    $secure = Read-Host "QNAP DB password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$repoRoot = Get-RepoRoot
$envPath = Join-Path (Split-Path -Parent $repoRoot) ".env"
$dotEnv = Read-DotEnvFile -Path $envPath

if (-not $DbHost) {
    $DbHost = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_HOST", "DB_HOST")
}
if (-not $DbPort) {
    $DbPort = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_PORT", "DB_PORT")
}
if (-not $DbName) {
    $DbName = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_NAME", "DB_NAME")
}
if (-not $DbUser) {
    $DbUser = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_USER", "DB_USER")
}
if (-not $DbPassword) {
    $DbPassword = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_PASSWORD", "DB_PASSWORD", "PGPASSWORD")
}

if (-not $DbHost) { throw "DB host is empty. Set PRICE_SYSTEM_DB_HOST or pass -DbHost." }
if (-not $DbPort) { $DbPort = "5432" }
if (-not $DbName) { $DbName = "price_system_migrate_test" }
if (-not $DbUser) { $DbUser = "price_app" }
$DbPassword = Read-PasswordIfNeeded -CurrentPassword $DbPassword

$sql = @"
SELECT 'amazon_products' AS table_name, COUNT(*) AS row_count FROM amazon_products
UNION ALL
SELECT 'store_products' AS table_name, COUNT(*) AS row_count FROM store_products
UNION ALL
SELECT 'amazon_check_stats' AS table_name, COUNT(*) AS row_count FROM amazon_check_stats;

SELECT COUNT(*) AS processing_count
FROM amazon_check_stats
WHERE status = 'processing';

SELECT id, worker_id, claimed_count, checked_count, success_count, system_error_count, business_ng_count, page_reset_count, started_at, finished_at
FROM amazon_check_worker_runs
ORDER BY id DESC
LIMIT 10;
"@

Write-Host "QNAP DB check start"
Write-Host "  host      : $DbHost"
Write-Host "  port      : $DbPort"
Write-Host "  dbname    : $DbName"
Write-Host "  user      : $DbUser"

$arguments = @(
    "-h", $DbHost,
    "-p", $DbPort,
    "-U", $DbUser,
    "-d", $DbName,
    "-c", $sql
)

try {
    $env:PGPASSWORD = $DbPassword
    & $PsqlPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "QNAP DB check complete"
