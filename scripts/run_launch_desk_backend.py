from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from launch_desk.routes import create_launch_desk_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Launch Desk API dev server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=int(os.getenv("LAUNCH_DESK_BACKEND_PORT", "5057")), type=int)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    app = create_launch_desk_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
