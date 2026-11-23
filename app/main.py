"""FastAPI 主应用 v3.1：零门槛 Web 初始化、多云监控源、脱敏测试补全与逻辑自洽校验"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import __version__
from app.database import (
    cleanup_old_logs,
    data_conn,
    export_config_snapshot,
    get_db_health,
    get_user_by_username,
    init_databases,
    is_initialized,
    list_self_heal_events,
    logs_conn,
    record_self_heal_event,
    utc_now_iso,
)
from app.notifier import send_test_notification
from app.qiniu_client import clamp_demo_config, test_source_connection
from app.scheduler import (
    build_schedule_cron,
    execute_task,
    scheduler_engine,
    validate_cron_expression,
)
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    is_masked_value,
    mask_secret,
    require_admin,
    verify_password,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
SOURCE_SECRET_FIELDS = ("secret_key", "access_key_secret")
NOTIF_SECRET_FIELDS = ("secret", "token", "password")

app = FastAPI(
    title="七牛 QVS 多云监控告警中心",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ==================== 全局异常友好兜底 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    record_self_heal_event("api_error_caught", f"捕获未处理接口异常 ({request.url.path}): {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"系统遇到临时异常，已自动保护现场：{exc}"},
    )


@app.on_event("startup")
async def on_startup() -> None:
    init_databases()
    scheduler_engine.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await scheduler_engine.stop()


# ==================== Pydantic 请求模型 ====================

class SetupInitRequest(BaseModel):
    username: str = Field(default="admin", min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user")


class SourceChannelPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    provider: str = Field(default="qiniu")
    namespace_id: str = Field(default="")
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class SourceTestPayload(BaseModel):
    channel_id: Optional[int] = Field(default=None)
    provider: str = Field(default="qiniu")
    namespace_id: str = Field(default="")
    config: dict[str, Any] = Field(default_factory=dict)


class NotificationChannelPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    type: str = Field(default="dingtalk")
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class NotificationTestPayload(BaseModel):
    channel_id: Optional[int] = Field(default=None)
    type: str = Field(default="dingtalk")
    config: dict[str, Any] = Field(default_factory=dict)


class TaskPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    source_channel_id: int
    gb_id: str = Field(default="")
    schedule_mode: str = Field(default="interval")
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    daily_time: str = Field(default="09:00")
    cron_expression: str = Field(default="*/5 * * * *")
    is_enabled: bool = Field(default=True)
    notification_channel_ids: list[int] = Field(default_factory=list)
    notify_offline: bool = Field(default=True)
    notify_online: bool = Field(default=True)
    fail_threshold: int = Field(default=2, ge=1, le=10)
    cooldown_minutes: int = Field(default=60, ge=0, le=10080)
    quiet_hours_enabled: bool = Field(default=False)
    quiet_start: str = Field(default="23:00")
    quiet_end: str = Field(default="07:00")


class SchedulerControlPayload(BaseModel):
    action: str = Field(..., description="start | stop | restart")


class RestorePayload(BaseModel):
    snapshot: dict[str, Any]


# ==================== 工具函数 ====================

def _normalize_source_config(provider: str, config: dict[str, Any]) -> dict[str, Any]:
    """统一清洗并强制校验监控源配置逻辑自洽"""
    cfg = dict(config or {})
    if (provider or "").strip().lower() == "demo":
        total, offline = clamp_demo_config(cfg)
        cfg["demo_total_count"] = total
        cfg["demo_offline_count"] = offline
    return cfg


def _sanitize_source_row(row: dict[str, Any]) -> dict[str, Any]:
    cfg = json.loads(row.get("config_json") or "{}")
    safe_cfg = dict(cfg)
    for k in SOURCE_SECRET_FIELDS:
        if safe_cfg.get(k):
            safe_cfg[k] = mask_secret(safe_cfg[k])
    return {
        "id": row["id"],
        "name": row["name"],
        "provider": row["provider"],
        "namespace_id": row["namespace_id"],
        "config": safe_cfg,
        "is_active": bool(row["is_active"]),
        "last_test_status": row.get("last_test_status") or "",
        "last_test_message": row.get("last_test_message") or "",
        "last_tested_at": row.get("last_tested_at") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _sanitize_notif_row(row: dict[str, Any]) -> dict[str, Any]:
    cfg = json.loads(row.get("config_json") or "{}")
    safe_cfg = dict(cfg)
    for k in NOTIF_SECRET_FIELDS:
        if safe_cfg.get(k):
            safe_cfg[k] = mask_secret(safe_cfg[k])
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "config": safe_cfg,
        "is_active": bool(row["is_active"]),
        "last_test_status": row.get("last_test_status") or "",
        "last_test_message": row.get("last_test_message") or "",
        "last_tested_at": row.get("last_tested_at") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _merge_secrets(new_cfg: dict[str, Any], old_cfg: dict[str, Any], secret_fields: tuple[str, ...]) -> dict[str, Any]:
    merged = dict(new_cfg)
    for key in secret_fields:
        val = merged.get(key)
        if val is None or val == "" or is_masked_value(val):
            if key in old_cfg:
                merged[key] = old_cfg[key]
    return merged


# ==================== 前端入口与公共探针 ====================

@app.get("/")
async def serve_index() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="前端页面文件缺失")
    return FileResponse(str(index_file))


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    db_health = get_db_health()
    sched = scheduler_engine.status()
    ok = db_health.get("data_db_ok") and db_health.get("logs_db_ok")
    return {
        "status": "ok" if ok else "degraded",
        "version": __version__,
        "initialized": is_initialized(),
        "scheduler_running": sched["running"],
        "db": db_health,
    }


@app.get("/api/system/status")
async def system_status() -> dict[str, Any]:
    return {
        "initialized": is_initialized(),
        "version": __version__,
        "scheduler_running": scheduler_engine.is_running(),
    }


@app.post("/api/setup/init")
async def setup_init(payload: SetupInitRequest) -> dict[str, Any]:
    if is_initialized():
        raise HTTPException(status_code=400, detail="系统已完成初始化，请直接登录")

    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="管理员用户名至少需要 3 个字符")

    now = utc_now_iso()
    pwd_hash = hash_password(payload.password)
    with data_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, is_first_admin, created_at, updated_at)
            VALUES (?, ?, 'admin', 1, ?, ?)
            """,
            (username, pwd_hash, now, now),
        )
        user_id = cur.lastrowid

    token = create_access_token(user_id=user_id, username=username, role="admin")
    return {
        "message": "初始化成功，已自动为您登录！",
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user_id, "username": username, "role": "admin", "is_first_admin": True},
    }


