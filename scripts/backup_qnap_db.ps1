param(
    [string]$OutputDir = "",
    [string]$PgDumpPath = "pg_dump",
    [int]$RetentionDays = 14,
    [string]$DbHost = "",
    [string]$DbPort = "",
    [string]$DbName = "",
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

function Remove-OldDumpFiles {
    param(
        [string]$TargetDir,
        [int]$KeepDays
    )

    if ($KeepDays -lt 0) {
        return 0
    }

    if (-not (Test-Path -LiteralPath $TargetDir)) {
        return 0
    }

    $cutoff = (Get-Date).AddDays(-1 * $KeepDays)
    $removed = 0

    Get-ChildItem -LiteralPath $TargetDir -Filter *.dump -File | ForEach-Object {
        if ($_.LastWriteTime -lt $cutoff) {
            Remove-Item -LiteralPath $_.FullName -Force
            $removed += 1
        }
    }

    return $removed
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
if (-not $DbName) { $DbName = "price_system" }
if (-not $DbUser) { $DbUser = "price_app" }
if ($RetentionDays -lt 0) { throw "RetentionDays must be 0 or greater." }
$DbPassword = Read-PasswordIfNeeded -CurrentPassword $DbPassword

if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "backup\qnap"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$removedCount = Remove-OldDumpFiles -TargetDir $OutputDir -KeepDays $RetentionDays

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpPath = Join-Path $OutputDir "$DbName`_$timestamp.dump"

Write-Host "QNAP DB backup start"
Write-Host "  host      : $DbHost"
Write-Host "  port      : $DbPort"
Write-Host "  dbname    : $DbName"
Write-Host "  user      : $DbUser"
Write-Host "  output    : $dumpPath"
Write-Host "  retention : $RetentionDays days"
Write-Host "  removed   : $removedCount"

$arguments = @(
    "-h", $DbHost,
    "-p", $DbPort,
    "-U", $DbUser,
    "-d", $DbName,
    "-F", "c",
    "-f", $dumpPath
)

try {
    $env:PGPASSWORD = $DbPassword
    & $PgDumpPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "QNAP DB backup complete"
Write-Host "  dump_path : $dumpPath"
