"""Interactive installer and service manager. It is never run as a background service."""
from __future__ import annotations

import shutil
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

from qvs_notifier.i18n import normalize_locale, system_locale, translate
from qvs_notifier.services import ServiceMode, get_service_manager
from web.models.settings import load_config, save_config

console = Console()
ROOT = Path(__file__).resolve().parents[1]


def language() -> str:
    configured = load_config().ui.language
    return normalize_locale(configured or system_locale())


def t(key: str, **values) -> str:
    return translate(key, language(), **values)


def choose_mode() -> ServiceMode | None:
    value = questionary.select(t("service.choose_mode"), choices=[
        questionary.Choice(t("service.web"), ServiceMode.WEB),
        questionary.Choice(t("service.monitor"), ServiceMode.MONITOR),
        questionary.Choice(t("common.back"), None),
    ]).ask()
    return value


def select_installed_mode(manager) -> ServiceMode | None:
    web, monitor = manager.status(ServiceMode.WEB), manager.status(ServiceMode.MONITOR)
    if web.installed:
        return ServiceMode.WEB
    if monitor.installed:
        return ServiceMode.MONITOR
    return choose_mode()


def show_status(manager, mode: ServiceMode) -> None:
    status = manager.status(mode)
    state = t("service.running") if status.running else (t("service.stopped") if status.installed else t("service.not_installed"))
    console.print(Panel(t("service.status", status=state, autostart=t("common.yes") if status.auto_start else t("common.no"), autorestart=t("common.yes") if status.auto_restart else t("common.no"), pid=status.pid or "-", uptime=status.uptime or "-"), title=t(f"service.{mode.value}")))


def configure() -> None:
    config = load_config()
    config.qiniu.access_key = questionary.text(t("web.access_key"), default=config.qiniu.access_key).ask() or ""
    config.qiniu.secret_key = questionary.password(t("web.secret_key"), default=config.qiniu.secret_key).ask() or ""
    config.webhook.url = questionary.text(t("web.url"), default=config.webhook.url).ask() or ""
    save_config(config)
    console.print(t("web.saved"))


def change_language() -> None:
    selected = questionary.select(t("menu.language"), choices=[
        questionary.Choice("简体中文", "zh-CN"), questionary.Choice("English", "en-US")
    ]).ask()
    if selected:
        config = load_config(); config.ui.language = selected; save_config(config)
        console.print(translate("common.language_saved", selected))


def uninstall(manager, mode: ServiceMode) -> None:
    if not questionary.confirm(t("uninstall.first_confirm"), default=False).ask():
        return
    keep = questionary.confirm(t("uninstall.keep_config"), default=True).ask()
    if not questionary.confirm(t("uninstall.second_confirm"), default=False).ask():
        return
    manager.uninstall(mode)
    if not keep:
        import shutil as _shutil
        _shutil.rmtree(ROOT / "config", ignore_errors=True)
        console.print(t("uninstall.config_removed"))
    console.print(t("uninstall.success"))


def main() -> None:
    console.print(Panel(t("installer.title"), border_style="cyan"))
    try:
        manager = get_service_manager()
    except NotImplementedError as error:
        console.print(str(error)); return
    while True:
        action = questionary.select(t("common.select"), choices=[
            t("menu.install"), t("menu.status"), t("menu.start"), t("menu.stop"), t("menu.restart"),
            t("menu.logs"), t("menu.configuration"), t("menu.language"), t("menu.uninstall"), t("menu.exit")
        ]).ask()
        if not action or action == t("menu.exit"):
            return
        try:
            if action == t("menu.configuration"):
                configure(); continue
            if action == t("menu.language"):
                change_language(); continue
            mode = choose_mode() if action == t("menu.install") else select_installed_mode(manager)
            if not mode:
                continue
            if action == t("menu.install"):
                if manager.status(mode).installed:
                    console.print(t("service.already_installed")); show_status(manager, mode)
                else:
                    manager.install(mode); console.print(t("service.install_success"))
            elif action == t("menu.status"):
                show_status(manager, mode)
            elif action == t("menu.start"):
                manager.start(mode); console.print(t("service.action_success"))
            elif action == t("menu.stop"):
                manager.stop(mode); console.print(t("service.action_success"))
            elif action == t("menu.restart"):
                manager.restart(mode); console.print(t("service.action_success"))
            elif action == t("menu.logs"):
                console.print(t("service.logs_hint")); console.print(t("service.logs_command", command=manager.log_command(mode)))
            elif action == t("menu.uninstall"):
                uninstall(manager, mode)
        except PermissionError:
            console.print(f"[yellow]{t('installer.admin_required')}[/yellow]")
        except Exception as error:
            console.print(f"[red]{t('service.action_failed', error=error)}[/red]")
