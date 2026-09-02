from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
from pathlib import Path
from web.models.settings import load_config, save_config, AppConfig
from web.models.device import init_db, get_all_devices, add_device, delete_device, import_from_txt
from web.monitor import start_daemon
from qvs_notifier.i18n import normalize_locale, web_messages

app = FastAPI(title="Qiniu Monitor Admin")

# 用于保存后台任务的引用，防止被垃圾回收
background_tasks = set()

@app.on_event("startup")
async def startup_event():
    init_db()
    import_from_txt()

    # 启动后台守护任务 (一键启动特性: Web服务和巡检监控在同一个进程内并发执行)
    loop = asyncio.get_event_loop()
    task = loop.create_task(start_daemon())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return FileResponse(html_path)

@app.get("/api/i18n")
async def get_i18n(language: str | None = None):
    config = load_config()
    return {"language": normalize_locale(language or config.ui.language), "messages": web_messages(language or config.ui.language)}

@app.get("/api/config")
async def get_config():
    return load_config()

@app.post("/api/config")
async def update_config(config: AppConfig):
    save_config(config)
    # 不重启任务，因为 start_daemon 内部使用 while True 每一轮休眠结束后都会重新 load_config
    return {"status": "success"}

class DevicePayload(BaseModel):
    namespace_id: str
    gb_id: str
    name: str

@app.get("/api/devices")
async def get_devices():
    return get_all_devices()

@app.post("/api/devices")
async def create_device(payload: DevicePayload):
    success = add_device(payload.namespace_id, payload.gb_id, payload.name)
    if success:
        return {"status": "success"}
    return {"status": "failed", "message": "device_exists"}

@app.delete("/api/devices/{device_id}")
async def remove_device(device_id: int):
    delete_device(device_id)
    return {"status": "success"}
