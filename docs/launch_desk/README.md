# Launch Desk

Launch Desk is a working launch-planning agent app for engineering teams. It turns a rough launch idea into a streamed release plan with prioritized work, a risk register, owner checklists, channel copy, and follow-up questions.

## Structure

- `launch-desk-frontend/` contains the Next/React UI.
- `launch_desk/routes.py` exposes `/api/launch-desk/health` and `/api/launch-desk/stream`.
- `launch_desk/agent.py` builds the OpenAI Agents SDK agent, streaming bridge, and tracing metadata.
- `launch_desk/tools.py` contains deterministic tool implementations that are wrapped as SDK function tools.
- `scripts/run_launch_desk_backend.py` starts the lightweight Flask backend for local Launch Desk development.
- `scripts/verify_launch_desk_stream.py` posts to the local stream endpoint and confirms tool progress, model text delta, completion, and completion metadata.
- `scripts/verify_launch_desk_local.ps1` runs the local packaging checks and can optionally start both dev servers for a live stream check.
- `docs/launch_desk/.env.example` and `launch-desk-frontend/.env.local.example` document backend and frontend environment variables.
- `docs/launch_desk/production_runbook.md` contains the deployment, observability, rollback, and failure-response checklist.
- `tests/test_launch_desk_tools.py`, `tests/test_launch_desk_routes.py`, and `tests/test_launch_desk_agent_contract.py` cover tool behavior, SSE route formatting, and agent event contracts.

## OpenAI setup

Create an API key in the OpenAI platform, then set:

```powershell
$env:OPENAI_API_KEY="replace-with-your-openai-api-key"
```

Optional model override:

```powershell
$env:LAUNCH_DESK_MODEL="gpt-5.4-mini"
```

Optional runtime controls:

```powershell
$env:LAUNCH_DESK_MAX_TOKENS="3600"
$env:LAUNCH_DESK_MODEL_RETRIES="2"
$env:LAUNCH_DESK_VERBOSITY="medium"
$env:LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS="120"
$env:LAUNCH_DESK_RATE_LIMIT_PER_MINUTE="12"
```

The default model is `gpt-5.4-mini` for lower-latency development. The model can be changed to `gpt-5.5` when a launch requires the highest reasoning quality. This follows the current OpenAI model guidance: use `gpt-5.5` when unsure or for complex reasoning, and smaller variants such as `gpt-5.4-mini` when optimizing latency and cost.

Reference environment templates:

```text
docs/launch_desk/.env.example
launch-desk-frontend/.env.local.example
```

## Install dependencies

Use a virtual environment for normal development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For this workspace, a sandbox-local SDK install can also be used when global Python is locked down:

```powershell
python -m pip install --target .codex_tmpdeps\openai_agents "openai-agents>=0.14.2,<0.15"
$env:PYTHONPATH=".codex_tmpdeps\openai_agents"
```

## Run locally

Start the backend:

```powershell
$env:PYTHONPATH=".codex_tmpdeps\openai_agents"
$env:OPENAI_API_KEY="replace-with-your-openai-api-key"
python scripts\run_launch_desk_backend.py --port 5057
```

Start the frontend in a second terminal:

```powershell
cd launch-desk-frontend
$env:NEXT_PUBLIC_LAUNCH_DESK_API_BASE="http://127.0.0.1:5057"
npm run dev
```

Open:

```text
http://127.0.0.1:3007
```

## Verify streaming

Do not stop after checking Vite/Next startup or `/api/health`. Run the real streamed agent check:

```powershell
$env:PYTHONPATH=".codex_tmpdeps\openai_agents"
python scripts\verify_launch_desk_stream.py --url http://127.0.0.1:5057/api/launch-desk/stream
```

The verifier succeeds only after it observes at least one `tool_progress` event, one `text_delta` event, and a final `complete` event from the same streamed local API call. The `complete` event must include `model`, `trace_id`, `duration_ms`, `timeout_seconds`, `tool_count`, `tool_completion_count`, and `text_char_count`.

## One-command local verification

Run non-network packaging checks:

```powershell
.\scripts\verify_launch_desk_local.ps1 -SkipLiveStream
```

Run the full local check, including starting Launch Desk dev servers and posting a real streamed request to OpenAI:

```powershell
$env:OPENAI_API_KEY="replace-with-your-openai-api-key"
.\scripts\verify_launch_desk_local.ps1 -StartServers
```

The full check starts the backend on `5057` and the frontend on `3008` by default. Logs go to `.launch_desk_logs/`.

For deployment prep, follow:

```text
docs/launch_desk/production_runbook.md
```

## Extending tools

Add deterministic helper logic to `launch_desk/tools.py`, then wrap it with `@function_tool` inside `launch_desk/agent.py`. Keep pure helpers separate from SDK wrappers so tests can validate behavior without making OpenAI calls.

Good next tools or handoffs:

- Docs readiness checker for API references and migration guides.
- Support launch handoff agent for FAQ and escalation paths.
- Analytics handoff agent for success metric instrumentation.
- Legal/compliance review handoff for regulated copy.

## Observability

`launch_desk/agent.py` passes Agents SDK trace metadata through `RunConfig` for the `Launch Desk release planning` workflow, including app name, audience, launch date, request id, and model. Stream completion events also expose request duration, request timeout, model, tool counts, text character count, and the trace id for lightweight local debugging.

The backend also writes structured `launch_desk.*` log messages for validation errors, missing API keys, request starts, rate-limit rejections, run starts, completions, and classified errors. These logs intentionally avoid storing the full product brief.

## Production hardening controls

- `LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS` bounds each streamed model run. Values are clamped between 10 and 600 seconds.
- `LAUNCH_DESK_RATE_LIMIT_PER_MINUTE` applies a lightweight per-client in-memory rate limit before opening the stream. Set it to `0` to disable the local limiter.
- `LAUNCH_DESK_ALLOWED_ORIGINS` can add frontend origins beyond the local defaults.

These controls are isolated to Launch Desk and do not touch the main website routes, membership flow, or multi-LLM selector.

## Exporting plans

The frontend can download a completed run as Markdown or JSON. Markdown contains the generated release plan. JSON contains the form inputs, final plan, completion metadata, and a compact event summary for debugging or handoff.
