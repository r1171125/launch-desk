from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_frontend_verifier_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_launch_desk_frontend_page.py"
    spec = importlib.util.spec_from_file_location("verify_launch_desk_frontend_page", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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
