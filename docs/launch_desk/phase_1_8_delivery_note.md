# Launch Desk Phase 1.8 Delivery Note

Recorded on 2026-04-29 Asia/Taipei.

## Scope

Phase 1.8 connected the deployed Launch Desk backend to the production
frontend path.

This delivery did not integrate Launch Desk into the main Flask app, did not
change the main website routes, and did not touch the existing FinMind,
QuantLabAI, membership, report, or multi-LLM selector flows.

## Production Endpoints

Frontend:

```text
https://launch-desk-orcin.vercel.app
```

Backend:

```text
https://launch-desk-backend-6gtyc6yuoq-de.a.run.app
```

The frontend calls the backend through:

```text
NEXT_PUBLIC_LAUNCH_DESK_API_BASE=https://launch-desk-backend-6gtyc6yuoq-de.a.run.app
```

## Vercel Frontend Deployment

Vercel project:

```text
launch-desk
```

Vercel team:

```text
r1171125's projects
```

GitHub source:

```text
r1171125/launch-desk
```

Branch:

```text
main
```

Root directory:

```text
launch-desk-frontend
```

Framework preset:

```text
Next.js
```

Deployment id observed during import:

```text
dpl_9QXDjzUTqGsVx1B8LpEfY78erR96
```

Commit deployed:

```text
4d28f5b Harden Launch Desk Cloud Run runtime
```

## Cloud Run Backend CORS

Cloud Run service:

```text
launch-desk-backend
```

Google Cloud project:

```text
my-ai-website-430003
```

Region:

```text
asia-east1
```

CORS environment variable:

```text
LAUNCH_DESK_ALLOWED_ORIGINS=https://launch-desk-orcin.vercel.app
```

Revision serving after the CORS update:

```text
launch-desk-backend-00004-nkc
```

The CORS update was applied with `gcloud run services update`; no new backend
image build was required.

## Production Secret Update

After the original Phase 1.8 frontend/backend connection, the exposed OpenAI key
was rotated in the shared Secret Manager secret:

```text
OPENAI_API_KEY
```

The active shared secret version observed during verification was:

```text
OPENAI_API_KEY version 4 enabled
created 2026-04-28T18:19:01
```

Launch Desk Cloud Run was temporarily updated to read the shared secret
reference:

```text
OPENAI_API_KEY=OPENAI_API_KEY:latest
```

Revision serving after the temporary shared-secret update:

```text
launch-desk-backend-00005-vnv
```

That state was behavior-compatible and verified, but it reduced isolation
because Launch Desk shared the same OpenAI key secret as the main site.

Isolation was then restored by copying the rotated key into the dedicated
Launch Desk secret:

```text
launch-desk-openai-api-key version 3 enabled
created 2026-04-28T18:47:09
```

Current production secret reference:

```text
OPENAI_API_KEY=launch-desk-openai-api-key:latest
```

Current production revision after restoring the dedicated secret:

```text
launch-desk-backend-00006-ppv
```

This is the current production state and restores Launch Desk secret isolation.

## Backend Stream Verification

The deployed backend stream endpoint was verified with:

```powershell
python scripts\verify_launch_desk_stream.py --url https://launch-desk-backend-6gtyc6yuoq-de.a.run.app/api/launch-desk/stream
```

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
trace_id=trace_f1c50ac70e914390921602f6a8fc82f2
duration_ms=13063
timeout_seconds=120
tool_count=5
text_chars=5259
```

Observed generated text began with:

```text
## Prioritized plan
```

After the secret reference was switched to `OPENAI_API_KEY:latest`, the backend
stream verifier was re-run successfully.

Complete event metadata after the switch:

```text
model=gpt-5.4-mini
trace_id=trace_308a1c529d8e455ab179fa0e7f9f67af
duration_ms=14783
timeout_seconds=120
tool_count=5
text_chars=6018
```

After isolation was restored with `launch-desk-openai-api-key:latest`, the
backend stream verifier was re-run successfully.

Complete event metadata after restoring isolation:

```text
model=gpt-5.4-mini
trace_id=trace_256ce0eded6048aaaa9d527cb735e898
duration_ms=17236
timeout_seconds=120
tool_count=5
text_chars=5365
```

## Frontend End-to-End Verification

The production frontend was opened at:

```text
https://launch-desk-orcin.vercel.app/
```

Verified flow:

- Page loaded and displayed the backend API host.
- `Load sample` populated the product brief, audience, launch date,
  constraints, and available assets.
- `Run launch plan` started the streamed agent run.
- The stream reached `Complete`.
- The page showed a generated release plan.
- The page showed readiness at `83%`.
- Tool progress appeared for all expected Launch Desk tools:
  - `extract_launch_tasks`
  - `check_launch_readiness`
  - `generate_owner_checklist`
  - `draft_channel_copy`
  - `missing_detail_questions`
- No visible frontend error was observed.
- No console warning or error was observed for the deployed app domain
  `launch-desk-orcin.vercel.app`.

After the secret reference was switched to `OPENAI_API_KEY:latest`, production
frontend verification was re-run:

- `Load sample` succeeded.
- `Run launch plan` succeeded.
- Agent stream reached `Complete`.
- The run produced a `Prioritized plan`.
- Tool calls and tool completions were observed for all expected Launch Desk
  tools.
- Readiness displayed `83%`.
- No visible frontend error was observed.
- No app-domain console warning or error was observed.

After isolation was restored with `launch-desk-openai-api-key:latest`,
production frontend verification was re-run again:

- `Load sample` succeeded.
- `Run launch plan` succeeded.
- Agent stream reached `Complete`.
- The run produced a `Prioritized plan`.
- Tool calls and tool completions were observed for all expected Launch Desk
  tools.
- Readiness displayed `83%`.
- No visible frontend error was observed.
- No app-domain console warning or error was observed.

## Verification Caveats

One PowerShell `Invoke-WebRequest` OPTIONS probe from the local sandbox failed
with a local remote-connection error. The production path was still validated
through:

- Cloud Run environment inspection confirming the frontend origin in
  `LAUNCH_DESK_ALLOWED_ORIGINS`.
- Remote backend stream verification.
- Browser-based production frontend run against the deployed backend.

## Security Follow-Up

Earlier Cloud Run logs exposed the OpenAI API key before the backend runtime was
hardened to trim secret whitespace. The runtime has been fixed, but the exposed
key should still be rotated.

Completed follow-up:

1. Rotate the OpenAI API key in the OpenAI dashboard.
2. Confirm the rotated key is available as `OPENAI_API_KEY` version 4.
3. Update Launch Desk Cloud Run to read `OPENAI_API_KEY:latest`.
4. Re-run backend stream verification.
5. Re-run frontend production verification.
6. Copy the rotated key into the dedicated `launch-desk-openai-api-key` secret
   as version 3.
7. Switch Cloud Run back to `launch-desk-openai-api-key:latest`.
8. Re-run backend stream verification.
9. Re-run frontend production verification.

Do not paste the key into docs, logs, shell history, issue comments, or PR
descriptions.

## Next Recommended Phase

Phase 1.9 should focus on production hardening without changing behavior:

- Keep the dedicated `launch-desk-openai-api-key` secret as the production
  source for Launch Desk.
- Add a small post-deploy checklist that runs backend stream verification and
  browser frontend verification.
- Decide whether to add Vercel deployment status notes to CI or keep them as a
  manual runbook step.
- Optionally add a custom domain after the current Vercel URL is stable.
