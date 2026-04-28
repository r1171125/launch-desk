from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


SAMPLE_PAYLOAD = {
    "productBrief": (
        "Launch a beta API for engineering managers that turns raw release notes into "
        "customer-ready rollout plans, risk summaries, and channel-specific launch copy."
    ),
    "audience": "Engineering managers and product leads at B2B SaaS companies",
    "launchDate": "2026-05-20",
    "constraints": "Beta cohort only, legal review required, rollback through feature flags.",
    "availableAssets": "API docs draft, product screenshots, demo recording, support FAQ outline.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Launch Desk streamed API behavior.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:5057/api/launch-desk/stream",
        help="Launch Desk stream endpoint.",
    )
    args = parser.parse_args()

    saw_tool_progress = False
    saw_text_delta = False
    saw_complete = False
    complete_payload: dict[str, Any] = {}
    events: list[str] = []
    text_preview = ""
    required_complete_fields = {
        "model",
        "trace_id",
        "duration_ms",
        "timeout_seconds",
        "tool_count",
        "tool_completion_count",
        "text_char_count",
    }

    try:
        with requests.post(args.url, json=SAMPLE_PAYLOAD, stream=True, timeout=120) as response:
            response.raise_for_status()
            for event_name, data in _iter_sse(response.iter_lines(decode_unicode=True)):
                events.append(event_name)
                if event_name == "tool_progress":
                    saw_tool_progress = True
                elif event_name == "text_delta" and data.get("delta"):
                    saw_text_delta = True
                    text_preview += str(data["delta"])
                elif event_name == "complete":
                    saw_complete = True
                    complete_payload = data
                elif event_name == "error":
                    print(json.dumps(data, indent=2), file=sys.stderr)
                    return 1

                if saw_tool_progress and saw_text_delta and saw_complete:
                    missing_complete_fields = sorted(
                        field for field in required_complete_fields if field not in complete_payload
                    )
                    if missing_complete_fields:
                        print(
                            "Launch Desk stream verification failed: complete event is missing "
                            f"fields: {', '.join(missing_complete_fields)}",
                            file=sys.stderr,
                        )
                        return 1
                    print("Launch Desk stream verification passed.")
                    print(f"Observed events: {', '.join(events[:10])}")
                    print(f"Text preview: {text_preview[:220].strip()}")
                    print(
                        "Complete flags: "
                        f"tool={complete_payload.get('saw_tool_progress')}, "
                        f"text={complete_payload.get('saw_text_delta')}"
                    )
                    print(
                        "Complete metadata: "
                        f"model={complete_payload.get('model')}, "
                        f"trace_id={complete_payload.get('trace_id')}, "
                        f"duration_ms={complete_payload.get('duration_ms')}, "
                        f"timeout_seconds={complete_payload.get('timeout_seconds')}, "
                        f"tool_count={complete_payload.get('tool_count')}, "
                        f"text_chars={complete_payload.get('text_char_count')}"
                    )
                    return 0
    except Exception as exc:
        print(f"Launch Desk stream verification failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Launch Desk stream verification failed: did not observe tool_progress, "
        "text_delta, and complete events.",
        file=sys.stderr,
    )
    print(f"Observed events: {', '.join(events)}", file=sys.stderr)
    return 1


def _iter_sse(lines: Any) -> Any:
    event_name = "message"
    data_lines: list[str] = []

    for line in lines:
        if line is None:
            continue
        if line == "":
            if data_lines:
                raw_data = "\n".join(data_lines)
                try:
                    payload = json.loads(raw_data)
                except json.JSONDecodeError:
                    payload = {"raw": raw_data}
                yield event_name, payload
            event_name = "message"
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())


if __name__ == "__main__":
    raise SystemExit(main())
