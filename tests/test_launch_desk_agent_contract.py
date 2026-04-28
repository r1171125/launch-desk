import asyncio
import os

from launch_desk.agent import (
    _build_launch_prompt,
    _classified_error_event,
    normalize_openai_api_key_env,
    stream_launch_desk_events,
)
from launch_desk.payloads import LaunchDeskPayload


def sample_payload():
    return LaunchDeskPayload(
        product_brief=(
            "Launch a beta API that turns raw engineering release notes into "
            "customer-ready launch plans."
        ),
        audience="Engineering managers",
        launch_date="2026-05-20",
        constraints="Legal review and feature flag rollback are required.",
        available_assets="API docs, screenshots, demo recording, and FAQ draft.",
    )


def test_launch_prompt_requires_stable_final_sections():
    prompt = _build_launch_prompt(sample_payload())

    assert "## Prioritized plan" in prompt
    assert "## Risk register" in prompt
    assert "## Owner checklist" in prompt
    assert "## Launch copy suggestions" in prompt
    assert "## Follow-up questions" in prompt


def test_classified_error_event_hides_raw_exception_details():
    event = _classified_error_event(
        RuntimeError("provider exploded with internal detail"),
        request_id="req-1",
        trace_id="trace-1",
        model="test-model",
        duration_ms=123,
        timeout_seconds=45,
    )

    assert event["type"] == "error"
    assert event["error_code"] == "unknown"
    assert event["message"] == "Launch Desk hit an unexpected error while generating the plan."
    assert "provider exploded" not in event["message"]
    assert event["trace_id"] == "trace-1"
    assert event["duration_ms"] == 123
    assert event["timeout_seconds"] == 45


def test_openai_api_key_is_normalized_for_header_safety(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", " test-key\r\n")

    assert normalize_openai_api_key_env() == "test-key"
    assert os.environ["OPENAI_API_KEY"] == "test-key"


def test_stream_bridge_preserves_async_events(monkeypatch):
    async def fake_async_stream(payload, request_id):
        assert payload.audience == "Engineering managers"
        yield {"type": "status", "request_id": request_id, "message": "ready"}
        await asyncio.sleep(0)
        yield {
            "type": "complete",
            "request_id": request_id,
            "model": "test-model",
            "trace_id": "trace-test",
            "saw_tool_progress": True,
            "saw_text_delta": True,
            "duration_ms": 1,
            "timeout_seconds": 45,
            "tool_count": 1,
            "tool_completion_count": 1,
            "text_char_count": 4,
        }

    monkeypatch.setattr("launch_desk.agent._stream_launch_desk_events_async", fake_async_stream)

    events = list(stream_launch_desk_events(sample_payload(), request_id="req-1"))

    assert [event["type"] for event in events] == ["status", "complete"]
    assert events[-1]["tool_count"] == 1
