<div align="center">

<img src="assets/logo.svg" width="112" height="112" alt="QVS 多云监控告警中心 Logo" />

<h1>QVS Notifier · 多云视频监控告警中心</h1>

<p>
  <b>把多云摄像头巡检、防骚扰告警与系统自愈收进一个开箱即用的网页控制台</b><br />
  面向运维与个人用户的零门槛部署方案 · 支持七牛云 QVS、腾讯云视联、阿里云 VCS 与自定义 HTTP 监控源
</p>

<p>
  <img src="https://img.shields.io/badge/Version-v3.2.0-2563EB" alt="Version v3.2.0" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/FastAPI-Web%20UI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Docker-amd64%20%7C%20arm64-2496ED?logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License MIT" />
</p>

<p>
  <a href="#这是什么">这是什么</a> ·
  <a href="#功能一览">功能一览</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#docker-与-ghcr-部署">Docker 部署</a> ·
  <a href="#多云监控源与通知渠道">多云配置</a> ·
  <a href="#数据与自愈机制">数据与自愈</a> ·
  <a href="#项目结构">结构</a> ·
  <a href="#测试">测试</a>
</p>

</div>

## 这是什么

`qiniu-qvs-notifier` 最初是一个用于监控七牛云视频监控（QVS）设备在线状态的脚本工具。在 **v3.2** 中，它被彻底重构为一个**前后端一体、零外部 CDN 依赖、纯图形化操作、具备逻辑自愈能力**的多云监控告警中心。

不需要手写 Cron 表达式，不需要对着黑框终端敲配置命令，也不需要安装任何需要 C 语言编译的重型依赖。部署完打开浏览器，跟着页面提示 3 步就能跑通自动巡检和实时告警；即使手上暂时没有云账号，也可以直接用内置的 **演示模拟源** 完整走一遍离线告警与恢复通知流程。

核心设计原则：**任何破坏性操作前都有确认，任何输入表单都防误丢草稿，任何后台异常都尽量自动恢复并留痕。**

## 功能一览

| 模块 | 能做什么 |
| :--- | :--- |
| **总览仪表盘** | 展示设备在线/离线状态矩阵、今日巡检与告警统计、新手 3 步引导卡片与系统健康指标 |
| **多云监控源** | 统一接入七牛云 QVS、腾讯云视联 / IoT Video、阿里云 VCS、自定义 HTTP/JSON 接口及演示模拟源；支持一键测试并实时预览设备列表 |
| **通知渠道** | 原生适配钉钉（加签 / 关键词）、企业微信、飞书（加签）、NTFY 手机推送与自定义模板 Webhook；支持一键发送测试消息与精准排错提示 |
| **监控任务** | 可视化选择巡检频率（每隔 N 分钟 / 每天固定时间 / 自定义 Cron），支持连续离线防误报、冷却防重复轰炸、设备恢复上线通知与夜间免打扰 |
| **巡检与告警日志** | 独立日志库记录每次巡检耗时、在线/离线明细与每条通知送达结果，支持按状态筛选与自动/手动日志轮转清理 |
| **系统自愈与设置** | 实时展示数据库完整性、WAL 模式、磁盘余量与调度器看门狗状态；支持一键导出/导入 JSON 配置备份与多账号管理 |
| **外观与交互** | 浅色 / 深色双主题一键切换，纯本地静态资源（断网/内网秒开），弹窗点击空白处自动保留草稿、点取消或关闭才清空 |

## 快速开始

### 1. Docker 一键部署（推荐长期值守）

只需要安装好 Docker，复制下面命令到终端回车即可启动：

```bash
docker run -d \
  --name qiniu-qvs-notifier \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e TZ=Asia/Shanghai \
  ghcr.io/katfionn/qiniu-qvs-notifier:latest
```

或者使用仓库里的 `docker-compose.yml`：

```bash
docker compose up -d
```

启动后在浏览器打开 `http://localhost:8000`（服务器部署请替换为 `http://服务器IP:8000`），会自动进入图形化初始化向导，设置管理员账号密码后即可开始使用。

### 2. 本地 Python 直接运行（Windows / macOS / Linux 通用）

环境要求：**Python 3.10+**，只需安装 3 个纯 Python 依赖（`fastapi`、`uvicorn`、`httpx`），无任何编译步骤。

