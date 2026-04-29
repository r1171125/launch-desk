from __future__ import annotations

from typing import Any


LAUNCH_PLAN_TEMPLATE_VERSION = "launch-plan-v2.0"
JSON_EXPORT_SCHEMA_VERSION = "launch-desk-export-v1.0"
FOLLOW_UP_MODE = "prioritized_missing_details_v1"

FINAL_RESPONSE_SECTIONS = (
    "## Prioritized plan",
    "## Risk register",
    "## Owner checklist",
    "## Launch copy suggestions",
    "## Follow-up questions",
)

LAUNCH_PLAN_JSON_EXPORT_SCHEMA: dict[str, Any] = {
    "schema_version": JSON_EXPORT_SCHEMA_VERSION,
    "template_version": LAUNCH_PLAN_TEMPLATE_VERSION,
    "required_top_level_keys": [
        "schema_version",
        "template_version",
        "exported_at",
        "inputs",
        "outputs",
        "run",
    ],
    "outputs": {
        "markdown": "string",
        "tool_outputs": {
            "tasks": "object|null",
            "readiness": "object|null",
            "owner_checklist": "object|null",
            "launch_copy": "object|null",
            "follow_up_questions": "object|null",
        },
    },
}
