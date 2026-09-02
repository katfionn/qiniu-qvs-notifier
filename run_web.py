"""Production Web entry point. Development reload is opt-in."""
from __future__ import annotations

import argparse
import uvicorn


def run_web(stop_event=None) -> None:
    config = uvicorn.Config("web.main:app", host="0.0.0.0", port=8000, reload=False)
    server = uvicorn.Server(config)
    if stop_event:
        import threading
        threading.Thread(target=lambda: (stop_event.wait(), setattr(server, "should_exit", True)), daemon=True).start()
    server.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true", help="enable development auto-reload")
    parser.add_argument("--no-reload", action="store_true", help="accepted for service compatibility")
    args = parser.parse_args()
    if args.reload:
        uvicorn.run("web.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        run_web()
