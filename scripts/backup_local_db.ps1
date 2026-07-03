param(
    [string]$OutputDir = "",
    [string]$PgDumpPath = "pg_dump"
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

    $secure = Read-Host "DB password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$repoRoot = Get-RepoRoot
$envPath = Join-Path $repoRoot ".env"
$dotEnv = Read-DotEnvFile -Path $envPath

$dbHost = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_HOST", "DB_HOST")
if (-not $dbHost) { $dbHost = "localhost" }

$dbPort = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_PORT", "DB_PORT")
if (-not $dbPort) { $dbPort = "5432" }

$dbName = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_NAME", "DB_NAME")
if (-not $dbName) { $dbName = "price_system" }

$dbUser = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_USER", "DB_USER")
if (-not $dbUser) { $dbUser = "price_app" }

$dbPassword = Get-EnvFirst -DotEnv $dotEnv -Names @("PRICE_SYSTEM_DB_PASSWORD", "DB_PASSWORD", "PGPASSWORD")
$dbPassword = Read-PasswordIfNeeded -CurrentPassword $dbPassword

if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "backup"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpPath = Join-Path $OutputDir "$dbName`_$timestamp.dump"

Write-Host "Local DB backup start"
Write-Host "  host      : $dbHost"
Write-Host "  port      : $dbPort"
Write-Host "  dbname    : $dbName"
Write-Host "  user      : $dbUser"
Write-Host "  output    : $dumpPath"

$arguments = @(
    "-h", $dbHost,
    "-p", $dbPort,
    "-U", $dbUser,
    "-d", $dbName,
    "-F", "c",
    "-f", $dumpPath
)

try {
    $env:PGPASSWORD = $dbPassword
    & $PgDumpPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "Local DB backup complete"
Write-Host "  dump_path : $dumpPath"
