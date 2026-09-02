"""Source-install entry point: bootstrap dependencies, then launch the TUI."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = ("questionary", "rich", "yaml", "fastapi", "uvicorn")


def main() -> None:
    missing = [name for name in REQUIRED if importlib.util.find_spec(name) is None]
    if missing:
        answer = input("Required Python packages are missing. Install them now? [Y/n] ").strip().lower()
        if answer not in ("", "y", "yes"):
            raise SystemExit(f"Run: {sys.executable} -m pip install -r requirements.txt")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    from qvs_notifier.tui import main as tui_main
    tui_main()


if __name__ == "__main__":
    main()
