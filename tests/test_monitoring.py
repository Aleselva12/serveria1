import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import monitoring as m


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        m._previous = None
        m._history.clear()
        app = FastAPI()
        app.include_router(m.router)
        self.client = TestClient(app)

    def test_live_endpoints_without_ollama_or_graph(self):
        response = self.client.get("/api/v1/server/telemetry")
        self.assertEqual(response.status_code, 200)
        first = response.json()
        self.assertIsNone(first["cpu"]["percent"])
        self.assertIsNone(first["network"])
        self.assertGreater(first["disks"][0]["totalBytes"], 0)
        self.assertGreaterEqual(first["ram"]["percent"], 0)
        second = self.client.get("/api/v1/server/telemetry").json()
        self.assertIn("cpuHistory", second)
        self.assertEqual(self.client.get("/api/v1/server/storage").status_code, 200)

    def test_cpu_network_deltas_and_reset_counters(self):
        from collections import namedtuple

        CPU = namedtuple("CPU", "user idle")
        with patch.object(
            m.psutil, "cpu_times", side_effect=[CPU(20, 80), CPU(50, 150), CPU(80, 220)]
        ), patch.object(m.time, "monotonic", side_effect=[10, 12, 14]), patch.object(
            m.psutil, "net_if_stats", return_value={"eth0": NS(isup=True)}
        ), patch.object(
            m.psutil,
            "net_io_counters",
            side_effect=[
                {"eth0": NS(bytes_recv=100, bytes_sent=50)},
                {"eth0": NS(bytes_recv=200, bytes_sent=75)},
                {"eth0": NS(bytes_recv=0, bytes_sent=0)},
            ],
        ), patch.object(
            m, "gpu_metric", return_value=None
        ):
            m.telemetry()
            data = m.telemetry()
            self.assertEqual(data["cpu"]["percent"], 30)
            self.assertEqual(data["network"]["receiveBitsPerSecond"], 400)
            self.assertEqual(data["network"]["transmitBitsPerSecond"], 100)
            self.assertEqual(m.telemetry()["network"]["receiveBitsPerSecond"], 0)

    def test_unknown_power_and_gpu_are_not_zero_load_or_mains(self):
        with patch.object(m.psutil, "sensors_battery", return_value=None):
            self.assertEqual(m.power()["kind"], "unknown")
        with patch.object(m.Path, "glob", return_value=[]), patch.object(
            m.shutil, "which", return_value=None
        ):
            self.assertIsNone(m.gpu_metric()["percent"])

    def test_failed_mount_does_not_break_other_disks(self):
        with patch.object(
            m.psutil,
            "disk_partitions",
            return_value=[
                NS(device="a", mountpoint="/bad"),
                NS(device="b", mountpoint="/good"),
            ],
        ), patch.object(
            m.psutil,
            "disk_usage",
            side_effect=[PermissionError(), NS(used=10, total=20)],
        ):
            self.assertEqual([d["id"] for d in m.disks()], ["/good"])

    def test_services_unconfigured_and_docker_unhealthy(self):
        output = '{"ID":"1","Names":"test","State":"running","Status":"Up 1 hour (unhealthy)"}\n'
        with patch.dict(
            m.os.environ,
            {
                "CORA_SERVICE_IMMICH_URL": "",
                "CORA_SERVICE_NEXTCLOUD_URL": "",
                "CORA_SERVICE_N8N_URL": "",
            },
        ), patch.object(m, "urlopen", side_effect=OSError()), patch.object(
            m.shutil, "which", return_value="/usr/bin/docker"
        ), patch.object(
            m.subprocess, "run", return_value=NS(stdout=output)
        ):
            data = self.client.get("/api/v1/system/status").json()
        states = {s["id"]: s["status"] for s in data["services"]}
        self.assertEqual(states["fastapi"], "ready")
        self.assertEqual(states["ollama"], "offline")
        self.assertEqual(states["immich"], "unknown")
        self.assertEqual(states["docker:1"], "error")

    def test_docker_permissions_not_reported_as_healthy(self):
        with patch.object(m, "urlopen", side_effect=OSError()), patch.object(
            m.shutil, "which", return_value="/usr/bin/docker"
        ), patch.object(m.subprocess, "run", side_effect=PermissionError()):
            data = m.service_status()
        self.assertEqual(
            next(s for s in data["services"] if s["id"] == "docker")["status"],
            "unknown",
        )


if __name__ == "__main__":
    unittest.main()
