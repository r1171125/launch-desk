param(
    [string]$BackendUrl = "http://127.0.0.1:5057",
    [int]$BackendPort = 5057,
    [int]$FrontendPort = 3008,
    [switch]$StartServers,
    [switch]$SkipLiveStream,
    [string]$PythonPath = ".codex_tmpdeps\openai_agents",
    [string]$NodePath = "C:\Program Files\nodejs\node.exe"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $root "launch-desk-frontend"
$logDir = Join-Path $root ".launch_desk_logs"
$frontendNextCli = Join-Path $frontendDir "node_modules\next\dist\bin\next"
$workspaceNextCli = Join-Path $root "node_modules\next\dist\bin\next"
$parentNextCli = Join-Path (Split-Path -Parent $root) "node_modules\next\dist\bin\next"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "== $Name ==" -ForegroundColor Cyan
    & $Command
}

function Invoke-Native {
    param(
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code $LASTEXITCODE."
    }
}

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $result = Invoke-RestMethod -Uri "$Url/api/launch-desk/health" -TimeoutSec 3
            if ($result.ok) {
                return $result
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    } while ((Get-Date) -lt $deadline)

    throw "Launch Desk backend did not become healthy at $Url within $TimeoutSeconds seconds."
}

if (-not (Test-Path $frontendDir)) {
    throw "Missing Launch Desk frontend directory: $frontendDir"
}

if (-not (Test-Path $NodePath)) {
    $NodePath = "node"
}

function Resolve-NextCli {
    if (Test-Path $frontendNextCli) {
        return $frontendNextCli
    }
    if (Test-Path $workspaceNextCli) {
        return $workspaceNextCli
    }
    if (Test-Path $parentNextCli) {
        return $parentNextCli
    }
    throw "Could not find Next.js CLI. Run npm install from launch-desk-frontend or install Next in a parent workspace node_modules."
}

$nextCli = Resolve-NextCli

if ((Test-Path (Join-Path $root $PythonPath)) -and -not $env:PYTHONPATH) {
    $env:PYTHONPATH = $PythonPath
}

Invoke-Step "Python syntax check" {
    Invoke-Native {
        python -m py_compile `
            launch_desk\agent.py `
            launch_desk\wsgi.py `
            launch_desk\routes.py `
            scripts\verify_launch_desk_stream.py `
            scripts\verify_launch_desk_frontend_page.py `
            tests\test_launch_desk_agent_contract.py `
            tests\test_launch_desk_routes.py `
            tests\test_launch_desk_post_deploy_verifiers.py
    }
}

Invoke-Step "Launch Desk unit tests" {
    Invoke-Native {
        python -m pytest `
            tests\test_launch_desk_tools.py `
            tests\test_launch_desk_routes.py `
            tests\test_launch_desk_agent_contract.py `
            tests\test_launch_desk_post_deploy_verifiers.py
    }
}

Invoke-Step "Launch Desk frontend build" {
    Push-Location $frontendDir
    try {
        Invoke-Native {
            & $NodePath $nextCli build
        }
    } finally {
        Pop-Location
    }
}

if ($StartServers) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $env:LAUNCH_DESK_BACKEND_PORT = [string]$BackendPort
    $env:NEXT_PUBLIC_LAUNCH_DESK_API_BASE = $BackendUrl

    Invoke-Step "Start Launch Desk backend" {
        Start-Process `
            -FilePath "python" `
            -ArgumentList @("scripts\run_launch_desk_backend.py", "--port", [string]$BackendPort) `
            -WorkingDirectory $root `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir "backend.out.log") `
            -RedirectStandardError (Join-Path $logDir "backend.err.log") | Out-Null
    }

    Invoke-Step "Start Launch Desk frontend" {
        Start-Process `
            -FilePath $NodePath `
            -ArgumentList @($nextCli, "dev", "-p", [string]$FrontendPort) `
            -WorkingDirectory $frontendDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir "frontend_$FrontendPort.out.log") `
            -RedirectStandardError (Join-Path $logDir "frontend_$FrontendPort.err.log") | Out-Null
    }
}

if (-not $SkipLiveStream) {
    if (-not $env:OPENAI_API_KEY) {
        throw "OPENAI_API_KEY is required for live streamed verification. Set it or pass -SkipLiveStream."
    }

    Invoke-Step "Launch Desk health" {
        $health = Wait-ForHealth -Url $BackendUrl
        $health | ConvertTo-Json -Depth 5
    }

    Invoke-Step "Live streamed API verification" {
        Invoke-Native {
            python scripts\verify_launch_desk_stream.py --url "$BackendUrl/api/launch-desk/stream"
        }
    }
} else {
    Write-Host ""
    Write-Host "Skipped live streamed API verification." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Launch Desk local verification completed." -ForegroundColor Green
