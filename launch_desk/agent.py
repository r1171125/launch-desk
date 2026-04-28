from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
import time
from collections.abc import AsyncGenerator, Generator
from typing import Any

from .payloads import LaunchDeskPayload
from .tools import (
    check_launch_readiness_impl,
    draft_channel_copy_impl,
    extract_launch_tasks_impl,
    generate_owner_checklist_impl,
    missing_detail_questions_impl,
)


class LaunchDeskDependencyError(RuntimeError):
    pass


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_TOKENS = 3600
DEFAULT_RETRY_COUNT = 2
DEFAULT_VERBOSITY = "medium"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120

LOGGER = logging.getLogger(__name__)

FINAL_RESPONSE_CONTRACT = (
    "Write the final answer in Markdown with these exact top-level sections, in this order:\n"
    "## Prioritized plan\n"
    "## Risk register\n"
    "## Owner checklist\n"
    "## Launch copy suggestions\n"
    "## Follow-up questions\n"
    "Each section must be concrete and launch-ready. Include owners and due hints in the plan, "
    "severity/mitigation/owner in the risk register, role-based checklists, channel-specific copy, "
    "and only practical follow-up questions for missing details."
)


def stream_launch_desk_events(
    payload: LaunchDeskPayload,
    request_id: str,
) -> Generator[dict[str, Any], None, None]:
    """Bridge the async Agents SDK stream into a sync Flask response generator."""

    event_queue: queue.Queue[dict[str, Any] | object] = queue.Queue()
    sentinel = object()

    def run_async_stream() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def consume() -> None:
            try:
                async for event in _stream_launch_desk_events_async(payload, request_id):
                    event_queue.put(event)
            except Exception as exc:
                event_queue.put(
                    _classified_error_event(exc, request_id=request_id)
                )
            finally:
                event_queue.put(sentinel)

        try:
            loop.run_until_complete(consume())
        finally:
            loop.close()

    thread = threading.Thread(target=run_async_stream, daemon=True)
    thread.start()

    while True:
        event = event_queue.get()
        if event is sentinel:
            break
        yield event


