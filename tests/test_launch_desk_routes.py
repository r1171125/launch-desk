from launch_desk.payloads import LaunchDeskPayload
from launch_desk.routes import _clear_rate_limit_state_for_tests
from launch_desk.routes import create_launch_desk_app


def test_launch_desk_health_reports_key_presence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LAUNCH_DESK_RATE_LIMIT_PER_MINUTE", "9")
    app = create_launch_desk_app()

    response = app.test_client().get("/api/launch-desk/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["openai_api_key_configured"] is True
    assert payload["stream_bridge"] == "async-queue"
    assert payload["request_timeout_seconds"] == 45
    assert payload["rate_limit_per_minute"] == 9


def test_launch_desk_stream_returns_sse(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LAUNCH_DESK_RATE_LIMIT_PER_MINUTE", "0")

    def fake_stream(payload: LaunchDeskPayload, request_id: str):
        assert payload.audience == "Engineering managers"
        yield {
            "type": "tool_progress",
            "request_id": request_id,
            "status": "called",
            "tool": "extract_launch_tasks",
        }
        yield {"type": "text_delta", "request_id": request_id, "delta": "Plan"}
        yield {
            "type": "complete",
            "request_id": request_id,
            "model": "test-model",
            "trace_id": "trace_test",
            "saw_tool_progress": True,
            "saw_text_delta": True,
            "duration_ms": 10,
            "timeout_seconds": 45,
            "tool_count": 1,
            "tool_completion_count": 0,
            "text_char_count": 4,
        }

    monkeypatch.setattr("launch_desk.routes.stream_launch_desk_events", fake_stream)
    app = create_launch_desk_app()

    response = app.test_client().post(
        "/api/launch-desk/stream",
        json={
            "productBrief": (
                "Launch a beta API that turns release notes into launch plans for "
                "engineering teams."
            ),
            "audience": "Engineering managers",
            "launchDate": "2026-05-20",
            "constraints": "Feature flag required.",
            "availableAssets": "Docs and screenshots.",
        },
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert "event: tool_progress" in body
    assert "event: text_delta" in body
    assert "event: complete" in body
    assert '"duration_ms": 10' in body


def test_launch_desk_stream_rate_limits_requests(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LAUNCH_DESK_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("LAUNCH_DESK_RATE_LIMIT_WINDOW_SECONDS", "60")
    _clear_rate_limit_state_for_tests()

    def fake_stream(payload: LaunchDeskPayload, request_id: str):
        yield {"type": "complete", "request_id": request_id}

    monkeypatch.setattr("launch_desk.routes.stream_launch_desk_events", fake_stream)
    app = create_launch_desk_app()
    client = app.test_client()
    payload = {
        "productBrief": (
            "Launch a beta API that turns release notes into launch plans for "
            "engineering teams."
        ),
        "audience": "Engineering managers",
        "launchDate": "2026-05-20",
        "constraints": "Feature flag required.",
        "availableAssets": "Docs and screenshots.",
    }

    first_response = client.post("/api/launch-desk/stream", json=payload)
    second_response = client.post("/api/launch-desk/stream", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.get_json()["error_code"] == "rate_limited"
    assert second_response.headers["Retry-After"]
