from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any


@dataclass(frozen=True)
class LaunchDeskPayload:
    product_brief: str
    audience: str
    launch_date: str
    constraints: str
    available_assets: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class LaunchDeskValidationError(ValueError):
    pass


def normalize_launch_payload(raw_payload: dict[str, Any] | None) -> LaunchDeskPayload:
    if not isinstance(raw_payload, dict):
        raise LaunchDeskValidationError("Request body must be a JSON object.")

    product_brief = _clean_text(raw_payload.get("productBrief") or raw_payload.get("product_brief"))
    audience = _clean_text(raw_payload.get("audience"))
    launch_date = _clean_text(raw_payload.get("launchDate") or raw_payload.get("launch_date"))
    constraints = _clean_text(raw_payload.get("constraints"))
    available_assets = _clean_text(
        raw_payload.get("availableAssets") or raw_payload.get("available_assets")
    )

    if len(product_brief) < 40:
        raise LaunchDeskValidationError(
            "Product brief must be at least 40 characters so the agent has enough launch context."
        )
    if not audience:
        raise LaunchDeskValidationError("Audience is required.")
    if not launch_date:
        raise LaunchDeskValidationError("Launch date is required.")

    try:
        date.fromisoformat(launch_date)
    except ValueError as exc:
        raise LaunchDeskValidationError("Launch date must use YYYY-MM-DD format.") from exc

    return LaunchDeskPayload(
        product_brief=product_brief,
        audience=audience,
        launch_date=launch_date,
        constraints=constraints or "No explicit constraints provided.",
        available_assets=available_assets or "No assets listed yet.",
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", "\n").split())
