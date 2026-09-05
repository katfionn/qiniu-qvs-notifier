"""First-time installation wizard"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

console = Console()


def run_installer() -> None:
    """运行首次安装向导（支持环境变量配置）"""
    console.print(Panel("[cyan]欢迎使用七牛 QVS 通知器 v2.0[/cyan]", border_style="cyan"))
    console.print("\n[yellow]检测到这是首次运行，开始配置向导...[/yellow]\n")

    # 检查是否在非交互式环境（如容器）
    use_env_config = os.environ.get("QVS_USE_ENV_CONFIG", "").lower() == "true"

    # 1. 配置数据存储位置
    console.print("[cyan]步骤 1/2: 配置数据存储位置[/cyan]")

    default_data_dir = ROOT / "data"

    if use_env_config:
        # 使用环境变量配置
        data_dir = Path(os.environ.get("QVS_DATA_DIR", str(default_data_dir))).resolve()
        console.print(f"[yellow]使用环境变量配置: QVS_DATA_DIR={data_dir}[/yellow]")
    else:
        # 交互式配置
        data_dir_input = questionary.text(
            "请输入数据存储目录",
            default=str(default_data_dir),
            instruction="(直接回车使用默认位置)"
        ).ask()

        if not data_dir_input:
            console.print("[red]安装已取消[/red]")
            sys.exit(1)

        data_dir = Path(data_dir_input).resolve()

    # 设置环境变量
    os.environ['QVS_DATA_DIR'] = str(data_dir)

    # 创建数据目录
    data_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✓ 数据目录已设置: {data_dir}[/green]\n")

    # 保存配置到 .env 文件（非容器环境）
    if not use_env_config:
        env_file = ROOT / ".env"
        with open(env_file, "w") as f:
            f.write(f"QVS_DATA_DIR={data_dir}\n")
        console.print(f"[green]✓ 配置已保存到: {env_file}[/green]\n")

    # 现在才导入 database 模块（在设置环境变量之后）
    from web.models.database import create_first_admin, init_databases

    # 初始化数据库
    init_databases()

    # 2. 创建管理员账号
    console.print("[cyan]步骤 2/2: 创建管理员账号[/cyan]")

    if use_env_config:
        # 使用环境变量配置
        username = os.environ.get("QVS_ADMIN_USERNAME", "admin")
        password = os.environ.get("QVS_ADMIN_PASSWORD", "")

        if not password:
            console.print("[red]错误: 容器环境必须设置 QVS_ADMIN_PASSWORD 环境变量[/red]")
            sys.exit(1)

        if len(username) < 3:
            console.print("[red]错误: QVS_ADMIN_USERNAME 至少 3 个字符[/red]")
            sys.exit(1)

        if len(password) < 6:
            console.print("[red]错误: QVS_ADMIN_PASSWORD 至少 6 个字符[/red]")
            sys.exit(1)

        console.print(f"[yellow]使用环境变量配置: 用户名={username}[/yellow]")
    else:
        # 交互式配置
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
        console.print(f"\n[cyan]数据目录:[/cyan] {data_dir}")
        console.print(f"[cyan]账号数据:[/cyan] {data_dir / 'data.db'}")
        console.print(f"[cyan]日志数据:[/cyan] {data_dir / 'logs.db'}\n")

        if not use_env_config:
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
