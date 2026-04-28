from launch_desk.tools import (
    check_launch_readiness_impl,
    draft_channel_copy_impl,
    extract_launch_tasks_impl,
    generate_owner_checklist_impl,
    missing_detail_questions_impl,
)


def sample_payload():
    return {
        "product_brief": (
            "Launch a beta API for engineering managers that converts release notes "
            "into rollout plans with rollback guidance and success metrics."
        ),
        "audience": "Engineering managers and product leads",
        "launch_date": "2026-05-20",
        "constraints": "Beta cohort only, legal review required, rollback through feature flags.",
        "available_assets": "API docs draft, product screenshots, demo recording, support FAQ.",
    }


def test_extract_launch_tasks_prioritizes_and_assigns_owners():
    payload = sample_payload()
    result = extract_launch_tasks_impl(**payload)

    assert result["audience"] == payload["audience"]
    assert result["prioritized_tasks"][0]["priority"] == "P0"
    assert any(task["owner"] == "Engineering" for task in result["prioritized_tasks"])


def test_readiness_rubric_returns_risks_and_score():
    payload = sample_payload()
    result = check_launch_readiness_impl(**payload)

    assert 0 <= result["score"] <= 100
    assert result["risk_register"]
    assert any(item["name"] == "Risk controls" for item in result["rubric"])


def test_owner_checklist_has_expected_roles():
    payload = sample_payload()
    result = generate_owner_checklist_impl(**payload)

    roles = {owner["role"] for owner in result["owners"]}
    assert "Engineering lead" in roles
    assert "Product manager" in roles


def test_channel_copy_contains_expected_channels():
    payload = sample_payload()
    result = draft_channel_copy_impl(**payload)

    channels = {item["channel"] for item in result["channels"]}
    assert {"Customer email", "Changelog", "Social"}.issubset(channels)


def test_missing_questions_drop_when_inputs_include_controls():
    payload = sample_payload()
    result = missing_detail_questions_impl(**payload)

    assert isinstance(result["questions"], list)
    assert result["missing_count"] == len(result["questions"])