# ==================== 登录与用户管理 ====================

@app.post("/api/auth/login")
async def login(payload: LoginRequest) -> dict[str, Any]:
    if not is_initialized():
        raise HTTPException(status_code=400, detail="系统尚未初始化，请先完成首次安装向导")
    user = get_user_by_username(payload.username.strip())
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误，请重新核对")
    token = create_access_token(user_id=user["id"], username=user["username"], role=user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "is_first_admin": bool(user["is_first_admin"]),
        },
    }


@app.get("/api/auth/me")
async def auth_me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_first_admin": bool(user["is_first_admin"]),
    }


@app.post("/api/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not verify_password(payload.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="当前原密码输入不正确")
    new_hash = hash_password(payload.new_password)
    with data_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, utc_now_iso(), user["id"]),
        )
    return {"message": "密码修改成功"}


@app.get("/api/users")
async def list_users(_: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    with data_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, role, is_first_admin, created_at FROM users ORDER BY id"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "username": r["username"],
            "role": r["role"],
            "is_first_admin": bool(r["is_first_admin"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.post("/api/users")
async def create_user(
    payload: UserCreateRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    username = payload.username.strip()
    role = "admin" if payload.role == "admin" else "user"
    if get_user_by_username(username):
        raise HTTPException(status_code=400, detail=f"用户名 '{username}' 已存在")
    now = utc_now_iso()
    with data_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, is_first_admin, created_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (username, hash_password(payload.password), role, now, now),
        )
        uid = cur.lastrowid
    return {"id": uid, "username": username, "role": role, "message": "账号创建成功"}


@app.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除当前正在登录的账号")
    with data_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if row["is_first_admin"]:
            raise HTTPException(status_code=400, detail="首个初始管理员账号受保护，不可删除")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"message": "账号已删除"}


# ==================== 总览仪表盘 ====================

@app.get("/api/dashboard/overview")
async def dashboard_overview(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with data_conn() as conn:
        src_cnt = conn.execute("SELECT COUNT(1) FROM source_channels").fetchone()[0]
        notif_cnt = conn.execute("SELECT COUNT(1) FROM notification_channels").fetchone()[0]
        task_cnt = conn.execute("SELECT COUNT(1) FROM tasks").fetchone()[0]
        enabled_task_cnt = conn.execute("SELECT COUNT(1) FROM tasks WHERE is_enabled = 1").fetchone()[0]
        device_rows = conn.execute(
            """
            SELECT ds.*, t.name AS task_name, sc.name AS source_name, sc.provider AS source_provider
            FROM device_states ds
            LEFT JOIN tasks t ON ds.task_id = t.id
            LEFT JOIN source_channels sc ON ds.source_channel_id = sc.id
            ORDER BY CASE WHEN ds.current_state = 'online' THEN 1 ELSE 0 END, ds.updated_at DESC
            LIMIT 100
            """
        ).fetchall()

    devices = [dict(r) for r in device_rows]
    online_devices = sum(1 for d in devices if d["current_state"] == "online")
    offline_devices = len(devices) - online_devices

    with logs_conn() as lconn:
        total_runs = lconn.execute("SELECT COUNT(1) FROM task_logs").fetchone()[0]
        today_checks = lconn.execute(
            "SELECT COUNT(1) FROM task_logs WHERE started_at LIKE ?",
            (f"{today_prefix}%",),
        ).fetchone()[0]
        today_alerts = lconn.execute(
            "SELECT COUNT(1) FROM notification_logs WHERE status = 'sent' AND created_at LIKE ?",
            (f"{today_prefix}%",),
        ).fetchone()[0]
        recent_logs = [
            dict(r)
            for r in lconn.execute("SELECT * FROM task_logs ORDER BY id DESC LIMIT 8").fetchall()
        ]

    return {
        "onboarding": {
            "has_source": src_cnt > 0,
            "has_notification": notif_cnt > 0,
            "has_task": task_cnt > 0,
            "has_run": total_runs > 0,
        },
        "stats": {
            "source_count": src_cnt,
            "notification_count": notif_cnt,
            "task_count": task_cnt,
            "enabled_task_count": enabled_task_cnt,
            "total_devices": len(devices),
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "today_checks": today_checks,
            "today_alerts": today_alerts,
        },
        "scheduler": scheduler_engine.status(),
        "db_health": get_db_health(),
        "devices": devices,
        "recent_logs": recent_logs,
    }


# ==================== 监控源管理 ====================

@app.get("/api/source-channels")
async def list_source_channels(_: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    with data_conn() as conn:
        rows = conn.execute("SELECT * FROM source_channels ORDER BY id DESC").fetchall()
    return [_sanitize_source_row(dict(r)) for r in rows]


@app.post("/api/source-channels")
async def create_source_channel(
    payload: SourceChannelPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    provider = payload.provider.strip().lower()
    clean_cfg = _normalize_source_config(provider, payload.config)
    now = utc_now_iso()
    with data_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO source_channels (name, provider, config_json, namespace_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                provider,
                json.dumps(clean_cfg, ensure_ascii=False),
                payload.namespace_id.strip(),
                1 if payload.is_active else 0,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM source_channels WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _sanitize_source_row(dict(row))


@app.put("/api/source-channels/{channel_id}")
async def update_source_channel(
    channel_id: int,
    payload: SourceChannelPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    provider = payload.provider.strip().lower()
    with data_conn() as conn:
        existing = conn.execute("SELECT * FROM source_channels WHERE id = ?", (channel_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="监控源不存在")
        old_cfg = json.loads(existing["config_json"] or "{}")
        merged_cfg = _normalize_source_config(
            provider,
            _merge_secrets(payload.config, old_cfg, SOURCE_SECRET_FIELDS),
        )
        conn.execute(
            """
            UPDATE source_channels
            SET name = ?, provider = ?, config_json = ?, namespace_id = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                provider,
                json.dumps(merged_cfg, ensure_ascii=False),
                payload.namespace_id.strip(),
                1 if payload.is_active else 0,
                utc_now_iso(),
                channel_id,
            ),
        )
        row = conn.execute("SELECT * FROM source_channels WHERE id = ?", (channel_id,)).fetchone()
    return _sanitize_source_row(dict(row))


@app.delete("/api/source-channels/{channel_id}")
async def delete_source_channel(
    channel_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with data_conn() as conn:
        refs = conn.execute(
            "SELECT name FROM tasks WHERE source_channel_id = ?",
            (channel_id,),
        ).fetchall()
        if refs:
            names = "、".join(r["name"] for r in refs)
            raise HTTPException(
                status_code=400,
                detail=f"该监控源正在被监控任务【{names}】使用，请先删除或修改对应任务。",
            )
        cur = conn.execute("DELETE FROM source_channels WHERE id = ?", (channel_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="监控源不存在")
    return {"message": "监控源已删除"}


@app.post("/api/source-channels/test")
async def test_unsaved_source(
    payload: SourceTestPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    cfg = dict(payload.config or {})
    if payload.channel_id:
        with data_conn() as conn:
            row = conn.execute("SELECT config_json FROM source_channels WHERE id = ?", (payload.channel_id,)).fetchone()
            if row:
                old_cfg = json.loads(row["config_json"] or "{}")
                cfg = _merge_secrets(cfg, old_cfg, SOURCE_SECRET_FIELDS)
    clean_cfg = _normalize_source_config(payload.provider, cfg)
    return await test_source_connection(
        provider=payload.provider,
        config=clean_cfg,
        namespace_id=payload.namespace_id,
    )


@app.post("/api/source-channels/{channel_id}/test")
async def test_saved_source(
    channel_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with data_conn() as conn:
        row = conn.execute("SELECT * FROM source_channels WHERE id = ?", (channel_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="监控源不存在")
        src = dict(row)

    cfg = _normalize_source_config(src["provider"], json.loads(src.get("config_json") or "{}"))
    result = await test_source_connection(
        provider=src["provider"],
        config=cfg,
        namespace_id=src.get("namespace_id", ""),
    )
    with data_conn() as conn:
        conn.execute(
            """
            UPDATE source_channels
            SET last_test_status = ?, last_test_message = ?, last_tested_at = ?
            WHERE id = ?
            """,
            ("ok" if result["ok"] else "failed", result["message"], utc_now_iso(), channel_id),
        )
    return result


# ==================== 通知渠道管理 ====================

@app.get("/api/notification-channels")
async def list_notification_channels(_: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    with data_conn() as conn:
        rows = conn.execute("SELECT * FROM notification_channels ORDER BY id DESC").fetchall()
    return [_sanitize_notif_row(dict(r)) for r in rows]


@app.post("/api/notification-channels")
async def create_notification_channel(
    payload: NotificationChannelPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    now = utc_now_iso()
    with data_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO notification_channels (name, type, config_json, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.type.strip().lower(),
                json.dumps(payload.config, ensure_ascii=False),
                1 if payload.is_active else 0,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM notification_channels WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _sanitize_notif_row(dict(row))


@app.put("/api/notification-channels/{channel_id}")
async def update_notification_channel(
    channel_id: int,
    payload: NotificationChannelPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with data_conn() as conn:
        existing = conn.execute("SELECT * FROM notification_channels WHERE id = ?", (channel_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="通知渠道不存在")
        old_cfg = json.loads(existing["config_json"] or "{}")
        merged_cfg = _merge_secrets(payload.config, old_cfg, NOTIF_SECRET_FIELDS)
        conn.execute(
            """
            UPDATE notification_channels
            SET name = ?, type = ?, config_json = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.type.strip().lower(),
                json.dumps(merged_cfg, ensure_ascii=False),
                1 if payload.is_active else 0,
                utc_now_iso(),
                channel_id,
            ),
        )
        row = conn.execute("SELECT * FROM notification_channels WHERE id = ?", (channel_id,)).fetchone()
    return _sanitize_notif_row(dict(row))


@app.delete("/api/notification-channels/{channel_id}")
async def delete_notification_channel(
    channel_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    unbound_count = 0
    with data_conn() as conn:
        cur = conn.execute("DELETE FROM notification_channels WHERE id = ?", (channel_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="通知渠道不存在")
        task_rows = conn.execute("SELECT id, notification_channel_ids_json FROM tasks").fetchall()
        for tr in task_rows:
            ids = json.loads(tr["notification_channel_ids_json"] or "[]")
            if channel_id in ids:
                new_ids = [i for i in ids if i != channel_id]
                conn.execute(
                    "UPDATE tasks SET notification_channel_ids_json = ? WHERE id = ?",
                    (json.dumps(new_ids), tr["id"]),
                )
                unbound_count += 1
    msg = "通知渠道已删除"
    if unbound_count > 0:
        msg += f"（已自动从 {unbound_count} 个关联任务中解除绑定）"
    return {"message": msg}


@app.post("/api/notification-channels/test")
async def test_unsaved_notification(
    payload: NotificationTestPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    cfg = dict(payload.config or {})
    if payload.channel_id:
        with data_conn() as conn:
            row = conn.execute("SELECT config_json FROM notification_channels WHERE id = ?", (payload.channel_id,)).fetchone()
            if row:
                old_cfg = json.loads(row["config_json"] or "{}")
                cfg = _merge_secrets(cfg, old_cfg, NOTIF_SECRET_FIELDS)
    return await send_test_notification(payload.type, cfg)


@app.post("/api/notification-channels/{channel_id}/test")
async def test_saved_notification(
    channel_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with data_conn() as conn:
        row = conn.execute("SELECT * FROM notification_channels WHERE id = ?", (channel_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="通知渠道不存在")
        ch = dict(row)

    cfg = json.loads(ch.get("config_json") or "{}")
    result = await send_test_notification(ch["type"], cfg)
    now = utc_now_iso()
    with data_conn() as conn:
        conn.execute(
            """
            UPDATE notification_channels
            SET last_test_status = ?, last_test_message = ?, last_tested_at = ?
            WHERE id = ?
            """,
            ("ok" if result["ok"] else "failed", result["message"], now, channel_id),
        )
    with logs_conn() as lconn:
        lconn.execute(
            """
            INSERT INTO notification_logs (
                task_log_id, channel_id, channel_name, channel_type,
                status, title, message, error_detail, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                channel_id,
                ch["name"],
                ch["type"],
                "sent" if result["ok"] else "failed",
                "手动测试通知",
                "测试渠道连通性",
                "" if result["ok"] else result["message"],
                now,
            ),
        )
    return result


# ==================== 监控任务管理 ====================

def _format_task_row(
    row: dict[str, Any],
    sources_map: dict[int, str],
    notifs_map: dict[int, str],
) -> dict[str, Any]:
    notif_ids = json.loads(row.get("notification_channel_ids_json") or "[]")
    try:
        _, schedule_text = build_schedule_cron(
            row.get("schedule_mode", "interval"),
            row.get("interval_minutes", 5),
            row.get("daily_time", "09:00"),
            row.get("cron_expression", "*/5 * * * *"),
        )
    except Exception:
        schedule_text = row.get("cron_expression", "")
    return {
        "id": row["id"],
        "name": row["name"],
        "source_channel_id": row["source_channel_id"],
        "source_channel_name": sources_map.get(row["source_channel_id"], "未知监控源"),
        "gb_id": row.get("gb_id") or "",
        "schedule_mode": row.get("schedule_mode") or "interval",
        "interval_minutes": row.get("interval_minutes") or 5,
        "daily_time": row.get("daily_time") or "09:00",
        "cron_expression": row["cron_expression"],
        "schedule_text": schedule_text,
        "is_enabled": bool(row["is_enabled"]),
        "notification_channel_ids": notif_ids,
        "notification_channel_names": [notifs_map[i] for i in notif_ids if i in notifs_map],
        "notify_offline": bool(row.get("notify_offline", 1)),
        "notify_online": bool(row.get("notify_online", 1)),
        "fail_threshold": int(row.get("fail_threshold") or 2),
        "cooldown_minutes": int(row.get("cooldown_minutes") or 60),
        "quiet_hours_enabled": bool(row.get("quiet_hours_enabled", 0)),
        "quiet_start": row.get("quiet_start") or "23:00",
        "quiet_end": row.get("quiet_end") or "07:00",
        "last_run_at": row.get("last_run_at") or "",
        "last_status": row.get("last_status") or "",
        "last_summary": row.get("last_summary") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _validate_task_logic(payload: TaskPayload) -> str:
    try:
        cron_expr, _ = build_schedule_cron(
            payload.schedule_mode,
            payload.interval_minutes,
            payload.daily_time,
            payload.cron_expression,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if payload.quiet_hours_enabled and payload.quiet_start == payload.quiet_end:
        raise HTTPException(status_code=400, detail="免打扰开始时间与结束时间不能完全相同。")
    return cron_expr


@app.get("/api/tasks")
async def list_tasks(_: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    with data_conn() as conn:
        sources_map = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM source_channels").fetchall()}
        notifs_map = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM notification_channels").fetchall()}
        rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    return [_format_task_row(dict(r), sources_map, notifs_map) for r in rows]


@app.post("/api/tasks")
async def create_task(
    payload: TaskPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    cron_expr = _validate_task_logic(payload)
    now = utc_now_iso()
    with data_conn() as conn:
        src = conn.execute("SELECT id FROM source_channels WHERE id = ?", (payload.source_channel_id,)).fetchone()
        if not src:
            raise HTTPException(status_code=400, detail="所选监控源不存在，请先添加监控源")
        cur = conn.execute(
            """
            INSERT INTO tasks (
                name, source_channel_id, gb_id, schedule_mode, interval_minutes, daily_time,
                cron_expression, is_enabled, notification_channel_ids_json,
                notify_offline, notify_online, fail_threshold, cooldown_minutes,
                quiet_hours_enabled, quiet_start, quiet_end, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.source_channel_id,
                payload.gb_id.strip(),
                payload.schedule_mode,
                payload.interval_minutes,
                payload.daily_time,
                cron_expr,
                1 if payload.is_enabled else 0,
                json.dumps(payload.notification_channel_ids),
                1 if payload.notify_offline else 0,
                1 if payload.notify_online else 0,
                payload.fail_threshold,
                payload.cooldown_minutes,
                1 if payload.quiet_hours_enabled else 0,
                payload.quiet_start,
                payload.quiet_end,
                now,
                now,
            ),
        )
        tid = cur.lastrowid
        row = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone())
        sources_map = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM source_channels").fetchall()}
        notifs_map = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM notification_channels").fetchall()}
    return _format_task_row(row, sources_map, notifs_map)


@app.put("/api/tasks/{task_id}")
async def update_task(
    task_id: int,
    payload: TaskPayload,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    cron_expr = _validate_task_logic(payload)
    with data_conn() as conn:
        if not conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone():
            raise HTTPException(status_code=404, detail="监控任务不存在")
        conn.execute(
            """
            UPDATE tasks
            SET name = ?, source_channel_id = ?, gb_id = ?, schedule_mode = ?,
                interval_minutes = ?, daily_time = ?, cron_expression = ?, is_enabled = ?,
                notification_channel_ids_json = ?, notify_offline = ?, notify_online = ?,
                fail_threshold = ?, cooldown_minutes = ?, quiet_hours_enabled = ?,
                quiet_start = ?, quiet_end = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.source_channel_id,
                payload.gb_id.strip(),
                payload.schedule_mode,
                payload.interval_minutes,
                payload.daily_time,
                cron_expr,
                1 if payload.is_enabled else 0,
                json.dumps(payload.notification_channel_ids),
                1 if payload.notify_offline else 0,
                1 if payload.notify_online else 0,
                payload.fail_threshold,
                payload.cooldown_minutes,
                1 if payload.quiet_hours_enabled else 0,
                payload.quiet_start,
                payload.quiet_end,
                utc_now_iso(),
                task_id,
            ),
        )
        row = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
        sources_map = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM source_channels").fetchall()}
        notifs_map = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM notification_channels").fetchall()}
    return _format_task_row(row, sources_map, notifs_map)


@app.patch("/api/tasks/{task_id}/toggle")
async def toggle_task(
    task_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with data_conn() as conn:
        row = conn.execute("SELECT is_enabled FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="监控任务不存在")
        new_val = 0 if row["is_enabled"] else 1
        conn.execute(
            "UPDATE tasks SET is_enabled = ?, updated_at = ? WHERE id = ?",
            (new_val, utc_now_iso(), task_id),
        )
    return {"id": task_id, "is_enabled": bool(new_val)}


@app.delete("/api/tasks/{task_id}")
async def delete_task(
    task_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    with data_conn() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="监控任务不存在")
    return {"message": "监控任务已删除"}


@app.post("/api/tasks/{task_id}/run")
async def run_task_now(
    task_id: int,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await execute_task(task_id, trigger_type="manual")


@app.get("/api/cron/validate")
async def cron_validate(expr: str = Query(...)) -> dict[str, Any]:
    ok, msg = validate_cron_expression(expr)
    return {"valid": ok, "message": msg}


# ==================== 日志、自愈与配置备份恢复 ====================

@app.get("/api/logs/tasks")
async def get_task_logs(
    status: Optional[str] = Query(default=None),
    task_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if task_id:
        clauses.append("task_id = ?")
        params.append(task_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with logs_conn() as lconn:
        rows = lconn.execute(
            f"SELECT * FROM task_logs {where_sql} ORDER BY id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/logs/notifications")
async def get_notification_logs(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with logs_conn() as lconn:
        rows = lconn.execute(
            f"SELECT * FROM notification_logs {where_sql} ORDER BY id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/logs/cleanup")
async def trigger_logs_cleanup(
    retention_days: int = Query(default=30, ge=0, le=365),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    removed = cleanup_old_logs(retention_days=retention_days)
    return {"removed": removed, "message": f"清理完成，共移除 {removed} 条历史日志"}


@app.get("/api/system/health-report")
async def system_health_report(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "version": __version__,
        "scheduler": scheduler_engine.status(),
        "db_health": get_db_health(),
        "self_heal_events": list_self_heal_events(limit=20),
    }


@app.post("/api/scheduler/control")
async def scheduler_control(
    payload: SchedulerControlPayload,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    action = payload.action.strip().lower()
    if action == "start":
        scheduler_engine.start()
    elif action == "stop":
        await scheduler_engine.stop()
    elif action == "restart":
        await scheduler_engine.stop()
        scheduler_engine.start()
    else:
        raise HTTPException(status_code=400, detail="不支持的操作，请使用 start / stop / restart")
    return {"message": f"调度器操作 ({action}) 已执行", "scheduler": scheduler_engine.status()}


@app.get("/api/system/backup")
async def backup_config(
    include_secrets: bool = Query(default=False),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    snap = export_config_snapshot(include_secrets=include_secrets)
    snap["schema_version"] = __version__
    return snap


@app.post("/api/system/restore")
async def restore_config(
    payload: RestorePayload,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    snap = payload.snapshot
    if not isinstance(snap, dict) or "source_channels" not in snap:
        raise HTTPException(status_code=400, detail="备份文件格式不正确，请上传从本系统导出的 JSON 文件")

    now = utc_now_iso()
    src_id_map: dict[int, int] = {}
    notif_id_map: dict[int, int] = {}
    imported = {"sources": 0, "notifications": 0, "tasks": 0}

    with data_conn() as conn:
        for s in snap.get("source_channels", []):
            prov = str(s.get("provider", "qiniu")).strip().lower()
            clean_cfg = _normalize_source_config(prov, s.get("config", {}))
            cur = conn.execute(
                """
                INSERT INTO source_channels (name, provider, config_json, namespace_id, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{s.get('name', '导入源')}",
                    prov,
                    json.dumps(clean_cfg, ensure_ascii=False),
                    s.get("namespace_id", ""),
                    1 if s.get("is_active", True) else 0,
                    now,
                    now,
                ),
            )
            if "id" in s:
                src_id_map[int(s["id"])] = cur.lastrowid
            imported["sources"] += 1

        for n in snap.get("notification_channels", []):
            cur = conn.execute(
                """
                INSERT INTO notification_channels (name, type, config_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{n.get('name', '导入通知')}",
                    n.get("type", "dingtalk"),
                    json.dumps(n.get("config", {}), ensure_ascii=False),
                    1 if n.get("is_active", True) else 0,
                    now,
                    now,
                ),
            )
            if "id" in n:
                notif_id_map[int(n["id"])] = cur.lastrowid
            imported["notifications"] += 1

        for t in snap.get("tasks", []):
            old_sid = int(t.get("source_channel_id", 0))
            new_sid = src_id_map.get(old_sid)
            if not new_sid:
                continue
            old_nids = t.get("notification_channel_ids", [])
            new_nids = [notif_id_map[int(i)] for i in old_nids if int(i) in notif_id_map]
            conn.execute(
                """
                INSERT INTO tasks (
                    name, source_channel_id, gb_id, schedule_mode, interval_minutes, daily_time,
                    cron_expression, is_enabled, notification_channel_ids_json,
                    notify_offline, notify_online, fail_threshold, cooldown_minutes,
                    quiet_hours_enabled, quiet_start, quiet_end, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    t.get("name", "导入任务"),
                    new_sid,
                    t.get("gb_id", ""),
                    t.get("schedule_mode", "interval"),
                    int(t.get("interval_minutes", 5)),
                    t.get("daily_time", "09:00"),
                    t.get("cron_expression", "*/5 * * * *"),
                    1 if t.get("is_enabled", True) else 0,
                    json.dumps(new_nids),
                    1 if t.get("notify_offline", True) else 0,
                    1 if t.get("notify_online", True) else 0,
                    int(t.get("fail_threshold", 2)),
                    int(t.get("cooldown_minutes", 60)),
                    1 if t.get("quiet_hours_enabled", False) else 0,
                    t.get("quiet_start", "23:00"),
                    t.get("quiet_end", "07:00"),
                    now,
                    now,
                ),
            )
            imported["tasks"] += 1

    record_self_heal_event("config_restore", f"已导入配置备份：{imported}")
    return {
        "message": f"恢复成功！已导入 {imported['sources']} 个监控源、{imported['notifications']} 个通知渠道、{imported['tasks']} 个监控任务。",
        "imported": imported,
    }
