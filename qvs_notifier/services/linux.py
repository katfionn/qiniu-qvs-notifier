from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .base import ServiceManager, ServiceMode, ServiceStatus


class LinuxServiceManager(ServiceManager):
    """Manage systemd units. All privileged mutations require root."""

    unit_directory = Path("/etc/systemd/system")

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()

    def is_admin(self) -> bool:
        return os.geteuid() == 0

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, text=True, capture_output=True, check=check)

    def _unit_path(self, mode: ServiceMode) -> Path:
        return self.unit_directory / f"{mode.service_name}.service"

    def _command(self, mode: ServiceMode) -> str:
        target = "run_web.py --no-reload" if mode is ServiceMode.WEB else "run_monitor.py"
        return f'"{sys.executable}" "{self.project_root / target.split()[0]}"' + (" --no-reload" if mode is ServiceMode.WEB else "")

    def _unit(self, mode: ServiceMode) -> str:
        user = os.environ.get("SUDO_USER") or getpass.getuser()
        return "\n".join((
            "[Unit]",
            f"Description=Qiniu QVS Notifier ({mode.value})",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={self.project_root}",
            f"ExecStart={self._command(mode)}",
            f"User={user}",
            f"Environment=PYTHONUNBUFFERED=1",
            "Restart=on-failure",
            "RestartSec=5",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        ))

    def _require_admin(self) -> None:
        if not self.is_admin():
            raise PermissionError("Administrator privileges are required; run this command with sudo.")
        if not shutil.which("systemctl"):
            raise RuntimeError("systemd/systemctl is not available on this Linux host.")

    def install(self, mode: ServiceMode) -> None:
        self._require_admin()
        self._unit_path(mode).write_text(self._unit(mode), encoding="utf-8")
        self._run("systemctl", "daemon-reload")
        self._run("systemctl", "enable", mode.service_name)
        self.start(mode)

    def start(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run("systemctl", "start", mode.service_name)

    def stop(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run("systemctl", "stop", mode.service_name)

    def restart(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run("systemctl", "restart", mode.service_name)

    def status(self, mode: ServiceMode) -> ServiceStatus:
        unit = self._unit_path(mode)
        if not unit.exists():
            return ServiceStatus(False, False, False, False)
        show = self._run("systemctl", "show", mode.service_name, "--no-page", "--property=ActiveState,SubState,UnitFileState,MainPID,ActiveEnterTimestamp", check=False)
        fields = dict(line.split("=", 1) for line in show.stdout.splitlines() if "=" in line)
        active = fields.get("ActiveState") == "active"
        return ServiceStatus(True, active, fields.get("UnitFileState") == "enabled", True,
                             fields.get("MainPID") if fields.get("MainPID") not in (None, "0") else None,
                             fields.get("ActiveEnterTimestamp") or None, fields.get("SubState", ""))

    def uninstall(self, mode: ServiceMode) -> None:
        self._require_admin()
        self._run("systemctl", "stop", mode.service_name, check=False)
        self._run("systemctl", "disable", mode.service_name, check=False)
        self._unit_path(mode).unlink(missing_ok=True)
        self._run("systemctl", "daemon-reload")

    def log_command(self, mode: ServiceMode) -> str:
        return f"journalctl -u {mode.service_name} -f"
