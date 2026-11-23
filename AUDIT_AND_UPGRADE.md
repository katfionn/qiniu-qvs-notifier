# 原仓库深度审计报告与 v3.0 重构说明

审计对象：[katfionn/qiniu-qvs-notifier](https://github.com/katfionn/qiniu-qvs-notifier)

---

## 一、原仓库核心 Bug 清单

1. **七牛云 QVS 接口鉴权与设备状态解析致命错误（`web/scheduler.py`）**
   - 原 v2 调度器使用 `qiniu.Auth(ak, sk).token_of_request(url, "GET", "application/json")`，而非七牛 QVS 要求的 `QiniuMacAuth` V2 签名（原 v1 的 `web/monitor.py` 使用的是 `QiniuMacAuth`）。
   - 原代码用整数 `state == 0` / `state == 1` 判断离线与在线，但七牛云 QVS 接口实际返回字符串状态（如 `"online"`、`"offline"`、`"notReg"`），导致离线统计恒为 0、告警失效。
   - 传入 `gb_id` 时使用列表查询参数而非单设备接口 `/v1/namespaces/{ns}/devices/{gb_id}`，且列表查询未做分页，设备较多时会漏检。
   - **v3.0 修复**：在 `app/qiniu_client.py` 中纯 Python 实现标准 `QiniuMacAuth` V2 签名、自动分页（`line`/`offset`）、单设备接口切换，并同时兼容字符串与数值状态归一化。

2. **Docker / 后台部署启动即崩溃死循环（`Dockerfile` + `run_web_v2.py` + `deploy.sh`）**
   - `Dockerfile` 与 `deploy.sh` 以无终端后台模式运行 `python run_web_v2.py`，但 `run_web_v2.py` 在启动 Uvicorn 前若检测到首次运行会阻塞调用终端交互向导 `qvs_notifier.installer.run_installer()`（依赖 `questionary` 读取 stdin），在容器内直接抛出 EOF 异常并触发 `--restart always` 无限重启；同时前端无 Web 初始化页面。
   - **v3.0 修复**：彻底移除阻塞式终端向导，改为服务直接启动 + 浏览器首次打开自动进入 Web 图形化初始化向导（`/api/setup/init`）。

3. **重复告警轰炸与缺少恢复通知（`web/scheduler.py`）**
   - 原任务只要检测到 `offline_count > 0` 每次调度都会无条件推送，5 分钟巡检一次即每小时轰炸 12 条重复告警，且无设备恢复上线通知与防网络瞬断误报机制。
   - **v3.0 修复**：在 `app/scheduler.py` 引入 `device_states` 状态机，支持连续离线防误报阈值、持续离线冷却防重复提醒、恢复上线通知与夜间免打扰时段。

4. **`docker-compose.yml` 数据持久化路径错误**
   - v2 数据库存于 `/app/data`，但 `docker-compose.yml` 仍挂载旧版 `- ./config:/app/config`，容器重建后用户配置全部丢失，且注释残留旧仓库镜像名。
   - **v3.0 修复**：统一挂载 `./data:/app/data`，改用 `python:3.11-slim` 免编译镜像并内置 `HEALTHCHECK`。

5. **Webhook 能力退化与国内主流机器人不兼容**
   - v2 退化为固定 JSON `{title, message, timestamp}`，无法直接对接钉钉加签/关键词、企业微信、飞书机器人。
   - **v3.0 修复**：在 `app/notifier.py` 原生内置钉钉（加签+关键词）、企业微信、飞书（加签）、NTFY 与自定义模板 Webhook。

6. **安全与运行稳定性隐患**
   - `web/auth.py` 硬编码公开默认 `JWT_SECRET_KEY`；`web/templates/index.html` 强依赖外部 CDN 导致内网/断网白屏；SQLite 未启用 WAL 模式易并发锁库；缺乏僵死 `running` 日志自愈与日志轮转清理；v1/v2 代码大量混杂。
   - **v3.0 修复**：首次运行自动生成持久化 48 字节随机密钥；接口密钥自动脱敏；零外部 CDN 前端；SQLite WAL + `busy_timeout`；启动僵死记录恢复 + 每日日志轮转 + 调度器看门狗。

---

## 二、交互体验（UX）优化升级

- **零门槛部署**：提供 Windows 双击脚本、Mac/Linux 一键脚本、Docker Compose 三种方案；依赖压缩至仅 3 个纯 Python 包，自动国内源加速+官方源回退，端口冲突自动顺延并自动打开浏览器。
- **新手 3 步引导 + 演示模拟源**：仪表盘自带引导清单，支持无需七牛账号一键创建“演示模拟源”完整体验告警流程。
- **所见即所得测试**：监控源支持“测试连接并预览设备列表”，通知渠道支持“一键发送测试消息”并给出人话排错提示，任务支持“立即巡检”。
- **告别手写 Cron 与 JSON**：可视化巡检频率下拉选择 + 平台卡片表单 + 一键配置备份/导入恢复。
