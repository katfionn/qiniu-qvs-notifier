"""pywin32 ServiceFramework host for Web and monitor service modes."""
from __future__ import annotations

import argparse
import asyncio
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil


class _BaseService(win32serviceutil.ServiceFramework):
    def __init__(self, args):
        super().__init__(args)
        self.stop_event = threading.Event()
        self.h_stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_event.set()
        win32event.SetEvent(self.h_stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ""))
        self.run_service()


class QiniuWebService(_BaseService):
    _svc_name_ = "qiniu-qvs-notifier-web"
    _svc_display_name_ = "Qiniu QVS Notifier Web"
    _svc_description_ = "Qiniu QVS Notifier Web dashboard and monitoring service"

    def run_service(self):
        from run_web import run_web
        run_web(self.stop_event)


class QiniuMonitorService(_BaseService):
    _svc_name_ = "qiniu-qvs-notifier-monitor"
    _svc_display_name_ = "Qiniu QVS Notifier Monitor"
    _svc_description_ = "Qiniu QVS Notifier background monitoring service"

    def run_service(self):
        from web.monitor import start_daemon
        asyncio.run(start_daemon(self.stop_event))


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("web", "monitor"), required=True)
    args, rest = parser.parse_known_args()
    win32serviceutil.HandleCommandLine(QiniuWebService if args.mode == "web" else QiniuMonitorService, argv=rest)


if __name__ == "__main__":
    main()
