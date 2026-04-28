param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$Region = "asia-east1",
    [string]$ServiceName = "launch-desk-backend",
    [string]$ArtifactRepository = "launch-desk",
    [string]$SecretName = "launch-desk-openai-api-key",
    [string]$RuntimeServiceAccount = "",
    [string]$FrontendOrigin = "",
    [string]$ImageTag = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Native {
    param([scriptblock]$Command)

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code $LASTEXITCODE."
    }
}

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

Require-Command "git"
Require-Command "gcloud"
Require-Command "tar"

$sha = (git -C $root rev-parse --short HEAD).Trim()
if (-not $ImageTag) {
    $ImageTag = $sha
}
if (-not $RuntimeServiceAccount) {
    $projectNumber = (
        gcloud projects describe $ProjectId --format "value(projectNumber)"
    ).Trim()
    $RuntimeServiceAccount = "$projectNumber-compute@developer.gserviceaccount.com"
}

$image = "$Region-docker.pkg.dev/$ProjectId/$ArtifactRepository/${ServiceName}:$ImageTag"
$context = Join-Path ([System.IO.Path]::GetTempPath()) "launch-desk-cloud-run-$sha"
$archivePath = Join-Path ([System.IO.Path]::GetTempPath()) "launch-desk-cloud-run-$sha.tar"

if (Test-Path $context) {
    Remove-Item $context -Recurse -Force
}
if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}
New-Item -ItemType Directory -Path $context | Out-Null

Write-Host "Creating clean deploy context from git HEAD: $sha" -ForegroundColor Cyan
Invoke-Native {
    git -C $root archive --format=tar --output=$archivePath HEAD
}
Invoke-Native {
    tar -xf $archivePath -C $context
}

Write-Host "Ensuring Artifact Registry repository exists: $ArtifactRepository" -ForegroundColor Cyan
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& gcloud artifacts repositories describe $ArtifactRepository `
    --project $ProjectId `
    --location $Region *> $null
$repositoryDescribeExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
if ($repositoryDescribeExitCode -ne 0) {
    Invoke-Native {
        gcloud artifacts repositories create $ArtifactRepository `
            --project $ProjectId `
            --location $Region `
            --repository-format docker `
            --description "Launch Desk container images"
    }
}

Write-Host "Building backend image: $image" -ForegroundColor Cyan
Invoke-Native {
    gcloud builds submit $context `
        --project $ProjectId `
        --config (Join-Path $context "deploy/cloud-run/cloudbuild.backend.yaml") `
        --substitutions "_IMAGE=$image"
}

Write-Host "Granting secret access to runtime service account: $RuntimeServiceAccount" -ForegroundColor Cyan
Invoke-Native {
    gcloud secrets add-iam-policy-binding $SecretName `
        --project $ProjectId `
        --member "serviceAccount:$RuntimeServiceAccount" `
        --role "roles/secretmanager.secretAccessor" `
        --quiet
}

$envVars = @(
    "LAUNCH_DESK_MODEL=gpt-5.4-mini",
    "LAUNCH_DESK_MAX_TOKENS=3600",
    "LAUNCH_DESK_MODEL_RETRIES=2",
    "LAUNCH_DESK_VERBOSITY=medium",
    "LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS=120",
    "LAUNCH_DESK_RATE_LIMIT_PER_MINUTE=12"
)
if ($FrontendOrigin) {
    $envVars += "LAUNCH_DESK_ALLOWED_ORIGINS=$FrontendOrigin"
}

Write-Host "Deploying Cloud Run service: $ServiceName" -ForegroundColor Cyan
Invoke-Native {
    gcloud run deploy $ServiceName `
        --project $ProjectId `
        --region $Region `
        --image $image `
        --platform managed `
        --allow-unauthenticated `
        --port 8080 `
        --service-account $RuntimeServiceAccount `
        --set-env-vars ($envVars -join ",") `
        --set-secrets "OPENAI_API_KEY=${SecretName}:latest"
}

$serviceUrl = (
    gcloud run services describe $ServiceName `
        --project $ProjectId `
        --region $Region `
        --format "value(status.url)"
).Trim()

Write-Host ""
Write-Host "Launch Desk backend deployed:" -ForegroundColor Green
Write-Host $serviceUrl
Write-Host ""
Write-Host "Health check:" -ForegroundColor Cyan
Write-Host "$serviceUrl/api/launch-desk/health"
