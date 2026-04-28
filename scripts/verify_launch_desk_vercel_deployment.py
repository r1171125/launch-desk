from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


VERCEL_DEPLOYMENT_API_BASE = "https://api.vercel.com/v13/deployments"


@dataclass(frozen=True)
class VercelDeploymentSummary:
    deployment_id: str
    deployment_url: str
    ready_state: str
    status: str
    commit_sha: str
    project_id: str
    target: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Vercel deployment behind Launch Desk frontend.")
    parser.add_argument("--deployment-url", required=True, help="Vercel deployment URL or hostname.")
    parser.add_argument(
        "--expected-commit",
        default="",
        help="Expected git commit SHA. Prefix matches are accepted for SHAs of at least 7 characters.",
    )
    parser.add_argument(
        "--expected-state",
        default="READY",
        help="Expected Vercel readyState/status value. Defaults to READY.",
    )
    parser.add_argument("--team-id", default=os.environ.get("VERCEL_TEAM_ID", ""), help="Optional Vercel team ID.")
    parser.add_argument("--team-slug", default=os.environ.get("VERCEL_TEAM_SLUG", ""), help="Optional Vercel team slug.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP request timeout in seconds.")
    parser.add_argument(
        "--required",
        action="store_true",
        help="Fail instead of skipping when VERCEL_TOKEN is not configured.",
    )
    args = parser.parse_args()

    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        message = (
            "Vercel deployment metadata verification skipped: VERCEL_TOKEN is not set. "
            "Set VERCEL_TOKEN and optionally VERCEL_TEAM_ID or VERCEL_TEAM_SLUG to enable this gate."
        )
        print(message, file=sys.stderr if args.required else sys.stdout)
        return 1 if args.required else 0

    deployment_host = normalize_deployment_host(args.deployment_url)
    try:
        payload = fetch_vercel_deployment(
            deployment_host=deployment_host,
            token=token,
            team_id=args.team_id,
            team_slug=args.team_slug,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"Vercel deployment metadata verification failed: {exc}", file=sys.stderr)
        return 1

    summary = summarize_deployment(payload)
    failures = validate_deployment_summary(
        summary,
        expected_commit=args.expected_commit,
        expected_state=args.expected_state,
    )
    if failures:
        print("Vercel deployment metadata verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        print(format_summary(summary), file=sys.stderr)
        return 1

    print("Vercel deployment metadata verification passed.")
    print(format_summary(summary))
    return 0


def normalize_deployment_host(deployment_url: str) -> str:
    value = deployment_url.strip().rstrip("/")
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc or parsed.path


def fetch_vercel_deployment(
    *,
    deployment_host: str,
    token: str,
    team_id: str = "",
    team_slug: str = "",
    timeout: float = 30.0,
) -> dict[str, Any]:
    query: dict[str, str] = {"withGitRepoInfo": "true"}
    if team_id:
        query["teamId"] = team_id
    if team_slug:
        query["slug"] = team_slug

    url = f"{VERCEL_DEPLOYMENT_API_BASE}/{deployment_host}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "LaunchDeskPostDeployVerifier/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vercel API returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Vercel API: {exc.reason}") from exc

    return json.loads(body)


def summarize_deployment(payload: dict[str, Any]) -> VercelDeploymentSummary:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    git_source = payload.get("gitSource") if isinstance(payload.get("gitSource"), dict) else {}

    return VercelDeploymentSummary(
        deployment_id=str(payload.get("id") or ""),
        deployment_url=str(payload.get("url") or ""),
        ready_state=str(payload.get("readyState") or ""),
        status=str(payload.get("status") or ""),
        commit_sha=first_nonempty(
            meta.get("githubCommitSha"),
            meta.get("gitCommitSha"),
            git_source.get("sha"),
            payload.get("commitSha"),
        ),
        project_id=str(payload.get("projectId") or ""),
        target=str(payload.get("target") or ""),
    )


def first_nonempty(*values: object) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def validate_deployment_summary(
    summary: VercelDeploymentSummary,
    *,
    expected_commit: str = "",
    expected_state: str = "READY",
) -> list[str]:
    failures: list[str] = []
    expected_state = expected_state.strip().upper()

    observed_states = {summary.ready_state.upper(), summary.status.upper()} - {""}
    if expected_state and expected_state not in observed_states:
        failures.append(
            f"expected Vercel state {expected_state}, observed "
            f"readyState={summary.ready_state or '<missing>'}, status={summary.status or '<missing>'}"
        )

    expected_commit = expected_commit.strip()
    if expected_commit:
        if not summary.commit_sha:
            failures.append("expected commit SHA could not be verified because Vercel did not return one")
        elif not commit_sha_matches(summary.commit_sha, expected_commit):
            failures.append(f"expected commit {expected_commit}, observed {summary.commit_sha}")

    return failures


def commit_sha_matches(observed: str, expected: str) -> bool:
    observed = observed.strip().lower()
    expected = expected.strip().lower()
    if not observed or not expected:
        return False
    if len(observed) < 7 or len(expected) < 7:
        return observed == expected
    return observed.startswith(expected) or expected.startswith(observed)


def format_summary(summary: VercelDeploymentSummary) -> str:
    return "\n".join(
        [
            f"Deployment ID: {summary.deployment_id or '<missing>'}",
            f"Deployment URL: {summary.deployment_url or '<missing>'}",
            f"readyState: {summary.ready_state or '<missing>'}",
            f"status: {summary.status or '<missing>'}",
            f"commit_sha: {summary.commit_sha or '<missing>'}",
            f"project_id: {summary.project_id or '<missing>'}",
            f"target: {summary.target or '<missing>'}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
