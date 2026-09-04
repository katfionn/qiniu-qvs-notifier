"""TUI v2.0 - Complete management interface with task/channel management"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 加载 .env 文件
env_file = ROOT / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

from web.models.database import (
    DataSession,
    NotificationChannel,
    SourceChannel,
    Task,
    init_databases,
    is_first_run,
)

console = Console()


def check_initialization() -> bool:
    """检查系统是否已初始化"""
    if is_first_run():
        console.print("[yellow]系统尚未初始化[/yellow]")
        console.print("请先运行安装脚本: [cyan]sudo bash install.sh[/cyan]\n")
        return False
    return True


# ==================== 任务管理 ====================

def list_tasks() -> None:
    """显示任务列表"""
    with DataSession() as session:
        tasks = session.query(Task).all()

        if not tasks:
            console.print("[yellow]暂无任务[/yellow]")
            return

        table = Table(title="任务列表", border_style="cyan")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("任务名称", style="white")
        table.add_column("监听渠道", style="yellow")
        table.add_column("Cron", style="green")
        table.add_column("状态", style="magenta")

        for task in tasks:
            source_name = task.source_channel.name if task.source_channel else "未知"
            status = "✓ 启用" if task.is_enabled else "✗ 禁用"
            table.add_row(
                str(task.id),
                task.name,
                source_name,
                task.cron_expression,
                status
            )

        console.print(table)


def create_task() -> None:
    """创建新任务"""
    with DataSession() as session:
        # 检查是否有监听渠道
        channels = session.query(SourceChannel).all()
        if not channels:
            console.print("[red]请先创建监听渠道[/red]")
            return

        console.print("\n[cyan]创建新任务[/cyan]\n")

        name = questionary.text("任务名称").ask()
        if not name:
            return

        # 选择监听渠道
        channel_choices = [questionary.Choice(f"{c.name} ({c.provider})", c.id) for c in channels]
        channel_id = questionary.select("选择监听渠道", choices=channel_choices).ask()
        if not channel_id:
            return

        # Cron 表达式
        cron = questionary.text("Cron 表达式", default="*/5 * * * *").ask()
        if not cron:
            return

        # 国标 ID（可选）
        gb_id = questionary.text("国标 ID（可选，按回车跳过）").ask() or None

        # 创建任务
        task = Task(
            name=name,
            source_channel_id=channel_id,
            cron_expression=cron,
            gb_id=gb_id,
            is_enabled=True
        )
        session.add(task)
        session.commit()

        console.print(f"[green]✓ 任务 '{name}' 创建成功[/green]")


def delete_task() -> None:
    """删除任务"""
    with DataSession() as session:
        tasks = session.query(Task).all()
        if not tasks:
            console.print("[yellow]暂无任务[/yellow]")
            return

        choices = [questionary.Choice(f"{t.name} (ID: {t.id})", t.id) for t in tasks]
        task_id = questionary.select("选择要删除的任务", choices=choices).ask()
        if not task_id:
            return

        if not questionary.confirm("确认删除？", default=False).ask():
            return

        task = session.query(Task).get(task_id)
        if task:
            session.delete(task)
            session.commit()
            console.print("[green]✓ 任务已删除[/green]")


def toggle_task() -> None:
    """启用/禁用任务"""
    with DataSession() as session:
        tasks = session.query(Task).all()
        if not tasks:
            console.print("[yellow]暂无任务[/yellow]")
            return

        choices = [
            questionary.Choice(
                f"{t.name} (当前: {'启用' if t.is_enabled else '禁用'})",
                t.id
            ) for t in tasks
        ]
        task_id = questionary.select("选择任务", choices=choices).ask()
        if not task_id:
            return

        task = session.query(Task).get(task_id)
        if task:
            task.is_enabled = not task.is_enabled
            session.commit()
            status = "启用" if task.is_enabled else "禁用"
            console.print(f"[green]✓ 任务已{status}[/green]")


def tasks_menu() -> None:
    """任务管理菜单"""
    while True:
        action = questionary.select(
            "任务管理",
            choices=[
                "查看任务列表",
                "创建新任务",
                "启用/禁用任务",
                "删除任务",
                "返回主菜单"
            ]
        ).ask()

        if action == "查看任务列表":
            list_tasks()
        elif action == "创建新任务":
            create_task()
        elif action == "启用/禁用任务":
            toggle_task()
        elif action == "删除任务":
            delete_task()
        elif action == "返回主菜单":
            break


# ==================== 监听渠道管理 ====================

def list_source_channels() -> None:
    """显示监听渠道列表"""
    with DataSession() as session:
        channels = session.query(SourceChannel).all()

        if not channels:
            console.print("[yellow]暂无监听渠道[/yellow]")
            return

        table = Table(title="监听渠道列表", border_style="cyan")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("渠道名称", style="white")
        table.add_column("服务商", style="yellow")
        table.add_column("状态", style="magenta")

        for channel in channels:
            status = "✓ 启用" if channel.is_active else "✗ 禁用"
            table.add_row(
                str(channel.id),
                channel.name,
                channel.provider,
                status
            )

        console.print(table)


def create_source_channel() -> None:
    """创建监听渠道"""
    console.print("\n[cyan]创建监听渠道[/cyan]\n")

    name = questionary.text("渠道名称").ask()
    if not name:
        return

    provider = questionary.select(
        "选择服务商",
        choices=["qiniu", "custom"]
    ).ask()
    if not provider:
        return

    config = {}

    if provider == "qiniu":
        access_key = questionary.text("Access Key").ask()
        secret_key = questionary.password("Secret Key").ask()
        namespace_id = questionary.text("Namespace ID").ask()

        config = {
            "access_key": access_key,
            "secret_key": secret_key
        }

        with DataSession() as session:
            channel = SourceChannel(
                name=name,
                provider=provider,
                namespace_id=namespace_id,
                is_active=True
            )
            channel.set_config(config)
            session.add(channel)
            session.commit()
            console.print(f"[green]✓ 监听渠道 '{name}' 创建成功[/green]")

    elif provider == "custom":
        console.print("[yellow]自定义服务商功能开发中[/yellow]")


def delete_source_channel() -> None:
    """删除监听渠道"""
    with DataSession() as session:
        channels = session.query(SourceChannel).all()
        if not channels:
            console.print("[yellow]暂无监听渠道[/yellow]")
            return

        choices = [questionary.Choice(f"{c.name} ({c.provider})", c.id) for c in channels]
        channel_id = questionary.select("选择要删除的渠道", choices=choices).ask()
        if not channel_id:
            return

        # 检查是否有任务使用此渠道
        task_count = session.query(Task).filter_by(source_channel_id=channel_id).count()
        if task_count > 0:
            console.print(f"[red]此渠道被 {task_count} 个任务使用，无法删除[/red]")
            return

        if not questionary.confirm("确认删除？", default=False).ask():
            return

        channel = session.query(SourceChannel).get(channel_id)
        if channel:
            session.delete(channel)
            session.commit()
            console.print("[green]✓ 监听渠道已删除[/green]")


def source_channels_menu() -> None:
    """监听渠道管理菜单"""
    while True:
        action = questionary.select(
            "监听渠道管理",
            choices=[
                "查看渠道列表",
                "创建新渠道",
                "删除渠道",
                "返回主菜单"
            ]
        ).ask()

        if action == "查看渠道列表":
            list_source_channels()
        elif action == "创建新渠道":
            create_source_channel()
        elif action == "删除渠道":
            delete_source_channel()
        elif action == "返回主菜单":
            break


# ==================== 通知渠道管理 ====================

def list_notification_channels() -> None:
    """显示通知渠道列表"""
    with DataSession() as session:
        channels = session.query(NotificationChannel).all()

        if not channels:
            console.print("[yellow]暂无通知渠道[/yellow]")
            return

        table = Table(title="通知渠道列表", border_style="cyan")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("渠道名称", style="white")
        table.add_column("类型", style="yellow")
        table.add_column("状态", style="magenta")

        for channel in channels:
            status = "✓ 启用" if channel.is_active else "✗ 禁用"
            table.add_row(
                str(channel.id),
                channel.name,
                channel.type,
                status
            )

        console.print(table)


def create_notification_channel() -> None:
    """创建通知渠道"""
    console.print("\n[cyan]创建通知渠道[/cyan]\n")

    name = questionary.text("渠道名称").ask()
    if not name:
        return

    channel_type = questionary.select(
        "选择通知类型",
        choices=["ntfy", "webhook"]
    ).ask()
    if not channel_type:
        return

    config = {}

    if channel_type == "ntfy":
        server = questionary.text("NTFY 服务器地址", default="https://ntfy.sh").ask()
        topic = questionary.text("Topic").ask()

        config = {
            "server": server,
            "topic": topic
        }

    elif channel_type == "webhook":
        url = questionary.text("Webhook URL").ask()

        config = {
            "url": url
        }

    with DataSession() as session:
        channel = NotificationChannel(
            name=name,
            type=channel_type,
            is_active=True
        )
        channel.set_config(config)
        session.add(channel)
        session.commit()
        console.print(f"[green]✓ 通知渠道 '{name}' 创建成功[/green]")


def delete_notification_channel() -> None:
    """删除通知渠道"""
    with DataSession() as session:
        channels = session.query(NotificationChannel).all()
        if not channels:
            console.print("[yellow]暂无通知渠道[/yellow]")
            return

        choices = [questionary.Choice(f"{c.name} ({c.type})", c.id) for c in channels]
        channel_id = questionary.select("选择要删除的渠道", choices=choices).ask()
        if not channel_id:
            return

        if not questionary.confirm("确认删除？", default=False).ask():
            return

        channel = session.query(NotificationChannel).get(channel_id)
        if channel:
            session.delete(channel)
            session.commit()
            console.print("[green]✓ 通知渠道已删除[/green]")


def notification_channels_menu() -> None:
    """通知渠道管理菜单"""
    while True:
        action = questionary.select(
            "通知渠道管理",
            choices=[
                "查看渠道列表",
                "创建新渠道",
                "删除渠道",
                "返回主菜单"
            ]
        ).ask()

        if action == "查看渠道列表":
            list_notification_channels()
        elif action == "创建新渠道":
            create_notification_channel()
        elif action == "删除渠道":
            delete_notification_channel()
        elif action == "返回主菜单":
            break


# ==================== 系统管理 ====================

def show_system_info() -> None:
    """显示系统信息"""
    from web.models.database import DATA_DIR, DATA_DB_PATH, LOGS_DB_PATH

    table = Table(title="系统信息", border_style="cyan")
    table.add_column("项目", style="cyan")
    table.add_column("值", style="white")

    table.add_row("版本", "v2.0.0")
    table.add_row("数据目录", str(DATA_DIR))
    table.add_row("账号数据库", str(DATA_DB_PATH))
    table.add_row("日志数据库", str(LOGS_DB_PATH))

    with DataSession() as session:
        task_count = session.query(Task).count()
        source_count = session.query(SourceChannel).count()
        notif_count = session.query(NotificationChannel).count()

        table.add_row("任务数量", str(task_count))
        table.add_row("监听渠道", str(source_count))
        table.add_row("通知渠道", str(notif_count))

    console.print(table)


def system_menu() -> None:
    """系统管理菜单"""
    while True:
        action = questionary.select(
            "系统管理",
            choices=[
                "查看系统信息",
                "管理员账号管理",
                "返回主菜单"
            ]
        ).ask()

        if action == "查看系统信息":
            show_system_info()
        elif action == "管理员账号管理":
            from qvs_notifier.admin import main as admin_main
            admin_main()
        elif action == "返回主菜单":
            break


# ==================== 主菜单 ====================

def main() -> None:
    """TUI 主入口"""
    console.print(Panel(
        "[cyan]七牛 QVS 通知器 v2.0 - TUI 管理界面[/cyan]",
        border_style="cyan"
    ))

    if not check_initialization():
        return

    # 初始化数据库
    init_databases()

    while True:
        action = questionary.select(
            "主菜单",
            choices=[
                "任务管理",
                "监听渠道管理",
                "通知渠道管理",
                "系统管理",
                "退出"
            ]
        ).ask()

        if action == "任务管理":
            tasks_menu()
        elif action == "监听渠道管理":
            source_channels_menu()
        elif action == "通知渠道管理":
            notification_channels_menu()
        elif action == "系统管理":
            system_menu()
        elif action == "退出":
            console.print("[cyan]再见！[/cyan]")
            break


if __name__ == "__main__":
    main()
