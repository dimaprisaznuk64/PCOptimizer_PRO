"""Sensor spike: verify which data sources work on this PC.

Run: python scripts/sensor_spike.py
Exit code 0 = enough data for Dashboard; failures are reported per-source.
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        val = fn()
        results.append((name, True, str(val)))
    except Exception as e:  # noqa: BLE001
        results.append((name, False, f"{type(e).__name__}: {e}"))


def cpu_info() -> str:
    import psutil

    f = psutil.cpu_freq()
    return (
        f"cores={psutil.cpu_count(logical=False)}/{psutil.cpu_count()} "
        f"freq={f.current:.0f}MHz (max {f.max:.0f}) usage={psutil.cpu_percent(interval=1):.1f}%"
    )


def ram_info() -> str:
    import psutil

    m = psutil.virtual_memory()
    return f"total={m.total / 2**30:.1f}GB used={m.used / 2**30:.1f}GB ({m.percent}%)"


def disk_info() -> str:
    import psutil

    parts = []
    for p in psutil.disk_partitions(all=False):
        if not shutil.disk_usage if False else True:
            pass
        try:
            u = psutil.disk_usage(p.mountpoint)
        except OSError:
            continue
        if u.total > 0:
            parts.append(f"{p.mountpoint} {u.total / 2**30:.0f}GB {u.percent}%")
    return "; ".join(parts)


def net_info() -> str:
    import psutil

    c = psutil.net_io_counters()
    return f"sent={c.bytes_sent / 2**20:.1f}MB recv={c.bytes_recv / 2**20:.1f}MB"


def gpu_info() -> str:
    import pynvml

    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(0)
    name = pynvml.nvmlDeviceGetName(h)
    if isinstance(name, bytes):
        name = name.decode()
    util = pynvml.nvmlDeviceGetUtilizationRates(h)
    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
    try:
        temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
    except pynvml.NVMLError:
        temp = "?"
    power = pynvml.nvmlDeviceGetPowerUsage(h) / 1000
    try:
        fan = f"{pynvml.nvmlDeviceGetFanSpeed(h)}%"
    except pynvml.NVMLError:
        fan = "n/a"
    pynvml.nvmlShutdown()
    return (
        f"{name} util={util.gpu}% vram={mem.used / 2**20:.0f}/{mem.total / 2**20:.0f}MB "
        f"temp={temp}C power={power:.0f}W fan={fan}"
    )


def temp_wmi() -> str:
    import wmi

    t = wmi.WMI(namespace="root\\wmi").MSAcpi_ThermalZoneTemperature()
    if not t:
        raise RuntimeError("no thermal zones")
    vals = [x.CurrentTemperature / 10 - 273.15 for x in t]
    return "; ".join(f"{v:.0f}C" for v in vals)


def temp_powershell() -> str:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_TemperatureZone).CurrentTemperature"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(out.stderr.strip() or "no data")
    return out.stdout.strip()


def cpu_temp_lhm() -> str:
    """LibreHardwareMonitor-style: OpenHardwareMonitor WMI namespace if running."""
    import wmi

    c = wmi.WMI(namespace="root\\OpenHardwareMonitor")
    sensors = c.Sensor()
    temps = [s for s in sensors if s.SensorType == "Temperature"]
    if not temps:
        raise RuntimeError("LHM not running / no sensors")
    return "; ".join(f"{s.Name}={s.Value:.0f}C" for s in temps)


def os_info() -> str:
    return f"{platform.platform()}"


def main() -> int:
    check("OS", os_info)
    check("CPU", cpu_info)
    check("RAM", ram_info)
    check("Disks", disk_info)
    check("Network", net_info)
    check("GPU (nvidia-ml-py)", gpu_info)
    check("Temp via WMI ACPI", temp_wmi)
    check("Temp via PowerShell", temp_powershell)
    check("Temp via LibreHardwareMonitor", cpu_temp_lhm)

    print("\n=== SENSOR SPIKE RESULTS ===")
    ok = 0
    for name, success, detail in results:
        mark = "OK  " if success else "FAIL"
        print(f"[{mark}] {name}: {detail}")
        ok += success

    print(f"\n{ok}/{len(results)} sources available")
    return 0 if ok >= 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
