export const LAUNCH_PLAN_TEMPLATE_VERSION = "launch-plan-v2.0";
export const JSON_EXPORT_SCHEMA_VERSION = "launch-desk-export-v1.0";

export const EXPECTED_SECTIONS = [
  "## Prioritized plan",
  "## Risk register",
  "## Owner checklist",
  "## Launch copy suggestions",
  "## Follow-up questions"
];

export function buildLaunchDeskExport({ form, draft, events }) {
  const toolOutputs = {
    tasks: latestToolOutput(events, "extract_launch_tasks"),
    readiness: latestToolOutput(events, "check_launch_readiness"),
    owner_checklist: latestToolOutput(events, "generate_owner_checklist"),
    launch_copy: latestToolOutput(events, "draft_channel_copy"),
    follow_up_questions: latestToolOutput(events, "missing_detail_questions")
  };
  const completeEvent = findLastEvent(events, "complete");

  return {
    schema_version: JSON_EXPORT_SCHEMA_VERSION,
    template_version: completeEvent?.template_version || LAUNCH_PLAN_TEMPLATE_VERSION,
    exported_at: new Date().toISOString(),
    inputs: {
      product_brief: form.productBrief,
      audience: form.audience,
      launch_date: form.launchDate,
      constraints: form.constraints,
      available_assets: form.availableAssets
    },
    outputs: {
      markdown: draft,
      expected_sections: EXPECTED_SECTIONS,
      detected_sections: EXPECTED_SECTIONS.filter((section) => draft.includes(section)),
      tool_outputs: toolOutputs
    },
    run: {
      request_id: completeEvent?.request_id || null,
      trace_id: completeEvent?.trace_id || null,
      model: completeEvent?.model || null,
      duration_ms: completeEvent?.duration_ms || null,
      timeout_seconds: completeEvent?.timeout_seconds || null,
      tool_count: completeEvent?.tool_count || 0,
      tool_completion_count: completeEvent?.tool_completion_count || 0,
      text_char_count: completeEvent?.text_char_count || draft.length,
      tool_names: completeEvent?.tool_names || [],
      saw_tool_progress: Boolean(completeEvent?.saw_tool_progress),
      saw_text_delta: Boolean(completeEvent?.saw_text_delta)
    }
  };
}

export function latestToolOutput(events, toolName) {
  return (
    findLast(
      events,
      (event) => event.type === "tool_progress" && event.status === "completed" && event.tool === toolName
    )?.output || null
  );
}

export function findLastEvent(events, type) {
  return findLast(events, (event) => event.type === type) || null;
}

function findLast(items, predicate) {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) return items[index];
  }
  return null;
}
