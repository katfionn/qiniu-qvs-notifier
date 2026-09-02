import sys
import platform
import os
import yaml
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress
from rich.prompt import Prompt
import time

console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    header_text = Text("七牛云监控告警系统 - 安装向导", style="bold cyan", justify="center")
    console.print(Panel(header_text, border_style="blue", expand=False))
    console.print("\n")

def detect_environment():
    console.print("[yellow]正在检测系统环境...[/yellow]")
    time.sleep(1)

    sys_os = platform.system()
    arch = platform.machine()
    python_version = platform.python_version()

    console.print(f"[green]✔[/green] 操作系统: {sys_os}")
    console.print(f"[green]✔[/green] 系统架构: {arch}")
    console.print(f"[green]✔[/green] Python版本: {python_version}")

    if sys_os not in ["Linux", "Darwin", "Windows"]:
        console.print("[yellow]⚠ 警告: 您的操作系统可能未被完全支持，但我们将尝试继续。[/yellow]")

    return sys_os

def choose_installation_type():
    console.print("\n")
    return questionary.select(
        "请选择安装模式:",
        choices=[
            "1. 源码部署/本地服务 (推荐 Linux/macOS 使用)",
            "2. Docker 容器化部署 (需要预装 Docker)",
            "3. 临时进程 (前台运行，适合测试)"
        ]
    ).ask()

def choose_database_type():
    console.print("\n")
    return questionary.select(
        "请选择状态存储介质 (用于防止告警风暴):",
        choices=[
            "1. SQLite (推荐，无需配置)",
            "2. 本地文件 (JSON，极简)",
            "3. MySQL (适合大规模和分布式部署)"
        ]
    ).ask()

def configure_mysql():
    console.print("\n[bold cyan]配置 MySQL 数据库[/bold cyan]")
    host = questionary.text("数据库地址:", default="127.0.0.1").ask()
    port = questionary.text("数据库端口:", default="3306").ask()
    user = questionary.text("数据库用户名:", default="root").ask()
    password = questionary.password("数据库密码:").ask()
    db_name = questionary.text("数据库名称:", default="qiniu_monitor").ask()

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "db_name": db_name
    }

def save_config(config_data):
    config_dir = os.path.join(os.getcwd(), 'config')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    config_file = os.path.join(config_dir, 'settings.yaml')
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

    console.print(f"\n[green]✔ 基础配置已保存至: {config_file}[/green]")

def main():
    print_header()

    # 1. 环境检测
    sys_os = detect_environment()

    # 2. 安装方式选择
    install_type = choose_installation_type()
    if not install_type:
        sys.exit(0)

    # 3. 存储选择
    db_type = choose_database_type()
    if not db_type:
        sys.exit(0)

    config_data = {
        "system": {
            "install_type": install_type.split(".")[0].strip(),
            "os": sys_os
        },
        "database": {
            "type": db_type.split(".")[0].strip()
        }
    }

    if "MySQL" in db_type:
        mysql_config = configure_mysql()
        config_data["database"].update(mysql_config)

    # 保存配置
    save_config(config_data)

    # 模拟安装过程
    console.print("\n")
    with Progress() as progress:
        task = progress.add_task("[cyan]正在生成配置文件并初始化环境...", total=100)
        while not progress.finished:
            progress.update(task, advance=2.5)
            time.sleep(0.05)

    console.print("\n[bold green]🎉 安装向导完成！[/bold green]")
    console.print("[cyan]接下来，您可以启动 Web 后台来配置 API Keys 和 Webhook 了。[/cyan]")
    console.print("运行命令: [bold yellow]python3 run_web.py[/bold yellow]\n")

if __name__ == "__main__":
    main()
