"""Admin command-line tool for managing the first admin account"""
from __future__ import annotations

import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.models.database import get_admin_info, is_first_run, reset_admin_password

console = Console()


def show_admin_info() -> None:
    """显示管理员信息"""
    if is_first_run():
        console.print("[yellow]系统尚未初始化，请先运行安装向导[/yellow]")
        console.print("运行: [cyan]python -m qvs_notifier.installer[/cyan]")
        return

    admin = get_admin_info()
    if not admin:
        console.print("[red]未找到管理员账号[/red]")
        return

    table = Table(title="管理员账号信息", border_style="cyan")
    table.add_column("字段", style="cyan")
    table.add_column("值", style="white")

    table.add_row("用户 ID", str(admin["id"]))
    table.add_row("用户名", admin["username"])
    table.add_row("创建时间", admin["created_at"])
    table.add_row("角色", "管理员（不可删除）")

    console.print(table)


def reset_password_interactive() -> None:
    """交互式重置管理员密码"""
    if is_first_run():
        console.print("[yellow]系统尚未初始化，请先运行安装向导[/yellow]")
        console.print("运行: [cyan]python -m qvs_notifier.installer[/cyan]")
        return

    admin = get_admin_info()
    if not admin:
        console.print("[red]未找到管理员账号[/red]")
        return

    console.print(f"\n[yellow]即将重置管理员账号的密码: {admin['username']}[/yellow]\n")

    if not questionary.confirm("确认继续？", default=False).ask():
        console.print("[yellow]操作已取消[/yellow]")
        return

    while True:
        new_password = questionary.password(
            "请输入新密码",
            validate=lambda x: len(x) >= 6 or "密码至少 6 个字符"
        ).ask()

        if not new_password:
            console.print("[yellow]操作已取消[/yellow]")
            return

        password_confirm = questionary.password("请再次输入新密码").ask()

        if new_password != password_confirm:
            console.print("[red]两次密码不一致，请重新输入[/red]\n")
            continue

        break

    # 执行重置
    if reset_admin_password(new_password):
        console.print(Panel(
            f"[green]✓ 管理员密码已重置[/green]\n\n"
            f"用户名: [cyan]{admin['username']}[/cyan]\n"
            f"新密码: [cyan]{'*' * len(new_password)}[/cyan]",
            border_style="green"
        ))
    else:
        console.print("[red]✗ 密码重置失败[/red]")


def main() -> None:
    """主入口"""
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset_password_interactive()
        return

    console.print(Panel("[cyan]管理员账号管理工具[/cyan]", border_style="cyan"))

    action = questionary.select(
        "请选择操作",
        choices=[
            "查看管理员信息",
            "重置管理员密码",
            "退出"
        ]
    ).ask()

    if action == "查看管理员信息":
        show_admin_info()
    elif action == "重置管理员密码":
        reset_password_interactive()
    elif action == "退出":
        return


if __name__ == "__main__":
    main()
