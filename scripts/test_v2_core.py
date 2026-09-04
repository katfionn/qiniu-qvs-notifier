#!/usr/bin/env python3
"""Quick test script to verify v2.0 core functionality"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.table import Table

console = Console()


def test_imports():
    """测试核心模块导入"""
    console.print("\n[cyan]测试 1: 核心模块导入[/cyan]")

    try:
        from web.models.database import init_databases, is_first_run
        from web.auth import create_access_token, verify_password
        from web.scheduler import start_scheduler, stop_scheduler
        console.print("[green]✓ 所有核心模块导入成功[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ 模块导入失败: {e}[/red]")
        return False


def test_database():
    """测试数据库初始化"""
    console.print("\n[cyan]测试 2: 数据库初始化[/cyan]")

    try:
        from web.models.database import DATA_DIR, init_databases

        console.print(f"  数据目录: {DATA_DIR}")

        # 初始化数据库
        init_databases()

        # 检查数据库文件
        data_db = DATA_DIR / "data.db"
        logs_db = DATA_DIR / "logs.db"

        if data_db.exists() and logs_db.exists():
            console.print(f"[green]✓ 数据库文件创建成功[/green]")
            console.print(f"  - {data_db}")
            console.print(f"  - {logs_db}")
            return True
        else:
            console.print("[red]✗ 数据库文件未创建[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 数据库初始化失败: {e}[/red]")
        return False


def test_auth():
    """测试认证系统"""
    console.print("\n[cyan]测试 3: 认证系统[/cyan]")

    try:
        from web.auth import create_access_token, get_password_hash, verify_password

        # 测试密码哈希
        password = "test123456"
        hashed = get_password_hash(password)

        if verify_password(password, hashed):
            console.print("[green]✓ 密码哈希验证成功[/green]")
        else:
            console.print("[red]✗ 密码验证失败[/red]")
            return False

        # 测试 JWT 生成
        token = create_access_token({"sub": 1})

        if token:
            console.print(f"[green]✓ JWT Token 生成成功[/green]")
            console.print(f"  Token 长度: {len(token)} 字符")
            return True
        else:
            console.print("[red]✗ JWT Token 生成失败[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 认证系统测试失败: {e}[/red]")
        return False


def test_models():
    """测试数据模型"""
    console.print("\n[cyan]测试 4: 数据模型操作[/cyan]")

    try:
        from web.models.database import (
            DataSession,
            SourceChannel,
            NotificationChannel,
            Task,
        )

        with DataSession() as session:
            # 测试查询
            source_count = session.query(SourceChannel).count()
            notif_count = session.query(NotificationChannel).count()
            task_count = session.query(Task).count()

            console.print(f"[green]✓ 数据模型查询成功[/green]")
            console.print(f"  - 监听渠道: {source_count} 个")
            console.print(f"  - 通知渠道: {notif_count} 个")
            console.print(f"  - 任务: {task_count} 个")
            return True

    except Exception as e:
        console.print(f"[red]✗ 数据模型测试失败: {e}[/red]")
        return False


def test_scheduler():
    """测试调度器"""
    console.print("\n[cyan]测试 5: 任务调度器[/cyan]")

    try:
        from web.scheduler import get_scheduler_status

        status = get_scheduler_status()

        console.print(f"[green]✓ 调度器状态查询成功[/green]")
        console.print(f"  - 运行状态: {'运行中' if status['running'] else '未启动'}")
        console.print(f"  - 已加载任务: {len(status['jobs'])} 个")
        return True

    except Exception as e:
        console.print(f"[red]✗ 调度器测试失败: {e}[/red]")
        return False


def test_api():
    """测试 API 应用"""
    console.print("\n[cyan]测试 6: FastAPI 应用[/cyan]")

    try:
        from web.main_v2 import app

        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    if method != 'HEAD':
                        routes.append(f"{method} {route.path}")

        console.print(f"[green]✓ FastAPI 应用加载成功[/green]")
        console.print(f"  - API 路由数量: {len(routes)} 个")

        # 显示部分路由
        console.print("\n  主要路由:")
        for route in routes[:10]:
            console.print(f"    {route}")

        if len(routes) > 10:
            console.print(f"    ... 还有 {len(routes) - 10} 个路由")

        return True

    except Exception as e:
        console.print(f"[red]✗ API 应用测试失败: {e}[/red]")
        return False


def main():
    """主测试流程"""
    console.print("\n" + "="*60)
    console.print("[bold cyan]七牛 QVS 通知器 v2.0 - 核心功能测试[/bold cyan]")
    console.print("="*60)

    results = []

    # 运行所有测试
    tests = [
        ("模块导入", test_imports),
        ("数据库初始化", test_database),
        ("认证系统", test_auth),
        ("数据模型", test_models),
        ("任务调度器", test_scheduler),
        ("FastAPI 应用", test_api),
    ]

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            console.print(f"[red]✗ 测试 '{name}' 异常: {e}[/red]")
            results.append((name, False))

    # 显示总结
    console.print("\n" + "="*60)
    console.print("[bold cyan]测试结果总结[/bold cyan]")
    console.print("="*60 + "\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("测试项", style="white")
    table.add_column("结果", style="white", justify="center")

    passed = 0
    for name, result in results:
        status = "[green]✓ 通过[/green]" if result else "[red]✗ 失败[/red]"
        table.add_row(name, status)
        if result:
            passed += 1

    console.print(table)

    # 最终结果
    total = len(results)
    console.print(f"\n[bold]总计: {passed}/{total} 通过[/bold]")

    if passed == total:
        console.print("[bold green]所有测试通过！v2.0 核心功能正常 ✓[/bold green]\n")
        return 0
    else:
        console.print(f"[bold red]{total - passed} 个测试失败，请检查错误信息 ✗[/bold red]\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
