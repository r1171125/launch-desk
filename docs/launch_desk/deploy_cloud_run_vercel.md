# Deploy Launch Desk To Cloud Run And Vercel

This deployment path keeps Launch Desk as two isolated services:

- Backend: Google Cloud Run, using `deploy/cloud-run/backend.Dockerfile`.
- Frontend: Vercel, using `launch-desk-frontend/vercel.json`.

It does not register routes in the main website Flask app and does not change the
main website multi-LLM selector.

## 1. Prerequisites

- GitHub `main` is green for `Launch Desk CI`.
- `gcloud` is authenticated with a project that can use Cloud Run, Cloud Build,
  Artifact Registry, and Secret Manager.
- A backend OpenAI key is available, but not committed to git.
- A Vercel account is connected to `r1171125/launch-desk`.

## 2. Backend Secret

Recommended isolated setup: create or update a dedicated Cloud Run backend
secret before deploying:

```powershell
$env:PROJECT_ID="your-google-cloud-project-id"
$env:REGION="asia-east1"
$env:SECRET_NAME="launch-desk-openai-api-key"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --project $env:PROJECT_ID

$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, "replace-with-your-openai-api-key", [System.Text.UTF8Encoding]::new($false))
gcloud secrets create $env:SECRET_NAME --data-file=$tmp --project $env:PROJECT_ID
Remove-Item $tmp -Force
```

If the secret already exists, add a new version instead:

```powershell
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, "replace-with-your-openai-api-key", [System.Text.UTF8Encoding]::new($false))
gcloud secrets versions add $env:SECRET_NAME --data-file=$tmp --project $env:PROJECT_ID
Remove-Item $tmp -Force
```

Make sure the stored secret value has no trailing newline. The backend also
trims surrounding whitespace at runtime as a defensive safeguard.

Current production note:

```text
launch-desk-backend currently reads OPENAI_API_KEY:latest.
```

That shared secret was used after rotating the exposed OpenAI key because the
rotated key was already available as `OPENAI_API_KEY` version 4. This is
verified and operational, but it is less isolated than the recommended
`launch-desk-openai-api-key` setup. If production should return to full Launch
Desk isolation, add the rotated key to `launch-desk-openai-api-key`, then
redeploy or update Cloud Run to point `OPENAI_API_KEY` back to
`launch-desk-openai-api-key:latest`.

## 3. Deploy Backend

From the repository root:

```powershell
.\scripts\deploy_launch_desk_cloud_run.ps1 `
  -ProjectId "your-google-cloud-project-id" `
  -Region "asia-east1" `
  -ServiceName "launch-desk-backend" `
  -SecretName "launch-desk-openai-api-key" `
  -FrontendOrigin "https://your-launch-desk-frontend.vercel.app"
```

The script creates a clean deploy context from `git archive HEAD`, so local
untracked files from the original workspace are not uploaded to Cloud Build.
It also grants `roles/secretmanager.secretAccessor` on the backend secret to the
Cloud Run runtime service account. By default, that runtime identity is the
Compute Engine default service account for the project. To use a dedicated
service account, pass `-RuntimeServiceAccount`.

To match the current production shared-secret state without rebuilding the image,
update the running Cloud Run service with:

```powershell
gcloud run services update launch-desk-backend `
  --project "my-ai-website-430003" `
  --region "asia-east1" `
  --update-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest"
```

The verified production revision after this update was:

```text
launch-desk-backend-00005-vnv
```

After deployment, capture the backend URL:

```text
https://launch-desk-backend-xxxxx.a.run.app
```

## 4. Deploy Frontend

In Vercel:

1. Import GitHub repository `r1171125/launch-desk`.
2. Set the project root directory to `launch-desk-frontend`.
3. Confirm framework preset is Next.js.
4. Set environment variable:

```text
NEXT_PUBLIC_LAUNCH_DESK_API_BASE=https://your-cloud-run-backend-url
```

5. Deploy.

Do not set `OPENAI_API_KEY` in Vercel. The frontend only needs the public API
base URL.

## 5. Update Backend CORS

After Vercel gives the final frontend URL, redeploy or update Cloud Run with:

```powershell
gcloud run services update launch-desk-backend `
  --project "your-google-cloud-project-id" `
  --region "asia-east1" `
  --set-env-vars "LAUNCH_DESK_ALLOWED_ORIGINS=https://your-final-vercel-domain"
```

If you use `scripts/deploy_launch_desk_cloud_run.ps1`, pass the same value with
`-FrontendOrigin`.

## 6. Post-Deploy Verification

Backend health:

```powershell
Invoke-RestMethod "https://your-cloud-run-backend-url/api/launch-desk/health"
```

Live stream verification:

```powershell
python scripts\verify_launch_desk_stream.py --url "https://your-cloud-run-backend-url/api/launch-desk/stream"
```

The live stream verifier must see:

- at least one `tool_progress` event
- at least one `text_delta` event
- one `complete` event

Frontend verification:

1. Open the Vercel URL.
2. Load the sample brief.
3. Run the launch plan.
4. Confirm tool progress, streamed text, run completion, and Markdown/JSON
   export buttons.
