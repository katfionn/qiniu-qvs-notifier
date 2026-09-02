from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import yaml
import os

CONFIG_PATH = "config/settings.yaml"

class WebhookConfig(BaseModel):
    url: str = Field(default="{{webhook_url}}", description="Webhook 地址")
    auth_type: str = Field(default="none", description="鉴权方式: none, sign, keyword")
    secret: str = Field(default="{{webhook_secret}}", description="加签密钥 (用于钉钉/企微等)")
    keyword: str = Field(default="{{webhook_keyword}}", description="自定义关键词 (用于钉钉等关键词校验)")
    # 使用字符串保存 JSON，方便前端渲染为文本域
    custom_body: str = Field(
        default='{"msgtype": "text", "text": {"content": "{message}"}}',
        description="自定义 Body (JSON格式), 可使用 {message}, {device}, {state} 变量"
    )
    template: str = Field(default="[{device} 设备{state}]", description="告警消息文本模板")

class QiniuConfig(BaseModel):
    access_key: str = Field(default="{{qiniu_access_key}}", description="七牛云 AK")
    secret_key: str = Field(default="{{qiniu_secret_key}}", description="七牛云 SK")

class ScheduleConfig(BaseModel):
    mode: str = Field(default="loop", description="调度模式: once (单次), loop (轮询)")
    interval_seconds: int = Field(default=60, description="轮询间隔 (秒)")

class AlertConfig(BaseModel):
    notify_online: bool = Field(default=False, description="上线时是否通知")
    notify_offline: bool = Field(default=True, description="下线时是否通知")

class UIConfig(BaseModel):
    language: str = Field(default="", description="Explicit UI language; empty uses system language")

class AppConfig(BaseModel):
    qiniu: QiniuConfig = QiniuConfig()
    webhook: WebhookConfig = WebhookConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    alert: AlertConfig = AlertConfig()
    ui: UIConfig = UIConfig()

def load_config() -> AppConfig:
    if not os.path.exists(CONFIG_PATH):
        return AppConfig()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return AppConfig(
        qiniu=QiniuConfig(**data.get("qiniu", {})),
        webhook=WebhookConfig(**data.get("webhook", {})),
        schedule=ScheduleConfig(**data.get("schedule", {})),
        alert=AlertConfig(**data.get("alert", {})),
        ui=UIConfig(**data.get("ui", {}))
    )

def save_config(config: AppConfig):
    if not os.path.exists("config"):
        os.makedirs("config")

    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except:
            data = {}

    data["qiniu"] = config.qiniu.model_dump()
    data["webhook"] = config.webhook.model_dump()
    data["schedule"] = config.schedule.model_dump()
    data["alert"] = config.alert.model_dump()
    data["ui"] = config.ui.model_dump()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
