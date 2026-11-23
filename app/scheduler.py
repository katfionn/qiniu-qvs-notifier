"""自愈调度与防重复告警状态机：内置 Cron 解析、连续失败防抖、冷却防轰炸、恢复上线通知与看门狗"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import (
    cleanup_old_logs,
    data_conn,
    logs_conn,
    record_self_heal_event,
    utc_now_iso,
)
from app.notifier import send_notification
from app.qiniu_client import fetch_devices


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    """解析单个 5 位标准 Cron 字段，支持 *, */n, a-b, a-b/n, 逗号列表"""
    result: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError("Cron 字段不能为空")
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError("步长必须大于 0")
        else:
            base = part

        if base == "*":
            start, end = min_val, max_val
        elif "-" in base:
            s_str, e_str = base.split("-", 1)
            start, end = int(s_str), int(e_str)
        else:
            val = int(base)
            start, end = val, val

        if start < min_val or end > max_val or start > end:
            raise ValueError(f"取值范围必须在 {min_val}-{max_val} 之间")
        for v in range(start, end + 1, step):
            result.add(v)
    return result


def validate_cron_expression(expr: str) -> tuple[bool, str]:
    """校验 5 段式 Cron 表达式（分 时 日 月 周）"""
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return False, "Cron 表达式必须包含 5 段（分 时 日 月 周），例如 */5 * * * *"
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    try:
        for p, (lo, hi) in zip(parts, ranges):
            # 兼容周日写作 7
            norm = p.replace("7", "0") if hi == 6 else p
            _parse_cron_field(norm, lo, hi)
        return True, "表达式合法"
    except Exception as exc:
        return False, f"Cron 表达式格式错误：{exc}"


def cron_matches_datetime(expr: str, dt: datetime) -> bool:
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return False
    try:
        minutes = _parse_cron_field(parts[0], 0, 59)
        hours = _parse_cron_field(parts[1], 0, 23)
        days = _parse_cron_field(parts[2], 1, 31)
        months = _parse_cron_field(parts[3], 1, 12)
        weekdays = _parse_cron_field(parts[4].replace("7", "0"), 0, 6)
        # Python weekday(): Monday=0..Sunday=6 -> Cron: Sunday=0, Monday=1..Saturday=6
        cron_dow = (dt.weekday() + 1) % 7
        return (
            dt.minute in minutes
            and dt.hour in hours
            and dt.day in days
            and dt.month in months
            and cron_dow in weekdays
        )
    except Exception:
        return False


def build_schedule_cron(
    schedule_mode: str,
    interval_minutes: int = 5,
    daily_time: str = "09:00",
    cron_expression: str = "*/5 * * * *",
) -> tuple[str, str]:
    """将小白友好调度配置转为标准 Cron 及中文说明"""
    mode = (schedule_mode or "interval").strip().lower()
    if mode == "interval":
        mins = max(1, min(1440, int(interval_minutes or 5)))
        if mins < 60:
            return f"*/{mins} * * * *", f"每 {mins} 分钟自动巡检一次"
        hours = max(1, mins // 60)
        return f"0 */{hours} * * *", f"每 {hours} 小时自动巡检一次"
    if mode == "daily":
        raw = (daily_time or "09:00").strip()
        try:
            hh, mm = raw.split(":", 1)
            h_int, m_int = max(0, min(23, int(hh))), max(0, min(59, int(mm)))
        except Exception:
            h_int, m_int = 9, 0
        return f"{m_int} {h_int} * * *", f"每天 {h_int:02d}:{m_int:02d} 自动巡检"
    ok, err = validate_cron_expression(cron_expression)
    if not ok:
        raise ValueError(err)
    return cron_expression.strip(), f"自定义计划 ({cron_expression.strip()})"


def is_in_quiet_hours(enabled: bool, start_hhmm: str, end_hhmm: str, now_local: datetime | None = None) -> bool:
    """判断当前是否处于免打扰静默时段（支持跨午夜如 23:00-07:00）"""
    if not enabled:
        return False
    dt = now_local or datetime.now()
    try:
        sh, sm = [int(x) for x in (start_hhmm or "23:00").split(":", 1)]
        eh, em = [int(x) for x in (end_hhmm or "07:00").split(":", 1)]
    except Exception:
        return False
    cur_m = dt.hour * 60 + dt.minute
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    if start_m == end_m:
        return False
    if start_m < end_m:
        return start_m <= cur_m < end_m
    return cur_m >= start_m or cur_m < end_m


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


async def execute_task(task_id: int, trigger_type: str = "scheduled") -> dict[str, Any]:
    """
    执行单次巡检任务：
    1. 拉取设备状态
    2. 通过 device_states 状态机完成防抖确认、防重复轰炸冷却、恢复上线检测
    3. 并发发送告警通知并落库完整巡检与通知日志
    """
    t0 = time.monotonic()
    started_iso = utc_now_iso()

    with data_conn() as conn:
        task_row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task_row:
            return {"ok": False, "message": "监控任务不存在"}
        task = dict(task_row)
        if trigger_type == "scheduled" and not task["is_enabled"]:
            return {"ok": False, "message": "任务已暂停"}

        src_row = conn.execute(
            "SELECT * FROM source_channels WHERE id = ?",
            (task["source_channel_id"],),
        ).fetchone()
        if not src_row:
            return {"ok": False, "message": "关联的监控源已被删除，请重新编辑任务"}
        source = dict(src_row)

        notif_ids = json.loads(task.get("notification_channel_ids_json") or "[]")
        notif_channels: list[dict[str, Any]] = []
        if notif_ids:
            placeholders = ",".join("?" for _ in notif_ids)
            rows = conn.execute(
                f"SELECT * FROM notification_channels WHERE id IN ({placeholders}) AND is_active = 1",
                tuple(notif_ids),
            ).fetchall()
            notif_channels = [dict(r) for r in rows]

    # 创建运行中日志
    with logs_conn() as lconn:
        cur = lconn.execute(
            """
            INSERT INTO task_logs (task_id, task_name, trigger_type, status, started_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (task["id"], task["name"], trigger_type, started_iso),
        )
        task_log_id = cur.lastrowid

    try:
        src_cfg = json.loads(source.get("config_json") or "{}")
        devices = await fetch_devices(
            provider=source["provider"],
            config=src_cfg,
            namespace_id=source.get("namespace_id", ""),
            gb_id=task.get("gb_id") or "",
        )

        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        fail_threshold = max(1, int(task.get("fail_threshold") or 2))
        # 手动立即巡检时，为了让用户直观看到当前离线设备状态，若阈值>1也照常累加并在摘要说明
        cooldown_minutes = max(0, int(task.get("cooldown_minutes") or 60))
        notify_offline = bool(task.get("notify_offline", 1))
        notify_online = bool(task.get("notify_online", 1))
        quiet_now = is_in_quiet_hours(
            bool(task.get("quiet_hours_enabled", 0)),
            task.get("quiet_start") or "23:00",
            task.get("quiet_end") or "07:00",
        )

        newly_alerting: list[dict[str, Any]] = []
        reminder_alerting: list[dict[str, Any]] = []
        recovered_devices: list[dict[str, Any]] = []
        pending_debounce: list[dict[str, Any]] = []

        online_count = 0
        offline_count = 0

        with data_conn() as conn:
            existing_rows = conn.execute(
                "SELECT * FROM device_states WHERE task_id = ?",
                (task["id"],),
            ).fetchall()
            state_map = {r["device_key"]: dict(r) for r in existing_rows}

            for dev in devices:
                key = dev["gb_id"]
                name = dev["name"]
                cur_state = dev["state"]
                prev = state_map.get(key)

                if cur_state == "online":
                    online_count += 1
                    was_alerting = bool(prev and prev.get("is_alerting"))
                    if was_alerting and notify_online:
                        recovered_devices.append(dev)
                    conn.execute(
                        """
                        INSERT INTO device_states (
                            task_id, source_channel_id, device_key, device_name,
                            current_state, consecutive_offline, is_alerting,
                            last_alert_at, last_seen_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'online', 0, 0, ?, ?, ?)
                        ON CONFLICT(task_id, device_key) DO UPDATE SET
                            device_name = excluded.device_name,
                            current_state = 'online',
                            consecutive_offline = 0,
                            is_alerting = 0,
                            last_seen_at = excluded.last_seen_at,
                            updated_at = excluded.updated_at
                        """,
                        (
                            task["id"],
                            source["id"],
                            key,
                            name,
                            prev["last_alert_at"] if prev else "",
                            now_iso,
                            now_iso,
                        ),
                    )
                else:
                    offline_count += 1
                    consec = (int(prev["consecutive_offline"]) if prev else 0) + 1
                    was_alerting = bool(prev and prev.get("is_alerting"))
                    last_alert_at = prev.get("last_alert_at", "") if prev else ""
                    new_is_alerting = 1 if was_alerting else 0
                    new_last_alert_at = last_alert_at

                    if notify_offline:
                        if consec >= fail_threshold:
                            if not was_alerting:
                                newly_alerting.append(dev)
                                new_is_alerting = 1
                                new_last_alert_at = now_iso
                            elif cooldown_minutes > 0:
                                last_dt = _parse_iso(last_alert_at)
                                if not last_dt or (now_utc - last_dt) >= timedelta(minutes=cooldown_minutes):
                                    reminder_alerting.append(dev)
                                    new_last_alert_at = now_iso
                        else:
                            pending_debounce.append(dev)

                    conn.execute(
                        """
                        INSERT INTO device_states (
                            task_id, source_channel_id, device_key, device_name,
                            current_state, consecutive_offline, is_alerting,
                            last_alert_at, last_seen_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(task_id, device_key) DO UPDATE SET
                            device_name = excluded.device_name,
                            current_state = excluded.current_state,
                            consecutive_offline = excluded.consecutive_offline,
                            is_alerting = excluded.is_alerting,
                            last_alert_at = excluded.last_alert_at,
                            updated_at = excluded.updated_at
                        """,
                        (
                            task["id"],
                            source["id"],
                            key,
                            name,
                            cur_state,
                            consec,
                            new_is_alerting,
                            new_last_alert_at,
                            prev["last_seen_at"] if prev else "",
                            now_iso,
                        ),
                    )

        # 发送告警与恢复通知
        alert_sent_count = 0
        notifications_to_send: list[tuple[str, str, str]] = []

        alert_targets = newly_alerting + reminder_alerting
        if alert_targets:
            lines = [f"- **{d['name']}** (`{d['gb_id']}`) — 状态：{d['state']}" for d in alert_targets[:10]]
            if len(alert_targets) > 10:
                lines.append(f"- ……以及另外 {len(alert_targets) - 10} 台离线设备")
            title = f"设备离线告警：{task['name']}（{len(alert_targets)} 台异常）"
            msg = (
                f"监控源：{source['name']}\n"
                f"在线：{online_count} 台 / 离线：{offline_count} 台（共 {len(devices)} 台）\n\n"
                f"异常设备明细：\n" + "\n".join(lines)
            )
            notifications_to_send.append((title, msg, "alert"))

        if recovered_devices:
            lines = [f"- **{d['name']}** (`{d['gb_id']}`) 已恢复在线" for d in recovered_devices[:10]]
            title = f"设备恢复上线：{task['name']}（{len(recovered_devices)} 台恢复）"
            msg = (
                f"监控源：{source['name']}\n"
                f"当前在线：{online_count} 台 / 离线：{offline_count} 台\n\n"
                f"已恢复设备：\n" + "\n".join(lines)
            )
            notifications_to_send.append((title, msg, "recovery"))

        if notifications_to_send and notif_channels:
            for title, body, ev_type in notifications_to_send:
                if quiet_now and trigger_type == "scheduled":
                    with logs_conn() as lconn:
                        for ch in notif_channels:
                            lconn.execute(
                                """
                                INSERT INTO notification_logs (
                                    task_log_id, channel_id, channel_name, channel_type,
                                    status, title, message, error_detail, created_at
                                ) VALUES (?, ?, ?, ?, 'skipped', ?, ?, ?, ?)
                                """,
                                (
                                    task_log_id,
                                    ch["id"],
                                    ch["name"],
                                    ch["type"],
                                    title,
                                    body,
                                    "当前处于免打扰静默时段，已自动静默",
                                    utc_now_iso(),
                                ),
                            )
                    continue

                async def _dispatch_one(ch: dict[str, Any]) -> bool:
                    cfg = json.loads(ch.get("config_json") or "{}")
                    res = await send_notification(ch["type"], cfg, title, body, event_type=ev_type)
                    with logs_conn() as lconn:
                        lconn.execute(
                            """
                            INSERT INTO notification_logs (
                                task_log_id, channel_id, channel_name, channel_type,
                                status, title, message, error_detail, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                task_log_id,
                                ch["id"],
                                ch["name"],
                                ch["type"],
                                "sent" if res["ok"] else "failed",
                                title,
                                body,
                                "" if res["ok"] else res["message"],
                                utc_now_iso(),
                            ),
                        )
                    return bool(res["ok"])

                results = await asyncio.gather(*(_dispatch_one(ch) for ch in notif_channels))
                alert_sent_count += sum(1 for ok in results if ok)

        duration_ms = int((time.monotonic() - t0) * 1000)
        summary_parts = [f"共检测 {len(devices)} 台（在线 {online_count}，离线 {offline_count}）"]
        if alert_sent_count > 0:
            summary_parts.append(f"已发送 {alert_sent_count} 条通知")
        elif pending_debounce:
            summary_parts.append(f"{len(pending_debounce)} 台离线观察中（未达连续 {fail_threshold} 次防误报阈值）")
        elif offline_count > 0 and not alert_targets:
            summary_parts.append("离线设备处于冷却期内，已自动防重复轰炸")
        elif quiet_now and notifications_to_send:
            summary_parts.append("处于免打扰时段，已静默")
        summary = "；".join(summary_parts)

        details = {
            "newly_alerting": len(newly_alerting),
            "reminder_alerting": len(reminder_alerting),
            "recovered": len(recovered_devices),
            "pending_debounce": len(pending_debounce),
            "quiet_now": quiet_now,
        }

        finished_iso = utc_now_iso()
        with logs_conn() as lconn:
            lconn.execute(
                """
                UPDATE task_logs
                SET status = 'success',
                    total_count = ?,
                    online_count = ?,
                    offline_count = ?,
                    alert_sent_count = ?,
                    message = ?,
                    details_json = ?,
                    finished_at = ?,
                    duration_ms = ?
                WHERE id = ?
                """,
                (
                    len(devices),
                    online_count,
                    offline_count,
                    alert_sent_count,
                    summary,
                    json.dumps(details, ensure_ascii=False),
                    finished_iso,
                    duration_ms,
                    task_log_id,
                ),
            )

        with data_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET last_run_at = ?, last_status = 'success', last_summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (finished_iso, summary, finished_iso, task["id"]),
            )

        return {
            "ok": True,
            "task_log_id": task_log_id,
            "total": len(devices),
            "online": online_count,
            "offline": offline_count,
            "alert_sent": alert_sent_count,
            "message": summary,
            "duration_ms": duration_ms,
        }

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        finished_iso = utc_now_iso()
        with logs_conn() as lconn:
            lconn.execute(
                """
                UPDATE task_logs
                SET status = 'failed', message = ?, finished_at = ?, duration_ms = ?
                WHERE id = ?
                """,
                (err_msg, finished_iso, duration_ms, task_log_id),
            )
        with data_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET last_run_at = ?, last_status = 'failed', last_summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (finished_iso, err_msg, finished_iso, task["id"]),
            )
        return {
            "ok": False,
            "task_log_id": task_log_id,
            "message": err_msg,
            "duration_ms": duration_ms,
        }


class SelfHealingScheduler:
    """零外部依赖的异步调度引擎（内置分钟去重、单任务隔离、自动日志轮转与看门狗自愈）"""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._last_minute_key: dict[int, str] = {}
        self._last_cleanup_date: str = ""
        self.last_heartbeat: str = ""
        self.restart_count: int = 0

    def is_running(self) -> bool:
        return bool(self._running and self._task and not self._task.done())

    def start(self) -> None:
        if self.is_running():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="qvs-self-healing-scheduler")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def ensure_alive(self) -> bool:
        """看门狗自愈：若调度循环意外退出则自动重启"""
        if self._running and (self._task is None or self._task.done()):
            self.restart_count += 1
            record_self_heal_event(
                "scheduler_auto_restart",
                f"看门狗检测到后台调度协程异常停止，已自动重启（第 {self.restart_count} 次）",
            )
            self._task = asyncio.create_task(self._loop(), name="qvs-self-healing-scheduler")
            return True
        return False

    async def _loop(self) -> None:
        while self._running:
            try:
                now_local = datetime.now()
                self.last_heartbeat = utc_now_iso()
                minute_key = now_local.strftime("%Y-%m-%d %H:%M")

                # 每日凌晨自动清理过期日志
                today_str = now_local.strftime("%Y-%m-%d")
                if today_str != self._last_cleanup_date and now_local.hour == 3:
                    self._last_cleanup_date = today_str
                    pruned = cleanup_old_logs()
                    if pruned > 0:
                        record_self_heal_event("daily_log_cleanup", f"每日定时清理了 {pruned} 条过期日志")

                with data_conn() as conn:
                    rows = conn.execute("SELECT id, cron_expression FROM tasks WHERE is_enabled = 1").fetchall()

                for row in rows:
                    tid = row["id"]
                    expr = row["cron_expression"]
                    if self._last_minute_key.get(tid) == minute_key:
                        continue
                    if cron_matches_datetime(expr, now_local):
                        self._last_minute_key[tid] = minute_key
                        asyncio.create_task(self._safe_run(tid))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                record_self_heal_event("scheduler_tick_error", f"调度周期出现异常，已自动隔离跳过：{exc}")

            await asyncio.sleep(15)

    async def _safe_run(self, task_id: int) -> None:
        try:
            await execute_task(task_id, trigger_type="scheduled")
        except Exception as exc:
            record_self_heal_event("task_crash_isolated", f"任务 #{task_id} 执行异常已隔离：{exc}")

    def status(self) -> dict[str, Any]:
        healed = self.ensure_alive()
        with data_conn() as conn:
            total_tasks = conn.execute("SELECT COUNT(1) FROM tasks").fetchone()[0]
            enabled_tasks = conn.execute("SELECT COUNT(1) FROM tasks WHERE is_enabled = 1").fetchone()[0]
        return {
            "running": self.is_running(),
            "last_heartbeat": self.last_heartbeat,
            "restart_count": self.restart_count,
            "healed_just_now": healed,
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
        }


scheduler_engine = SelfHealingScheduler()
