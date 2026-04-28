# Launch Desk Post-Deploy Verification

Use this checklist after changing Cloud Run settings, rotating the OpenAI key,
redeploying the backend, or deploying the Vercel frontend.

The verification is intentionally scoped to Launch Desk. It does not import the
main Flask app, does not touch `app/`, and does not exercise FinMind,
QuantLabAI, membership, report, or multi-LLM flows.

## Current Production Targets

Frontend:

```text
https://launch-desk-orcin.vercel.app
```

Backend:

```text
https://launch-desk-backend-6gtyc6yuoq-de.a.run.app
```

Current backend secret reference:

```text
OPENAI_API_KEY=launch-desk-openai-api-key:latest
```

Current backend CORS origin:

```text
LAUNCH_DESK_ALLOWED_ORIGINS=https://launch-desk-orcin.vercel.app
```

## One-Command Verification

From the repository root:

```powershell
.\scripts\verify_launch_desk_post_deploy.ps1 `
  -BackendBaseUrl "https://launch-desk-backend-6gtyc6yuoq-de.a.run.app" `
  -FrontendUrl "https://launch-desk-orcin.vercel.app"
```

This runs:

- Backend streamed API verification via `scripts/verify_launch_desk_stream.py`.
- Frontend deployed page verification via
  `scripts/verify_launch_desk_frontend_page.py`.
- A fixed browser checklist for the production UI flow.

For a release gate where a human should confirm the browser behavior:

```powershell
.\scripts\verify_launch_desk_post_deploy.ps1 `
  -BackendBaseUrl "https://launch-desk-backend-6gtyc6yuoq-de.a.run.app" `
  -FrontendUrl "https://launch-desk-orcin.vercel.app" `
  -OpenBrowser `
  -RequireBrowserConfirmation
```

Type `PASS` only after the browser checklist is complete.

## Backend Pass Criteria

The streamed backend verifier must receive:

- At least one `tool_progress` event.
- At least one `text_delta` event.
- One `complete` event.

The `complete` event must include:

- `model`
- `trace_id`
- `duration_ms`
- `timeout_seconds`
- `tool_count`
- `tool_completion_count`
- `text_char_count`

## Frontend Page Pass Criteria

The page verifier checks that the deployed frontend returns HTTP 200 and contains
the expected Launch Desk UI text plus the configured backend API host.

This is a lightweight page check, not a substitute for browser interaction.

## Browser Pass Criteria

Open the production frontend and verify:

- The API badge shows the expected Cloud Run backend host.
- `Load sample` fills the launch brief inputs.
- `Run launch plan` starts the stream.
- The Agent stream reaches `Complete`.
- Tool calls and tool completions appear for:
  - `extract_launch_tasks`
  - `check_launch_readiness`
  - `generate_owner_checklist`
  - `draft_channel_copy`
  - `missing_detail_questions`
- The generated release plan includes `Prioritized plan`.
- Readiness shows a percentage.
- Markdown and JSON export buttons are enabled after output appears.
- No visible frontend error appears.
- No app-domain console warning or error appears during the run.

## Common Failures

| Symptom | Likely cause | Response |
|---|---|---|
| Backend verifier reports `authentication_error` | Cloud Run cannot read a valid OpenAI key | Check `OPENAI_API_KEY` secret reference and Secret Manager access |
| Backend verifier reports `network_error` | Cloud Run cannot reach OpenAI | Check Cloud Run egress/network policy and retry |
| Backend verifier reports `rate_limited` | Launch Desk local limiter or OpenAI rate limit | Wait, then retry; adjust only Launch Desk rate settings if needed |
| Frontend page verifier misses API host | Vercel was built with the wrong API base URL | Update `NEXT_PUBLIC_LAUNCH_DESK_API_BASE` and redeploy frontend |
| Browser shows CORS failure | Cloud Run allowed origins do not include the Vercel URL | Update `LAUNCH_DESK_ALLOWED_ORIGINS` and create a new Cloud Run revision |
