[CmdletBinding()]
param(
    [string]$BackendBaseUrl = "https://launch-desk-backend-6gtyc6yuoq-de.a.run.app",
    [string]$FrontendUrl = "https://launch-desk-orcin.vercel.app",
    [string]$Python = "python",
    [string]$VercelDeploymentUrl = "",
    [string]$ExpectedVercelCommitSha = "",
    [string]$VercelTeamId = $env:VERCEL_TEAM_ID,
    [string]$VercelTeamSlug = $env:VERCEL_TEAM_SLUG,
    [switch]$SkipBackendStream,
    [switch]$SkipFrontendPage,
    [switch]$SkipVercelDeployment,
    [switch]$RequireVercelDeploymentMetadata,
    [switch]$OpenBrowser,
    [switch]$RequireBrowserConfirmation
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendBaseUrl = $BackendBaseUrl.TrimEnd("/")
$FrontendUrl = $FrontendUrl.TrimEnd("/")
$BackendStreamUrl = "$BackendBaseUrl/api/launch-desk/stream"
$ExpectedApiHost = ([System.Uri]$BackendBaseUrl).Host
if ([string]::IsNullOrWhiteSpace($VercelDeploymentUrl)) {
    $VercelDeploymentUrl = $FrontendUrl
}

function Invoke-LaunchDeskStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Push-Location $RepoRoot
try {
    Write-Host "Launch Desk post-deploy verification"
    Write-Host "Backend:  $BackendBaseUrl"
    Write-Host "Frontend: $FrontendUrl"

    if (-not $SkipBackendStream) {
        Invoke-LaunchDeskStep "Backend streamed API verification" {
            & $Python "scripts\verify_launch_desk_stream.py" --url $BackendStreamUrl
        }
    }

    if (-not $SkipFrontendPage) {
        Invoke-LaunchDeskStep "Frontend deployed page verification" {
            & $Python "scripts\verify_launch_desk_frontend_page.py" `
                --url $FrontendUrl `
                --expected-api-host $ExpectedApiHost
        }
    }

    if (-not $SkipVercelDeployment) {
        if ([string]::IsNullOrWhiteSpace($ExpectedVercelCommitSha)) {
            $ExpectedVercelCommitSha = (& git rev-parse HEAD 2>$null)
            if ($LASTEXITCODE -ne 0) {
                $ExpectedVercelCommitSha = ""
            }
        }

        Invoke-LaunchDeskStep "Vercel deployment metadata verification" {
            $vercelArgs = @(
                "scripts\verify_launch_desk_vercel_deployment.py",
                "--deployment-url",
                $VercelDeploymentUrl,
                "--expected-state",
                "READY"
            )
            if (-not [string]::IsNullOrWhiteSpace($ExpectedVercelCommitSha)) {
                $vercelArgs += @("--expected-commit", $ExpectedVercelCommitSha.Trim())
            }
            if (-not [string]::IsNullOrWhiteSpace($VercelTeamId)) {
                $vercelArgs += @("--team-id", $VercelTeamId)
            }
            if (-not [string]::IsNullOrWhiteSpace($VercelTeamSlug)) {
                $vercelArgs += @("--team-slug", $VercelTeamSlug)
            }
            if ($RequireVercelDeploymentMetadata) {
                $vercelArgs += "--required"
            }
            & $Python @vercelArgs
        }
    }

    Write-Host ""
    Write-Host "Browser verification checklist"
    Write-Host "- Open: $FrontendUrl"
    Write-Host "- Confirm the API badge shows: $ExpectedApiHost"
    Write-Host "- Click 'Load sample'."
    Write-Host "- Click 'Run launch plan'."
    Write-Host "- Confirm the Agent stream reaches 'Complete'."
    Write-Host "- Confirm tool calls and completions appear for all five Launch Desk tools."
    Write-Host "- Confirm the generated plan contains 'Prioritized plan'."
    Write-Host "- Confirm readiness shows a percentage and no visible error is displayed."
    Write-Host "- Check browser console for app-domain warnings/errors if this is a release gate."

    if ($OpenBrowser) {
        Start-Process $FrontendUrl
    }

    if ($RequireBrowserConfirmation) {
        $answer = Read-Host "Type PASS after completing the browser checklist"
        if ($answer -ne "PASS") {
            throw "Browser checklist was not confirmed."
        }
    }

    Write-Host ""
    Write-Host "Launch Desk post-deploy verification completed."
} finally {
    Pop-Location
}
