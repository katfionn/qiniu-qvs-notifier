"""Migration script from v1 to v2"""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

console = Console()


def migrate_v1_to_v2() -> None:
    """从 v1 迁移到 v2"""
    console.print(Panel(
        "[cyan]数据迁移：v1.x → v2.0[/cyan]",
        border_style="cyan"
    ))

    # 检查 v1 配置文件
    v1_config_path = ROOT / "config" / "config.yaml"
    v1_devices_db = ROOT / "config" / "devices.db"

    if not v1_config_path.exists() and not v1_devices_db.exists():
        console.print("[yellow]未检测到 v1 数据，跳过迁移[/yellow]")
        return

    console.print("\n[yellow]检测到 v1 数据文件：[/yellow]")
    if v1_config_path.exists():
        console.print(f"  - {v1_config_path}")
    if v1_devices_db.exists():
        console.print(f"  - {v1_devices_db}")

    console.print("\n[cyan]开始迁移数据...[/cyan]\n")

    # 初始化 v2 数据库
    from web.models.database import (
        DataSession,
        NotificationChannel,
        SourceChannel,
        Task,
        init_databases,
    )

    init_databases()

    migrated_count = 0

    # 1. 迁移配置文件
    if v1_config_path.exists():
        try:
            from web.models.settings import load_config as load_v1_config

            v1_config = load_v1_config()

            with DataSession() as session:
                # 创建七牛监听渠道
                qiniu_channel = SourceChannel(
                    name="七牛云（从 v1 迁移）",
                    provider="qiniu",
                    namespace_id="",  # v1 没有存储此字段
                    is_active=True
                )
                qiniu_channel.set_config({
                    "access_key": v1_config.qiniu.access_key,
                    "secret_key": v1_config.qiniu.secret_key
                })
                session.add(qiniu_channel)
                session.flush()

                # 创建 Webhook 通知渠道
                webhook_channel = NotificationChannel(
                    name="Webhook（从 v1 迁移）",
                    type="webhook",
                    is_active=True
                )
                webhook_channel.set_config({
                    "url": v1_config.webhook.url
                })
                session.add(webhook_channel)
                session.flush()

                # 创建默认任务（v1 没有任务概念，创建一个默认任务）
                default_task = Task(
                    name="默认监控任务（从 v1 迁移）",
                    source_channel_id=qiniu_channel.id,
                    cron_expression="*/5 * * * *",  # 默认 5 分钟
                    is_enabled=False  # 默认禁用，需要用户手动启用
                )
                default_task.set_notification_channels([webhook_channel.id])
                session.add(default_task)

                session.commit()

                console.print("[green]✓ 配置文件迁移完成[/green]")
                console.print(f"  - 创建监听渠道: {qiniu_channel.name}")
                console.print(f"  - 创建通知渠道: {webhook_channel.name}")
                console.print(f"  - 创建任务: {default_task.name} (已禁用，需手动启用)")

                migrated_count += 1

        except Exception as e:
            console.print(f"[red]✗ 配置文件迁移失败: {e}[/red]")

    # 2. 迁移设备数据库
    if v1_devices_db.exists():
        try:
            import sqlite3

            conn = sqlite3.connect(v1_devices_db)
            cursor = conn.cursor()

            cursor.execute("SELECT namespace_id, gb_id, name FROM devices")
            devices = cursor.fetchall()

            conn.close()

            if devices:
                console.print(f"\n[yellow]检测到 {len(devices)} 个设备记录[/yellow]")
                console.print("[yellow]v2 采用设备分组方式，建议在 TUI/Web UI 中手动创建设备分组[/yellow]")

                # 导出设备列表到文本文件
                export_path = ROOT / "data" / "v1_devices_export.txt"
                export_path.parent.mkdir(exist_ok=True)

                with open(export_path, "w", encoding="utf-8") as f:
                    f.write("# 从 v1 导出的设备列表\n")
                    f.write("# 格式: namespace_id | gb_id | name\n\n")
                    for namespace_id, gb_id, name in devices:
                        f.write(f"{namespace_id} | {gb_id} | {name}\n")

                console.print(f"[green]✓ 设备列表已导出到: {export_path}[/green]")
                migrated_count += 1

        except Exception as e:
            console.print(f"[red]✗ 设备数据迁移失败: {e}[/red]")

    # 迁移完成
    console.print(f"\n[green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/green]")
    console.print(f"[green]迁移完成！共迁移 {migrated_count} 项数据[/green]")
    console.print(f"[green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/green]\n")

    console.print("[yellow]重要提示：[/yellow]")
    console.print("  1. 默认任务已创建但处于禁用状态")
    console.print("  2. 请在 TUI/Web UI 中编辑任务，配置 Cron 表达式和设备")
    console.print("  3. 启用任务后，调度器将自动执行监控")
    console.print("  4. 可选：备份 v1 数据后删除 config/ 目录\n")


if __name__ == "__main__":
    try:
        migrate_v1_to_v2()
    except Exception as e:
        console.print(f"[red]迁移过程发生错误: {e}[/red]")
        sys.exit(1)
