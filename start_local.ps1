$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$LogRoot = Join-Path $ProjectRoot "logs"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogRoot "local-$Timestamp.log"

Set-Location -LiteralPath $ProjectRoot
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$LogWriter = New-Object System.IO.StreamWriter($LogPath, $true, (New-Object System.Text.UTF8Encoding($false)))
$LogWriter.AutoFlush = $true
$Processes = @()

function Write-CombinedLog {
    param([string]$Source, [string]$Line)
    if ($null -eq $Line) { return }
    $rendered = "[{0}] {1}" -f $Source, $Line
    Write-Host $rendered
    $script:LogWriter.WriteLine(("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $rendered))
}

function Assert-PortFree {
    param([int]$Port)
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $pids = ($listener | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
        throw "端口 $Port 已被占用（PID: $pids）。请先停止旧的本地服务。"
    }
}

function Start-LoggedProcess {
    param(
        [string]$Name,
        [string]$FileName,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $FileName
    $info.Arguments = $Arguments
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($key in $Environment.Keys) {
        $info.EnvironmentVariables[$key] = [string]$Environment[$key]
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    if (-not $process.Start()) {
        throw "无法启动 $Name"
    }
    $entry = [pscustomobject]@{
        Name = $Name
        Process = $process
        Streams = @(
            [pscustomobject]@{ Reader = $process.StandardOutput; Task = $process.StandardOutput.ReadLineAsync() },
            [pscustomobject]@{ Reader = $process.StandardError; Task = $process.StandardError.ReadLineAsync() }
        )
    }
    $script:Processes += $entry
    Write-CombinedLog $Name "已启动，PID=$($process.Id)"
    return $entry
}

function Stop-ProcessTree {
    param($Entry)
    if ($null -eq $Entry -or $Entry.Process.HasExited) { return }
    Write-CombinedLog $Entry.Name "正在停止 PID=$($Entry.Process.Id) ..."
    & taskkill.exe /PID $Entry.Process.Id /T /F 2>&1 | ForEach-Object {
        Write-CombinedLog $Entry.Name ([string]$_)
    }
}

try {
    $python = (Get-Command python -ErrorAction Stop).Source
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    Assert-PortFree 8080
    Assert-PortFree 3000

    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".deps_installed"))) {
        Write-CombinedLog "setup" "正在安装 Python 依赖..."
        & $python -m pip install --find-links=wheels -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Python 依赖安装失败" }
        Set-Content -LiteralPath (Join-Path $ProjectRoot ".deps_installed") -Value "installed" -Encoding ASCII
    }

    if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
        Write-CombinedLog "setup" "正在安装前端依赖..."
        Push-Location $FrontendRoot
        try {
            & $npm ci
            if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败" }
        } finally {
            Pop-Location
        }
    }

    Write-CombinedLog "setup" "初始化本地用户和工作空间..."
    & $python -m synth_engine.admin create localtest 2>&1 | ForEach-Object {
        Write-CombinedLog "setup" ([string]$_)
    }
    if ($LASTEXITCODE -ne 0) { throw "本地用户初始化失败" }

    $backend = Start-LoggedProcess `
        -Name "backend" `
        -FileName $python `
        -Arguments "-m uvicorn synth_engine.api.main:app --host 127.0.0.1 --port 8080 --log-level info" `
        -WorkingDirectory $ProjectRoot `
        -Environment @{ SYNTH_DEV_USER = "localtest" }

    $frontend = Start-LoggedProcess `
        -Name "frontend" `
        -FileName $npm `
        -Arguments "run dev -- --host 127.0.0.1 --port 3000" `
        -WorkingDirectory $FrontendRoot

    Write-CombinedLog "system" "本地网站启动中：http://127.0.0.1:3000/synth/"
    Write-CombinedLog "system" "完整日志文件：$LogPath"
    Write-CombinedLog "system" "按 Ctrl+C 同时停止前端和后端"

    while ($true) {
        $receivedOutput = $false
        foreach ($entry in $Processes) {
            foreach ($stream in $entry.Streams) {
                if ($stream.Task.IsCompleted) {
                    $line = $stream.Task.GetAwaiter().GetResult()
                    if ($null -ne $line) {
                        Write-CombinedLog $entry.Name $line
                        $stream.Task = $stream.Reader.ReadLineAsync()
                        $receivedOutput = $true
                    }
                }
            }
            if ($entry.Process.HasExited) {
                throw "$($entry.Name) 已退出，退出码 $($entry.Process.ExitCode)"
            }
        }
        if (-not $receivedOutput) {
            Start-Sleep -Milliseconds 50
        }
    }
} catch [System.Management.Automation.PipelineStoppedException] {
    # Ctrl+C，交给 finally 统一停止子进程。
} catch {
    Write-CombinedLog "error" $_.Exception.Message
    exit 1
} finally {
    foreach ($entry in $Processes) {
        Stop-ProcessTree $entry
    }
    Write-CombinedLog "system" "本地前端和后端已停止"
    $LogWriter.Dispose()
}
