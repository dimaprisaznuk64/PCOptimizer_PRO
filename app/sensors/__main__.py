from __future__ import annotations

import argparse

from .manager import SensorManager
from .types import Snapshot


def _gb(n: float) -> str:
    return f"{n / 1024**3:.1f}GB"


def _rate(n: float) -> str:
    if n >= 1024**2:
        return f"{n / 1024**2:.1f}MB/s"
    return f"{n / 1024:.1f}KB/s"


def render(s: Snapshot) -> str:
    lines: list[str] = []
    if s.cpu:
        c = s.cpu
        lines.append(
            f"CPU     {c.percent:5.1f}%  cores={c.physical_cores}/{c.logical_cores}  "
            f"freq={c.freq_mhz or 0:.0f}MHz"
        )
    if s.memory:
        m = s.memory
        lines.append(
            f"RAM     {m.percent:5.1f}%  used={_gb(m.used)}/{_gb(m.total)}  "
            f"swap={m.swap_percent:.1f}%"
        )
    for d in s.disks:
        lines.append(f"DISK    {d.percent:5.1f}%  {d.mountpoint}  {_gb(d.used)}/{_gb(d.total)}  {d.fstype}")
    if s.net:
        n = s.net
        lines.append(
            f"NET     up={_rate(n.send_rate)} down={_rate(n.recv_rate)}  "
            f"total up={_gb(n.bytes_sent)} down={_gb(n.bytes_recv)}"
        )
    for g in s.gpus:
        fan = f"{g.fan_percent:.0f}%" if g.fan_percent is not None else "n/a"
        temp = f"{g.temperature:.0f}C" if g.temperature is not None else "?"
        power = f"{g.power_w:.0f}W" if g.power_w is not None else "?"
        lines.append(
            f"GPU{g.index}    {g.name}  util={g.utilization:.0f}%  "
            f"vram={_gb(g.memory_used)}/{_gb(g.memory_total)}  {temp} {power} fan={fan}"
        )
    if s.thermal:
        temps = "  ".join(f"{k}={v:.0f}C" for k, v in s.thermal.temperatures)
        lines.append(f"THERMAL [{s.thermal.source}]  {temps}")
    for name, err in s.errors.items():
        lines.append(f"ERROR   {name}: {err}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.sensors", description="Sample sensors once")
    parser.add_argument("--mock", action="store_true", help="use deterministic mock backend")
    parser.add_argument("--interval", type=float, default=0.0, help="seconds between two samples")
    args = parser.parse_args(argv)

    manager = SensorManager.mock() if args.mock else SensorManager.with_defaults()
    print(f"backends: {', '.join(manager.backend_names) or 'none'}\n")
    try:
        print(render(manager.snapshot()))
        if args.interval > 0:
            import time

            time.sleep(args.interval)
            print("\n--- second sample ---")
            print(render(manager.snapshot()))
    finally:
        manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
