"""FastAPI v2.0 - Complete RESTful API with JWT authentication"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web.auth import (
    authenticate_user,
    create_access_token,
    require_admin,
    require_auth,
)
from web.models.database import (
    DataSession,
    NotificationChannel,
    SourceChannel,
    SystemSetting,
    Task,
    User,
    init_databases,
)
from web.scheduler import (
    get_scheduler_status,
    reload_scheduler,
    start_scheduler,
    stop_scheduler,
)

app = FastAPI(title="Qiniu QVS Notifier v2.0", version="2.0.0")


# ==================== Pydantic Models ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class TaskCreate(BaseModel):
    name: str
    source_channel_id: int
    cron_expression: str
    gb_id: str | None = None
    notification_channels: list[int] = []
    is_enabled: bool = True


class TaskUpdate(BaseModel):
    name: str | None = None
    source_channel_id: int | None = None
    cron_expression: str | None = None
    gb_id: str | None = None
    notification_channels: list[int] | None = None
    is_enabled: bool | None = None


class SourceChannelCreate(BaseModel):
    name: str
    provider: str
    config: dict
    namespace_id: str | None = None


class NotificationChannelCreate(BaseModel):
    name: str
    type: str
    config: dict


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


# ==================== Startup ====================

@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库和调度器"""
    init_databases()
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时停止调度器"""
    stop_scheduler()


# ==================== Authentication ====================

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """用户登录"""
    user = authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(days=7)
    )

    return LoginResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
    )


@app.get("/api/auth/me")
async def get_current_user_info(current_user: User = Depends(require_auth)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "created_at": current_user.created_at.isoformat()
    }


# ==================== Users Management (Admin Only) ====================

@app.get("/api/users")
async def list_users(current_user: User = Depends(require_admin)):
    """获取用户列表（管理员）"""
    with DataSession() as session:
        users = session.query(User).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "is_first_admin": u.is_first_admin,
                "created_at": u.created_at.isoformat()
            }
            for u in users
        ]


@app.post("/api/users")
async def create_user(payload: UserCreate, current_user: User = Depends(require_admin)):
    """创建用户（管理员）"""
    from web.auth import get_password_hash

    with DataSession() as session:
        # 检查用户名是否已存在
        existing = session.query(User).filter_by(username=payload.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="用户名已存在")

        user = User(
            username=payload.username,
            password_hash=get_password_hash(payload.password),
            role=payload.role
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        return {"id": user.id, "username": user.username, "role": user.role}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(require_admin)):
    """删除用户（管理员）"""
    with DataSession() as session:
        user = session.query(User).get(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if user.is_first_admin:
            raise HTTPException(status_code=403, detail="无法删除首个管理员")

        session.delete(user)
        session.commit()

        return {"status": "success"}


# ==================== Tasks ====================

@app.get("/api/tasks")
async def list_tasks(current_user: User = Depends(require_auth)):
    """获取任务列表"""
    with DataSession() as session:
        tasks = session.query(Task).all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "source_channel_id": t.source_channel_id,
                "source_channel_name": t.source_channel.name if t.source_channel else None,
                "gb_id": t.gb_id,
                "cron_expression": t.cron_expression,
                "is_enabled": t.is_enabled,
                "notification_channels": t.get_notification_channels(),
                "created_at": t.created_at.isoformat()
            }
            for t in tasks
        ]


@app.post("/api/tasks")
async def create_task(payload: TaskCreate, current_user: User = Depends(require_auth)):
    """创建任务"""
    with DataSession() as session:
        task = Task(
            name=payload.name,
            source_channel_id=payload.source_channel_id,
            cron_expression=payload.cron_expression,
            gb_id=payload.gb_id,
            is_enabled=payload.is_enabled
        )
        task.set_notification_channels(payload.notification_channels)
        session.add(task)
        session.commit()
        session.refresh(task)

        return {"id": task.id, "name": task.name}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int, current_user: User = Depends(require_auth)):
    """获取任务详情"""
    with DataSession() as session:
        task = session.query(Task).get(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "id": task.id,
            "name": task.name,
            "source_channel_id": task.source_channel_id,
            "gb_id": task.gb_id,
            "cron_expression": task.cron_expression,
            "is_enabled": task.is_enabled,
            "notification_channels": task.get_notification_channels(),
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        }


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: int, payload: TaskUpdate, current_user: User = Depends(require_auth)):
    """更新任务"""
    with DataSession() as session:
        task = session.query(Task).get(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if payload.name is not None:
            task.name = payload.name
        if payload.source_channel_id is not None:
            task.source_channel_id = payload.source_channel_id
        if payload.cron_expression is not None:
            task.cron_expression = payload.cron_expression
        if payload.gb_id is not None:
            task.gb_id = payload.gb_id
        if payload.is_enabled is not None:
            task.is_enabled = payload.is_enabled
        if payload.notification_channels is not None:
            task.set_notification_channels(payload.notification_channels)

        task.updated_at = datetime.utcnow()
        session.commit()

        return {"status": "success"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, current_user: User = Depends(require_auth)):
    """删除任务"""
    with DataSession() as session:
        task = session.query(Task).get(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        session.delete(task)
        session.commit()

        return {"status": "success"}


# ==================== Source Channels ====================

@app.get("/api/source-channels")
async def list_source_channels(current_user: User = Depends(require_auth)):
    """获取监听渠道列表"""
    with DataSession() as session:
        channels = session.query(SourceChannel).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "provider": c.provider,
                "namespace_id": c.namespace_id,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat()
            }
            for c in channels
        ]


@app.post("/api/source-channels")
async def create_source_channel(payload: SourceChannelCreate, current_user: User = Depends(require_auth)):
    """创建监听渠道"""
    with DataSession() as session:
        channel = SourceChannel(
            name=payload.name,
            provider=payload.provider,
            namespace_id=payload.namespace_id,
            is_active=True
        )
        channel.set_config(payload.config)
        session.add(channel)
        session.commit()
        session.refresh(channel)

        return {"id": channel.id, "name": channel.name}


@app.delete("/api/source-channels/{channel_id}")
async def delete_source_channel(channel_id: int, current_user: User = Depends(require_auth)):
    """删除监听渠道"""
    with DataSession() as session:
        channel = session.query(SourceChannel).get(channel_id)

        if not channel:
            raise HTTPException(status_code=404, detail="渠道不存在")

        # 检查是否有任务使用此渠道
        task_count = session.query(Task).filter_by(source_channel_id=channel_id).count()
        if task_count > 0:
            raise HTTPException(status_code=400, detail=f"此渠道被 {task_count} 个任务使用，无法删除")

        session.delete(channel)
        session.commit()

        return {"status": "success"}


# ==================== Notification Channels ====================

@app.get("/api/notification-channels")
async def list_notification_channels(current_user: User = Depends(require_auth)):
    """获取通知渠道列表"""
    with DataSession() as session:
        channels = session.query(NotificationChannel).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat()
            }
            for c in channels
        ]


@app.post("/api/notification-channels")
async def create_notification_channel(payload: NotificationChannelCreate, current_user: User = Depends(require_auth)):
    """创建通知渠道"""
    with DataSession() as session:
        channel = NotificationChannel(
            name=payload.name,
            type=payload.type,
            is_active=True
        )
        channel.set_config(payload.config)
        session.add(channel)
        session.commit()
        session.refresh(channel)

        return {"id": channel.id, "name": channel.name}


@app.delete("/api/notification-channels/{channel_id}")
async def delete_notification_channel(channel_id: int, current_user: User = Depends(require_auth)):
    """删除通知渠道"""
    with DataSession() as session:
        channel = session.query(NotificationChannel).get(channel_id)

        if not channel:
            raise HTTPException(status_code=404, detail="渠道不存在")

        session.delete(channel)
        session.commit()

        return {"status": "success"}


# ==================== System Settings ====================

@app.get("/api/settings")
async def get_settings(current_user: User = Depends(require_auth)):
    """获取系统设置"""
    with DataSession() as session:
        settings = session.query(SystemSetting).all()
        return {s.key: s.value for s in settings}


@app.post("/api/settings")
async def update_settings(settings: dict, current_user: User = Depends(require_admin)):
    """更新系统设置（管理员）"""
    with DataSession() as session:
        for key, value in settings.items():
            setting = session.query(SystemSetting).get(key)
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = SystemSetting(key=key, value=value)
                session.add(setting)

        session.commit()

        return {"status": "success"}


# ==================== Scheduler Management ====================

@app.get("/api/scheduler/status")
async def get_scheduler_status_api(current_user: User = Depends(require_auth)):
    """获取调度器状态"""
    return get_scheduler_status()


@app.post("/api/scheduler/reload")
async def reload_scheduler_api(current_user: User = Depends(require_admin)):
    """重新加载调度器（管理员）"""
    reload_scheduler()
    return {"status": "success", "message": "调度器已重新加载"}


@app.post("/api/scheduler/start")
async def start_scheduler_api(current_user: User = Depends(require_admin)):
    """启动调度器（管理员）"""
    start_scheduler()
    return {"status": "success", "message": "调度器已启动"}


@app.post("/api/scheduler/stop")
async def stop_scheduler_api(current_user: User = Depends(require_admin)):
    """停止调度器（管理员）"""
    stop_scheduler()
    return {"status": "success", "message": "调度器已停止"}


# ==================== Static Files & Frontend ====================

@app.get("/")
async def serve_index():
    """服务前端页面"""
    html_path = Path(__file__).parent / "templates" / "index.html"
    return FileResponse(html_path)


# Mount static files if they exist
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")
