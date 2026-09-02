from __future__ import annotations

import platform

from .base import ServiceManager, ServiceMode, ServiceStatus


def get_service_manager() -> ServiceManager:
    system = platform.system()
    if system == "Linux":
        from .linux import LinuxServiceManager
        return LinuxServiceManager()
    if system == "Windows":
        from .windows import WindowsServiceManager
        return WindowsServiceManager()
    raise NotImplementedError(f"{system} service management is reserved for future macOS support.")


__all__ = ["ServiceManager", "ServiceMode", "ServiceStatus", "get_service_manager"]