解压后在项目文件夹里打开终端（Windows 可在文件夹地址栏输入 `cmd` 回车，macOS / Linux 打开终端 `cd` 到该目录），依次复制以下两条命令回车：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python start.py
```

> **提示**：Windows 下如果 `python` 命令未识别，可改用 `py -3 start.py`；macOS / Linux 如需区分版本请使用 `python3` 与 `pip3`。
> 启动后会自动打开默认浏览器访问控制台；如果 `8000` 端口已被占用，本地模式会自动顺延到 `8001` 等空闲端口并在终端打印新地址。

<details>
<summary><b>启动异常排查（端口占用 / 依赖安装 / 服务器无桌面环境）</b></summary>
<br />

- **pip 安装缓慢或超时**：上面的命令已默认使用清华源；如果内网或海外机器无法访问清华源，直接执行 `pip install -r requirements.txt` 即可。
- **服务器无图形界面，不想尝试弹出浏览器**：运行时加上环境变量 `NO_BROWSER=1 python start.py`。
- **想指定固定端口运行**：通过环境变量指定，例如 Linux/macOS 执行 `PORT=9000 python3 start.py`，Windows PowerShell 执行 `$env:PORT=9000; python start.py`。
- **Docker 容器内修改了本地源码想重新构建**：编辑 `docker-compose.yml`，注释掉 `image: ghcr.io/...` 并取消注释 `build: .`，然后执行 `docker compose up -d --build`。

</details>

## Docker 与 GHCR 部署

仓库内置了 `.github/workflows/docker-publish.yml`，当你把代码推送到 GitHub `main` 分支或打上版本标签（如 `v3.2.0`）时，GitHub Actions 会自动构建 `linux/amd64` 与 `linux/arm64` 双架构镜像并发布到 GitHub Container Registry（GHCR）：

| 触发条件 | 自动生成的镜像标签 |
| :--- | :--- |
| 推送到 `main` 分支 | `ghcr.io/<用户名>/qiniu-qvs-notifier:latest` 与 `:main` |
| 推送 `v*.*.*` 标签（如 `v3.2.0`） | `:3.2.0`、`:3.2` 与 `:latest` |
| 发起 Pull Request | 仅构建验证，不推送镜像 |

镜像内置了 `HEALTHCHECK`，每 30 秒自动探测 `/api/health` 接口检查数据库与调度器存活状态。

## 多云监控源与通知渠道

### 支持的监控源（均采用纯 Python 原生签名，零重型 SDK 依赖）

| 服务商 | 认证与签名协议 | 关键配置项 |
| :--- | :--- | :--- |
| **七牛云 QVS** | 官方 `QiniuMacAuth` V2 签名 + 自动分页 + 单设备接口 | `Access Key`、`Secret Key`、`Namespace ID` |
| **腾讯云视联 / IoT Video** | 官方 `TC3-HMAC-SHA256` V3 签名 | `SecretId`、`SecretKey`、`Region`、`Endpoint`、`Action` |
| **阿里云视频监控 VCS** | 官方 `POP RPC 1.0 HMAC-SHA1` 签名 | `AccessKey ID`、`AccessKey Secret`、`Endpoint`、`Action` |
| **自定义 HTTP / JSON** | 自定义请求头 / GET / POST + 点号路径取值 | `URL`、`items_path`、ID/名称/状态字段映射、在线判定值 |
| **演示模拟源** | 本地虚拟摄像头数据（严格约束 `0 <= 离线数 <= 总数`） | `模拟设备总数 N`、`模拟离线数量` |

### 支持的通知渠道

| 平台 | 支持能力 |
| :--- | :--- |
| **钉钉机器人** | Markdown 富文本、HMAC-SHA256 加签校验、自定义关键词自动补齐 |
| **企业微信机器人** | Markdown 富文本群推送 |
| **飞书机器人** | 文本卡片推送、HMAC-SHA256 签名校验 |
| **NTFY 手机推送** | 支持官方 `ntfy.sh` 与私有部署、Bearer Token 鉴权、中文标题安全编码 |
| **自定义 Webhook** | 自定义请求头与 JSON 模板（支持 `{title}`、`{message}`、`{timestamp}`、`{event_type}` 变量安全转义） |

## 数据与自愈机制

所有运行时文件统一保存在 `./data/` 目录（可通过环境变量 `QVS_DATA_DIR` 修改），配置与日志彻底分离：

| 文件 | 用途 |
| :--- | :--- |
| `data/data.db` | 存储账号、监控源、通知渠道、任务、设备状态机与自愈事件（SQLite WAL 模式） |
| `data/logs.db` | 存储巡检任务日志与通知发送记录，每日凌晨自动清理 30 天前或超量旧日志 |
| `data/.secret_key` | 首次启动自动生成的 48 字节高强度随机 JWT 密钥（权限 `0600`），告别硬编码弱密钥 |

内置自愈能力包括：启动时自动修复上次异常退出残留的 `running` 僵死日志、SQLite WAL + `busy_timeout` 防止并发锁库、后台调度器看门狗异常自动重启、通知渠道删除时自动清理关联任务中的坏引用、以及一键导出/导入 JSON 配置备份。

## 项目结构

```text
qiniu-qvs-notifier/
├── .github/
│   └── workflows/
│       └── docker-publish.yml   # GHCR 多架构自动构建发布工作流
├── app/
│   ├── static/
│   │   ├── css/style.css        # Light/Dark 双主题设计系统样式
│   │   ├── img/logo.svg         # 品牌矢量图标与网站 Favicon
│   │   ├── js/app.js            # 零依赖前端控制台（含草稿保留与联动校验）
│   │   └── index.html           # 控制台主页面
│   ├── __init__.py              # 版本号定义 (v3.2.0)
│   ├── config.py                # 目录初始化与随机 JWT 密钥持久化
│   ├── database.py              # 双 SQLite 持久化层、WAL、自愈与备份
│   ├── main.py                  # FastAPI 主应用与全部 REST API
│   ├── notifier.py              # 五大平台告警通知与自动重试引擎
│   ├── qiniu_client.py          # 多云监控源引擎（七牛/腾讯/阿里/自定义/演示）
│   ├── scheduler.py             # 异步自愈调度器、Cron 解析与防重复告警状态机
│   └── security.py              # PBKDF2-SHA256 密码哈希、HS256 JWT 与脱敏
├── assets/
│   └── logo.svg                 # README 展示图标
├── tests/
│   └── test_full_system.py      # 全链路单元测试与接口集成测试
├── .dockerignore
├── .env.example                 # 可选环境变量说明
├── AUDIT_AND_UPGRADE.md         # 原仓库审计记录与重构说明
├── Dockerfile                   # 免编译精简镜像（含 HEALTHCHECK）
├── LICENSE                      # MIT 协议
├── README.md
├── docker-compose.yml           # 默认拉取 GHCR 镜像的编排文件
├── requirements.txt             # 仅 3 个纯 Python 核心依赖
└── start.py                     # 统一智能启动入口
```

## 测试

仓库自带端到端自动化测试套件，覆盖七牛/腾讯/阿里三云签名、Cron 与跨午夜免打扰逻辑、僵死任务自愈、Web 首次初始化、演示源边界钳制、防误报防重复状态机以及配置备份恢复：

```bash
python tests/test_full_system.py
```

## 安全与边界

- **敏感密钥脱敏**：所有云服务 `SecretKey` 与机器人加签密钥在 API 返回时自动脱敏为星号；编辑已有渠道并点击测试时，后端会自动使用数据库内原密钥补全未修改的脱敏字段。
- **零外部 CDN 依赖**：前端页面与图标全部由本地后端托管，可在纯内网或弱网环境下稳定打开。
- **生产建议**：如直接暴露到公网，建议在前端配置 Nginx / Caddy 反向代理启用 HTTPS，并定期通过页面内的「一键配置备份」下载备份文件。

## 已知限制

- 腾讯云与阿里云不同视频子产品（如视联、物联网视频、直播中心）的接口 `Endpoint` 与 `Action` 可能因开通服务类型而异，可在监控源表单中按需修改默认域名与接口名。
- 调度器默认按分钟级粒度触发（最小 1 分钟一次），不支持秒级高频轮询，以免触发云厂商 API 限流。

## 已知不足 / 待优化

- [ ] 支持按设备分组（Device Group）批量配置差异化告警策略
- [ ] 支持钉钉 / 企微 / 飞书卡片消息内附带自定义跳转链接
- [ ] 支持多语言界面切换（中文 / English）
- [ ] 支持在 Web 界面直接查看单台设备的历史离线时间线图表

## License

本项目基于 [MIT License](LICENSE) 开源。
