# Launch Desk Phase 1.11 Strict Release Gate Note

Recorded on 2026-04-29 Asia/Taipei.

## Scope

This note records the strict post-deploy release gate run after adding Vercel
deployment metadata verification to Launch Desk.

The verification remained isolated to Launch Desk. It did not integrate Launch
Desk into the main Flask app, did not change the main website routes, and did
not touch the existing FinMind, QuantLabAI, membership, report, or multi-LLM
selector flows.

## Production Targets

Frontend:

```text
https://launch-desk-orcin.vercel.app
```

Backend:

```text
https://launch-desk-backend-6gtyc6yuoq-de.a.run.app
```

Backend stream endpoint:

```text
https://launch-desk-backend-6gtyc6yuoq-de.a.run.app/api/launch-desk/stream
```

## Release Gate Command

The strict release gate was run with Vercel deployment metadata required:

```powershell
.\scripts\verify_launch_desk_post_deploy.ps1 -RequireVercelDeploymentMetadata
```

The command verified:

- Backend streamed API behavior.
- Frontend deployed page content and backend API host.
- Vercel deployment metadata status.
- Vercel deployment commit SHA.

## Verified Commit

The production Vercel deployment matched this commit:

```text
1323d7c52a6a84d35be2f95a8f8a324581696a34
```

Short commit:

```text
1323d7c Add Vercel deployment metadata verification
```

## Backend Stream Verification Result

Result:

```text
Launch Desk stream verification passed.
```

Observed event requirements:

- At least one `tool_progress` event was received.
- At least one `text_delta` event was received.
- One `complete` event was received.

Complete event metadata:

```text
model=gpt-5.4-mini
trace_id=trace_6cd4856289704009b726a8736583516b
duration_ms=15689
timeout_seconds=120
tool_count=5
text_chars=5000
```

Observed generated text began with:

```text
## Prioritized plan
```

## Frontend Page Verification Result

Result:

```text
Launch Desk frontend page verification passed.
```

Verified frontend URL:

```text
https://launch-desk-orcin.vercel.app
```

Verified backend API host rendered by the frontend:

```text
launch-desk-backend-6gtyc6yuoq-de.a.run.app
```

## Vercel Deployment Metadata Verification Result

Result:

```text
Vercel deployment metadata verification passed.
```

Deployment ID:

```text
dpl_CZWtWa18mvHUuWqCDwhKyRb3nJEb
```

Deployment URL:

```text
launch-desk-ftqonrjuh-r1171125s-projects.vercel.app
```

Vercel state:

```text
readyState=READY
status=READY
target=production
```

Project ID:

```text
prj_ikTSlQ7mUcx2oYEtxmv8FqplU4Qb
```

Commit SHA reported by Vercel:

```text
1323d7c52a6a84d35be2f95a8f8a324581696a34
```

## Browser Checklist

The release gate printed the browser checklist for the production frontend:

- Open `https://launch-desk-orcin.vercel.app`.
- Confirm the API badge shows `launch-desk-backend-6gtyc6yuoq-de.a.run.app`.
- Click `Load sample`.
- Click `Run launch plan`.
- Confirm the Agent stream reaches `Complete`.
- Confirm tool calls and completions appear for all five Launch Desk tools.
- Confirm the generated plan contains `Prioritized plan`.
- Confirm readiness shows a percentage and no visible error is displayed.
- Check browser console for app-domain warnings/errors if this is a release
  gate.

## Token Handling

A Vercel access token was used only to read deployment metadata during the
strict release gate.

The token value is intentionally not recorded in this repository.

Security status:

- The Vercel token was exposed in chat during manual verification.
- The local PowerShell session variable `VERCEL_TOKEN` was cleared.
- The exposed Vercel token was revoked in the Vercel Tokens page.
- Future strict release gates should use a newly generated token and should not
  paste the token into chat, docs, logs, issue comments, or PR descriptions.

## Final Status

The strict post-deploy release gate passed:

- Backend stream verification: passed.
- Frontend page verification: passed.
- Vercel deployment metadata verification: passed.
- Vercel deployment status: `READY`.
- Vercel commit SHA matched the expected Launch Desk commit.
- Exposed Vercel token: revoked.
