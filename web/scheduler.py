"""Task scheduler using APScheduler with cron expressions"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from web.models.database import (
    DataSession,
    LogsSession,
    NotificationChannel,
    NotificationLog,
    SourceChannel,
    Task,
    TaskLog,
)

logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler: AsyncIOScheduler | None = None


# ==================== 服务商适配器 ====================

async def fetch_qiniu_devices(channel: SourceChannel, gb_id: str | None = None) -> dict:
    """获取七牛设备状态"""
    from qiniu import Auth

    config = channel.get_config()
    access_key = config.get("access_key")
    secret_key = config.get("secret_key")
    namespace_id = channel.namespace_id

    if not all([access_key, secret_key, namespace_id]):
        raise ValueError("七牛配置不完整")

    auth = Auth(access_key, secret_key)
    url = f"https://qvs.qiniuapi.com/v1/namespaces/{namespace_id}/devices"

    if gb_id:
        url += f"?gbId={gb_id}"

    token = auth.token_of_request(url, "GET", "application/json")

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={"Authorization": f"Qiniu {token}"}
        ) as response:
            if response.status != 200:
                raise Exception(f"七牛 API 错误: {response.status}")

            data = await response.json()
            return data


async def check_devices_status(channel: SourceChannel, gb_id: str | None = None) -> dict:
    """检查设备状态（服务商适配层）"""
    if channel.provider == "qiniu":
        return await fetch_qiniu_devices(channel, gb_id)
    elif channel.provider == "custom":
        # TODO: 自定义服务商实现
        raise NotImplementedError("自定义服务商功能开发中")
    else:
        raise ValueError(f"不支持的服务商: {channel.provider}")


# ==================== 通知发送 ====================

async def send_ntfy_notification(config: dict, title: str, message: str) -> bool:
    """发送 NTFY 通知"""
    server = config.get("server", "https://ntfy.sh")
    topic = config.get("topic")

    if not topic:
        logger.error("NTFY topic 未配置")
        return False

    url = f"{server}/{topic}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": "high"
                }
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"NTFY 发送失败: {e}")
            return False


async def send_webhook_notification(config: dict, title: str, message: str) -> bool:
    """发送 Webhook 通知"""
    url = config.get("url")

    if not url:
        logger.error("Webhook URL 未配置")
        return False

    payload = {
        "title": title,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                return response.status in [200, 201, 204]
        except Exception as e:
            logger.error(f"Webhook 发送失败: {e}")
            return False


async def send_notification(channel: NotificationChannel, title: str, message: str, task_log_id: int) -> None:
    """发送通知并记录日志"""
    config = channel.get_config()
    success = False

    try:
        if channel.type == "ntfy":
            success = await send_ntfy_notification(config, title, message)
        elif channel.type == "webhook":
            success = await send_webhook_notification(config, title, message)
        else:
            logger.error(f"不支持的通知类型: {channel.type}")

        # 记录通知日志
        with LogsSession() as session:
            log = NotificationLog(
                task_log_id=task_log_id,
                channel_id=channel.id,
                channel_name=channel.name,
                status="sent" if success else "failed",
                message=message
            )
            session.add(log)
            session.commit()

    except Exception as e:
        logger.error(f"通知发送异常: {e}")

        with LogsSession() as session:
            log = NotificationLog(
                task_log_id=task_log_id,
                channel_id=channel.id,
                channel_name=channel.name,
                status="failed",
                message=str(e)
            )
            session.add(log)
            session.commit()


# ==================== 任务执行 ====================

async def execute_task(task_id: int) -> None:
    """执行单个任务"""
    logger.info(f"开始执行任务 ID: {task_id}")

    with DataSession() as session:
        task = session.query(Task).get(task_id)

        if not task or not task.is_enabled:
            logger.warning(f"任务 {task_id} 不存在或已禁用")
            return

        # 创建任务执行日志
        task_log = TaskLog(
            task_id=task.id,
            task_name=task.name,
            status="running",
            started_at=datetime.utcnow()
        )

        with LogsSession() as log_session:
            log_session.add(task_log)
            log_session.commit()
            log_session.refresh(task_log)
            task_log_id = task_log.id

        try:
            # 获取设备状态
            result = await check_devices_status(task.source_channel, task.gb_id)

            # 统计在线/离线设备
            devices = result.get("items", [])
            offline_devices = [d for d in devices if d.get("state") == 0]
            online_devices = [d for d in devices if d.get("state") == 1]

            offline_count = len(offline_devices)
            online_count = len(online_devices)

            logger.info(f"任务 {task.name}: 在线 {online_count}, 离线 {offline_count}")

            # 更新任务日志
            with LogsSession() as log_session:
                task_log = log_session.query(TaskLog).get(task_log_id)
                task_log.status = "success"
                task_log.offline_count = offline_count
                task_log.online_count = online_count
                task_log.finished_at = datetime.utcnow()
                log_session.commit()

            # 如果有离线设备，发送通知
            if offline_count > 0:
                notification_channel_ids = task.get_notification_channels()

                if notification_channel_ids:
                    channels = session.query(NotificationChannel).filter(
                        NotificationChannel.id.in_(notification_channel_ids),
                        NotificationChannel.is_active == True
                    ).all()

                    title = f"设备离线告警: {task.name}"
                    message = f"发现 {offline_count} 个离线设备\n"

                    for device in offline_devices[:5]:  # 最多显示 5 个
                        device_name = device.get("name", device.get("gbId", "未知"))
                        message += f"\n- {device_name}"

                    if offline_count > 5:
                        message += f"\n... 还有 {offline_count - 5} 个设备"

                    # 并发发送通知
                    await asyncio.gather(*[
                        send_notification(channel, title, message, task_log_id)
                        for channel in channels
                    ])

        except Exception as e:
            logger.error(f"任务执行失败: {e}")

            # 更新任务日志为失败
            with LogsSession() as log_session:
                task_log = log_session.query(TaskLog).get(task_log_id)
                task_log.status = "failed"
                task_log.message = str(e)
                task_log.finished_at = datetime.utcnow()
                log_session.commit()


# ==================== 调度器管理 ====================

def start_scheduler() -> AsyncIOScheduler:
    """启动调度器"""
    global scheduler

    if scheduler is not None:
        logger.warning("调度器已在运行")
        return scheduler

    scheduler = AsyncIOScheduler()

    # 加载所有启用的任务
    with DataSession() as session:
        tasks = session.query(Task).filter_by(is_enabled=True).all()

        for task in tasks:
            try:
                trigger = CronTrigger.from_crontab(task.cron_expression)
                scheduler.add_job(
                    execute_task,
                    trigger=trigger,
                    args=[task.id],
                    id=f"task_{task.id}",
                    name=task.name,
                    replace_existing=True
                )
                logger.info(f"已加载任务: {task.name} (Cron: {task.cron_expression})")
            except Exception as e:
                logger.error(f"加载任务 {task.name} 失败: {e}")

    scheduler.start()
    logger.info("调度器已启动")
    return scheduler


def stop_scheduler() -> None:
    """停止调度器"""
    global scheduler

    if scheduler is None:
        logger.warning("调度器未运行")
        return

    scheduler.shutdown()
    scheduler = None
    logger.info("调度器已停止")


def reload_scheduler() -> None:
    """重新加载调度器（重新读取任务配置）"""
    logger.info("重新加载调度器...")

    if scheduler is None:
        start_scheduler()
        return

    # 移除所有现有任务
    scheduler.remove_all_jobs()

    # 重新加载任务
    with DataSession() as session:
        tasks = session.query(Task).filter_by(is_enabled=True).all()

        for task in tasks:
            try:
                trigger = CronTrigger.from_crontab(task.cron_expression)
                scheduler.add_job(
                    execute_task,
                    trigger=trigger,
                    args=[task.id],
                    id=f"task_{task.id}",
                    name=task.name,
                    replace_existing=True
                )
                logger.info(f"已重新加载任务: {task.name}")
            except Exception as e:
                logger.error(f"加载任务 {task.name} 失败: {e}")

    logger.info("调度器重新加载完成")


def get_scheduler_status() -> dict:
    """获取调度器状态"""
    if scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })

    return {
        "running": True,
        "jobs": jobs
    }
