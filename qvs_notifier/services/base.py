from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ServiceMode(str, Enum):
    WEB = "web"
    MONITOR = "monitor"

    @property
    def service_name(self) -> str:
        return f"qiniu-qvs-notifier-{self.value}"


@dataclass
class ServiceStatus:
    installed: bool
    running: bool
    auto_start: bool
    auto_restart: bool
    pid: Optional[str] = None
    uptime: Optional[str] = None
    detail: str = ""


class ServiceManager(ABC):
    """OS-neutral contract used by the installer and TUI."""

    @abstractmethod
    def is_admin(self) -> bool: ...

    @abstractmethod
    def install(self, mode: ServiceMode) -> None: ...

    @abstractmethod
    def start(self, mode: ServiceMode) -> None: ...

    @abstractmethod
    def stop(self, mode: ServiceMode) -> None: ...

    @abstractmethod
    def restart(self, mode: ServiceMode) -> None: ...

    @abstractmethod
    def status(self, mode: ServiceMode) -> ServiceStatus: ...

    @abstractmethod
    def uninstall(self, mode: ServiceMode) -> None: ...

    @abstractmethod
    def log_command(self, mode: ServiceMode) -> str: ...
