param(
    [string]$Store = "rakuten_1",
    [string]$NodeCode = "",
    [string]$ProjectDir = "C:\price_system",
    [string]$PythonCommand = "py",
    [switch]$Once,
    [switch]$Maximized,
    [switch]$DryRun,
    [switch]$PopupInput,
    [switch]$Configure,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Read-IniFile {
    param([string]$Path)

    $data = @{}
    if (-not (Test-Path $Path)) {
        return $data
    }

    foreach ($line in Get-Content $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#") -or $trimmed.StartsWith(";")) {
            continue
        }

        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -eq 2) {
            $data[$parts[0].Trim()] = $parts[1].Trim()
        }
    }

    return $data
}

function Write-IniFile {
    param(
        [string]$Path,
        [hashtable]$Data
    )

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $lines = @(
        "# Rakuten price update simulator launcher settings",
        "# This file is auto-updated by start_rakuten_price_update_simulator.ps1",
        "Store=$($Data.Store)",
        "NodeCode=$($Data.NodeCode)",
        "ProjectDir=$($Data.ProjectDir)",
        "PythonCommand=$($Data.PythonCommand)"
    )

    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

function Q {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Test-ProcessId {
    param([int]$Id)

    if ($Id -le 0) {
        return $false
    }

    try {
        $null = Get-Process -Id $Id -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Get-LockInfo {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    try {
        return Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Remove-StaleLock {
    param([string]$Path)

    if (Test-Path $Path) {
        Remove-Item -Path $Path -Force
    }
}

function Prompt-String {
    param(
        [string]$Label,
        [string]$CurrentValue
    )

    $value = Read-Host "$Label [$CurrentValue]"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $CurrentValue
    }

    return $value.Trim()
}

function Show-LauncherPrompts {
    param(
        [string]$StoreValue,
        [string]$NodeCodeValue
    )

    $selectedStore = Prompt-String -Label "Store" -CurrentValue $StoreValue
    $selectedNodeCode = Prompt-String -Label "NodeCode" -CurrentValue $NodeCodeValue

    return @{
        Store = $selectedStore
        NodeCode = $selectedNodeCode
    }
}

$iniPath = Join-Path $ProjectDir "config\rakuten_price_simulator.ini"
$lockPath = Join-Path $ProjectDir "config\rakuten_price_simulator.lock.json"
$settings = Read-IniFile -Path $iniPath

if ($settings.ContainsKey("Store") -and -not $PSBoundParameters.ContainsKey("Store")) {
    $Store = $settings.Store
}
if ($settings.ContainsKey("NodeCode") -and -not $PSBoundParameters.ContainsKey("NodeCode")) {
    $NodeCode = $settings.NodeCode
}
if ($settings.ContainsKey("ProjectDir") -and -not $PSBoundParameters.ContainsKey("ProjectDir")) {
    $ProjectDir = $settings.ProjectDir
}
if ($settings.ContainsKey("PythonCommand") -and -not $PSBoundParameters.ContainsKey("PythonCommand")) {
    $PythonCommand = $settings.PythonCommand
}

if ($PopupInput) {
    $inputValues = Show-LauncherPrompts `
        -StoreValue $Store `
        -NodeCodeValue $NodeCode

    $Store = $inputValues.Store
    $NodeCode = $inputValues.NodeCode
}

$shouldPromptLauncherSettings = $Configure -or [string]::IsNullOrWhiteSpace($Store) -or [string]::IsNullOrWhiteSpace($NodeCode)
if ($shouldPromptLauncherSettings -and -not $PopupInput) {
    $inputValues = Show-LauncherPrompts `
        -StoreValue $Store `
        -NodeCodeValue $NodeCode

    $Store = $inputValues.Store
    $NodeCode = $inputValues.NodeCode
}

if ([string]::IsNullOrWhiteSpace($Store)) {
    throw "Store must not be empty."
}

$hostName = $env:COMPUTERNAME
if ([string]::IsNullOrWhiteSpace($hostName)) {
    $hostName = "PC"
}
$workerId = "$hostName-$Store-price-sim"

$scriptsDir = Join-Path $ProjectDir "scripts"
$workerScript = Join-Path $scriptsDir "rakuten_price_update_simulator.py"
$logsDir = Join-Path $ProjectDir "logs\rakuten_price_update_simulator"

if (-not (Test-Path $workerScript)) {
    throw "Worker script not found: $workerScript"
}

$lockInfo = Get-LockInfo -Path $lockPath
if ($lockInfo -and $lockInfo.pid) {
    if (Test-ProcessId -Id ([int]$lockInfo.pid)) {
        if (-not $Force) {
            throw "Rakuten price simulator appears to be running already. Use -Force only if the lock is stale."
        }
    } else {
        Remove-StaleLock -Path $lockPath
    }
}

$newSettings = @{
    Store = $Store
    NodeCode = $NodeCode
    ProjectDir = $ProjectDir
    PythonCommand = $PythonCommand
}
Write-IniFile -Path $iniPath -Data $newSettings

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logsDir ("rakuten_price_simulator_{0}_{1}.log" -f $Store, $timestamp)

$workerArgs = @(
    "--store", $Store
)

if ($Once) {
    $workerArgs += "--once"
}

$workerArgsLiteral = ($workerArgs | ForEach-Object { Q ([string]$_) }) -join ", "

$inner = @"
`$ErrorActionPreference = 'Stop'
`$env:PYTHONIOENCODING = 'utf-8'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONUNBUFFERED = '1'
`$env:PRICE_SYSTEM_NODE_CODE = '$(($NodeCode).Replace("'", "''"))'
`$utf8NoBom = [System.Text.UTF8Encoding]::new(`$false)
[Console]::InputEncoding = `$utf8NoBom
[Console]::OutputEncoding = `$utf8NoBom
`$OutputEncoding = `$utf8NoBom
`$lockPath = '$(($lockPath).Replace("'", "''"))'
`$logPath = '$(($logPath).Replace("'", "''"))'
`$logsDir = '$(($logsDir).Replace("'", "''"))'
`$pythonCommand = '$(($PythonCommand).Replace("'", "''"))'
`$workerScript = '$(($workerScript).Replace("'", "''"))'
`$workerArgs = @($workerArgsLiteral)
Set-Location '$(($scriptsDir).Replace("'", "''"))'
if (-not (Test-Path `$logsDir)) {
    New-Item -ItemType Directory -Path `$logsDir -Force | Out-Null
}
`$lockData = @{
    pid = `$PID
    startedAt = (Get-Date).ToString('s')
    workerId = '$(($workerId).Replace("'", "''"))'
    store = '$(($Store).Replace("'", "''"))'
    logPath = `$logPath
}
`$lockData | ConvertTo-Json | Set-Content -Path `$lockPath -Encoding UTF8
`$commandDisplay = `$pythonCommand + ' -u ' + `$workerScript + ' ' + (`$workerArgs -join ' ')
Write-Host '===== Rakuten price update simulator ====='
Write-Host 'WorkerId:' '$(($workerId).Replace("'", "''"))'
Write-Host 'NodeCode:' '$(($NodeCode).Replace("'", "''"))'
Write-Host 'Command:' `$commandDisplay
Write-Host 'LogPath:' `$logPath
Write-Host ''
try {
    & `$pythonCommand '-u' `$workerScript @workerArgs 2>&1 | Tee-Object -FilePath `$logPath -Append
    `$exitCode = if (`$LASTEXITCODE -ne `$null) { [int]`$LASTEXITCODE } else { 0 }
} finally {
    if (Test-Path `$lockPath) {
        Remove-Item -Path `$lockPath -Force
    }
}
Write-Host ''
Write-Host 'ExitCode:' `$exitCode
Write-Host '===== Rakuten price update simulator stopped. Press Enter to close. ====='
Read-Host
exit `$exitCode
"@

$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
$args = "-NoExit -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded"

Write-Host ""
Write-Host "===== Rakuten price update simulator launcher ====="
Write-Host "mode         : $(if ($Once) { 'SIMULATE ONCE' } else { 'SIMULATE LOOP' })"
Write-Host "workerId     : $workerId"
Write-Host "store        : $Store"
Write-Host "nodeCode     : $(if ([string]::IsNullOrWhiteSpace($NodeCode)) { '<hostname fallback>' } else { $NodeCode })"
Write-Host "configure    : $Configure"
Write-Host "projectDir   : $ProjectDir"
Write-Host "ini          : $iniPath"
Write-Host "lock         : $lockPath"
Write-Host "logPath      : $logPath"
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY-RUN] powershell.exe $args"
    exit 0
}

$windowStyle = if ($Maximized) { "Maximized" } else { "Normal" }
Start-Process -FilePath "powershell.exe" -ArgumentList $args -WorkingDirectory $scriptsDir -WindowStyle $windowStyle

Write-Host "Launch complete."
Write-Host "Saved settings to ini: $iniPath"
Write-Host "Log file: $logPath"
