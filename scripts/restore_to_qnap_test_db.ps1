param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [string]$TargetDbName = "price_system_migrate_test",
    [string]$PgRestorePath = "pg_restore",
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

if (-not (Test-Path -LiteralPath $DumpPath)) {
    throw "Dump file not found: $DumpPath"
}

$repoRoot = Get-RepoRoot
$envPath = Join-Path $repoRoot ".env"
$dotEnv = Read-DotEnvFile -Path $envPath

if (-not $DbHost) {
    $DbHost = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_HOST", "DB_HOST")
}
if (-not $DbPort) {
    $DbPort = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_PORT", "DB_PORT")
}
if (-not $DbUser) {
    $DbUser = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_USER", "DB_USER")
}
if (-not $DbPassword) {
    $DbPassword = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_PASSWORD", "DB_PASSWORD", "PGPASSWORD")
}

if (-not $DbHost) { throw "DB host is empty. Set PRICE_SYSTEM_DB_HOST or pass -DbHost." }
if (-not $DbPort) { $DbPort = "5432" }
if (-not $DbUser) { $DbUser = "price_app" }
$DbPassword = Read-PasswordIfNeeded -CurrentPassword $DbPassword

Write-Host "Restore to QNAP test DB start"
Write-Host "  host        : $DbHost"
Write-Host "  port        : $DbPort"
Write-Host "  dbname      : $TargetDbName"
Write-Host "  user        : $DbUser"
Write-Host "  dump_path   : $DumpPath"

$arguments = @(
    "-h", $DbHost,
    "-p", $DbPort,
    "-U", $DbUser,
    "-d", $TargetDbName,
    $DumpPath
)

try {
    $env:PGPASSWORD = $DbPassword
    & $PgRestorePath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "Restore to QNAP test DB complete"