async def _stream_launch_desk_events_async(
    payload: LaunchDeskPayload,
    request_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    agents = _load_agents_sdk()
    ResponseTextDeltaEvent = _load_response_text_delta_event()

    model = os.getenv("LAUNCH_DESK_MODEL", DEFAULT_MODEL)
    started_at = time.perf_counter()
    trace_id = agents.gen_trace_id()
    agent = _build_launch_desk_agent(agents=agents, model=model)
    prompt = _build_launch_prompt(payload)
    timeout_seconds = _env_int(
        "LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS",
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
        minimum=10,
        maximum=600,
    )
    run_config = agents.RunConfig(
        workflow_name="Launch Desk release planning",
        trace_id=trace_id,
        group_id=request_id,
        trace_metadata={
            "app": "launch-desk",
            "audience": payload.audience[:80],
            "launch_date": payload.launch_date,
            "model": model,
        },
    )
    _log_observation(
        "start",
        {
            "request_id": request_id,
            "trace_id": trace_id,
            "model": model,
            "timeout_seconds": timeout_seconds,
        },
    )

    yield {
        "type": "status",
        "request_id": request_id,
        "trace_id": trace_id,
        "model": model,
        "timeout_seconds": timeout_seconds,
        "message": "Launch Desk agent initialized.",
    }

    text_seen = False
    tool_seen = False
    text_char_count = 0
    tool_call_count = 0
    tool_completion_count = 0
    tool_call_names: dict[str, str] = {}
    tool_names: set[str] = set()
    usage_snapshot: Any = None

    try:
        async with asyncio.timeout(timeout_seconds):
            result = agents.Runner.run_streamed(
                agent,
                input=prompt,
                max_turns=8,
                run_config=run_config,
            )
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    if event.data.delta:
                        text_seen = True
                        text_char_count += len(event.data.delta)
                        yield {
                            "type": "text_delta",
                            "request_id": request_id,
                            "delta": event.data.delta,
                        }
                    continue

                usage_candidate = _usage_from_event_data(getattr(event, "data", None))
                if usage_candidate is not None:
                    usage_snapshot = usage_candidate

                if event.type == "agent_updated_stream_event":
                    yield {
                        "type": "status",
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "message": f"Agent updated: {event.new_agent.name}",
                    }
                    continue

                if event.type == "run_item_stream_event":
                    if event.item.type == "tool_call_item":
                        tool_seen = True
                        tool_call_count += 1
                        tool_name = _tool_name(event.item)
                        tool_names.add(tool_name)
                        tool_call_id = _tool_call_id(event.item)
                        if tool_call_id:
                            tool_call_names[tool_call_id] = tool_name
                        yield {
                            "type": "tool_progress",
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "status": "called",
                            "tool": tool_name,
                            "title": getattr(event.item, "title", None),
                        }
                    elif event.item.type == "tool_call_output_item":
                        tool_seen = True
                        tool_completion_count += 1
                        tool_call_id = _tool_call_id(event.item)
                        tool_name = tool_call_names.get(tool_call_id) or _tool_name(event.item)
                        tool_names.add(tool_name)
                        yield {
                            "type": "tool_progress",
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "status": "completed",
                            "tool": tool_name,
                            "output": _json_safe(event.item.output),
                        }

        complete_event = {
            "type": "complete",
            "request_id": request_id,
            "trace_id": trace_id,
            "model": model,
            "saw_tool_progress": tool_seen,
            "saw_text_delta": text_seen,
            "duration_ms": _elapsed_ms(started_at),
            "timeout_seconds": timeout_seconds,
            "tool_count": tool_call_count,
            "tool_completion_count": tool_completion_count,
            "tool_names": sorted(tool_names),
            "text_char_count": text_char_count,
            "usage": _json_safe(usage_snapshot),
        }
        _log_observation("complete", complete_event)
        yield complete_event
    except Exception as exc:
        error_event = _classified_error_event(
            exc,
            request_id=request_id,
            trace_id=trace_id,
            model=model,
            duration_ms=_elapsed_ms(started_at),
            timeout_seconds=timeout_seconds,
        )
        _log_observation("error", error_event)
        yield error_event


def _build_launch_desk_agent(*, agents: Any, model: str) -> Any:
    function_tool = agents.function_tool

    @function_tool
    def extract_launch_tasks(
        product_brief: str,
        audience: str,
        launch_date: str,
        constraints: str,
        available_assets: str,
    ) -> dict[str, Any]:
        """Extract prioritized launch tasks from the rough product brief."""

        return extract_launch_tasks_impl(
            product_brief, audience, launch_date, constraints, available_assets
        )

    @function_tool
    def check_launch_readiness(
        product_brief: str,
        audience: str,
        launch_date: str,
        constraints: str,
        available_assets: str,
    ) -> dict[str, Any]:
        """Score launch readiness and identify risks using the Launch Desk rubric."""

        return check_launch_readiness_impl(
            product_brief, audience, launch_date, constraints, available_assets
        )

    @function_tool
    def generate_owner_checklist(
        product_brief: str,
        audience: str,
        launch_date: str,
        constraints: str,
        available_assets: str,
    ) -> dict[str, Any]:
        """Generate owner-specific pre-launch and launch-day checklists."""

        return generate_owner_checklist_impl(
            product_brief, audience, launch_date, constraints, available_assets
        )

    @function_tool
    def draft_channel_copy(
        product_brief: str,
        audience: str,
        launch_date: str,
        constraints: str,
        available_assets: str,
    ) -> dict[str, Any]:
        """Draft short launch copy for internal, customer, changelog, and social channels."""

        return draft_channel_copy_impl(
            product_brief, audience, launch_date, constraints, available_assets
        )

    @function_tool
    def missing_detail_questions(
        product_brief: str,
        audience: str,
        launch_date: str,
        constraints: str,
        available_assets: str,
    ) -> dict[str, Any]:
        """Ask follow-up questions when key launch inputs are missing."""

        return missing_detail_questions_impl(
            product_brief, audience, launch_date, constraints, available_assets
        )

    return agents.Agent(
        name="Launch Desk",
        model=model,
        instructions=(
            "You are Launch Desk, a release-planning agent for engineering teams. "
            "Turn rough launch inputs into an actionable, prioritized release plan. "
            "Use the available tools before writing the final answer. Call tools with the exact "
            "product_brief, audience, launch_date, constraints, and available_assets values from "
            "the user payload. "
            f"{FINAL_RESPONSE_CONTRACT} "
            "Be concrete, assign owners, identify blockers, and keep copy suggestions channel-specific. "
            "If details are missing, include practical questions rather than inventing facts."
        ),
        tools=[
            extract_launch_tasks,
            check_launch_readiness,
            generate_owner_checklist,
            draft_channel_copy,
            missing_detail_questions,
        ],
        model_settings=_build_model_settings(agents),
    )


def _build_launch_prompt(payload: LaunchDeskPayload) -> str:
    data = payload.to_dict()
    return (
        "Create a launch plan from this JSON payload. Use the tools first, then synthesize "
        "the final plan in concise Markdown.\n\n"
        f"{FINAL_RESPONSE_CONTRACT}\n\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}"
    )


def _load_agents_sdk() -> Any:
    try:
        import agents
        from agents import Agent, ModelSettings, RunConfig, Runner, function_tool
        from agents.model_settings import ModelRetrySettings
        from agents.tracing import gen_trace_id
    except ModuleNotFoundError as exc:
        raise LaunchDeskDependencyError(
            "OpenAI Agents SDK is not installed. Install with `pip install openai-agents` "
            "or set PYTHONPATH to the workspace-local SDK folder used by this repo."
        ) from exc

    agents.Agent = Agent
    agents.ModelSettings = ModelSettings
    agents.ModelRetrySettings = ModelRetrySettings
    agents.RunConfig = RunConfig
    agents.Runner = Runner
    agents.function_tool = function_tool
    agents.gen_trace_id = gen_trace_id
    return agents


def _build_model_settings(agents: Any) -> Any:
    retry_count = _env_int("LAUNCH_DESK_MODEL_RETRIES", DEFAULT_RETRY_COUNT, minimum=0, maximum=5)
    max_tokens = _env_int("LAUNCH_DESK_MAX_TOKENS", DEFAULT_MAX_TOKENS, minimum=800, maximum=12000)
    verbosity = os.getenv("LAUNCH_DESK_VERBOSITY", DEFAULT_VERBOSITY).strip().lower()
    if verbosity not in {"low", "medium", "high"}:
        verbosity = DEFAULT_VERBOSITY

    prompt_cache_retention = os.getenv("LAUNCH_DESK_PROMPT_CACHE_RETENTION", "").strip()
    if prompt_cache_retention not in {"in_memory", "24h"}:
        prompt_cache_retention = None

    return agents.ModelSettings(
        tool_choice="required",
        parallel_tool_calls=True,
        verbosity=verbosity,
        max_tokens=max_tokens,
        include_usage=True,
        retry=agents.ModelRetrySettings(max_retries=retry_count),
        prompt_cache_retention=prompt_cache_retention,
        metadata={"app": "launch-desk"},
    )


def _load_response_text_delta_event() -> Any:
    try:
        from openai.types.responses import ResponseTextDeltaEvent
    except ModuleNotFoundError as exc:
        raise LaunchDeskDependencyError(
            "OpenAI Python SDK 2.x is required for Agents SDK streaming events."
        ) from exc
    return ResponseTextDeltaEvent


def _tool_name(item: Any) -> str:
    origin = getattr(item, "tool_origin", None)
    if origin is not None:
        name = getattr(origin, "name", None)
        if name:
            return str(name)
    raw_item = getattr(item, "raw_item", {})
    if isinstance(raw_item, dict):
        return str(raw_item.get("name") or raw_item.get("tool_name") or "tool")
    return str(getattr(raw_item, "name", None) or getattr(raw_item, "type", None) or "tool")


def _tool_call_id(item: Any) -> str:
    direct = getattr(item, "call_id", None)
    if direct:
        return str(direct)
    raw_item = getattr(item, "raw_item", None)
    if isinstance(raw_item, dict):
        return str(raw_item.get("call_id") or raw_item.get("id") or "")
    return str(getattr(raw_item, "call_id", None) or getattr(raw_item, "id", None) or "")


def _classified_error_event(
    exc: Exception,
    *,
    request_id: str,
    trace_id: str | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    error_code, message, retryable = _classify_error(exc)
    event: dict[str, Any] = {
        "type": "error",
        "request_id": request_id,
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
        "error_class": exc.__class__.__name__,
    }
    if trace_id:
        event["trace_id"] = trace_id
    if model:
        event["model"] = model
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    if timeout_seconds is not None:
        event["timeout_seconds"] = timeout_seconds
    return event


def _classify_error(exc: Exception) -> tuple[str, str, bool]:
    class_name = exc.__class__.__name__.lower()
    message = str(exc).lower()

    if isinstance(exc, LaunchDeskDependencyError):
        return (
            "dependency_missing",
            "Launch Desk is missing the OpenAI Agents SDK dependency.",
            False,
        )
    if "authentication" in class_name or "api key" in message or "401" in message:
        return (
            "authentication_error",
            "The backend cannot authenticate with OpenAI. Check OPENAI_API_KEY for the server process.",
            False,
        )
    if "ratelimit" in class_name or "rate limit" in message or "429" in message:
        return (
            "rate_limit",
            "OpenAI rate limit was reached. Wait briefly and try again.",
            True,
        )
    if "timeout" in class_name or "timed out" in message or "timeout" in message:
        return (
            "timeout",
            "Launch Desk timed out while waiting for the model response. Try again with a shorter brief.",
            True,
        )
    if "connection" in class_name or "network" in message or "connection" in message:
        return (
            "network_error",
            "The backend could not reach OpenAI. Check network access from the server process.",
            True,
        )
    if "badrequest" in class_name or "not found" in message or "invalid" in message:
        return (
            "model_error",
            "The configured model or request settings were rejected. Check LAUNCH_DESK_MODEL and model settings.",
            False,
        )
    if "openai" in getattr(exc.__class__, "__module__", "").lower():
        return (
            "openai_error",
            "OpenAI returned an error while generating the launch plan.",
            True,
        )
    return (
        "unknown",
        "Launch Desk hit an unexpected error while generating the plan.",
        False,
    )


def _usage_from_event_data(data: Any) -> Any:
    if data is None:
        return None
    usage = getattr(data, "usage", None)
    if usage is not None:
        return usage
    if isinstance(data, dict):
        return data.get("usage")
    return None


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _log_observation(event_name: str, payload: dict[str, Any]) -> None:
    LOGGER.info(
        "launch_desk.%s %s",
        event_name,
        json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True),
    )


def get_launch_desk_runtime_config() -> dict[str, Any]:
    return {
        "model": os.getenv("LAUNCH_DESK_MODEL", DEFAULT_MODEL),
        "max_tokens": _env_int(
            "LAUNCH_DESK_MAX_TOKENS",
            DEFAULT_MAX_TOKENS,
            minimum=800,
            maximum=12000,
        ),
        "model_retries": _env_int(
            "LAUNCH_DESK_MODEL_RETRIES",
            DEFAULT_RETRY_COUNT,
            minimum=0,
            maximum=5,
        ),
        "request_timeout_seconds": _env_int(
            "LAUNCH_DESK_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
            minimum=10,
            maximum=600,
        ),
        "verbosity": os.getenv("LAUNCH_DESK_VERBOSITY", DEFAULT_VERBOSITY).strip().lower()
        or DEFAULT_VERBOSITY,
    }


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))
