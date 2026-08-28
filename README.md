# Qiniu QVS Device Monitor & Alert System (V2)

一个高性能、可配置的七牛云设备监控与告警系统，内置 Web 控制台。

## 🌟 核心特性 (Features)
- 🚀 **异步高并发**: 基于 `aiohttp`，秒级完成数千台设备的巡检。
- 🛡️ **智能防抖告警**: 仅在设备状态**发生翻转**时发送通知，彻底告别钉钉消息风暴。
- 🤖 **通用 Webhook 引擎**:
  - 支持 **钉钉/企业微信 HMAC-SHA256 加签** 以及 关键字校验。
  - 支持在 UI 上编写自定义 **JSON Body 模板**，无缝对接 Server酱、飞书等任何平台。
- ⏱️ **内置任务调度 (Daemon)**: 无需自行配置 crontab，Web 服务启动后自动拉起后台守护协程，支持动态修改轮询间隔和模式 (单次/无限)。
- 🖥️ **一站式 Web 面板**: 零编译前端，可视化管理 七牛 API 凭证、设备库和通知策略。
- 🐳 **容器化支持**: 提供现成的 Docker 镜像和流水线，实现极简部署。

---

## 🚀 安装与部署

我们推荐使用 Docker 方式部署，环境完全隔离且极简。如果你希望在本地开发或不想用 Docker，也可以选择源码部署。

### 方式一：Docker 部署 (推荐)

本项目借助 GitHub Actions 自动构建最新镜像并发布到 GHCR (GitHub Container Registry)。

**1. 准备目录与 docker-compose**
在你的服务器上新建一个目录，并创建 `docker-compose.yml` 文件：
```yaml
version: '3.8'
services:
  qiniu-monitor:
    image: ghcr.io/katfionn/qiniu-qvs-device-alert-to-dingtalk-bot:latest
    container_name: qiniu-monitor
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config  # 数据持久化目录
    environment:
      - TZ=Asia/Shanghai
```

**2. 启动服务**
```bash
docker-compose up -d
```
服务启动后，访问 `http://<你的IP>:8000` 进入后台。配置和设备数据均会安全地保存在本地的 `./config` 目录中。

---

### 方式二：源码部署

推荐使用 Python 3.9+ 环境。

**1. 拉取代码与依赖**
```bash
git clone https://github.com/katfionn/Qiniu-QVS-device-alert-to-Dingtalk-bot-.git
cd Qiniu-QVS-device-alert-to-Dingtalk-bot-
pip install -r requirements.txt
```

**2. 启动一站式服务**
我们已将监控调度引擎无缝嵌入在 Web 服务内部，运行以下命令，系统就会开始运转：
```bash
python3 run_web.py
```

- 浏览器访问 `http://127.0.0.1:8000` 进行所有设置。
- **后台控制实时生效**: 修改轮询间隔、增减设备，系统下个调度周期立刻生效！
