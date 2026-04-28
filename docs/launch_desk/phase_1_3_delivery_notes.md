# Launch Desk Phase 1.3 Delivery Notes

This delivery slice is Launch Desk only. It must not include existing main-site dirty changes under `app/`, main Flask routes, the main website LLM selector, FinMind/QuantLabAI dashboards, or `requirements.txt`.

## Include In Commit

Backend:

- `launch_desk/__init__.py`
- `launch_desk/agent.py`
- `launch_desk/payloads.py`
- `launch_desk/routes.py`
- `launch_desk/tools.py`

Frontend:

- `launch-desk-frontend/.env.local.example`
- `launch-desk-frontend/.gitignore`
- `launch-desk-frontend/next.config.js`
- `launch-desk-frontend/package.json`
- `launch-desk-frontend/pages/_app.jsx`
- `launch-desk-frontend/pages/index.jsx`
- `launch-desk-frontend/public/favicon.svg`
- `launch-desk-frontend/styles/globals.css`

Scripts:

- `scripts/run_launch_desk_backend.py`
- `scripts/verify_launch_desk_stream.py`
- `scripts/verify_launch_desk_local.ps1`

Tests:

- `tests/test_launch_desk_agent_contract.py`
- `tests/test_launch_desk_routes.py`
- `tests/test_launch_desk_tools.py`

Docs:

- `docs/launch_desk/.env.example`
- `docs/launch_desk/README.md`
- `docs/launch_desk/production_runbook.md`
- `docs/launch_desk/validation_checklist.md`
- `docs/launch_desk/phase_1_3_delivery_notes.md`

## Exclude From Commit

Do not include:

- `app/`
- `app/routes.py`
- `app/llm_options.py`
- `app/finmind_*.py`
- `app/templates/finmind_*.html`
- `app/static/js/finmind_*.js`
- `app/templates/chat-frontend-react/`
- `requirements.txt`
- `launch-desk-frontend/.next/`
- `launch_desk/__pycache__/`
- `.launch_desk_logs/`
- Any local `.env` file with secrets

## Safe Staging Command

Use exact paths instead of broad `git add .`:

```powershell
git add `
  launch_desk `
  launch-desk-frontend/.env.local.example `
  launch-desk-frontend/.gitignore `
  launch-desk-frontend/next.config.js `
  launch-desk-frontend/package.json `
  launch-desk-frontend/pages `
  launch-desk-frontend/public `
  launch-desk-frontend/styles `
  scripts/run_launch_desk_backend.py `
  scripts/verify_launch_desk_stream.py `
  scripts/verify_launch_desk_local.ps1 `
  tests/test_launch_desk_agent_contract.py `
  tests/test_launch_desk_routes.py `
  tests/test_launch_desk_tools.py `
  docs/launch_desk
```

Before committing, verify the staged diff:

```powershell
git diff --cached --name-only
git diff --cached --check
```

The staged file list should match the include list above and should not contain `app/`, `requirements.txt`, `.next/`, logs, or secrets.

## Proposed Commit Message

```text
Add isolated Launch Desk agent app

- add standalone Launch Desk backend, tools, payload validation, and SSE route
- add Next frontend with streamed tool/model progress and Markdown/JSON export
- add OpenAI Agents SDK runtime controls, timeout, rate limit, and observability metadata
- add Launch Desk docs, env examples, local verification wrapper, and production runbook
- add Launch Desk unit and contract tests
```

## Proposed PR Description

```markdown
## Summary

Adds Launch Desk as an isolated launch-planning agent app. The app helps engineering teams turn a rough product brief into a prioritized release plan, risk register, owner checklist, channel-specific launch copy, and follow-up questions.

This PR intentionally keeps Launch Desk separate from the main Flask app and does not modify the existing multi-LLM selector or FinMind/QuantLabAI flows.

## Scope

- Adds standalone `launch_desk/` backend using the OpenAI Agents SDK.
- Adds standalone `launch-desk-frontend/` Next UI.
- Adds Launch Desk SSE streaming events: `status`, `tool_progress`, `text_delta`, `complete`, and `error`.
- Adds runtime controls for model, max tokens, retry count, verbosity, timeout, and rate limit.
- Adds completion metadata: model, trace id, duration, timeout, tool counts, text character count, and usage when available.
- Adds Markdown/JSON export for completed plans.
- Adds Launch Desk docs, env examples, validation checklist, local verifier, and production runbook.

## Out Of Scope

- No changes to `app/`.
- No registration in `app/routes.py`.
- No changes to `app/llm_options.py`.
- No changes to FinMind/QuantLabAI dashboards or reports.
- No multi-provider support in this slice.
- No dependency changes in `requirements.txt`.

## Validation

- `python -m pytest tests\test_launch_desk_tools.py tests\test_launch_desk_routes.py tests\test_launch_desk_agent_contract.py`
- `node ..\node_modules\next\dist\bin\next build` from `launch-desk-frontend/`
- `python scripts\verify_launch_desk_stream.py --url http://127.0.0.1:5057/api/launch-desk/stream`
- `.\scripts\verify_launch_desk_local.ps1 -SkipLiveStream`
- `.\scripts\verify_launch_desk_local.ps1`
- `.\scripts\verify_launch_desk_local.ps1 -StartServers`
- Browser check at `http://127.0.0.1:3008/`

## Notes

The full streamed verifier requires `OPENAI_API_KEY` to be visible to the backend process. The frontend never receives the API key.
```

## Latest Local Validation Snapshot

- `.\scripts\verify_launch_desk_local.ps1 -SkipLiveStream`: passed.
- `.\scripts\verify_launch_desk_local.ps1`: passed, including health and real streamed API verification.
- `.\scripts\verify_launch_desk_local.ps1 -StartServers`: passed from a clean 3008/5057 port state.
- Browser page load at `http://127.0.0.1:3008/`: loaded `Launch Desk` and showed `Run launch plan`.

## Current Delivery Risk

The repo has many unrelated existing dirty and untracked files under `app/`, `scripts/`, `tests/`, and `requirements.txt`. Do not use `git add .` for this delivery slice.
