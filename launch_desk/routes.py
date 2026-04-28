from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any

from flask import Blueprint, Flask, Response, jsonify, request, stream_with_context

from .agent import (
    DEFAULT_MODEL,
    get_launch_desk_runtime_config,
    normalize_openai_api_key_env,
    stream_launch_desk_events,
)
from .payloads import LaunchDeskValidationError, normalize_launch_payload

launch_desk_bp = Blueprint("launch_desk", __name__)
LOGGER = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_PER_MINUTE = 12
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


@launch_desk_bp.after_request
def add_launch_desk_cors_headers(response: Response) -> Response:
    origin = request.headers.get("Origin")
    if _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@launch_desk_bp.route("/api/launch-desk/health", methods=["GET"])
def launch_desk_health() -> Response:
    runtime_config = get_launch_desk_runtime_config()
    return jsonify(
        {
            "ok": True,
            "app": "launch-desk",
            "model": runtime_config["model"],
            "openai_api_key_configured": bool(normalize_openai_api_key_env()),
            "stream_bridge": "async-queue",
            "request_timeout_seconds": runtime_config["request_timeout_seconds"],
            "max_tokens": runtime_config["max_tokens"],
            "model_retries": runtime_config["model_retries"],
            "rate_limit_per_minute": _rate_limit_per_minute(),
        }
    )


@launch_desk_bp.route("/api/launch-desk/stream", methods=["POST", "OPTIONS"])
def launch_desk_stream() -> Response:
    if request.method == "OPTIONS":
        return Response(status=204)

    try:
        payload = normalize_launch_payload(request.get_json(silent=True))
    except LaunchDeskValidationError as exc:
        LOGGER.info(
            "launch_desk.validation_error %s",
            json.dumps({"error": str(exc)}, ensure_ascii=False),
        )
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not normalize_openai_api_key_env():
        LOGGER.warning("launch_desk.missing_api_key")
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "OPENAI_API_KEY is not configured for the backend process.",
                }
            ),
            500,
        )

    client_key = _client_rate_limit_key()
    allowed, retry_after_seconds = _consume_rate_limit(client_key)
    if not allowed:
        LOGGER.warning(
            "launch_desk.rate_limited %s",
            json.dumps(
                {
                    "client": client_key,
                    "retry_after_seconds": retry_after_seconds,
                    "limit": _rate_limit_per_minute(),
                },
                ensure_ascii=False,
            ),
        )
        response = jsonify(
            {
                "ok": False,
                "error_code": "rate_limited",
                "error": "Too many Launch Desk requests. Wait briefly and try again.",
                "retry_after_seconds": retry_after_seconds,
            }
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after_seconds)
        return response

    request_id = uuid.uuid4().hex
    LOGGER.info(
        "launch_desk.request_start %s",
        json.dumps(
            {
                "request_id": request_id,
                "client": client_key,
                "model": os.getenv("LAUNCH_DESK_MODEL", DEFAULT_MODEL),
            },
            ensure_ascii=False,
        ),
    )

    def generate() -> Any:
        for event in stream_launch_desk_events(payload, request_id=request_id):
            yield _sse(event["type"], event)

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def create_launch_desk_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(launch_desk_bp)
    return app


def _sse(event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _is_allowed_origin(origin: str | None) -> bool:
    if not origin:
        return False
    configured = {
        item.strip()
        for item in os.getenv("LAUNCH_DESK_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    local_defaults = {
        "http://localhost:3007",
        "http://127.0.0.1:3007",
        "http://localhost:3008",
        "http://127.0.0.1:3008",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
    return origin in configured or origin in local_defaults


def _client_rate_limit_key() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return request.remote_addr or "unknown"


def _consume_rate_limit(client_key: str) -> tuple[bool, int]:
    limit = _rate_limit_per_minute()
    if limit <= 0:
        return True, 0

    window_seconds = _rate_limit_window_seconds()
    now = time.time()
    cutoff = now - window_seconds

    with _RATE_LIMIT_LOCK:
        timestamps = [
            timestamp
            for timestamp in _RATE_LIMIT_BUCKETS.get(client_key, [])
            if timestamp >= cutoff
        ]
        allowed = len(timestamps) < limit
        if allowed:
            timestamps.append(now)
        _RATE_LIMIT_BUCKETS[client_key] = timestamps

        retry_after = 0
        if not allowed and timestamps:
            retry_after = max(1, round(window_seconds - (now - timestamps[0])))
        return allowed, retry_after


def _rate_limit_per_minute() -> int:
    return _env_int(
        "LAUNCH_DESK_RATE_LIMIT_PER_MINUTE",
        DEFAULT_RATE_LIMIT_PER_MINUTE,
        minimum=0,
        maximum=120,
    )


def _rate_limit_window_seconds() -> int:
    return _env_int(
        "LAUNCH_DESK_RATE_LIMIT_WINDOW_SECONDS",
        60,
        minimum=1,
        maximum=3600,
    )


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _clear_rate_limit_state_for_tests() -> None:
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()
