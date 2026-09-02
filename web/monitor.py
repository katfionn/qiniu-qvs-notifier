import asyncio
import aiohttp
import sqlite3
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import logging
from qiniu import QiniuMacAuth
from web.models.settings import load_config
from web.models.device import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('check_online.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MonitorDaemon")

def generate_dingtalk_sign(secret: str):
    """生成钉钉/企微的加签参数"""
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign

async def send_webhook_message(session: aiohttp.ClientSession, config, state_cn: str, device_name: str):
    webhook_cfg = config.webhook
    if not webhook_cfg.url:
        return

    # 1. 组装消息文本
    message = webhook_cfg.template.replace("{device}", device_name).replace("{state}", state_cn)

    # 如果启用了关键字鉴权，需确保 keyword 包含在 message 中
    if webhook_cfg.auth_type == 'keyword' and webhook_cfg.keyword:
        if webhook_cfg.keyword not in message:
            message = f"{message} {webhook_cfg.keyword}"

    # 2. 解析和替换 JSON Body
    try:
        body_str = webhook_cfg.custom_body.replace("{device}", device_name)\
                                          .replace("{state}", state_cn)\
                                          .replace("{message}", message)
        # 处理可能因为转义带来的 JSON 解析问题，这里要求用户在配置时不要写破坏 json 结构的引号
        data = json.loads(body_str)
    except Exception as e:
        logger.error(f"解析自定义 JSON Body 失败: {e}. 请检查 Web 后台配置。")
        return

    # 3. 处理 URL 签名
    url = webhook_cfg.url
    if webhook_cfg.auth_type == 'sign' and webhook_cfg.secret:
        timestamp, sign = generate_dingtalk_sign(webhook_cfg.secret)
        separator = '&' if '?' in url else '?'
        url = f"{url}{separator}timestamp={timestamp}&sign={sign}"

    # 4. 发送请求
    headers = {'Content-Type': 'application/json;charset=utf-8'}
    try:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                logger.info(f"告警推送成功: [{device_name}] -> {state_cn}")
            else:
                resp_text = await response.text()
                logger.error(f"告警推送失败, HTTP {response.status}: {resp_text}")
    except Exception as e:
        logger.error(f"发送告警消息发生网络异常: {e}")

async def check_device_state(session: aiohttp.ClientSession, access_key: str, secret_key: str, namespace_id: str, gb_id: str):
    auth = QiniuMacAuth(access_key, secret_key)
    url = f"http://qvs.qiniuapi.com/v1/namespaces/{namespace_id}/devices/{gb_id}"
    token = auth.token_of_request('GET', url.replace("http://qvs.qiniuapi.com", ""), "", "")
    headers = {"Authorization": f"Qiniu {token}"}

    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("state", "unknown")
            else:
                return "error"
    except Exception as e:
        return "error"

def update_device_last_state(device_id: int, state: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE devices SET last_state = ? WHERE id = ?', (state, device_id))
        conn.commit()
    except Exception as e:
        logger.error(f"更新数据库状态失败: {e}")
    finally:
        conn.close()

async def process_device(session: aiohttp.ClientSession, config, device):
    device_id = device['id']
    namespace_id = device['namespace_id']
    gb_id = device['gb_id']
    name = device['name']
    last_state = device['last_state']

    current_state = await check_device_state(
        session, config.qiniu.access_key, config.qiniu.secret_key, namespace_id, gb_id
    )

    if current_state in ["unknown", "error"]:
        return

    if current_state != last_state:
        logger.info(f"状态翻转 | 设备: [{name}] | {last_state} -> {current_state}")

        # 判断配置中是否开启了对应状态的通知
        should_notify = False
        state_cn = ""

        if current_state == 'offline' and config.alert.notify_offline:
            should_notify = True
            state_cn = "离线"
        elif current_state == 'online' and config.alert.notify_online:
            should_notify = True
            state_cn = "在线/恢复"

        if should_notify and last_state != "unknown": # 初始化时不发通知
            await send_webhook_message(session, config, state_cn, name)

        update_device_last_state(device_id, current_state)

async def run_inspection_cycle():
    """执行一次完整的巡检生命周期"""
    config = load_config()
    if not config.qiniu.access_key or not config.qiniu.secret_key:
        logger.warning("跳过巡检: AK/SK 未配置。")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        if not cursor.fetchone():
             conn.close()
             return

        cursor.execute('SELECT * FROM devices')
        devices = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        logger.error(f"读取设备列表异常: {e}")
        return

    if not devices:
        return

    logger.info(f"==> 启动本轮巡检，当前共 {len(devices)} 台设备")
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_device(session, config, device) for device in devices]
        await asyncio.gather(*tasks)

async def start_daemon(stop_event=None):
    """常驻后台调度器"""
    logger.info("监控调度守护线程已启动...")
    while not (stop_event and stop_event.is_set()):
        config = load_config()

        # 不论是 once 还是 loop，都先执行一次
        await run_inspection_cycle()

        if config.schedule.mode == 'once':
            logger.info("配置为单次执行 (Once)，后台任务退出休眠。如果需再次执行请更改配置或重启。")
            break

        # 轮询模式，读取间隔并等待
        interval = max(10, config.schedule.interval_seconds) # 至少10秒保护
        logger.info(f"进入休眠，等待 {interval} 秒后进行下一轮巡检...")
        if stop_event:
            await asyncio.to_thread(stop_event.wait, interval)
        else:
            await asyncio.sleep(interval)

if __name__ == "__main__":
    asyncio.run(start_daemon())
