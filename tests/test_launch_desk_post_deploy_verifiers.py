from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_frontend_verifier_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_launch_desk_frontend_page.py"
    spec = importlib.util.spec_from_file_location("verify_launch_desk_frontend_page", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_vercel_verifier_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_launch_desk_vercel_deployment.py"
    spec = importlib.util.spec_from_file_location("verify_launch_desk_vercel_deployment", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frontend_page_verifier_accepts_expected_page_content():
    verifier = _load_frontend_verifier_module()
    html = """
    <html>
      <head><title>Launch Desk</title></head>
      <body>
        <h1>Launch Desk</h1>
        <button>Load sample</button>
        <button>Run launch plan</button>
        <section>Generated release plan</section>
        <span>launch-desk-backend-6gtyc6yuoq-de.a.run.app</span>
      </body>
    </html>
    """

    assert verifier.verify_frontend_html(
        html,
        expected_api_host="launch-desk-backend-6gtyc6yuoq-de.a.run.app",
    ) == []


def test_frontend_page_verifier_reports_missing_expected_content():
    verifier = _load_frontend_verifier_module()

    missing = verifier.verify_frontend_html("<html>Launch Desk</html>", expected_api_host="api.example.com")

    assert "Load sample" in missing
    assert "Run launch plan" in missing
    assert "Generated release plan" in missing
    assert "api.example.com" in missing


def test_vercel_deployment_verifier_extracts_status_and_commit_sha():
    verifier = _load_vercel_verifier_module()
    payload = {
        "id": "dpl_123",
        "url": "launch-desk-orcin.vercel.app",
        "readyState": "READY",
        "status": "READY",
        "projectId": "prj_123",
        "target": "production",
        "meta": {
            "githubCommitSha": "c6c7dc62d6b6e5eb7bce37f27ccafbffcf10b7ea",
        },
    }

    summary = verifier.summarize_deployment(payload)

    assert summary.commit_sha == "c6c7dc62d6b6e5eb7bce37f27ccafbffcf10b7ea"
    assert verifier.validate_deployment_summary(
        summary,
        expected_commit="c6c7dc6",
        expected_state="READY",
    ) == []


def test_vercel_deployment_verifier_reports_bad_status_or_commit():
    verifier = _load_vercel_verifier_module()
    summary = verifier.VercelDeploymentSummary(
        deployment_id="dpl_123",
        deployment_url="launch-desk-orcin.vercel.app",
        ready_state="BUILDING",
        status="BUILDING",
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        project_id="prj_123",
        target="production",
    )

    failures = verifier.validate_deployment_summary(
        summary,
        expected_commit="bbbbbbb",
        expected_state="READY",
    )

    assert len(failures) == 2
    assert "expected Vercel state READY" in failures[0]
    assert "expected commit bbbbbbb" in failures[1]
