"""First-time installation wizard"""
from __future__ import annotations

import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.models.database import create_first_admin, init_databases, is_first_run

console = Console()


def run_installer() -> None:
    """运行首次安装向导"""
    console.print(Panel("[cyan]欢迎使用七牛 QVS 通知器 v2.0[/cyan]", border_style="cyan"))
    console.print("\n[yellow]检测到这是首次运行，需要创建管理员账号[/yellow]\n")

    # 初始化数据库
    init_databases()

    # 创建管理员账号
    while True:
        username = questionary.text(
            "请输入管理员用户名",
            default="admin",
            validate=lambda x: len(x) >= 3 or "用户名至少 3 个字符"
        ).ask()

        if not username:
            console.print("[red]安装已取消[/red]")
            sys.exit(1)

        password = questionary.password(
            "请输入管理员密码",
            validate=lambda x: len(x) >= 6 or "密码至少 6 个字符"
        ).ask()

        if not password:
            console.print("[red]安装已取消[/red]")
            sys.exit(1)

        password_confirm = questionary.password("请再次输入密码").ask()

        if password != password_confirm:
            console.print("[red]两次密码不一致，请重新输入[/red]\n")
            continue

        break

    # 创建管理员
    try:
        admin = create_first_admin(username, password)
        console.print(f"\n[green]✓ 管理员账号创建成功！[/green]")
        console.print(Panel(
            f"[cyan]用户名:[/cyan] {admin.username}\n"
            f"[cyan]角色:[/cyan] 管理员\n"
            f"[cyan]创建时间:[/cyan] {admin.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            title="账号信息",
            border_style="green"
        ))

        # 数据目录信息
        from web.models.database import DATA_DIR
        console.print(f"\n[cyan]数据目录:[/cyan] {DATA_DIR}")
        console.print(f"[cyan]账号数据:[/cyan] {DATA_DIR / 'data.db'}")
        console.print(f"[cyan]日志数据:[/cyan] {DATA_DIR / 'logs.db'}\n")

        console.print("[yellow]提示：[/yellow]")
        console.print("  1. 使用 [cyan]python -m qvs_notifier.tui[/cyan] 启动 TUI 管理界面")
        console.print("  2. 使用 [cyan]python run_web.py[/cyan] 启动 Web 服务")
        console.print("  3. 使用 [cyan]python -m qvs_notifier admin[/cyan] 查看/重置管理员密码\n")

    except Exception as error:
        console.print(f"[red]✗ 创建管理员失败: {error}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    if is_first_run():
        run_installer()
    else:
        console.print("[yellow]系统已初始化，无需重新安装[/yellow]")
        console.print("使用 [cyan]python -m qvs_notifier admin[/cyan] 管理账号")
