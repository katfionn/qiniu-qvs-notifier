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


# ==================== Web 服务管理 ====================

def get_web_port() -> int:
    """从环境变量获取 Web 端口"""
    return int(os.getenv("WEB_PORT", "8000"))


def is_web_service_running() -> bool:
    """检查 Web 服务是否运行"""
    import subprocess
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "run_web_v2.py" in result.stdout
    except:
        return False


def start_web_service() -> None:
    """启动 Web 服务"""
    import subprocess

    if is_web_service_running():
        console.print("[yellow]Web 服务已在运行中[/yellow]")
        return

    port = get_web_port()
    console.print(f"[cyan]正在启动 Web 服务（端口: {port}）...[/cyan]")

    try:
        # 使用 nohup 在后台启动
        subprocess.Popen(
            ["nohup", "python", str(ROOT / "run_web_v2.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # 等待服务启动
        import time
        time.sleep(3)

        if is_web_service_running():
            console.print(f"[green]✓ Web 服务启动成功[/green]")
            console.print(f"[cyan]访问地址: http://localhost:{port}[/cyan]")
        else:
            console.print("[red]✗ Web 服务启动失败，请检查日志[/red]")
    except Exception as e:
        console.print(f"[red]✗ 启动失败: {e}[/red]")


def stop_web_service() -> None:
    """停止 Web 服务"""
    import subprocess

    if not is_web_service_running():
        console.print("[yellow]Web 服务未运行[/yellow]")
        return

    console.print("[cyan]正在停止 Web 服务...[/cyan]")

    try:
        subprocess.run(
            ["pkill", "-f", "run_web_v2.py"],
            timeout=10
        )

        import time
        time.sleep(2)

        if not is_web_service_running():
            console.print("[green]✓ Web 服务已停止[/green]")
        else:
            console.print("[yellow]服务可能仍在运行，请手动检查[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ 停止失败: {e}[/red]")


def restart_web_service() -> None:
    """重启 Web 服务"""
    console.print("[cyan]正在重启 Web 服务...[/cyan]")
    stop_web_service()
    import time
    time.sleep(2)
    start_web_service()


def show_web_service_status() -> None:
    """显示 Web 服务状态"""
    running = is_web_service_running()
    port = get_web_port()

    status_text = "[green]运行中[/green]" if running else "[red]未运行[/red]"

    table = Table(title="Web 服务状态", border_style="cyan")
    table.add_column("项目", style="cyan")
    table.add_column("值", style="white")

    table.add_row("状态", status_text)
    table.add_row("端口", str(port))
    if running:
        table.add_row("访问地址", f"http://localhost:{port}")

    console.print(table)


def web_service_menu() -> None:
    """Web 服务管理菜单"""
    while True:
        running = is_web_service_running()

        choices = [
            "查看服务状态",
            "启动服务" if not running else "停止服务",
            "重启服务",
            "返回上级"
        ]

        action = questionary.select(
            "Web 服务管理",
            choices=choices
        ).ask()

        if action == "查看服务状态":
            show_web_service_status()
        elif action == "启动服务":
            start_web_service()
        elif action == "停止服务":
            stop_web_service()
        elif action == "重启服务":
            restart_web_service()
        elif action == "返回上级":
            break


# ==================== 卸载功能 ====================

def uninstall_program() -> None:
    """卸载程序"""
    console.print("\n[bold red]警告：此操作将完全卸载 QVS 通知器[/bold red]")
    console.print("[yellow]将删除以下内容：[/yellow]")
    console.print("  • systemd 服务（如果存在）")
    console.print("  • qvs 命令")
    console.print("  • 程序文件（如果在标准位置）")
    console.print("\n[cyan]数据文件将会保留，可手动删除[/cyan]\n")

    confirm = questionary.confirm(
        "确认卸载？此操作不可恢复",
        default=False
    ).ask()

    if not confirm:
        console.print("[cyan]已取消卸载[/cyan]")
        return

    # 再次确认
    final_confirm = questionary.text(
        "请输入 'UNINSTALL' 确认卸载"
    ).ask()

    if final_confirm != "UNINSTALL":
        console.print("[cyan]已取消卸载[/cyan]")
        return

    import subprocess
    from web.models.database import DATA_DIR

    console.print("\n[cyan]开始卸载...[/cyan]\n")

    # 1. 停止 Web 服务
    console.print("1. 停止 Web 服务...")
    if is_web_service_running():
        stop_web_service()
    else:
        console.print("   [yellow]服务未运行[/yellow]")

    # 2. 停止并删除 systemd 服务
    console.print("2. 删除 systemd 服务...")
    try:
        subprocess.run(["sudo", "systemctl", "stop", "qvs-notifier"],
                      capture_output=True, timeout=10)
        subprocess.run(["sudo", "systemctl", "disable", "qvs-notifier"],
                      capture_output=True, timeout=10)
        subprocess.run(["sudo", "rm", "-f", "/etc/systemd/system/qvs-notifier.service"],
                      timeout=10)
        subprocess.run(["sudo", "systemctl", "daemon-reload"],
                      capture_output=True, timeout=10)
        console.print("   [green]✓ systemd 服务已删除[/green]")
    except:
        console.print("   [yellow]systemd 服务不存在或删除失败[/yellow]")

    # 3. 删除 qvs 命令
    console.print("3. 删除 qvs 命令...")
    try:
        subprocess.run(["sudo", "rm", "-f", "/usr/local/bin/qvs"], timeout=10)
        console.print("   [green]✓ qvs 命令已删除[/green]")
    except:
        console.print("   [yellow]qvs 命令删除失败[/yellow]")

    # 4. 提示数据文件位置
    console.print(f"\n[cyan]数据文件位置: {DATA_DIR}[/cyan]")
    console.print("[cyan]如需删除数据，请手动运行:[/cyan]")
    console.print(f"  rm -rf {DATA_DIR}")

    # 5. 提示程序文件位置
    console.print(f"\n[cyan]程序文件位置: {ROOT}[/cyan]")
    console.print("[cyan]如需删除程序，请手动运行:[/cyan]")
    console.print(f"  rm -rf {ROOT}")

    console.print("\n[green]✓ 卸载完成！[/green]")
    console.print("[yellow]建议重启终端以刷新环境变量[/yellow]\n")


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

    # Web 服务状态
    web_running = is_web_service_running()
    web_status = "[green]运行中[/green]" if web_running else "[red]未运行[/red]"
    table.add_row("Web 服务", web_status)
    table.add_row("Web 端口", str(get_web_port()))

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
                "Web 服务管理",
                "管理员账号管理",
                "卸载程序",
                "返回主菜单"
            ]
        ).ask()

        if action == "查看系统信息":
            show_system_info()
        elif action == "Web 服务管理":
            web_service_menu()
        elif action == "管理员账号管理":
            from qvs_notifier.admin import main as admin_main
            admin_main()
        elif action == "卸载程序":
            uninstall_program()
            break  # 卸载后退出
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
