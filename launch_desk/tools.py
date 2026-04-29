from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from .contracts import FOLLOW_UP_MODE


def extract_launch_tasks_impl(
    product_brief: str,
    audience: str,
    launch_date: str,
    constraints: str,
    available_assets: str,
) -> dict[str, Any]:
    """Derive a pragmatic launch task list from the raw brief."""

    days_until_launch = _days_until(launch_date)
    task_candidates = [
        ("Brief alignment", "Confirm value proposition, audience, scope, and success metrics."),
        ("Release scope", "Freeze launch scope and identify feature flags or staged rollout needs."),
        ("Quality gates", "Schedule QA, accessibility, security, analytics, and rollback checks."),
        ("Enablement", "Prepare support notes, internal FAQs, sales notes, and handoff owners."),
        ("Launch comms", "Draft in-product, email, social, changelog, and internal announcement copy."),
        ("Post-launch watch", "Assign metric monitoring, incident response, and feedback triage."),
    ]

    if "beta" in product_brief.lower() or "pilot" in product_brief.lower():
        task_candidates.insert(
            2,
            ("Beta cohort readiness", "Validate invite list, opt-in language, and beta feedback loop."),
        )
    if "api" in product_brief.lower():
        task_candidates.insert(
            3,
            ("Developer documentation", "Publish API reference, examples, auth notes, and migration guidance."),
        )
    if "compliance" in constraints.lower() or "legal" in constraints.lower():
        task_candidates.insert(
            3,
            ("Legal and compliance review", "Lock approval path for claims, data handling, and launch copy."),
        )

    prioritized_tasks = []
    for index, (title, description) in enumerate(task_candidates, start=1):
        priority = "P0" if index <= 3 else "P1" if index <= 5 else "P2"
        owner = _owner_for_title(title)
        prioritized_tasks.append(
            {
                "priority": priority,
                "title": title,
                "owner": owner,
                "description": description,
                "due": _due_hint(days_until_launch, priority),
            }
        )

    return {
        "launch_date": launch_date,
        "days_until_launch": days_until_launch,
        "audience": audience,
        "assets_summary": _summarize_assets(available_assets),
        "prioritized_tasks": prioritized_tasks,
    }


def check_launch_readiness_impl(
    product_brief: str,
    audience: str,
    launch_date: str,
    constraints: str,
    available_assets: str,
) -> dict[str, Any]:
    """Score launch readiness against an engineering release rubric."""

    text = " ".join([product_brief, audience, constraints, available_assets]).lower()
    rubric = [
        ("Positioning", _contains_any(text, ["value", "problem", "benefit", "why", "persona"])),
        ("Audience clarity", len(audience.split()) >= 2),
        ("Date realism", _days_until(launch_date) >= 7),
        ("Risk controls", _contains_any(text, ["rollback", "flag", "qa", "test", "security"])),
        ("Launch assets", _contains_any(text, ["copy", "demo", "doc", "screenshot", "video", "faq"])),
        ("Ownership", _contains_any(text, ["owner", "dri", "pm", "eng", "support", "marketing"])),
    ]

    passed = sum(1 for _, ok in rubric if ok)
    score = round((passed / len(rubric)) * 100)
    gaps = [name for name, ok in rubric if not ok]

    risk_register = [
        {
            "risk": "Scope changes after plan creation",
            "severity": "High" if _days_until(launch_date) < 14 else "Medium",
            "mitigation": "Freeze P0 scope and route late additions through a launch captain.",
        },
        {
            "risk": "Launch claims not backed by assets",
            "severity": "Medium" if "doc" not in text and "demo" not in text else "Low",
            "mitigation": "Tie every public claim to a demo, doc, metric, or approved screenshot.",
        },
        {
            "risk": "Support team sees issues before engineering does",
            "severity": "Medium",
            "mitigation": "Create support macros, escalation owner, and launch-day incident channel.",
        },
    ]

    if "compliance" in text or "legal" in text:
        risk_register.append(
            {
                "risk": "Regulated claims require approval",
                "severity": "High",
                "mitigation": "Block external copy until legal/compliance signs off.",
            }
        )

    return {
        "score": score,
        "status": "ready" if score >= 75 else "needs_work" if score >= 50 else "blocked",
        "rubric": [{"name": name, "passed": ok} for name, ok in rubric],
        "gaps": gaps,
        "risk_register": risk_register,
    }


def generate_owner_checklist_impl(
    product_brief: str,
    audience: str,
    launch_date: str,
    constraints: str,
    available_assets: str,
) -> dict[str, Any]:
    """Create an owner-based launch checklist."""

    return {
        "owners": [
            {
                "role": "Engineering lead",
                "checks": [
                    "Confirm release branch, feature flag, rollback owner, and monitoring dashboard.",
                    "Validate QA completion and unresolved bug threshold.",
                    "Prepare launch-day support rotation.",
                ],
            },
            {
                "role": "Product manager",
                "checks": [
                    "Confirm launch goals, target audience, customer-facing scope, and success metrics.",
                    "Approve follow-up question answers before external copy ships.",
                    "Run final go/no-go meeting.",
                ],
            },
            {
                "role": "Design or content",
                "checks": [
                    "Review screenshots, product naming, UI copy, and empty/error states.",
                    "Make sure available assets match the selected channels.",
                ],
            },
            {
                "role": "Support or customer success",
                "checks": [
                    "Prepare FAQ, known limitations, escalation path, and customer messaging.",
                    "Staff the launch window and post-launch feedback triage.",
                ],
            },
        ],
        "launch_date": launch_date,
        "constraint_note": constraints,
        "asset_note": _summarize_assets(available_assets),
        "audience": audience,
    }


