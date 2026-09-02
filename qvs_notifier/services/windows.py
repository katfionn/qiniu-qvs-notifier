from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

from .base import ServiceManager, ServiceMode, ServiceStatus


class WindowsServiceManager(ServiceManager):
    """Manage real pywin32 ServiceFramework services, never systemctl."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()

    def is_admin(self) -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except AttributeError:
            return False

    def _require_admin(self) -> None:
        if not self.is_admin():
            raise PermissionError("Administrator privileges are required. Re-run the installer as Administrator.")
        try:
            import win32serviceutil  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("pywin32 is required for Windows Service support.") from exc

    def _class_name(self, mode: ServiceMode) -> str:
        return "QiniuWebService" if mode is ServiceMode.WEB else "QiniuMonitorService"

    def _service_command(self, mode: ServiceMode, action: str) -> list[str]:
        return [sys.executable, "-m", "qvs_notifier.windows_service", "--mode", mode.value, action]

    def _run(self, mode: ServiceMode, action: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(self._service_command(mode, action), cwd=self.project_root, text=True, capture_output=True, check=check)

    def install(self, mode: ServiceMode) -> None:
        self._require_admin()
        self._run(mode, "install")
        # Configure SCM recovery, so an unexpected process exit restarts the real service.
        subprocess.run(["sc.exe", "failure", mode.service_name, "reset=", "86400", "actions=", "restart/5000/restart/5000/restart/5000"], text=True, capture_output=True, check=True)
        self._run(mode, "start")

    def start(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run(mode, "start")

    def stop(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run(mode, "stop")

    def restart(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run(mode, "restart")

    def status(self, mode: ServiceMode) -> ServiceStatus:
        try:
            import win32service
            import win32serviceutil
        except ImportError:
            return ServiceStatus(False, False, False, False, detail="pywin32 is not installed")
        try:
            status = win32serviceutil.QueryServiceStatus(mode.service_name)
            config = win32service.QueryServiceConfig(win32service.OpenService(
                win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT), mode.service_name, win32service.SERVICE_QUERY_CONFIG))
            running = status[1] == win32service.SERVICE_RUNNING
            return ServiceStatus(True, running, config[1] == win32service.SERVICE_AUTO_START, True)
        except Exception:
            return ServiceStatus(False, False, False, False)

    def uninstall(self, mode: ServiceMode) -> None:
        self._require_admin(); self._run(mode, "stop", check=False); self._run(mode, "remove")

    def log_command(self, mode: ServiceMode) -> str:
        return f"Get-WinEvent -LogName Application | Where-Object {{$_.ProviderName -eq '{mode.service_name}'}}"
