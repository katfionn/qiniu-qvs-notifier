"""
多云视频监控源适配引擎（纯 Python 零编译实现）：
1. 七牛云 QVS（QiniuMacAuth V2 签名 + 自动分页 + 单设备接口）
2. 腾讯云 IoT Video / 视联监控（TC3-HMAC-SHA256 V3 签名）
3. 阿里云视频监控 VCS / 直播（POP RPC HMAC-SHA1 签名）
4. 自定义 HTTP / JSON 监控源（适配 WVP-PRO / ZLMediaKit / 海康大华网关等任意 API）
5. 演示模拟源（严格逻辑自洽：0 <= offline <= total）
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode

import httpx

QVS_HOST = "qvs.qiniuapi.com"
QVS_BASE_URL = f"https://{QVS_HOST}"
MAX_PAGES = 50
PAGE_SIZE = 100

PROVIDER_LABELS = {
    "qiniu": "七牛云 QVS",
    "tencent": "腾讯云视联 / IoT Video",
    "aliyun": "阿里云视频监控 VCS",
    "custom": "自定义 HTTP / JSON 接口",
    "demo": "演示模拟源",
}


# ==================== 通用状态归一化与路径取值 ====================

def normalize_device_state(raw_state: Any, online_values: set[str] | None = None) -> str:
    """将各云厂商或自定义接口返回的设备状态统一归一化为 online / offline / unregistered"""
    if isinstance(raw_state, bool):
        return "online" if raw_state else "offline"
    if isinstance(raw_state, (int, float)):
        if online_values:
            return "online" if str(int(raw_state)).lower() in online_values else "offline"
        return "online" if int(raw_state) == 1 else "offline"

    text = str(raw_state if raw_state is not None else "").strip().lower()
    if online_values:
        return "online" if text in online_values else "offline"
    if text in {"online", "1", "true", "connected", "up", "on", "running", "active"}:
        return "online"
    if text in {"notreg", "not_reg", "unregistered", "unreg"}:
        return "unregistered"
    return "offline"


def _extract_by_path(data: Any, path: str) -> Any:
    """支持点号路径取值，如 data.list 或 Response.Devices"""
    if not path or not path.strip():
        return data
    cur = data
    for key in path.strip().split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if 0 <= idx < len(cur) else None
        else:
            return None
    return cur


def clamp_demo_config(config: dict[str, Any]) -> tuple[int, int]:
    """严格保证演示源逻辑自洽：1 <= total <= 50 且 0 <= offline <= total"""
    try:
        total = int(config.get("demo_total_count", 4))
    except (TypeError, ValueError):
        total = 4
    total = max(1, min(50, total))

    try:
        offline = int(config.get("demo_offline_count", 1))
    except (TypeError, ValueError):
        offline = 1
    offline = max(0, min(total, offline))
    return total, offline


# ==================== 1. 七牛云 QVS ====================

def build_qiniu_v2_token(
    access_key: str,
    secret_key: str,
    method: str,
    path: str,
    query: str = "",
    host: str = QVS_HOST,
    content_type: str = "",
    body: str = "",
) -> str:
    """按七牛云官方 QiniuMacAuth V2 规范生成管理凭证"""
    ak = access_key.strip()
    sk = secret_key.strip()
    signing_str = f"{method.upper()} {path}"
    if query:
        signing_str += f"?{query}"
    signing_str += f"\nHost: {host}"
    if content_type:
        signing_str += f"\nContent-Type: {content_type}"
    signing_str += "\n\n"
    if body and content_type and content_type != "application/octet-stream":
        signing_str += body

    digest = hmac.new(sk.encode("utf-8"), signing_str.encode("utf-8"), hashlib.sha1).digest()
    encoded_sign = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{ak}:{encoded_sign}"


def _friendly_qiniu_error(status_code: int, body_text: str) -> str:
    snippet = (body_text or "")[:180].strip()
    if status_code == 401:
        return "七牛云鉴权失败 (401)：请检查 Access Key 和 Secret Key 是否填写正确、有无多余空格。"
    if status_code == 403:
        return "七牛云权限不足 (403)：当前密钥没有访问该 QVS 视频监控空间的权限。"
    if status_code == 404:
        return "未找到目标资源 (404)：请检查 Namespace ID（空间 ID）或国标设备 ID (gbId) 是否正确。"
    if status_code == 429:
        return "七牛云接口请求过于频繁 (429)：请适当调大巡检间隔。"
    if status_code >= 500:
        return f"七牛云服务端暂时异常 ({status_code})，系统将在下次巡检自动重试。"
    return f"七牛云接口返回错误 (HTTP {status_code})：{snippet or '未知错误'}"


async def _qvs_get_with_retry(
    client: httpx.AsyncClient,
    access_key: str,
    secret_key: str,
    path: str,
    params: dict[str, Any] | None = None,
    retries: int = 3,
) -> dict[str, Any]:
    query = urlencode(params) if params else ""
    url = f"{QVS_BASE_URL}{path}" + (f"?{query}" if query else "")
    token = build_qiniu_v2_token(
        access_key=access_key,
        secret_key=secret_key,
        method="GET",
        path=path,
        query=query,
        host=QVS_HOST,
    )
    headers = {"Authorization": f"Qiniu {token}", "Accept": "application/json"}

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, headers=headers, timeout=12.0)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code >= 500 and attempt < retries:
                await asyncio.sleep(0.8 * attempt)
                continue
            raise RuntimeError(_friendly_qiniu_error(resp.status_code, resp.text))
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(0.8 * attempt)
                continue
            raise RuntimeError("连接七牛云 QVS 接口超时或网络不通，请检查服务器外网连接。") from exc

    raise RuntimeError(f"请求七牛云接口失败：{last_err}")


def _parse_qiniu_device_item(item: dict[str, Any]) -> dict[str, Any]:
    gb_id = str(item.get("gbId") or item.get("gb_id") or item.get("id") or "").strip()
    name = str(item.get("name") or item.get("desc") or gb_id or "未命名设备").strip()
    raw_state = item.get("state")
    return {
        "gb_id": gb_id or name,
        "name": name,
        "state": normalize_device_state(raw_state),
        "raw_state": str(raw_state if raw_state is not None else "unknown"),
        "ip": str(item.get("remoteIp") or item.get("ip") or ""),
        "vendor": str(item.get("vendor") or "Qiniu"),
        "channels": int(item.get("channels") or 0),
    }


async def _fetch_qiniu_devices(config: dict[str, Any], namespace_id: str, gb_id: str) -> list[dict[str, Any]]:
    ak = str(config.get("access_key") or "").strip()
    sk = str(config.get("secret_key") or "").strip()
    ns = str(namespace_id or config.get("namespace_id") or "").strip()
    if not ak or not sk:
        raise RuntimeError("请先填写七牛云 Access Key 和 Secret Key。")
    if not ns:
        raise RuntimeError("请先填写七牛云 QVS 空间 ID (Namespace ID)。")

    target_gb = (gb_id or "").strip()
    async with httpx.AsyncClient() as client:
        if target_gb:
            data = await _qvs_get_with_retry(client, ak, sk, f"/v1/namespaces/{ns}/devices/{target_gb}")
            return [_parse_qiniu_device_item(data)]

        all_devices: list[dict[str, Any]] = []
        offset = 0
        for _ in range(MAX_PAGES):
            data = await _qvs_get_with_retry(
                client,
                ak,
                sk,
                f"/v1/namespaces/{ns}/devices",
                params={"line": PAGE_SIZE, "offset": offset},
            )
            items = data.get("items") or []
            if not isinstance(items, list):
                break
            for item in items:
                if isinstance(item, dict):
                    all_devices.append(_parse_qiniu_device_item(item))
            if len(items) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return all_devices


# ==================== 2. 腾讯云视联 / IoT Video (TC3-HMAC-SHA256) ====================

def build_tencent_tc3_headers(
    secret_id: str,
    secret_key: str,
    service: str,
    host: str,
    action: str,
    version: str,
    region: str,
    payload_str: str,
    timestamp: int | None = None,
) -> dict[str, str]:
    """纯 Python 实现腾讯云官方 TC3-HMAC-SHA256 V3 签名"""
    ts = timestamp or int(datetime.now(timezone.utc).timestamp())
    date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"TC3-HMAC-SHA256\n{ts}\n{credential_scope}\n{hashed_canonical}"

    def _hmac_sha256(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac_sha256(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(ts),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }


async def _fetch_tencent_devices(config: dict[str, Any], namespace_id: str, gb_id: str) -> list[dict[str, Any]]:
    secret_id = str(config.get("secret_id") or config.get("access_key") or "").strip()
    secret_key = str(config.get("secret_key") or "").strip()
    if not secret_id or not secret_key:
        raise RuntimeError("请先填写腾讯云 SecretId 和 SecretKey。")

    region = str(config.get("region") or "ap-guangzhou").strip()
    host = str(config.get("endpoint") or "iotvideoindustry.tencentcloudapi.com").strip()
    service = host.split(".")[0]
    action = str(config.get("action") or "DescribeAllDeviceList").strip()
    version = str(config.get("api_version") or "2020-12-01").strip()

    body_dict: dict[str, Any] = {"Offset": 0, "Limit": 100}
    if namespace_id.strip():
        body_dict["GroupId"] = namespace_id.strip()
    if gb_id.strip():
        body_dict["NickName"] = gb_id.strip()
    extra_raw = str(config.get("extra_params") or "").strip()
    if extra_raw:
        try:
            extra_obj = json.loads(extra_raw)
            if isinstance(extra_obj, dict):
                body_dict.update(extra_obj)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"腾讯云附加请求参数不是合法的 JSON：{exc}") from exc

    payload_str = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)
    headers = build_tencent_tc3_headers(
        secret_id=secret_id,
        secret_key=secret_key,
        service=service,
        host=host,
        action=action,
        version=version,
        region=region,
        payload_str=payload_str,
    )

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            resp = await client.post(f"https://{host}/", content=payload_str.encode("utf-8"), headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise RuntimeError(f"连接腾讯云接口 ({host}) 超时或网络不通：{exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"腾讯云接口返回 HTTP {resp.status_code}：{resp.text[:180]}")

    data = resp.json()
    res_body = data.get("Response") or data
    if isinstance(res_body, dict) and "Error" in res_body:
        err = res_body["Error"]
        raise RuntimeError(f"腾讯云接口报错 ({err.get('Code', 'Error')})：{err.get('Message', '未知错误')}")

    raw_items = (
        res_body.get("Devices")
        or res_body.get("DeviceList")
        or res_body.get("Data")
        or res_body.get("Items")
        or []
    )
    if not isinstance(raw_items, list):
        raw_items = []

    devices: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        dev_id = str(item.get("DeviceId") or item.get("DeviceCode") or item.get("Id") or "").strip()
        dev_name = str(item.get("NickName") or item.get("DeviceName") or item.get("Name") or dev_id or "未命名设备").strip()
        raw_st = item.get("Status") if "Status" in item else item.get("Online")
        devices.append(
            {
                "gb_id": dev_id or dev_name,
                "name": dev_name,
                "state": normalize_device_state(raw_st),
                "raw_state": str(raw_st if raw_st is not None else "unknown"),
                "ip": str(item.get("Ip") or item.get("RemoteIp") or ""),
                "vendor": "Tencent",
                "channels": int(item.get("ChannelNum") or 0),
            }
        )
    if gb_id.strip():
        filtered = [d for d in devices if d["gb_id"] == gb_id.strip() or d["name"] == gb_id.strip()]
        if filtered:
            return filtered
    return devices


# ==================== 3. 阿里云视频监控 VCS / 直播 (POP RPC HMAC-SHA1) ====================

def _aliyun_percent_encode(val: Any) -> str:
    return quote(str(val), safe="-_.~")


def build_aliyun_rpc_query(
    access_key_id: str,
    access_key_secret: str,
    action: str,
    version: str,
    extra_params: dict[str, Any] | None = None,
    timestamp: str | None = None,
    nonce: str | None = None,
) -> str:
    """纯 Python 实现阿里云 POP RPC 1.0 HMAC-SHA1 签名"""
    params: dict[str, Any] = {
        "Format": "JSON",
        "Version": version,
        "AccessKeyId": access_key_id.strip(),
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SignatureVersion": "1.0",
        "SignatureNonce": nonce or str(uuid.uuid4()),
        "Action": action,
    }
    if extra_params:
        for k, v in extra_params.items():
            if v is not None and v != "":
                params[str(k)] = v

    sorted_items = sorted(params.items(), key=lambda kv: kv[0])
    canonical_query = "&".join(f"{_aliyun_percent_encode(k)}={_aliyun_percent_encode(v)}" for k, v in sorted_items)
    string_to_sign = f"GET&%2F&{_aliyun_percent_encode(canonical_query)}"
    key = f"{access_key_secret.strip()}&".encode("utf-8")
    sig = base64.b64encode(hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")
    return f"{canonical_query}&Signature={_aliyun_percent_encode(sig)}"


async def _fetch_aliyun_devices(config: dict[str, Any], namespace_id: str, gb_id: str) -> list[dict[str, Any]]:
    ak = str(config.get("access_key_id") or config.get("access_key") or "").strip()
    sk = str(config.get("access_key_secret") or config.get("secret_key") or "").strip()
    if not ak or not sk:
        raise RuntimeError("请先填写阿里云 AccessKey ID 和 AccessKey Secret。")

    endpoint = str(config.get("endpoint") or "vcs.cn-shanghai.aliyuncs.com").strip().replace("https://", "").replace("http://", "").rstrip("/")
    action = str(config.get("action") or "ListDevices").strip()
    version = str(config.get("api_version") or "2020-05-15").strip()

    extra: dict[str, Any] = {"PageNumber": 1, "PageSize": 100}
    if namespace_id.strip():
        extra["CorpId"] = namespace_id.strip()
    if gb_id.strip():
        extra["GbId"] = gb_id.strip()
    extra_raw = str(config.get("extra_params") or "").strip()
    if extra_raw:
        try:
            extra_obj = json.loads(extra_raw)
            if isinstance(extra_obj, dict):
                extra.update(extra_obj)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"阿里云附加请求参数不是合法的 JSON：{exc}") from exc

    query = build_aliyun_rpc_query(ak, sk, action=action, version=version, extra_params=extra)
    url = f"https://{endpoint}/?{query}"

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            resp = await client.get(url)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise RuntimeError(f"连接阿里云接口 ({endpoint}) 超时或网络不通：{exc}") from exc

    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200 or (isinstance(data, dict) and data.get("Code") and str(data.get("Code")) not in {"0", "200", "Success"}):
        code = data.get("Code") or resp.status_code
        msg = data.get("Message") or resp.text[:180]
        raise RuntimeError(f"阿里云接口报错 ({code})：{msg}")

    raw_items = (
        _extract_by_path(data, "Data.Records")
        or _extract_by_path(data, "Data.List")
        or _extract_by_path(data, "Devices")
        or _extract_by_path(data, "Items")
        or []
    )
    if not isinstance(raw_items, list):
        raw_items = []

    devices: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        dev_id = str(item.get("GbId") or item.get("DeviceId") or item.get("Id") or "").strip()
        dev_name = str(item.get("DeviceName") or item.get("Name") or dev_id or "未命名设备").strip()
        raw_st = item.get("Status") if "Status" in item else item.get("DeviceStatus")
        devices.append(
            {
                "gb_id": dev_id or dev_name,
                "name": dev_name,
                "state": normalize_device_state(raw_st),
                "raw_state": str(raw_st if raw_st is not None else "unknown"),
                "ip": str(item.get("DeviceIp") or item.get("Ip") or ""),
                "vendor": "Aliyun",
                "channels": int(item.get("ChannelCount") or 0),
            }
        )
    return devices


# ==================== 4. 自定义 HTTP / JSON 监控源 ====================

async def _fetch_custom_devices(config: dict[str, Any], gb_id: str) -> list[dict[str, Any]]:
    url = str(config.get("url") or "").strip()
    if not url:
        raise RuntimeError("请先填写自定义监控接口 URL。")
    method = str(config.get("method") or "GET").strip().upper()
    if method not in {"GET", "POST"}:
        method = "GET"

    headers: dict[str, str] = {"Accept": "application/json"}
    headers_raw = str(config.get("headers") or "").strip()
    if headers_raw:
        try:
            parsed = json.loads(headers_raw)
            if isinstance(parsed, dict):
                headers.update({str(k): str(v) for k, v in parsed.items()})
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"自定义请求头不是合法的 JSON：{exc}") from exc

    req_body: Any = None
    body_raw = str(config.get("body") or "").strip()
    if method == "POST" and body_raw:
        try:
            req_body = json.loads(body_raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"自定义 POST 请求体不是合法的 JSON：{exc}") from exc

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            if method == "POST":
                resp = await client.post(url, headers=headers, json=req_body)
            else:
                resp = await client.get(url, headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise RuntimeError(f"连接自定义监控接口失败：{exc}") from exc

    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"自定义监控接口返回 HTTP {resp.status_code}：{resp.text[:180]}")

    try:
        payload = resp.json()
    except Exception as exc:
        raise RuntimeError("自定义接口返回的不是有效 JSON 数据。") from exc

    items_path = str(config.get("items_path") or "").strip()
    raw_items = _extract_by_path(payload, items_path) if items_path else payload
    if isinstance(raw_items, dict):
        # 若未填路径且返回对象，自动尝试常见列表键
        for candidate in ("items", "data", "list", "devices", "records"):
            if isinstance(raw_items.get(candidate), list):
                raw_items = raw_items[candidate]
                break
        else:
            raw_items = [raw_items]

    if not isinstance(raw_items, list):
        raise RuntimeError(f"在路径 '{items_path or '<root>'}' 下未找到设备数组列表。")

    id_field = str(config.get("id_field") or "gbId").strip()
    name_field = str(config.get("name_field") or "name").strip()
    state_field = str(config.get("state_field") or "state").strip()
    online_vals_raw = str(config.get("online_values") or "online,1,true,ON").strip()
    online_values = {v.strip().lower() for v in online_vals_raw.split(",") if v.strip()}

    devices: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        dev_id = str(
            _extract_by_path(item, id_field)
            or item.get("id")
            or item.get("deviceId")
            or f"dev-{idx + 1}"
        ).strip()
        dev_name = str(
            _extract_by_path(item, name_field)
            or item.get("name")
            or dev_id
        ).strip()
        raw_st = _extract_by_path(item, state_field)
        devices.append(
            {
                "gb_id": dev_id,
                "name": dev_name,
                "state": normalize_device_state(raw_st, online_values=online_values),
                "raw_state": str(raw_st if raw_st is not None else "unknown"),
                "ip": str(item.get("ip") or item.get("hostAddress") or ""),
                "vendor": "Custom",
                "channels": int(item.get("channels") or item.get("channelCount") or 0),
            }
        )

    if gb_id.strip():
        return [d for d in devices if d["gb_id"] == gb_id.strip()]
    return devices


# ==================== 5. 演示模拟源（严格逻辑自洽） ====================

def _generate_demo_devices(config: dict[str, Any], gb_id: str = "") -> list[dict[str, Any]]:
    total_count, offline_count = clamp_demo_config(config)
    presets = [
        ("31011500991320000101", "园区东门主干道枪机"),
        ("31011500991320000102", "地下车库B1出口抓拍机"),
        ("31011500991320000103", "仓库A区货架全景球机"),
        ("31011500991320000104", "办公楼一楼前台监控"),
        ("31011500991320000105", "配电室机房红外监控"),
        ("31011500991320000106", "屋顶消防通道监控"),
        ("31011500991320000107", "西门访客登记处球机"),
        ("31011500991320000108", "物流装卸月台高清枪机"),
    ]
    devices: list[dict[str, Any]] = []
    for idx in range(total_count):
        if idx < len(presets):
            dev_id, dev_name = presets[idx]
        else:
            dev_id = f"310115009913200001{idx + 1:02d}"
            dev_name = f"演示监控摄像头 #{idx + 1}"
        is_off = idx >= (total_count - offline_count)
        devices.append(
            {
                "gb_id": dev_id,
                "name": dev_name,
                "state": "offline" if is_off else "online",
                "raw_state": "offline" if is_off else "online",
                "ip": f"192.168.1.{101 + idx}",
                "vendor": "DemoCam",
                "channels": 1,
            }
        )
    if gb_id:
        return [d for d in devices if d["gb_id"] == gb_id]
    return devices


# ==================== 统一对外调度入口 ====================

async def fetch_devices(
    provider: str,
    config: dict[str, Any],
    namespace_id: str = "",
    gb_id: str = "",
) -> list[dict[str, Any]]:
    p = (provider or "qiniu").strip().lower()
    if p == "qiniu":
        return await _fetch_qiniu_devices(config, namespace_id, gb_id)
    if p == "tencent":
        return await _fetch_tencent_devices(config, namespace_id, gb_id)
    if p == "aliyun":
        return await _fetch_aliyun_devices(config, namespace_id, gb_id)
    if p == "custom":
        return await _fetch_custom_devices(config, gb_id)
    if p == "demo":
        return _generate_demo_devices(config, gb_id=gb_id.strip())
    raise RuntimeError(f"暂不支持的监控源类型：{p}")


async def test_source_connection(
    provider: str,
    config: dict[str, Any],
    namespace_id: str = "",
) -> dict[str, Any]:
    try:
        devices = await fetch_devices(provider=provider, config=config, namespace_id=namespace_id)
        online = sum(1 for d in devices if d["state"] == "online")
        offline = len(devices) - online
        return {
            "ok": True,
            "message": f"连接成功！共发现 {len(devices)} 台设备（在线 {online} 台，离线/异常 {offline} 台）。",
            "total": len(devices),
            "online": online,
            "offline": offline,
            "devices": devices[:50],
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": str(exc),
            "total": 0,
            "online": 0,
            "offline": 0,
            "devices": [],
        }
