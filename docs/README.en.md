# Qiniu QVS Notifier

[简体中文](../README.md) | [English](README.en.md) | [Español](README.es.md) | [Français](README.fr.md)

Qiniu QVS device monitoring with state-change alerts through DingTalk or another webhook. The Web dashboard and background monitor share the monitor core, configuration, and SQLite device store.

## Installation

### Docker: Use pre-built image (Recommended)

```bash
docker run -d \
  -p 8000:8000 \
  -v ./config:/app/config \
  --restart always \
  --name qiniu-qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:latest
```

Open `http://localhost:8000` to configure.

### Docker: Build from source

Docker deliberately provides only the Web service, without the interactive TUI or a service-mode choice.

```bash
docker compose up -d --build
```

Open `http://localhost:8000`. The mounted `./config` directory persists settings and devices. `restart: always` restores the service after failures and host restarts.

### Source: TUI installer and manager

Use Python 3.9 or newer:

```bash
python install.py
```

The entry point checks dependencies and can install `requirements.txt`, then opens the TUI. Select one mode:

- **Web service**: runs the dashboard and embedded monitor at `http://127.0.0.1:8000`.
- **TUI/monitor service**: runs only the non-interactive monitor in the background. The TUI remains a foreground management tool.

The TUI supports install, status, start, stop, restart, log command, configuration, language selection, and uninstall. Existing services are managed rather than duplicated.

## Native services and uninstall

On Linux, the installer creates a dynamic systemd unit with the actual `WorkingDirectory`, `ExecStart`, `Restart=on-failure`, and `systemctl enable`; use `sudo` for service changes.

On Windows, pywin32 `ServiceFramework` registers a real Windows Service. Administrator rights are required, and the Windows Service recovery policy restarts failed services.

Choose **Uninstall Qiniu QVS Notifier** in the TUI. After two confirmations it removes the native service and startup configuration, then lets you keep or remove `config/` (credentials and device data).

## Languages

This README is available in Simplified Chinese, English, Spanish, and French; Chinese is the default.

The application currently provides Simplified Chinese (`zh-CN`) and English (`en-US`) for its installer, TUI, service/API messages, and Web UI. The explicit choice is stored in `config/settings.yaml`.

## Development

Use `python run_web.py --reload` only for local Web development. Production source services and Docker do not use reload mode.