def draft_channel_copy_impl(
    product_brief: str,
    audience: str,
    launch_date: str,
    constraints: str,
    available_assets: str,
) -> dict[str, Any]:
    """Draft channel-specific launch copy starters."""

    short_brief = _first_sentence(product_brief)
    audience_fragment = audience.rstrip(".")
    return {
        "channels": [
            {
                "channel": "Internal launch room",
                "copy": (
                    f"Launch Desk draft for {launch_date}: {short_brief} "
                    f"Target audience: {audience_fragment}. Please review owner checks and launch risks."
                ),
            },
            {
                "channel": "Customer email",
                "copy": (
                    f"We are launching an update for {audience_fragment}: {short_brief} "
                    "This release is designed to make the workflow clearer, faster, and easier to adopt."
                ),
            },
            {
                "channel": "Changelog",
                "copy": (
                    f"New: {short_brief} Available on {launch_date}. "
                    "See the linked docs and support notes for rollout details."
                ),
            },
            {
                "channel": "Social",
                "copy": (
                    f"Shipping on {launch_date}: {short_brief} Built for {audience_fragment}."
                ),
            },
        ],
        "asset_note": _summarize_assets(available_assets),
        "constraints_to_review": constraints,
    }


def missing_detail_questions_impl(
    product_brief: str,
    audience: str,
    launch_date: str,
    constraints: str,
    available_assets: str,
) -> dict[str, Any]:
    """Return follow-up questions for missing launch details."""

    text = " ".join([product_brief, audience, constraints, available_assets]).lower()
    questions: list[dict[str, Any]] = []
    if not _contains_any(text, ["metric", "kpi", "success", "activation", "retention"]):
        questions.append(
            _follow_up_question(
                priority="P0",
                category="Success metrics",
                question="What launch success metric should determine whether this worked?",
                why_it_matters="The launch plan cannot define go/no-go or post-launch review criteria without a measurable outcome.",
                suggested_owner="Product",
                blocks_launch=True,
            )
        )
    if not _contains_any(text, ["rollback", "flag", "gradual", "ramp", "kill switch"]):
        questions.append(
            _follow_up_question(
                priority="P0",
                category="Release safety",
                question="Is there a feature flag, rollback path, or phased rollout plan?",
                why_it_matters="Engineering needs a safe release control before launch-day issues appear.",
                suggested_owner="Engineering",
                blocks_launch=True,
            )
        )
    if not _contains_any(text, ["support", "faq", "customer success", "known issue"]):
        questions.append(
            _follow_up_question(
                priority="P1",
                category="Support readiness",
                question="What should Support say if customers hit a launch-day issue?",
                why_it_matters="Support needs approved language and escalation paths before customers ask for help.",
                suggested_owner="Support or customer success",
                blocks_launch=False,
            )
        )
    if not _contains_any(text, ["doc", "demo", "screenshot", "video", "email", "asset"]):
        questions.append(
            _follow_up_question(
                priority="P1",
                category="Asset readiness",
                question="Which launch assets are approved versus still in progress?",
                why_it_matters="Launch copy should only make claims that approved assets can support.",
                suggested_owner="Marketing or product",
                blocks_launch=False,
            )
        )
    if _days_until(launch_date) < 7:
        questions.append(
            _follow_up_question(
                priority="P0",
                category="Date risk",
                question="What scope can be cut if the team cannot hit the launch date safely?",
                why_it_matters="A near-term launch needs an explicit cut line to avoid unsafe last-minute work.",
                suggested_owner="Launch captain",
                blocks_launch=True,
            )
        )

    return {
        "mode": FOLLOW_UP_MODE,
        "questions": questions,
        "missing_count": len(questions),
        "critical_count": sum(1 for question in questions if question["blocks_launch"]),
    }


def _follow_up_question(
    *,
    priority: str,
    category: str,
    question: str,
    why_it_matters: str,
    suggested_owner: str,
    blocks_launch: bool,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "category": category,
        "question": question,
        "why_it_matters": why_it_matters,
        "suggested_owner": suggested_owner,
        "blocks_launch": blocks_launch,
    }


def _days_until(launch_date: str) -> int:
    try:
        target = date.fromisoformat(launch_date)
    except ValueError:
        return 0
    return (target - datetime.now(UTC).date()).days


def _due_hint(days_until_launch: int, priority: str) -> str:
    if priority == "P0":
        return "Within 48 hours"
    if days_until_launch <= 14:
        return "Before go/no-go"
    return "This sprint"


def _owner_for_title(title: str) -> str:
    mapping = {
        "Brief": "Product",
        "Release": "Engineering",
        "Quality": "QA",
        "Beta": "Product",
        "Developer": "DevRel",
        "Legal": "Legal",
        "Enablement": "Support",
        "Launch": "Marketing",
        "Post": "Engineering",
    }
    for needle, owner in mapping.items():
        if needle in title:
            return owner
    return "Launch captain"


def _summarize_assets(available_assets: str) -> str:
    if not available_assets or available_assets == "No assets listed yet.":
        return "Assets are not yet listed."
    words = available_assets.split()
    if len(words) <= 24:
        return available_assets
    return " ".join(words[:24]) + "..."


def _first_sentence(text: str) -> str:
    normalized = " ".join(text.split())
    for separator in [". ", "\n", "; "]:
        if separator in normalized:
            return normalized.split(separator, 1)[0].strip(".; ")
    return normalized[:180].strip()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)
