# Launch Desk Validation Checklist

## Agent behavior

- The agent uses the OpenAI Agents SDK, not Assistants API or Chat Completions scaffolding.
- The agent instructions require the final answer to include prioritized plan, risk register, owner checklist, launch copy suggestions, and follow-up questions.
- The model is configurable through `LAUNCH_DESK_MODEL`, with `gpt-5.4-mini` as the local default.
- Runtime controls for max output tokens, retry count, and verbosity do not require touching the main website LLM selector.
- Runtime controls for request timeout and rate limit are isolated to Launch Desk.
- The streamed API emits `status`, `tool_progress`, `text_delta`, `complete`, and `error` events as applicable.
- A real local streamed POST receives at least one `tool_progress` event, one `text_delta` event, and one `complete` event.
- The `complete` event includes model, trace id, duration, timeout, tool counts, and text character count.
- Error events use user-facing error codes and messages instead of raw provider exception text.
- Backend logs use `launch_desk.*` messages and avoid writing the full product brief.
- The stream route returns a friendly `429` response with `Retry-After` when the Launch Desk rate limit is exceeded.

## Frontend flow

- Users can enter product brief, audience, launch date, constraints, and available assets.
- The Run launch plan button is disabled until required inputs are present.
- The UI streams progress without requiring a page refresh.
- The agent transcript grows progressively as `text_delta` events arrive.
- Stream parsing handles chunked SSE blocks and the final buffered event.
- The right rail updates with readiness, tool progress, and owner checklist outputs when tool events complete.
- Completed plans can be downloaded as Markdown.
- Completed runs can be downloaded as JSON with compact event and completion metadata.
- Desktop and mobile layouts remain readable without overlapping text or controls.

## Tool outputs

- `extract_launch_tasks` returns prioritized tasks with owners and due hints.
- `check_launch_readiness` returns a score, status, rubric, gaps, and risk register.
- `generate_owner_checklist` returns owner roles and actionable checks.
- `draft_channel_copy` returns internal, customer email, changelog, and social copy drafts.
- `missing_detail_questions` returns targeted follow-up questions when key launch details are absent.

## Local run checks

- `docs/launch_desk/.env.example` documents backend secrets and runtime controls without exposing real secrets.
- `launch-desk-frontend/.env.local.example` documents the frontend API base URL.
- `scripts/verify_launch_desk_local.ps1 -SkipLiveStream` runs syntax, unit tests, and frontend build without requiring OpenAI network access.
- `scripts/verify_launch_desk_local.ps1 -StartServers` can start both dev servers and run live streamed verification when `OPENAI_API_KEY` is configured.
- `scripts/verify_launch_desk_post_deploy.ps1` runs the fixed production post-deploy sequence for backend stream verification, frontend page verification, optional Vercel deployment metadata verification, and browser checklist output.
- Backend server starts with `OPENAI_API_KEY` visible to that process.
- Frontend server starts with `NEXT_PUBLIC_LAUNCH_DESK_API_BASE` pointing at the backend.
- `/api/launch-desk/health` confirms whether the backend process sees `OPENAI_API_KEY`.
- `scripts/verify_launch_desk_stream.py` passes against the local backend stream endpoint.
- Browser testing confirms the UI can submit a launch brief and render streamed output.
- Browser testing confirms the Markdown and JSON export buttons become available after streamed output appears.
- The first-phase Launch Desk changes do not modify `app/`, `app/routes.py`, `app/llm_options.py`, or existing FinMind/QuantLabAI dashboard files.

## Deployment packaging

- `.github/workflows/launch-desk-ci.yml` runs Launch Desk-only backend tests and frontend build checks on Launch Desk path changes.
- `deploy/cloud-run/backend.Dockerfile` builds only the Launch Desk backend runtime image.
- `deploy/cloud-run/cloudbuild.backend.yaml` builds the backend image from the Cloud Run Dockerfile.
- `scripts/deploy_launch_desk_cloud_run.ps1` creates a clean deploy context from `git archive HEAD`.
- `launch-desk-frontend/vercel.json` defines the Vercel frontend build/install settings.
- `launch_desk/requirements.txt` defines backend runtime dependencies for standalone deployment.
- `launch_desk/requirements-dev.txt` defines CI/test dependencies for Launch Desk only.
- `docs/launch_desk/deployment_settings.md` defines backend/frontend service settings without binding deployment to the main site.
- `docs/launch_desk/deploy_cloud_run_vercel.md` documents the Cloud Run backend and Vercel frontend deployment sequence.
- `docs/launch_desk/post_deploy_verification.md` documents the production backend/frontend/Vercel metadata verification sequence and pass criteria.
- `docs/launch_desk/production_runbook.md` defines the isolated backend/frontend deployment boundary.
- The runbook lists required backend and frontend environment variables.
- The runbook includes pre-deployment checks, release steps, observability signals, rollback steps, and common failure responses.
- The runbook explicitly leaves main-site integration and multi-provider support as future product/infrastructure decisions.
