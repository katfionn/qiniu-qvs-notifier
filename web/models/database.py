"""Database models for v2.0 - separated into data.db and logs.db"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

# 数据目录配置（支持环境变量自定义）
DATA_DIR = Path(os.getenv('QVS_DATA_DIR', Path(__file__).resolve().parents[2] / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 两个独立的数据库
DATA_DB_PATH = DATA_DIR / "data.db"
LOGS_DB_PATH = DATA_DIR / "logs.db"

# 账号体系数据库（users, tasks, channels, settings）
DataBase = declarative_base()
data_engine = create_engine(f"sqlite:///{DATA_DB_PATH}", echo=False)
DataSession = sessionmaker(bind=data_engine)

# 日志数据库（task_logs, notification_logs）
LogsBase = declarative_base()
logs_engine = create_engine(f"sqlite:///{LOGS_DB_PATH}", echo=False)
LogsSession = sessionmaker(bind=logs_engine)


# ==================== 账号体系数据库表 ====================

class User(DataBase):
    """用户表（仅 Web UI 使用）"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash
    role = Column(String(20), nullable=False, default="user")  # admin/user
    is_first_admin = Column(Boolean, default=False)  # 首个管理员不可删除
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SourceChannel(DataBase):
    """监听渠道表（数据来源配置）"""
    __tablename__ = "source_channels"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # 渠道名称
    provider = Column(String(50), nullable=False)  # 服务商类型：qiniu/custom
    config = Column(Text, nullable=False)  # JSON 格式配置
    namespace_id = Column(String(100))  # 七牛专用字段
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tasks = relationship("Task", back_populates="source_channel")

    def get_config(self) -> dict[str, Any]:
        """解析配置 JSON"""
        return json.loads(self.config) if self.config else {}

    def set_config(self, config_dict: dict[str, Any]) -> None:
        """设置配置 JSON"""
        self.config = json.dumps(config_dict, ensure_ascii=False)


class NotificationChannel(DataBase):
    """通知渠道表"""
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # 渠道名称
    type = Column(String(50), nullable=False)  # ntfy/webhook
    config = Column(Text, nullable=False)  # JSON 格式配置
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_config(self) -> dict[str, Any]:
        return json.loads(self.config) if self.config else {}

    def set_config(self, config_dict: dict[str, Any]) -> None:
        self.config = json.dumps(config_dict, ensure_ascii=False)


class Task(DataBase):
    """任务表"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    source_channel_id = Column(Integer, ForeignKey("source_channels.id"), nullable=False)
    gb_id = Column(String(100))  # 国标 ID（可选）
    cron_expression = Column(String(100), nullable=False)  # cron 表达式
    is_enabled = Column(Boolean, default=True)
    notification_channels = Column(Text)  # JSON 数组：[1, 2, 3] 通知渠道 ID 列表
    device_group_id = Column(Integer, ForeignKey("device_groups.id"))  # 设备分组（可选）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    source_channel = relationship("SourceChannel", back_populates="tasks")
    device_group = relationship("DeviceGroup", back_populates="tasks")

    def get_notification_channels(self) -> list[int]:
        """获取通知渠道 ID 列表"""
        return json.loads(self.notification_channels) if self.notification_channels else []

    def set_notification_channels(self, channel_ids: list[int]) -> None:
        """设置通知渠道 ID 列表"""
        self.notification_channels = json.dumps(channel_ids)


class DeviceGroup(DataBase):
    """设备分组表"""
    __tablename__ = "device_groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    device_ids = Column(Text)  # JSON 数组：["device1", "device2"]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tasks = relationship("Task", back_populates="device_group")

    def get_device_ids(self) -> list[str]:
        return json.loads(self.device_ids) if self.device_ids else []

    def set_device_ids(self, ids: list[str]) -> None:
        self.device_ids = json.dumps(ids)


class SystemSetting(DataBase):
    """系统设置表（Key-Value 存储）"""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ==================== 日志数据库表 ====================

class TaskLog(LogsBase):
    """任务执行日志表"""
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, nullable=False)
    task_name = Column(String(100))
    status = Column(String(20), nullable=False)  # success/failed/running
    offline_count = Column(Integer, default=0)
    online_count = Column(Integer, default=0)
    message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)


class NotificationLog(LogsBase):
    """通知发送日志表"""
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True)
    task_log_id = Column(Integer, ForeignKey("task_logs.id"))
    channel_id = Column(Integer)
    channel_name = Column(String(100))
    status = Column(String(20), nullable=False)  # sent/failed
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 数据库初始化 ====================

def init_databases() -> None:
    """初始化两个数据库"""
    DataBase.metadata.create_all(data_engine)
    LogsBase.metadata.create_all(logs_engine)


def is_first_run() -> bool:
    """检查是否首次运行（是否存在用户）"""
    # 先检查数据库文件是否存在
    if not DATA_DB_PATH.exists():
        return True

    try:
        with DataSession() as session:
            return session.query(User).count() == 0
    except Exception:
        # 表不存在，说明是首次运行
        return True


def create_first_admin(username: str, password: str) -> User:
    """创建首个管理员账号"""
    import bcrypt

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with DataSession() as session:
        admin = User(
            username=username,
            password_hash=password_hash,
            role="admin",
            is_first_admin=True
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return admin


def get_admin_info() -> dict[str, Any] | None:
    """获取首个管理员信息"""
    with DataSession() as session:
        admin = session.query(User).filter_by(is_first_admin=True).first()
        if admin:
            return {
                "id": admin.id,
                "username": admin.username,
                "created_at": admin.created_at.isoformat()
            }
        return None


def reset_admin_password(new_password: str) -> bool:
    """重置首个管理员密码"""
    import bcrypt

    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

    with DataSession() as session:
        admin = session.query(User).filter_by(is_first_admin=True).first()
        if admin:
            admin.password_hash = password_hash
            admin.updated_at = datetime.utcnow()
            session.commit()
            return True
        return False
