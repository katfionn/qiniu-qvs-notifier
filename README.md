# 七牛 QVS 通知器

[简体中文](README.md) | [English](docs/README.en.md) | [Español](docs/README.es.md) | [Français](docs/README.fr.md)

通过钉钉或其他 Webhook，在七牛 QVS 设备状态发生变化时发送告警。Web 控制台与后台监控共用现有的巡检核心、配置和 SQLite 设备存储。

## 安装

### Docker：仅 Web 服务

Docker 只提供 Web 服务，不包含交互式 TUI 或服务模式选择。

```bash
docker compose up -d --build
```

访问 `http://localhost:8000`。挂载的 `./config` 目录会持久化配置和设备数据；`restart: always` 会在故障及主机重启后自动恢复服务。

### 源码：TUI 安装器与管理器

请使用 Python 3.9 或更高版本：

```bash
python install.py
```

入口会检查依赖（并可安装 `requirements.txt`），然后打开 TUI。请选择一种服务模式：

- **Web 服务**：运行 Web 控制台及内置监控。安装后访问 `http://127.0.0.1:8000`。
- **TUI/监控服务**：仅在后台运行非交互式监控。TUI 始终是前台管理工具，不会被错误地注册为无交互后台服务。

TUI 支持安装、状态查看、启动、停止、重启、日志命令、凭证配置、语言选择和卸载。已安装服务会进入管理流程，不会重复创建。

## 原生服务

Linux 上，安装器会在 `/etc/systemd/system` 创建动态 systemd unit，使用真实安装路径生成 `WorkingDirectory` 和 `ExecStart`，并设置 `Restart=on-failure` 与 `systemctl enable`。安装、删除和控制需要 `sudo`。

Windows 上，项目使用注册到 Windows Service Control Manager 的 pywin32 `ServiceFramework`，而不是 `systemctl` 或脱离管理的进程。安装器会检测管理员权限不足并提示以管理员身份重新运行；两个服务模式均使用 Windows 服务恢复策略自动重启。

服务抽象层已为 macOS 预留，但尚未实现。

## 卸载

在 TUI 中选择“卸载七牛 QVS 通知器”。系统会进行两次确认，停止并删除原生服务及开机启动配置，随后允许保留或删除 `config/`。保留时会留下凭证和设备数据；删除时会移除 `settings.yaml` 和 `devices.db`。

## 语言

本 README 提供简体中文、English、Español 和 Français 四种版本，默认显示简体中文。

应用的安装器、TUI、服务消息、API 消息和 Web UI 目前提供简体中文（`zh-CN`）与 English（`en-US`）。显式选择会保存到 `config/settings.yaml`；否则使用系统语言，最终回退到 English。

## 开发

仅在本地 Web 开发时使用：

```bash
python run_web.py --reload
```

生产源码服务与 Docker 使用非 reload 的启动方式。
