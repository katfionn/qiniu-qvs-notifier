"""统一智能启动入口 v3.1：端口冲突自愈、环境自检、本地自动打开浏览器"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import __version__  # noqa: E402
from app.config import DATA_DIR, DEFAULT_HOST, DEFAULT_PORT  # noqa: E402


def _is_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("IN_DOCKER") == "1"


def _is_port_free(host: str, port: int) -> bool:
    bind_host = "0.0.0.0" if host in ("", "0.0.0.0") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((bind_host, port))
            return True
        except OSError:
            return False


def _choose_port(host: str, preferred: int, allow_auto_shift: bool) -> int:
    if _is_port_free(host, preferred):
        return preferred
    if not allow_auto_shift:
        return preferred
    for candidate in range(preferred + 1, preferred + 21):
        if _is_port_free(host, candidate):
            print(f"[自愈提示] 默认端口 {preferred} 已被其他程序占用，已自动切换至空闲端口 {candidate}")
            return candidate
    return preferred


def _open_browser_later(url: str) -> None:
    time.sleep(1.4)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    in_docker = _is_in_docker()
    allow_auto_shift = (not in_docker) and os.getenv("AUTO_PORT", "1") != "0"
    port = _choose_port(DEFAULT_HOST, DEFAULT_PORT, allow_auto_shift)
    local_url = f"http://127.0.0.1:{port}"

    print("=" * 62)
    print(f"  QVS 多云监控告警中心 v{__version__} 已启动")
    print(f"  数据存储目录 : {DATA_DIR}")
    print(f"  浏览器访问   : {local_url}")
    print("  首次打开浏览器会自动进入图形化初始化向导，按提示设置管理员即可！")
    print("=" * 62)

    if not in_docker and os.getenv("NO_BROWSER", "0") != "1":
        threading.Thread(target=_open_browser_later, args=(local_url,), daemon=True).start()

    import uvicorn
    from app.main import app

    uvicorn.run(app, host=DEFAULT_HOST, port=port, log_level="info")


if __name__ == "__main__":
    main()
