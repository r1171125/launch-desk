# Launch Desk Production Runbook

This runbook is intentionally scoped to the standalone Launch Desk app. It does not register Launch Desk inside the main Flask app, does not modify `app/`, and does not change the main website multi-LLM selector.

## Deployment Boundary

Launch Desk has two deployable surfaces:

- Backend: Flask API from `launch_desk/routes.py`, usually started through `scripts/run_launch_desk_backend.py`.
- Frontend: Next app in `launch-desk-frontend/`, configured with `NEXT_PUBLIC_LAUNCH_DESK_API_BASE`.

Keep the backend and frontend deployable as an isolated service pair until there is an explicit product decision to integrate into the main site.

## Required Environment

Backend:

```text
OPENAI_API_KEY=replace-with-your-openai-api-key
LAUNCH_DESK_MODEL=gpt-5.4-mini
LAUNCH_DESK_MAX_TOKENS=3600
LAUNCH_DESK_MODEL_RETRIES=2
LAUNCH_DESK_VERBOSITY=medium
LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS=120
LAUNCH_DESK_RATE_LIMIT_PER_MINUTE=12
LAUNCH_DESK_ALLOWED_ORIGINS=https://your-launch-desk-frontend.example.com
```

Frontend:

```text
NEXT_PUBLIC_LAUNCH_DESK_API_BASE=https://your-launch-desk-api.example.com
```

Never put `OPENAI_API_KEY` in the frontend environment.

## Pre-Deployment Checks

Confirm the GitHub Actions workflow passes:

```text
.github/workflows/launch-desk-ci.yml
```

Run these from the repository root:

```powershell
python -m pytest tests\test_launch_desk_tools.py tests\test_launch_desk_routes.py tests\test_launch_desk_agent_contract.py
cd launch-desk-frontend
node ..\node_modules\next\dist\bin\next build
```

For a live local check, start the backend with `OPENAI_API_KEY` visible to that process, then run:

```powershell
python scripts\verify_launch_desk_stream.py --url http://127.0.0.1:5057/api/launch-desk/stream
```

The stream verifier must see at least one `tool_progress`, one `text_delta`, and one `complete` event. The `complete` event must include `model`, `trace_id`, `duration_ms`, `timeout_seconds`, `tool_count`, `tool_completion_count`, and `text_char_count`.

## Release Procedure

1. Confirm the deploy commit only changes Launch Desk-owned files.
2. Confirm `docs/launch_desk/deployment_settings.md` and `docs/launch_desk/deploy_cloud_run_vercel.md` match the selected backend/frontend hosting targets.
3. Build the frontend with the production `NEXT_PUBLIC_LAUNCH_DESK_API_BASE`.
4. Deploy the backend with `OPENAI_API_KEY`, model settings, timeout, rate limit, and allowed origins.
5. Hit `/api/launch-desk/health` and confirm:
   - `ok` is `true`
   - `openai_api_key_configured` is `true`
   - `model` is expected
   - `request_timeout_seconds` and `rate_limit_per_minute` match deployment settings
6. Run a streamed POST verification from the deployment network if possible.
7. Open the frontend and run the sample brief. Confirm tool progress, streamed text, run completion, and Markdown/JSON export buttons.

## Observability

Use these signals first:

- `trace_id` in `complete` and `error` stream events.
- Agents SDK trace metadata for workflow `Launch Desk release planning`.
- Backend log lines prefixed with `launch_desk.*`.
- `duration_ms`, `timeout_seconds`, `tool_count`, `tool_completion_count`, and `text_char_count` in `complete`.

The backend logs intentionally avoid recording the full product brief. If deeper request debugging is required, add temporary request-id-scoped diagnostics instead of logging user brief content.

## Rollback

Launch Desk is isolated, so rollback should be service-local:

1. Revert the Launch Desk backend/frontend deployment to the previous known-good artifact.
2. Keep the main website deployment unchanged.
3. If failures are caused by rate limit or timeout settings, adjust only Launch Desk environment variables first.
4. If OpenAI authentication fails, rotate or repair `OPENAI_API_KEY` only in the backend runtime.

## Common Failures

| Symptom | Likely cause | Response |
|---|---|---|
| `/health` says `openai_api_key_configured=false` | Backend process did not receive `OPENAI_API_KEY` | Fix backend secret injection and restart backend |
| Stream returns `authentication_error` | Key missing, invalid, or scoped incorrectly | Check backend secret value and OpenAI project access |
| Stream returns `rate_limited` or HTTP 429 | Local Launch Desk limiter is active | Wait for `Retry-After`, raise `LAUNCH_DESK_RATE_LIMIT_PER_MINUTE`, or disable with `0` only for controlled testing |
| Stream returns `timeout` | Model run exceeded `LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS` | Shorten the brief, increase timeout, or investigate model latency |
| Browser fails CORS | Frontend origin is not allowed | Add the deployed frontend origin to `LAUNCH_DESK_ALLOWED_ORIGINS` |
| Frontend builds but cannot call API | `NEXT_PUBLIC_LAUNCH_DESK_API_BASE` points to the wrong backend | Rebuild frontend with the correct public API URL |

## Decisions Not Included

These require separate product or infrastructure decisions:

- Integrating Launch Desk into the main website navigation or Flask app.
- Adding non-OpenAI providers or reusing the main site's multi-LLM selector.
- Persisting Launch Desk runs in a database.
- Adding authentication, per-user quotas, or organization-level audit trails.
