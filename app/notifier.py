"""多渠道告警通知引擎：内置钉钉(加签/关键词)、企业微信、飞书(加签)、NTFY、通用 Webhook 与自动重试"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx


def _dingtalk_signed_url(url: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = quote_plus(base64.b64encode(hmac_code))
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}timestamp={timestamp}&sign={sign}"


def _feishu_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        b"",
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


async def _post_with_retry(
    url: str,
    *,
    json_body: Any = None,
    content_bytes: bytes | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
) -> httpx.Response:
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=12.0) as client:
        for attempt in range(1, retries + 1):
            try:
                if content_bytes is not None:
                    resp = await client.post(url, content=content_bytes, headers=headers)
                else:
                    resp = await client.post(url, json=json_body, headers=headers)
                if resp.status_code >= 500 and attempt < retries:
                    await asyncio.sleep(0.8 * attempt)
                    continue
                return resp
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < retries:
                    await asyncio.sleep(0.8 * attempt)
                    continue
                raise RuntimeError(f"无法连接到通知服务器（网络超时或地址不可达）：{exc}") from exc
    raise RuntimeError(f"发送通知失败：{last_exc}")


async def send_notification(
    channel_type: str,
    config: dict[str, Any],
    title: str,
    message: str,
    event_type: str = "alert",
) -> dict[str, Any]:
    """
    统一发送告警通知。
    返回: {"ok": bool, "message": str, "error": str}
    """
    ctype = (channel_type or "").strip().lower()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if ctype == "dingtalk":
            url = str(config.get("url") or "").strip()
            if not url:
                return {"ok": False, "message": "未填写钉钉机器人 Webhook 地址", "error": "missing url"}
            secret = str(config.get("secret") or "").strip()
            keyword = str(config.get("keyword") or "").strip()
            body_text = message
            if keyword and keyword not in body_text and keyword not in title:
                body_text = f"[{keyword}]\n{body_text}"
            final_url = _dingtalk_signed_url(url, secret) if secret else url
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"### {title}\n\n{body_text}\n\n> 时间：{now_str}",
                },
            }
            resp = await _post_with_retry(final_url, json_body=payload)
            if resp.status_code != 200:
                return {"ok": False, "message": f"钉钉接口 HTTP {resp.status_code}", "error": resp.text[:200]}
            data = resp.json()
            if data.get("errcode") == 0:
                return {"ok": True, "message": "钉钉机器人推送成功", "error": ""}
            errmsg = data.get("errmsg", "未知错误")
            hint = ""
            if "keywords" in errmsg.lower():
                hint = "（提示：请在通知渠道中填写钉钉机器人设置的自定义关键词）"
            elif "sign" in errmsg.lower():
                hint = "（提示：请检查钉钉加签 Secret 是否以 SEC 开头且复制完整）"
            return {"ok": False, "message": f"钉钉拒收：{errmsg}{hint}", "error": json.dumps(data, ensure_ascii=False)}

        if ctype == "wecom":
            url = str(config.get("url") or "").strip()
            if not url:
                return {"ok": False, "message": "未填写企业微信机器人 Webhook 地址", "error": "missing url"}
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {title}\n{message}\n> 时间：{now_str}",
                },
            }
            resp = await _post_with_retry(url, json_body=payload)
            if resp.status_code != 200:
                return {"ok": False, "message": f"企业微信接口 HTTP {resp.status_code}", "error": resp.text[:200]}
            data = resp.json()
            if data.get("errcode") == 0:
                return {"ok": True, "message": "企业微信机器人推送成功", "error": ""}
            return {"ok": False, "message": f"企业微信拒收：{data.get('errmsg', '未知错误')}", "error": json.dumps(data, ensure_ascii=False)}

        if ctype == "feishu":
            url = str(config.get("url") or "").strip()
            if not url:
                return {"ok": False, "message": "未填写飞书机器人 Webhook 地址", "error": "missing url"}
            secret = str(config.get("secret") or "").strip()
            payload: dict[str, Any] = {
                "msg_type": "text",
                "content": {"text": f"{title}\n\n{message}\n\n时间：{now_str}"},
            }
            if secret:
                ts = str(int(time.time()))
                payload["timestamp"] = ts
                payload["sign"] = _feishu_sign(ts, secret)
            resp = await _post_with_retry(url, json_body=payload)
            if resp.status_code != 200:
                return {"ok": False, "message": f"飞书接口 HTTP {resp.status_code}", "error": resp.text[:200]}
            data = resp.json()
            if data.get("code") == 0 or data.get("StatusCode") == 0:
                return {"ok": True, "message": "飞书机器人推送成功", "error": ""}
            return {"ok": False, "message": f"飞书拒收：{data.get('msg') or data.get('StatusMessage') or '未知错误'}", "error": json.dumps(data, ensure_ascii=False)}

        if ctype == "ntfy":
            server = str(config.get("server") or "https://ntfy.sh").strip().rstrip("/")
            topic = str(config.get("topic") or "").strip().lstrip("/")
            if not topic:
                return {"ok": False, "message": "未填写 NTFY 订阅主题 (Topic)", "error": "missing topic"}
            target_url = f"{server}/{topic}"
            headers: dict[str, str] = {
                "Priority": "high" if event_type == "alert" else "default",
                "Tags": "warning" if event_type == "alert" else "white_check_mark",
                "Content-Type": "text/plain; charset=utf-8",
            }
            # HTTP header 仅安全支持 ASCII；含中文标题时合并进正文顶部，避免编码报错
            if all(ord(ch) < 128 for ch in title):
                headers["Title"] = title
                body_str = f"{message}\n\n时间：{now_str}"
            else:
                headers["Title"] = "QVS Alert" if event_type == "alert" else "QVS Recovery"
                body_str = f"【{title}】\n{message}\n\n时间：{now_str}"
            token = str(config.get("token") or "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            resp = await _post_with_retry(target_url, content_bytes=body_str.encode("utf-8"), headers=headers)
            if 200 <= resp.status_code < 300:
                return {"ok": True, "message": "NTFY 推送成功", "error": ""}
            return {"ok": False, "message": f"NTFY 返回错误 (HTTP {resp.status_code})", "error": resp.text[:200]}

        if ctype == "webhook":
            url = str(config.get("url") or "").strip()
            if not url:
                return {"ok": False, "message": "未填写自定义 Webhook 地址", "error": "missing url"}
            headers = {"Content-Type": "application/json"}
            custom_headers_raw = str(config.get("headers") or "").strip()
            if custom_headers_raw:
                try:
                    parsed_h = json.loads(custom_headers_raw)
                    if isinstance(parsed_h, dict):
                        headers.update({str(k): str(v) for k, v in parsed_h.items()})
                except json.JSONDecodeError:
                    return {"ok": False, "message": "自定义请求头不是合法的 JSON 格式", "error": "invalid headers json"}

            template_raw = str(config.get("custom_body") or "").strip()
            if template_raw:
                # 使用 json.dumps 去掉首尾引号，确保换行与双引号安全转义
                esc_title = json.dumps(title, ensure_ascii=False)[1:-1]
                esc_msg = json.dumps(message, ensure_ascii=False)[1:-1]
                rendered = (
                    template_raw
                    .replace("{title}", esc_title)
                    .replace("{message}", esc_msg)
                    .replace("{timestamp}", now_str)
                    .replace("{event_type}", event_type)
                )
                try:
                    payload_obj = json.loads(rendered)
                except json.JSONDecodeError as exc:
                    return {"ok": False, "message": f"自定义 JSON 模板格式有误：{exc}", "error": str(exc)}
            else:
                payload_obj = {
                    "title": title,
                    "message": message,
                    "event_type": event_type,
                    "timestamp": now_str,
                }

            resp = await _post_with_retry(url, json_body=payload_obj, headers=headers)
            if 200 <= resp.status_code < 300:
                return {"ok": True, "message": f"自定义 Webhook 推送成功 (HTTP {resp.status_code})", "error": ""}
            return {"ok": False, "message": f"自定义 Webhook 返回错误 (HTTP {resp.status_code})", "error": resp.text[:200]}

        return {"ok": False, "message": f"暂不支持的通知渠道类型：{ctype}", "error": "unsupported channel type"}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "error": str(exc)}


async def send_test_notification(channel_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """一键发送测试消息"""
    return await send_notification(
        channel_type=channel_type,
        config=config,
        title="七牛 QVS 监控告警中心 · 测试通知",
        message="恭喜！如果您看到这条消息，说明告警通知渠道已配置成功，可以正常接收设备离线与恢复通知。",
        event_type="test",
    )
