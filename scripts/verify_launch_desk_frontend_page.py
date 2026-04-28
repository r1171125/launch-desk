from __future__ import annotations

import argparse
import sys

import requests


REQUIRED_TEXT = (
    "Launch Desk",
    "Load sample",
    "Run launch plan",
    "Generated release plan",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the deployed Launch Desk frontend page.")
    parser.add_argument("--url", required=True, help="Launch Desk frontend URL.")
    parser.add_argument(
        "--expected-api-host",
        default="",
        help="Expected backend API host rendered by the frontend, without protocol.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP request timeout in seconds.")
    args = parser.parse_args()

    try:
        response = requests.get(args.url, timeout=args.timeout)
        response.raise_for_status()
    except Exception as exc:
        print(f"Launch Desk frontend page verification failed: {exc}", file=sys.stderr)
        return 1

    missing = verify_frontend_html(response.text, expected_api_host=args.expected_api_host)
    if missing:
        print(
            "Launch Desk frontend page verification failed: missing expected content: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    print("Launch Desk frontend page verification passed.")
    print(f"URL: {args.url}")
    if args.expected_api_host:
        print(f"Expected API host: {args.expected_api_host}")
    return 0


def verify_frontend_html(html: str, expected_api_host: str = "") -> list[str]:
    expected: list[str] = list(REQUIRED_TEXT)
    if expected_api_host:
        expected.append(expected_api_host)
    return [item for item in expected if item not in html]


if __name__ == "__main__":
    raise SystemExit(main())
