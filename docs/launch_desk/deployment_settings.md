# Launch Desk Deployment Settings

These settings are scoped to the standalone Launch Desk repository. They do not
register Launch Desk inside the main website Flask app and do not reuse the main
website multi-LLM selector.

## Repository Layout

- Backend package: `launch_desk/`
- Backend entrypoint: `scripts/run_launch_desk_backend.py`
- Frontend app: `launch-desk-frontend/`
- CI workflow: `.github/workflows/launch-desk-ci.yml`
- Production checklist: `docs/launch_desk/production_runbook.md`

## CI Defaults

GitHub Actions runs non-live checks only:

- Python compile check for Launch Desk backend, scripts, and tests.
- `pytest` for `tests/test_launch_desk_*.py`.
- Next production build from `launch-desk-frontend/`.

CI intentionally uses a non-live placeholder key:

```text
OPENAI_API_KEY=test-key-for-non-live-ci
```

Do not add a real OpenAI key to CI unless you intentionally create a separate
live smoke workflow with explicit budget and rate-limit controls.

## Backend Service

Install command:

```bash
python -m pip install --upgrade pip
python -m pip install -r launch_desk/requirements.txt
```

Start command:

```bash
python scripts/run_launch_desk_backend.py --host 0.0.0.0 --port ${PORT:-5057}
```

Required secret:

```text
OPENAI_API_KEY
```

Recommended environment:

```text
LAUNCH_DESK_MODEL=gpt-5.4-mini
LAUNCH_DESK_MAX_TOKENS=3600
LAUNCH_DESK_MODEL_RETRIES=2
LAUNCH_DESK_VERBOSITY=medium
LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS=120
LAUNCH_DESK_RATE_LIMIT_PER_MINUTE=12
LAUNCH_DESK_ALLOWED_ORIGINS=https://your-launch-desk-frontend.example.com
```

Health check:

```text
GET /api/launch-desk/health
```

The health response should report `ok=true`, `openai_api_key_configured=true`,
and the expected model/runtime settings.

## Frontend Service

Set the deployment root directory to:

```text
launch-desk-frontend
```

Install command:

```bash
npm install --no-audit --no-fund
```

Build command:

```bash
npm run build
```

Start command:

```bash
npm run start
```

Required public environment:

```text
NEXT_PUBLIC_LAUNCH_DESK_API_BASE=https://your-launch-desk-api.example.com
```

Never set `OPENAI_API_KEY` in the frontend service.

## Platform Notes

Use two services unless a platform explicitly supports split backend/frontend
deploys from one repository:

- Backend: Python web service.
- Frontend: Next.js web service.

For Cloud Run, build separate backend and frontend container artifacts or use a
source deploy flow that can set different working directories and start
commands. Keep the OpenAI key only on the backend Cloud Run service.

For Vercel-style frontend hosting, deploy `launch-desk-frontend/` as the project
root and point `NEXT_PUBLIC_LAUNCH_DESK_API_BASE` at the backend service URL.

## Release Gate

Before changing production routing or DNS:

1. Confirm GitHub Actions passes on `main`.
2. Run `scripts/verify_launch_desk_stream.py` against the deployed backend from
   a network that can reach OpenAI.
3. Open the deployed frontend and run the sample brief.
4. Confirm at least one tool progress event, one text delta, and one completion.
5. Confirm Markdown and JSON export buttons work after completion.
