import Head from "next/head";
import { useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_LAUNCH_DESK_API_BASE || "http://127.0.0.1:5057";

const sampleBrief = {
  productBrief:
    "Launch a beta API for engineering managers that turns raw release notes into customer-ready rollout plans, risk summaries, and channel-specific launch copy.",
  audience: "Engineering managers and product leads at B2B SaaS companies",
  launchDate: "2026-05-20",
  constraints: "Beta cohort only, legal review required, rollback through feature flags.",
  availableAssets: "API docs draft, product screenshots, demo recording, support FAQ outline."
};

const initialForm = {
  productBrief: "",
  audience: "",
  launchDate: "2026-05-20",
  constraints: "",
  availableAssets: ""
};

const ERROR_HELP = {
  authentication_error: "Backend cannot authenticate with OpenAI. Check OPENAI_API_KEY on the server.",
  dependency_missing: "Backend is missing the OpenAI Agents SDK dependency.",
  model_error: "The configured Launch Desk model or request settings were rejected.",
  network_error: "Backend could not reach OpenAI. Check server network access.",
  rate_limited: "Too many Launch Desk requests. Wait briefly and retry.",
  rate_limit: "OpenAI rate limit was reached. Wait briefly and retry.",
  timeout: "The request timed out. Try again with a shorter brief.",
  openai_error: "OpenAI returned an error while generating this launch plan.",
  unknown: "Launch Desk hit an unexpected error."
};

export default function LaunchDesk() {
  const [form, setForm] = useState(initialForm);
  const [events, setEvents] = useState([]);
  const [draft, setDraft] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");

  const toolEvents = useMemo(
    () => events.filter((event) => event.type === "tool_progress"),
    [events]
  );
  const completeEvent = useMemo(
    () => events.findLast ? events.findLast((event) => event.type === "complete") : [...events].reverse().find((event) => event.type === "complete"),
    [events]
  );

  const readinessOutput = useMemo(() => {
    const completed = toolEvents.find(
      (event) => event.status === "completed" && event.tool === "check_launch_readiness"
    );
    return completed?.output || null;
  }, [toolEvents]);

  const latestChecklist = useMemo(() => {
    const completed = toolEvents.find(
      (event) => event.status === "completed" && event.tool === "generate_owner_checklist"
    );
    return completed?.output || null;
  }, [toolEvents]);

  async function runAgent() {
    setIsRunning(true);
    setError("");
    setEvents([]);
    setDraft("");

    try {
      const response = await fetch(`${API_BASE}/api/launch-desk/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });

      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `Launch Desk API returned ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const consumeEventBlock = (part) => {
        const event = parseSse(part);
        if (!event) return;
        setEvents((current) => [...current, event.data]);
        if (event.name === "text_delta") {
          setDraft((current) => current + (event.data.delta || ""));
        }
        if (event.name === "error") {
          throw new Error(formatStreamError(event.data));
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          consumeEventBlock(part);
        }
      }

      if (buffer.trim()) {
        consumeEventBlock(buffer);
      }
    } catch (streamError) {
      setError(streamError.message || String(streamError));
    } finally {
      setIsRunning(false);
    }
  }

  function updateField(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function loadSample() {
    setForm(sampleBrief);
    setError("");
  }

  function downloadMarkdown() {
    if (!draft) return;
    downloadText("launch-desk-plan.md", draft, "text/markdown;charset=utf-8");
  }

  function downloadJson() {
    if (!draft) return;
    downloadText(
      "launch-desk-run.json",
      JSON.stringify(
        {
          exportedAt: new Date().toISOString(),
          form,
          generatedPlan: draft,
          completeEvent: completeEvent || null,
          events: events.map((event) => ({
            type: event.type,
            status: event.status,
            tool: event.tool,
            model: event.model,
            trace_id: event.trace_id,
            duration_ms: event.duration_ms,
            tool_count: event.tool_count,
            text_char_count: event.text_char_count
          }))
        },
        null,
        2
      ),
      "application/json;charset=utf-8"
    );
  }

  const canRun = form.productBrief.trim().length >= 40 && form.audience && form.launchDate;

  return (
    <>
      <Head>
        <title>Launch Desk</title>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </Head>
      <main className="appShell">
      <header className="topbar">
        <div>
          <div className="brandKicker">Agent release planning</div>
          <h1>Launch Desk</h1>
        </div>
        <div className="serverBadge">
          <span className="pulse" />
          API {API_BASE.replace(/^https?:\/\//, "")}
        </div>
      </header>

      <section className="workspace" aria-label="Launch planning workspace">
        <aside className="inputPane" aria-label="Launch inputs">
          <div className="paneHeader">
            <div>
              <h2>Launch brief</h2>
              <p>Give the agent enough context to produce owners, risks, copy, and questions.</p>
            </div>
            <button className="ghostButton" type="button" onClick={loadSample}>
              Load sample
            </button>
          </div>

          <label className="fieldGroup">
            <span>Product brief</span>
            <textarea
              rows={8}
              value={form.productBrief}
              onChange={(event) => updateField("productBrief", event.target.value)}
              placeholder="What are you launching, why now, and what needs to be true before release?"
            />
          </label>

          <label className="fieldGroup">
            <span>Audience</span>
            <textarea
              rows={2}
              value={form.audience}
              onChange={(event) => updateField("audience", event.target.value)}
              placeholder="Engineering managers, beta customers, admins..."
            />
          </label>

          <div className="splitFields">
            <label className="fieldGroup">
              <span>Launch date</span>
              <input
                type="date"
                value={form.launchDate}
                onChange={(event) => updateField("launchDate", event.target.value)}
              />
            </label>
            <div className="readinessMini">
              <span>Readiness</span>
              <strong>{readinessOutput ? `${readinessOutput.score}%` : "Pending"}</strong>
            </div>
          </div>

          <label className="fieldGroup">
            <span>Constraints</span>
            <textarea
              rows={4}
              value={form.constraints}
              onChange={(event) => updateField("constraints", event.target.value)}
              placeholder="Legal review, beta-only, no migration, feature flag, support staffing..."
            />
          </label>

          <label className="fieldGroup">
            <span>Available assets</span>
            <textarea
              rows={4}
              value={form.availableAssets}
              onChange={(event) => updateField("availableAssets", event.target.value)}
              placeholder="Docs, screenshots, demo, changelog, FAQ, emails, launch room..."
            />
          </label>

          <button
            className="runButton"
            type="button"
            disabled={!canRun || isRunning}
            onClick={runAgent}
          >
            <span aria-hidden="true">{isRunning ? "..." : ">"}</span>
            {isRunning ? "Planning launch" : "Run launch plan"}
          </button>
          {!canRun && (
            <p className="inlineHint">Brief, audience, and launch date are required before running.</p>
          )}
          {error && <p className="errorText">{error}</p>}
        </aside>

        <section className="agentPane" aria-live="polite" aria-label="Agent stream">
          <div className="paneHeader">
            <div>
              <h2>Agent stream</h2>
              <p>Tool calls and model text stream through the same API route.</p>
            </div>
            <span className={isRunning ? "stateChip running" : "stateChip"}>
              {isRunning ? "Streaming" : completeEvent ? "Complete" : "Idle"}
            </span>
          </div>

          <div className="timeline">
            {events.length === 0 && (
              <div className="emptyState">
                <strong>No run yet</strong>
                <span>Load the sample or enter your launch brief to start a streamed plan.</span>
              </div>
            )}
            {events.map((event, index) => (
              <div className={`timelineItem ${event.type}`} key={`${event.type}-${index}`}>
                <span className="timelineDot" />
                <div>
                  <strong>{eventLabel(event)}</strong>
                  <span>{eventDetail(event)}</span>
                </div>
              </div>
            ))}
          </div>

          <article className="responseCard">
            <div className="responseHeader">
              <div className="responseTitle">
                <span>Generated release plan</span>
                <span>{draft.length} chars</span>
              </div>
              <div className="responseActions" aria-label="Export generated release plan">
                <button type="button" disabled={!draft} onClick={downloadMarkdown}>
                  Markdown
                </button>
                <button type="button" disabled={!draft} onClick={downloadJson}>
                  JSON
                </button>
              </div>
            </div>
            <pre>{draft || "The final plan will stream here as the model writes it."}</pre>
          </article>
        </section>

        <aside className="insightPane" aria-label="Launch outputs">
          <section className="insightBlock">
            <div className="sectionTitle">
              <span>Readiness rubric</span>
              <strong>{readinessOutput ? readinessOutput.status.replace("_", " ") : "Waiting"}</strong>
            </div>
            <div className="scoreRing" style={{ "--score": readinessOutput?.score || 0 }}>
              <span>{readinessOutput ? readinessOutput.score : 0}%</span>
            </div>
            <ul className="rubricList">
              {(readinessOutput?.rubric || []).map((item) => (
                <li key={item.name}>
                  <span className={item.passed ? "checkMark pass" : "checkMark"} />
                  {item.name}
                </li>
              ))}
              {!readinessOutput && <li>Tool output appears after the readiness check completes.</li>}
            </ul>
          </section>

          <section className="insightBlock">
            <div className="sectionTitle">
              <span>Tool progress</span>
              <strong>{toolEvents.length}</strong>
            </div>
            <div className="toolList">
              {toolEvents.slice(-6).map((event, index) => (
                <div className="toolRow" key={`${event.tool}-${index}`}>
                  <span>{event.tool || "tool"}</span>
                  <strong>{event.status}</strong>
                </div>
              ))}
              {toolEvents.length === 0 && <p>Waiting for the first tool call.</p>}
            </div>
          </section>

          <section className="insightBlock">
            <div className="sectionTitle">
              <span>Owner checklist</span>
              <strong>{latestChecklist?.owners?.length || 0}</strong>
            </div>
            <div className="ownerList">
              {(latestChecklist?.owners || []).slice(0, 4).map((owner) => (
                <div className="ownerCard" key={owner.role}>
                  <strong>{owner.role}</strong>
                  <span>{owner.checks[0]}</span>
                </div>
              ))}
              {!latestChecklist && <p>Checklist cards populate from the owner checklist tool.</p>}
            </div>
          </section>
        </aside>
      </section>
      </main>
    </>
  );
}

function parseSse(block) {
  const lines = block.split("\n");
  const nameLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (dataLines.length === 0) return null;
  const name = nameLine ? nameLine.slice("event:".length).trim() : "message";
  const rawData = dataLines.map((line) => line.slice("data:".length).trim()).join("\n");
  try {
    return { name, data: JSON.parse(rawData) };
  } catch {
    return null;
  }
}

function eventLabel(event) {
  if (event.type === "tool_progress") return `Tool ${event.status}`;
  if (event.type === "text_delta") return "Model text";
  if (event.type === "complete") return "Run complete";
  if (event.type === "error") return "Run error";
  return "Status";
}

function eventDetail(event) {
  if (event.type === "tool_progress") return event.tool || "Launch Desk tool";
  if (event.type === "text_delta") return event.delta?.trim() || "Streaming token";
  if (event.type === "complete") {
    return `Tool event: ${event.saw_tool_progress ? "yes" : "no"}; text delta: ${
      event.saw_text_delta ? "yes" : "no"
    }; tools: ${event.tool_count ?? 0}; duration: ${event.duration_ms ?? 0}ms; timeout: ${
      event.timeout_seconds ?? "n/a"
    }s; model: ${event.model || "unknown"}`;
  }
  if (event.type === "error") return formatStreamError(event);
  return event.message || event.model || "Agent status update";
}

function formatStreamError(error) {
  const code = error?.error_code || "unknown";
  return ERROR_HELP[code] || error?.message || "Agent stream failed.";
}

function downloadText(filename, contents, mimeType) {
  const blob = new Blob([contents], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
