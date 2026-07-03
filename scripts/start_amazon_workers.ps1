param(
    [string]$Workers = "",
    [int]$Limit = 300,
    [int]$Sleep = 10,
    [int]$PageTimeout = 15000,
    [int]$EmptySleep = 300,
    [string]$WorkerPrefix = "",
    [string]$ProjectDir = "C:\price_system",
    [string]$PythonCommand = "py",
    [switch]$Once,
    [switch]$Maximized,
    [switch]$DryRun,
    [switch]$PopupInput
)

$ErrorActionPreference = "Stop"

function Read-IniFile {
    param([string]$Path)
    $data = @{}
    if (-not (Test-Path $Path)) { return $data }

    foreach ($line in Get-Content $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#") -or $trimmed.StartsWith(";")) { continue }

        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -eq 2) {
            $data[$parts[0].Trim()] = $parts[1].Trim()
        }
    }

    return $data
}

function Write-IniFile {
    param([string]$Path, [hashtable]$Data)

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $lines = @(
        "# Amazon worker launcher settings",
        "# This file is auto-updated by start_amazon_workers.ps1",
        "LastWorkers=$($Data.LastWorkers)",
        "Limit=$($Data.Limit)",
        "Sleep=$($Data.Sleep)",
        "PageTimeout=$($Data.PageTimeout)",
        "EmptySleep=$($Data.EmptySleep)",
        "WorkerPrefix=$($Data.WorkerPrefix)",
        "ProjectDir=$($Data.ProjectDir)",
        "PythonCommand=$($Data.PythonCommand)"
    )

    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

function Parse-WorkerSpec {
    param([string]$Spec)

    $result = New-Object System.Collections.Generic.List[int]
    $items = $Spec.Split(",", [System.StringSplitOptions]::RemoveEmptyEntries)

    foreach ($raw in $items) {
        $item = $raw.Trim()

        if ($item -match "^\d+$") {
            $result.Add([int]$item)
            continue
        }

        if ($item -match "^(\d+)\s*-\s*(\d+)$") {
            $start = [int]$Matches[1]
            $end = [int]$Matches[2]

            if ($start -gt $end) {
                throw "Invalid worker range: $item"
            }

            for ($i = $start; $i -le $end; $i++) {
                $result.Add($i)
            }
            continue
        }

        throw "Invalid worker spec: '$item'. Use examples like 1-3, 4-6, 2, or 1,3,5."
    }

    $unique = $result | Sort-Object -Unique
    if (-not $unique -or $unique.Count -eq 0) {
        throw "No workers specified."
    }

    return $unique
}

function Q {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Show-WorkerInputBox {
    param([string]$DefaultValue)

    try {
        Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction Stop
        $message = "Enter worker numbers.`r`n`r`nExamples:`r`n  1-3 = worker1,2,3`r`n  4-6 = worker4,5,6`r`n  2   = worker2`r`n  1,3 = worker1,3"
        $title = "Amazon worker launcher"
        return [Microsoft.VisualBasic.Interaction]::InputBox($message, $title, $DefaultValue)
    } catch {
        Write-Host "Popup input failed. Falling back to console input."
        return (Read-Host "Enter worker numbers. Examples: 1-3 / 4-6 / 2")
    }
}

$iniPath = Join-Path $ProjectDir "config\amazon_worker_launcher.ini"
$settings = Read-IniFile -Path $iniPath

if ([string]::IsNullOrWhiteSpace($Workers) -and $settings.ContainsKey("LastWorkers")) {
    $Workers = $settings.LastWorkers
}
if ($settings.ContainsKey("Limit") -and -not $PSBoundParameters.ContainsKey("Limit")) {
    $Limit = [int]$settings.Limit
}
if ($settings.ContainsKey("Sleep") -and -not $PSBoundParameters.ContainsKey("Sleep")) {
    $Sleep = [int]$settings.Sleep
}
if ($settings.ContainsKey("PageTimeout") -and -not $PSBoundParameters.ContainsKey("PageTimeout")) {
    $PageTimeout = [int]$settings.PageTimeout
}
if ($settings.ContainsKey("EmptySleep") -and -not $PSBoundParameters.ContainsKey("EmptySleep")) {
    $EmptySleep = [int]$settings.EmptySleep
}
if ([string]::IsNullOrWhiteSpace($WorkerPrefix) -and $settings.ContainsKey("WorkerPrefix")) {
    $WorkerPrefix = $settings.WorkerPrefix
}
if ($settings.ContainsKey("ProjectDir") -and -not $PSBoundParameters.ContainsKey("ProjectDir")) {
    $ProjectDir = $settings.ProjectDir
}
if ($settings.ContainsKey("PythonCommand") -and -not $PSBoundParameters.ContainsKey("PythonCommand")) {
    $PythonCommand = $settings.PythonCommand
}

$iniPath = Join-Path $ProjectDir "config\amazon_worker_launcher.ini"

if ([string]::IsNullOrWhiteSpace($WorkerPrefix)) {
    $WorkerPrefix = $env:COMPUTERNAME
    if ([string]::IsNullOrWhiteSpace($WorkerPrefix)) {
        $WorkerPrefix = "PC"
    }
}

if ($PopupInput) {
    $defaultWorkers = $Workers
    if ([string]::IsNullOrWhiteSpace($defaultWorkers)) {
        $defaultWorkers = "1-3"
    }

    $inputValue = Show-WorkerInputBox -DefaultValue $defaultWorkers

    if ([string]::IsNullOrWhiteSpace($inputValue)) {
        Write-Host "Worker input is empty. Canceled."
        exit 0
    }

    $Workers = $inputValue.Trim()
}

if ([string]::IsNullOrWhiteSpace($Workers)) {
    $Workers = Read-Host "Enter worker numbers. Examples: 1-3 / 4-6 / 2"
}

$workerNumbers = Parse-WorkerSpec -Spec $Workers
$scriptsDir = Join-Path $ProjectDir "scripts"
$workerScript = Join-Path $scriptsDir "amazon_check_worker_loop.py"

if (-not (Test-Path $workerScript)) {
    throw "Worker script not found: $workerScript"
}

$newSettings = @{
    LastWorkers = $Workers
    Limit = $Limit
    Sleep = $Sleep
    PageTimeout = $PageTimeout
    EmptySleep = $EmptySleep
    WorkerPrefix = $WorkerPrefix
    ProjectDir = $ProjectDir
    PythonCommand = $PythonCommand
}
Write-IniFile -Path $iniPath -Data $newSettings

Write-Host ""
Write-Host "===== Amazon workers launcher ====="
Write-Host "workers      : $Workers"
Write-Host "worker nums  : $($workerNumbers -join ', ')"
Write-Host "workerPrefix : $WorkerPrefix"
Write-Host "limit        : $Limit"
Write-Host "sleep        : $Sleep"
Write-Host "pageTimeout  : $PageTimeout"
Write-Host "emptySleep   : $EmptySleep"
Write-Host "projectDir   : $ProjectDir"
Write-Host "ini          : $iniPath"
Write-Host ""

foreach ($num in $workerNumbers) {
    $workerId = "$WorkerPrefix-worker$num"

    $command = "& " + (Q $PythonCommand) + " " + (Q $workerScript) +
        " --worker-id " + (Q $workerId) +
        " --limit $Limit" +
        " --sleep $Sleep" +
        " --page-timeout $PageTimeout" +
        " --empty-sleep $EmptySleep"

    if ($Once) {
        $command += " --once"
    }

    $inner = @"
Set-Location '$($scriptsDir.Replace("'", "''"))'
Write-Host '===== $workerId ====='
Write-Host 'Command: $command'
Write-Host ''
$command
Write-Host ''
Write-Host '===== $workerId stopped. Press Enter to close. ====='
Read-Host
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
    $args = "-NoExit -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded"

    Write-Host "Starting $workerId..."

    if ($DryRun) {
        Write-Host "[DRY-RUN] powershell.exe $args"
    } else {
        $windowStyle = if ($Maximized) { "Maximized" } else { "Normal" }
        Start-Process -FilePath "powershell.exe" -ArgumentList $args -WorkingDirectory $scriptsDir -WindowStyle $windowStyle
        Start-Sleep -Milliseconds 500
    }
}

Write-Host ""
Write-Host "Launch complete."
Write-Host "Saved settings to ini: $iniPath"
