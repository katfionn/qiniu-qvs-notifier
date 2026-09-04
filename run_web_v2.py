"""Run web server with first-time installation check"""
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from rich.console import Console

console = Console()


def load_env():
    """加载 .env 文件中的环境变量"""
    env_file = ROOT / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value


def main():
    """Main entry point"""
    # 加载环境变量
    load_env()

    # Check if this is first run
    from web.models.database import is_first_run

    if is_first_run():
        console.print("[yellow]检测到首次运行，启动安装向导...[/yellow]\n")
        from qvs_notifier.installer import run_installer
        run_installer()
        console.print("\n[cyan]安装完成！现在启动 Web 服务...[/cyan]\n")

    # Start web server
    import uvicorn
    from web.main_v2 import app

    console.print("[cyan]启动 Web 服务...[/cyan]")
    console.print("[cyan]访问地址: http://0.0.0.0:8000[/cyan]\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()
