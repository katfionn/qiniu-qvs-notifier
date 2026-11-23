"""端到端自动化测试套件 v3.2：验证三云签名、逻辑自洽钳制、脱敏测试补全、防重复状态机与自愈"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

TMP_DIR = Path(tempfile.mkdtemp(prefix="qvs_v31_test_"))
os.environ["QVS_DATA_DIR"] = str(TMP_DIR)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from app import __version__  # noqa: E402
from app.database import init_databases, logs_conn, utc_now_iso  # noqa: E402
from app.main import app  # noqa: E402
from app.qiniu_client import (  # noqa: E402
    build_aliyun_rpc_query,
    build_qiniu_v2_token,
    build_tencent_tc3_headers,
    clamp_demo_config,
    normalize_device_state,
)
from app.scheduler import (  # noqa: E402
    build_schedule_cron,
    cron_matches_datetime,
    is_in_quiet_hours,
    validate_cron_expression,
)


class FullSystemV31Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_databases()
        cls.client = TestClient(app)
        cls.token = ""

    def test_01_version_and_multi_cloud_signatures(self) -> None:
        self.assertEqual(__version__, "3.2.0")

        # 七牛 V2 签名
        q_token = build_qiniu_v2_token("ak_demo", "sk_demo", "GET", "/v1/namespaces/ns1/devices", "line=100")
        self.assertTrue(q_token.startswith("ak_demo:"))

        # 腾讯云 TC3 签名
        tc_headers = build_tencent_tc3_headers(
            secret_id="AKID_TEST",
            secret_key="SK_TEST",
            service="iotvideoindustry",
            host="iotvideoindustry.tencentcloudapi.com",
            action="DescribeAllDeviceList",
            version="2020-12-01",
            region="ap-guangzhou",
            payload_str='{"Offset":0,"Limit":100}',
            timestamp=1700000000,
        )
        self.assertIn("TC3-HMAC-SHA256 Credential=AKID_TEST/", tc_headers["Authorization"])
        self.assertEqual(tc_headers["X-TC-Action"], "DescribeAllDeviceList")

        # 阿里云 POP RPC 签名
        ali_q = build_aliyun_rpc_query(
            access_key_id="LTAI_TEST",
            access_key_secret="ALI_SK_TEST",
            action="ListDevices",
            version="2020-05-15",
            extra_params={"PageSize": 100},
            timestamp="2026-11-23T00:00:00Z",
            nonce="nonce-123",
        )
        self.assertIn("Signature=", ali_q)
        self.assertIn("Action=ListDevices", ali_q)

        # 状态归一化
        self.assertEqual(normalize_device_state("online"), "online")
        self.assertEqual(normalize_device_state("notReg"), "unregistered")
        self.assertEqual(normalize_device_state(0), "offline")

    def test_02_demo_config_strict_logic_consistency(self) -> None:
        # 当模拟离线数 > 总设备数时，必须严格钳制到总设备数，绝不能反过来改大总设备数
        total, off = clamp_demo_config({"demo_total_count": 5, "demo_offline_count": 99})
        self.assertEqual(total, 5)
        self.assertEqual(off, 5)

        total2, off2 = clamp_demo_config({"demo_total_count": 0, "demo_offline_count": -3})
        self.assertEqual(total2, 1)
        self.assertEqual(off2, 0)

    def test_03_cron_and_quiet_hours(self) -> None:
        ok, _ = validate_cron_expression("*/5 * * * *")
        self.assertTrue(ok)
        ok_bad, _ = validate_cron_expression("bad cron")
        self.assertFalse(ok_bad)
        expr, txt = build_schedule_cron("interval", interval_minutes=15)
        self.assertEqual(expr, "*/15 * * * *")
        self.assertIn("15 分钟", txt)

        self.assertTrue(cron_matches_datetime("*/5 * * * *", datetime(2026, 11, 23, 10, 15)))
        self.assertTrue(is_in_quiet_hours(True, "23:00", "07:00", datetime(2026, 11, 23, 23, 30)))
        self.assertFalse(is_in_quiet_hours(True, "23:00", "07:00", datetime(2026, 11, 23, 12, 0)))

    def test_04_stale_running_log_self_healing(self) -> None:
        with logs_conn() as lconn:
            lconn.execute(
                "INSERT INTO task_logs (task_id, task_name, status, started_at) VALUES (999, '模拟崩溃任务', 'running', ?)",
                (utc_now_iso(),),
            )
        res = init_databases()
        self.assertTrue(res["ok"])
        with logs_conn() as lconn:
            row = lconn.execute("SELECT status FROM task_logs WHERE task_id = 999").fetchone()
        self.assertEqual(row["status"], "interrupted")

    def test_05_web_setup_assets_and_auth_flow(self) -> None:
        r_html = self.client.get("/")
        self.assertEqual(r_html.status_code, 200)
        self.assertIn("QVS 多云监控告警中心 v3.2", r_html.text)

        r_logo = self.client.get("/static/img/logo.svg")
        self.assertEqual(r_logo.status_code, 200)
        self.assertIn("<svg", r_logo.text)

        r_init = self.client.post("/api/setup/init", json={"username": "admin", "password": "StrongPassword123"})
        self.assertEqual(r_init.status_code, 200)
        FullSystemV31Test.token = r_init.json()["access_token"]

        r_dup = self.client.post("/api/setup/init", json={"username": "admin2", "password": "StrongPassword123"})
        self.assertEqual(r_dup.status_code, 400)

    def test_06_demo_clamp_api_task_validation_and_backup(self) -> None:
        headers = {"Authorization": f"Bearer {FullSystemV31Test.token}"}

        # API 层验证：传入 total=3, offline=999，后端应自动钳制为 total=3, offline=3
        r_src = self.client.post(
            "/api/source-channels",
            headers=headers,
            json={
                "name": "逻辑自洽演示源",
                "provider": "demo",
                "namespace_id": "demo-ns",
                "config": {"demo_total_count": 3, "demo_offline_count": 999},
            },
        )
        self.assertEqual(r_src.status_code, 200)
        src = r_src.json()
        self.assertEqual(src["config"]["demo_total_count"], 3)
        self.assertEqual(src["config"]["demo_offline_count"], 3)
        src_id = src["id"]

        # 任务校验：免打扰开始与结束时间相同时应拦截
        r_bad_task = self.client.post(
            "/api/tasks",
            headers=headers,
            json={
                "name": "非法静默时段任务",
                "source_channel_id": src_id,
                "quiet_hours_enabled": True,
                "quiet_start": "23:00",
                "quiet_end": "23:00",
            },
        )
        self.assertEqual(r_bad_task.status_code, 400)

        # 创建正常任务并验证连续防误报 + 冷却防重复
        r_task = self.client.post(
            "/api/tasks",
            headers=headers,
            json={
                "name": "多云巡检任务",
                "source_channel_id": src_id,
                "schedule_mode": "interval",
                "interval_minutes": 5,
                "fail_threshold": 2,
                "cooldown_minutes": 60,
            },
        )
        self.assertEqual(r_task.status_code, 200)
        tid = r_task.json()["id"]

        run1 = self.client.post(f"/api/tasks/{tid}/run", headers=headers).json()
        self.assertIn("观察中", run1["message"])
        run2 = self.client.post(f"/api/tasks/{tid}/run", headers=headers).json()
        self.assertNotIn("观察中", run2["message"])
        run3 = self.client.post(f"/api/tasks/{tid}/run", headers=headers).json()
        self.assertIn("冷却期", run3["message"])

        # 健康检查版本号应为 3.2.0
        h = self.client.get("/api/health").json()
        self.assertEqual(h["status"], "ok")
        self.assertEqual(h["version"], "3.2.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
