"""Read-only host monitoring. No LLM, privileged commands or remote controls."""

import json
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import psutil
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Home"])
_lock = threading.Lock()
_previous = None
_history = deque(maxlen=120)


def now():
    return datetime.now(timezone.utc).isoformat()


def gpu_metric():
    # AMD exposes utilization directly through sysfs on Linux.
    for device in sorted(Path("/sys/class/drm").glob("card[0-9]*/device")):
        try:
            value = float((device / "gpu_busy_percent").read_text().strip())
            return {
                "percent": max(0, min(100, value)),
                "label": "GPU AMD",
                "detail": "Utilizzo GPU rilevato dal driver",
            }
        except (OSError, ValueError):
            continue
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
            name, usage, temp = result.stdout.splitlines()[0].rsplit(",", 2)
            return {
                "percent": float(usage),
                "label": name.strip(),
                "temperatureC": float(temp),
            }
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            pass
    return {
        "percent": None,
        "label": "GPU",
        "detail": "Nessun sensore GPU compatibile disponibile",
    }


def disks():
    result = []
    seen = set()
    for part in psutil.disk_partitions(all=False):
        if part.device in seen:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        seen.add(part.device)
        result.append(
            {
                "id": part.mountpoint,
                "label": part.mountpoint,
                "usedBytes": usage.used,
                "totalBytes": usage.total,
            }
        )
    if not result:
        root = Path.cwd().anchor
        usage = psutil.disk_usage(root)
        result.append(
            {
                "id": root,
                "label": root,
                "usedBytes": usage.used,
                "totalBytes": usage.total,
            }
        )
    return result


def power():
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, OSError):
        battery = None
    if battery is None:
        return {
            "kind": "unknown",
            "detail": "Alimentazione e UPS non rilevabili dai sensori disponibili",
        }
    return {
        "kind": "mains" if battery.power_plugged else "battery",
        "detail": f"Batteria {battery.percent:.0f}%",
    }


@router.get("/server/telemetry")
def telemetry():
    global _previous
    with _lock:
        timestamp = now()
        clock = time.monotonic()
        counters = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        interfaces = {
            name: item
            for name, item in counters.items()
            if name not in ("lo", "lo0") and name in stats and stats[name].isup
        }
        cpu = psutil.cpu_times()
        # Use deltas rather than cpu_percent's per-thread state in FastAPI's pool.
        cpu_total = sum(cpu) - getattr(cpu, "guest", 0) - getattr(cpu, "guest_nice", 0)
        cpu_idle = cpu.idle + getattr(cpu, "iowait", 0)
        percent = None
        network = None
        if _previous is not None:
            old_clock, old_total, old_idle, old_interfaces = _previous
            delta = cpu_total - old_total
            if delta > 0:
                percent = round(
                    max(0, min(100, 100 * (1 - (cpu_idle - old_idle) / delta))), 1
                )
                _history.append({"at": timestamp, "percent": percent})
            elapsed = clock - old_clock
            common = interfaces.keys() & old_interfaces.keys()
            if elapsed > 0 and common:
                network = {
                    "receiveBitsPerSecond": sum(
                        max(0, interfaces[n].bytes_recv - old_interfaces[n].bytes_recv)
                        for n in common
                    )
                    * 8
                    / elapsed,
                    "transmitBitsPerSecond": sum(
                        max(0, interfaces[n].bytes_sent - old_interfaces[n].bytes_sent)
                        for n in common
                    )
                    * 8
                    / elapsed,
                    "interfaceName": ", ".join(sorted(common)),
                }
        _previous = (clock, cpu_total, cpu_idle, interfaces)
        memory = psutil.virtual_memory()
        return {
            "sampledAt": timestamp,
            "cpu": {
                "percent": percent,
                "label": "CPU",
                "detail": f"{psutil.cpu_count() or 0} processori logici",
            },
            "ram": {
                "percent": memory.percent,
                "label": "RAM",
                "detail": f"{(memory.total - memory.available) / 1024**3:.1f} / {memory.total / 1024**3:.1f} GiB",
            },
            "gpu": gpu_metric(),
            "disks": disks(),
            "network": network,
            "power": power(),
            "cpuHistory": list(_history),
        }


@router.get("/server/storage")
def storage():
    return {"sampledAt": now(), "disks": disks()}


@router.get("/system/status")
def service_status():
    timestamp = now()
    services = [
        {"id": "fastapi", "label": "FastAPI", "status": "ready", "checkedAt": timestamp}
    ]
    targets = [
        (
            "ollama",
            "Ollama",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11435").rstrip("/")
            + "/api/tags",
        )
    ]
    for identifier, label in [
        ("immich", "Immich"),
        ("nextcloud", "Nextcloud"),
        ("n8n", "n8n"),
    ]:
        targets.append(
            (identifier, label, os.getenv(f"CORA_SERVICE_{identifier.upper()}_URL", ""))
        )
    for identifier, label, url in targets:
        status, detail = "unknown", "Indirizzo di controllo non configurato"
        if url:
            try:
                with urlopen(url, timeout=1) as response:
                    status = "ready" if 200 <= response.status < 400 else "error"
                detail = "Endpoint HTTP raggiungibile"
            except (OSError, ValueError):
                status, detail = "offline", "Endpoint HTTP non raggiungibile"
        services.append(
            {
                "id": identifier,
                "label": label,
                "status": status,
                "detail": detail,
                "checkedAt": timestamp,
            }
        )
    docker_status, docker_detail = (
        "unknown",
        "Docker CLI non disponibile per il backend",
    )
    containers = []
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
            containers = [
                json.loads(line) for line in result.stdout.splitlines() if line.strip()
            ]
            docker_status, docker_detail = "ready", "Docker daemon raggiungibile"
        except (OSError, ValueError, subprocess.SubprocessError):
            docker_status, docker_detail = (
                "unknown",
                "Docker non verificabile: accesso negato, daemon assente o timeout",
            )
    services.append(
        {
            "id": "docker",
            "label": "Docker",
            "status": docker_status,
            "detail": docker_detail,
            "checkedAt": timestamp,
        }
    )
    for container in containers:
        state = container.get("State", "")
        description = container.get("Status", "")
        status = (
            "error"
            if "unhealthy" in description
            else (
                "ready"
                if state == "running" and "health: starting" not in description
                else "offline" if state in ("exited", "dead") else "unknown"
            )
        )
        services.append(
            {
                "id": "docker:" + container.get("ID", ""),
                "label": container.get("Names", "Container"),
                "status": status,
                "detail": description,
                "checkedAt": timestamp,
            }
        )
    return {"checkedAt": timestamp, "services": services}
