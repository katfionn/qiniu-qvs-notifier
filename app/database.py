"""双 SQLite 数据库与自愈持久化层（data.db 配置数据 + logs.db 运行日志）"""
from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import DATA_DB_PATH, DATA_DIR, LOGS_DB_PATH


def utc_now_iso() -> str:
    """返回标准 UTC ISO 时间字符串"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def data_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect(DATA_DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def logs_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect(LOGS_DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_databases() -> dict[str, Any]:
    """初始化双数据库表结构，并执行完整性校验与僵死记录自愈"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    heal_actions: list[str] = []

    with data_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_first_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'qiniu',
                config_json TEXT NOT NULL DEFAULT '{}',
                namespace_id TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                last_test_status TEXT DEFAULT '',
                last_test_message TEXT DEFAULT '',
                last_tested_at TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notification_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'dingtalk',
                config_json TEXT NOT NULL DEFAULT '{}',
                is_active INTEGER NOT NULL DEFAULT 1,
                last_test_status TEXT DEFAULT '',
                last_test_message TEXT DEFAULT '',
                last_tested_at TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source_channel_id INTEGER NOT NULL,
                gb_id TEXT DEFAULT '',
                schedule_mode TEXT NOT NULL DEFAULT 'interval',
                interval_minutes INTEGER NOT NULL DEFAULT 5,
                daily_time TEXT DEFAULT '09:00',
                cron_expression TEXT NOT NULL DEFAULT '*/5 * * * *',
                is_enabled INTEGER NOT NULL DEFAULT 1,
                notification_channel_ids_json TEXT NOT NULL DEFAULT '[]',
                notify_offline INTEGER NOT NULL DEFAULT 1,
                notify_online INTEGER NOT NULL DEFAULT 1,
                fail_threshold INTEGER NOT NULL DEFAULT 2,
                cooldown_minutes INTEGER NOT NULL DEFAULT 60,
                quiet_hours_enabled INTEGER NOT NULL DEFAULT 0,
                quiet_start TEXT DEFAULT '23:00',
                quiet_end TEXT DEFAULT '07:00',
                last_run_at TEXT DEFAULT '',
                last_status TEXT DEFAULT '',
                last_summary TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (source_channel_id) REFERENCES source_channels(id)
            );

            CREATE TABLE IF NOT EXISTS device_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                source_channel_id INTEGER NOT NULL,
                device_key TEXT NOT NULL,
                device_name TEXT NOT NULL DEFAULT '',
                current_state TEXT NOT NULL DEFAULT 'unknown',
                consecutive_offline INTEGER NOT NULL DEFAULT 0,
                is_alerting INTEGER NOT NULL DEFAULT 0,
                last_alert_at TEXT DEFAULT '',
                last_seen_at TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(task_id, device_key),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS self_heal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    with logs_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                trigger_type TEXT NOT NULL DEFAULT 'scheduled',
                status TEXT NOT NULL DEFAULT 'running',
                total_count INTEGER NOT NULL DEFAULT 0,
                online_count INTEGER NOT NULL DEFAULT 0,
                offline_count INTEGER NOT NULL DEFAULT 0,
                alert_sent_count INTEGER NOT NULL DEFAULT 0,
                message TEXT DEFAULT '',
                details_json TEXT DEFAULT '{}',
                started_at TEXT NOT NULL,
                finished_at TEXT DEFAULT '',
                duration_ms INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_task_logs_started ON task_logs(started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_task_logs_task ON task_logs(task_id);

            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_log_id INTEGER,
                channel_id INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                channel_type TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'sent',
                title TEXT DEFAULT '',
                message TEXT DEFAULT '',
                error_detail TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notif_logs_created ON notification_logs(created_at DESC);
            """
        )

    # 自愈 1：清理异常退出残留的 running 状态任务日志
    recovered = recover_stale_running_logs()
    if recovered > 0:
        msg = f"启动自愈：检测到 {recovered} 条上次异常中断的巡检记录，已自动标记为 interrupted"
        record_self_heal_event("stale_log_recovery", msg)
        heal_actions.append(msg)

    # 自愈 2：清理过期日志，避免磁盘占满
    pruned = cleanup_old_logs()
    if pruned > 0:
        msg = f"启动自愈：自动清理了 {pruned} 条过期历史日志以释放存储空间"
        record_self_heal_event("log_rotation", msg)
        heal_actions.append(msg)

    return {"ok": True, "heal_actions": heal_actions}


def record_self_heal_event(event_type: str, description: str) -> None:
    try:
        with data_conn() as conn:
            conn.execute(
                "INSERT INTO self_heal_events (event_type, description, created_at) VALUES (?, ?, ?)",
                (event_type, description, utc_now_iso()),
            )
            # 仅保留最近 200 条自愈记录
            conn.execute(
                """
                DELETE FROM self_heal_events
                WHERE id NOT IN (
                    SELECT id FROM self_heal_events ORDER BY id DESC LIMIT 200
                )
                """
            )
    except Exception:
        pass


def recover_stale_running_logs() -> int:
    with logs_conn() as conn:
        cur = conn.execute(
            """
            UPDATE task_logs
            SET status = 'interrupted',
                message = CASE
                    WHEN message IS NULL OR message = '' THEN '服务重启或异常退出导致本次巡检中断，系统已自动恢复'
                    ELSE message || '（已自动恢复）'
                END,
                finished_at = ?
            WHERE status = 'running'
            """,
            (utc_now_iso(),),
        )
        return cur.rowcount or 0


def cleanup_old_logs(retention_days: int = 30, max_rows: int = 10000) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    removed = 0
    with logs_conn() as conn:
        c1 = conn.execute("DELETE FROM task_logs WHERE started_at < ?", (cutoff,))
        c2 = conn.execute("DELETE FROM notification_logs WHERE created_at < ?", (cutoff,))
        c3 = conn.execute(
            """
            DELETE FROM task_logs
            WHERE id NOT IN (SELECT id FROM task_logs ORDER BY id DESC LIMIT ?)
            """,
            (max_rows,),
        )
        c4 = conn.execute(
            """
            DELETE FROM notification_logs
            WHERE id NOT IN (SELECT id FROM notification_logs ORDER BY id DESC LIMIT ?)
            """,
            (max_rows,),
        )
        removed = (c1.rowcount or 0) + (c2.rowcount or 0) + (c3.rowcount or 0) + (c4.rowcount or 0)
    return removed


def is_initialized() -> bool:
    """检查系统是否已完成首次管理员初始化"""
    if not DATA_DB_PATH.exists():
        return False
    try:
        with data_conn() as conn:
            row = conn.execute("SELECT COUNT(1) AS cnt FROM users").fetchone()
            return bool(row and row["cnt"] > 0)
    except Exception:
        return False


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with data_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with data_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_setting(key: str, default: str = "") -> str:
    with data_conn() as conn:
        row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with data_conn() as conn:
        conn.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, utc_now_iso()),
        )


def get_db_health() -> dict[str, Any]:
    """返回数据库完整性、WAL 状态与磁盘剩余空间"""
    health: dict[str, Any] = {
        "data_db_ok": False,
        "logs_db_ok": False,
        "data_db_size_kb": 0,
        "logs_db_size_kb": 0,
        "journal_mode": "unknown",
        "disk_free_mb": 0,
    }
    try:
        with data_conn() as conn:
            chk = conn.execute("PRAGMA quick_check").fetchone()
            jm = conn.execute("PRAGMA journal_mode").fetchone()
            health["data_db_ok"] = bool(chk and chk[0] == "ok")
            health["journal_mode"] = jm[0] if jm else "unknown"
        if DATA_DB_PATH.exists():
            health["data_db_size_kb"] = round(DATA_DB_PATH.stat().st_size / 1024, 1)
    except Exception as exc:
        health["data_db_error"] = str(exc)

    try:
        with logs_conn() as conn:
            chk = conn.execute("PRAGMA quick_check").fetchone()
            health["logs_db_ok"] = bool(chk and chk[0] == "ok")
        if LOGS_DB_PATH.exists():
            health["logs_db_size_kb"] = round(LOGS_DB_PATH.stat().st_size / 1024, 1)
    except Exception as exc:
        health["logs_db_error"] = str(exc)

    try:
        usage = shutil.disk_usage(str(DATA_DIR))
        health["disk_free_mb"] = round(usage.free / (1024 * 1024), 1)
    except Exception:
        pass
    return health


def list_self_heal_events(limit: int = 20) -> list[dict[str, Any]]:
    with data_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM self_heal_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def export_config_snapshot(include_secrets: bool = False) -> dict[str, Any]:
    """导出可迁移的系统配置备份"""
    from app.security import mask_secret

    with data_conn() as conn:
        sources = [dict(r) for r in conn.execute("SELECT * FROM source_channels ORDER BY id").fetchall()]
        notifs = [dict(r) for r in conn.execute("SELECT * FROM notification_channels ORDER BY id").fetchall()]
        tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()]
        settings = {
            r["key"]: r["value"]
            for r in conn.execute("SELECT key, value FROM system_settings").fetchall()
        }

    for s in sources:
        cfg = json.loads(s.pop("config_json", "{}") or "{}")
        if not include_secrets:
            for k in ("secret_key", "access_key"):
                if cfg.get(k):
                    cfg[k] = mask_secret(cfg[k])
        s["config"] = cfg

    for n in notifs:
        cfg = json.loads(n.pop("config_json", "{}") or "{}")
        if not include_secrets:
            for k in ("secret", "token", "password"):
                if cfg.get(k):
                    cfg[k] = mask_secret(cfg[k])
        n["config"] = cfg

    for t in tasks:
        t["notification_channel_ids"] = json.loads(t.pop("notification_channel_ids_json", "[]") or "[]")

    return {
        "schema_version": "3.0",
        "exported_at": utc_now_iso(),
        "includes_secrets": include_secrets,
        "source_channels": sources,
        "notification_channels": notifs,
        "tasks": tasks,
        "settings": settings,
    }
