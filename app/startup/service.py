from __future__ import annotations

import json
import os
import time
import winreg
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

APPROVED_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
APPROVED_FOLDER = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"

RUN_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU Run"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM Run"),
    ("HKLM", r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM Run (32-bit)"),
)

HIGH_KEYWORDS = (
    "update",
    "updater",
    "steam",
    "discord",
    "epicgames",
    "battle.net",
    "riot",
    "adobe",
    "acrobat",
    "teams",
    "spotify",
    "onedrive",
    "dropbox",
    "geforce",
    "nvidia",
    "icue",
    "razer",
    "logi",
    "obs",
    "zoom",
)
MEDIUM_KEYWORDS = (
    "sync",
    "backup",
    "security",
    "antivirus",
    "realtek",
    "bluetooth",
    "printer",
    "chat",
    "cloud",
    "audio",
    "skype",
    "slack",
    "helper",
    "launcher",
)

DISABLED_FLAG = bytes([0x02]) + bytes(15)


class StartupError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StartupItem:
    id: str
    name: str
    source: str
    kind: str
    command: str
    location: str
    enabled: bool
    impact: str
    impact_reason: str
    target_size: int | None = None
    hive: str | None = None
    key_path: str | None = None
    approved_name: str | None = None
    file_path: str | None = None
    task_path: str | None = None


def approved_enabled(data: bytes | bytearray | None) -> bool:
    if not data:
        return True
    return data[0] not in (0x02, 0x03)


def impact_of(name: str, size: int | None) -> tuple[str, str]:
    if size is not None and size >= 100 * 1024**2:
        return "High", f"large target ({size // 1024**2}MB)"
    lower = name.lower()
    if any(keyword in lower for keyword in HIGH_KEYWORDS):
        return "High", "known heavyweight app"
    if size is not None and size >= 20 * 1024**2:
        return "Medium", f"medium target ({size // 1024**2}MB)"
    if any(keyword in lower for keyword in MEDIUM_KEYWORDS):
        return "Medium", "common background app"
    if size is not None:
        return "Low", f"small target ({max(size // 1024, 1)}KB)"
    return "Low", "lightweight or unknown target"


def _hive(hive: str):
    if hive == "HKCU":
        return winreg.HKEY_CURRENT_USER
    if hive == "HKLM":
        return winreg.HKEY_LOCAL_MACHINE
    raise StartupError(f"unknown hive {hive}")


def _resolve_command(command: str) -> str:
    return os.path.expandvars(command.strip())


def _target_size(command: str) -> int | None:
    resolved = _resolve_command(command)
    if not resolved:
        return None
    if resolved.startswith('"'):
        candidate = resolved.split('"', 2)[1]
    else:
        candidate = resolved.split(" ", 1)[0]
    candidate = candidate.strip('"')
    try:
        return os.path.getsize(candidate)
    except OSError:
        return None


def _resolve_lnk(path: str) -> str:
    try:
        import pythoncom
        from win32com.shell import shell
        from win32com.client import Dispatch

        pythoncom.CoInitialize()
        try:
            shortcut = Dispatch("WScript.Shell").CreateShortCut(path)
            target = shortcut.Targetpath or ""
            arguments = shortcut.Arguments or ""
            return f"{target} {arguments}".strip()
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        return path


class StartupService:
    def __init__(
        self,
        *,
        user_startup_dir: str | None = None,
        common_startup_dir: str | None = None,
        backup_dir: str | Path | None = None,
        run_sources: Sequence[tuple[str, str, str]] | None = None,
    ) -> None:
        appdata = os.environ.get("APPDATA", "")
        program_data = os.environ.get("PROGRAMDATA", "")
        local = os.environ.get("LOCALAPPDATA", "")
        self.user_startup_dir = user_startup_dir or os.path.join(
            appdata, r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        self.common_startup_dir = common_startup_dir or os.path.join(
            program_data, r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        self.backup_dir = Path(backup_dir) if backup_dir else (
            Path(local) / "PCOptimizer_PRO" / "startup_backup"
        )
        self.run_sources = tuple(run_sources) if run_sources is not None else RUN_SOURCES

    def list_items(self) -> tuple[list[StartupItem], list[str]]:
        items: list[StartupItem] = []
        errors: list[str] = []
        for hive, key_path, label in self.run_sources:
            try:
                items.extend(self._registry_items(hive, key_path, label))
            except OSError as e:
                errors.append(f"{label}: {e}")
        for folder, label in (
            (self.user_startup_dir, "Startup folder"),
            (self.common_startup_dir, "Startup folder (common)"),
        ):
            try:
                items.extend(self._folder_items(folder, label))
            except OSError as e:
                errors.append(f"{label}: {e}")
        try:
            items.extend(self._task_items())
        except Exception as e:
            errors.append(f"Task Scheduler: {e}")
        items.sort(key=lambda i: ({"High": 0, "Medium": 1, "Low": 2}.get(i.impact, 3), i.name.lower()))
        return items, errors

    def _registry_items(self, hive: str, key_path: str, label: str) -> list[StartupItem]:
        items: list[StartupItem] = []
        try:
            values = self._reg_enum_values(hive, key_path)
        except FileNotFoundError:
            return []
        for name, data, value_type in values:
            if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not name:
                continue
            command = str(data)
            approved = self._approved_get(hive, APPROVED_RUN, name)
            size = _target_size(command)
            impact, reason = impact_of(name, size)
            items.append(
                StartupItem(
                    id=f"registry:{hive}:{key_path}:{name}".lower(),
                    name=name,
                    source=label,
                    kind="registry",
                    command=command,
                    location=f"{hive}\\{key_path}",
                    enabled=approved_enabled(approved),
                    impact=impact,
                    impact_reason=reason,
                    target_size=size,
                    hive=hive,
                    key_path=key_path,
                    approved_name=name,
                )
            )
        return items

    def _folder_items(self, folder: str, label: str) -> list[StartupItem]:
        items: list[StartupItem] = []
        if not os.path.isdir(folder):
            return items
        for entry in sorted(os.scandir(folder), key=lambda e: e.name.lower()):
            if not entry.is_file(follow_symlinks=False) or not entry.name.lower().endswith(".lnk"):
                continue
            command = _resolve_lnk(entry.path)
            approved = self._approved_get("HKCU", APPROVED_FOLDER, entry.name)
            size = _target_size(command)
            impact, reason = impact_of(entry.name, size)
            items.append(
                StartupItem(
                    id=f"folder:{entry.path}".lower(),
                    name=entry.name,
                    source=label,
                    kind="folder",
                    command=command,
                    location=folder,
                    enabled=approved_enabled(approved),
                    impact=impact,
                    impact_reason=reason,
                    target_size=size,
                    approved_name=entry.name,
                    file_path=entry.path,
                )
            )
        return items

    def _task_items(self) -> list[StartupItem]:
        import pythoncom
        from win32com.client import Dispatch

        pythoncom.CoInitialize()
        try:
            service = Dispatch("Schedule.Service")
            service.Connect()
            folder = service.GetFolder("\\")
            tasks = folder.GetTasks(0)
        finally:
            pythoncom.CoUninitialize()

        items: list[StartupItem] = []
        count = tasks.Count
        for index in range(1, count + 1):
            task = tasks.Item(index)
            triggers = task.Definition.Triggers
            trigger_types = [triggers.Item(i).Type for i in range(1, triggers.Count + 1)]
            if not any(t in (8, 9) for t in trigger_types):
                continue
            actions = task.Definition.Actions
            command = ""
            if actions.Count >= 1:
                action = actions.Item(1)
                command = str(getattr(action, "Path", "") or "")
                arguments = str(getattr(action, "Arguments", "") or "")
                if arguments:
                    command = f"{command} {arguments}".strip()
            size = _target_size(command) if command else None
            impact, reason = impact_of(task.Name, size)
            items.append(
                StartupItem(
                    id=f"task:{task.Path}".lower(),
                    name=task.Name,
                    source="Task Scheduler",
                    kind="task",
                    command=command,
                    location=task.Path,
                    enabled=bool(task.Enabled),
                    impact=impact,
                    impact_reason=reason,
                    target_size=size,
                    task_path=task.Path,
                )
            )
        return items

    def set_enabled(self, item: StartupItem, enabled: bool) -> None:
        if item.kind == "registry":
            if item.hive is None or item.approved_name is None:
                raise StartupError("item is missing registry locators")
            if enabled:
                self._approved_delete(item.hive, APPROVED_RUN, item.approved_name)
            else:
                self._approved_set(item.hive, APPROVED_RUN, item.approved_name, DISABLED_FLAG)
            return
        if item.kind == "folder":
            if item.approved_name is None:
                raise StartupError("item is missing folder locator")
            if enabled:
                self._approved_delete("HKCU", APPROVED_FOLDER, item.approved_name)
            else:
                self._approved_set("HKCU", APPROVED_FOLDER, item.approved_name, DISABLED_FLAG)
            return
        if item.kind == "task":
            self._task_set_enabled(item, enabled)
            return
        raise StartupError(f"cannot toggle {item.kind}")

    def remove(self, item: StartupItem) -> str:
        if item.kind == "registry":
            return self._remove_registry(item)
        if item.kind == "folder":
            return self._remove_folder(item)
        raise StartupError("scheduled tasks can only be disabled, not removed")

    def undo_last(self) -> str:
        history = self._history_path()
        if not history.exists():
            raise StartupError("no backup history yet")
        lines = [line for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            raise StartupError("no backup history yet")
        entry = json.loads(lines[-1])
        if entry["action"] == "registry":
            data: object = str(entry["data"]) if entry["data"] is not None else ""
            if entry["data_hex"] is not None:
                data = bytes.fromhex(entry["data_hex"])
            try:
                self._reg_set(entry["hive"], entry["key_path"], entry["name"], int(entry["type"]), data)
            except OSError as e:
                raise StartupError(f"cannot restore {entry['name']}: {e}") from e
        elif entry["action"] == "folder":
            source = Path(entry["stored"])
            target = Path(entry["original"])
            if not source.exists():
                raise StartupError(f"backup file missing: {source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
        else:
            raise StartupError(f"unknown backup action {entry['action']}")
        history.write_text("\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")
        return entry.get("description", "restored")

    def _remove_registry(self, item: StartupItem) -> str:
        if item.hive is None or item.key_path is None or item.approved_name is None:
            raise StartupError("item is missing registry locators")
        try:
            data, value_type = self._reg_query(item.hive, item.key_path, item.approved_name)
        except OSError as e:
            raise StartupError(f"cannot read {item.name}: {e}") from e
        data_hex = data.hex() if isinstance(data, (bytes, bytearray)) else None
        entry = {
            "action": "registry",
            "ts": time.time(),
            "hive": item.hive,
            "key_path": item.key_path,
            "name": item.approved_name,
            "type": value_type,
            "data": None if data_hex is not None else str(data),
            "data_hex": data_hex,
            "description": f"registry value {item.name}",
        }
        try:
            self._reg_delete(item.hive, item.key_path, item.approved_name)
        except OSError as e:
            raise StartupError(f"cannot remove {item.name}: {e} (administrator rights may be required)") from e
        self._append_history(entry)
        return f"removed {item.name} (backup saved)"

    def _remove_folder(self, item: StartupItem) -> str:
        if item.file_path is None:
            raise StartupError("item is missing file locator")
        source = Path(item.file_path)
        if not source.exists():
            raise StartupError(f"{item.name} no longer exists")
        removed_dir = self.backup_dir / "removed"
        removed_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        stored = removed_dir / f"{stamp}_{source.name}"
        try:
            source.replace(stored)
        except OSError as e:
            raise StartupError(f"cannot move {item.name}: {e}") from e
        entry = {
            "action": "folder",
            "ts": time.time(),
            "original": str(source),
            "stored": str(stored),
            "description": f"startup shortcut {item.name}",
        }
        self._append_history(entry)
        return f"removed {item.name} (backup saved)"

    def _history_path(self) -> Path:
        return self.backup_dir / "history.jsonl"

    def _append_history(self, entry: dict) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        history = self._history_path()
        with history.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _approved_get(self, hive: str, key_path: str, name: str) -> bytes | None:
        try:
            data, _value_type = self._reg_query(hive, key_path, name)
        except OSError:
            return None
        return bytes(data) if isinstance(data, (bytes, bytearray)) else None

    def _approved_set(self, hive: str, key_path: str, name: str, data: bytes) -> None:
        try:
            self._reg_set(hive, key_path, name, winreg.REG_BINARY, data)
        except OSError as e:
            raise StartupError(f"cannot write {name}: {e} (administrator rights may be required)") from e

    def _approved_delete(self, hive: str, key_path: str, name: str) -> None:
        try:
            self._reg_delete(hive, key_path, name)
        except FileNotFoundError:
            return
        except OSError as e:
            raise StartupError(f"cannot enable {name}: {e} (administrator rights may be required)") from e

    def _reg_enum_values(self, hive: str, key_path: str) -> list[tuple[str, object, int]]:
        with winreg.OpenKey(_hive(hive), key_path, 0, winreg.KEY_READ) as key:
            values: list[tuple[str, object, int]] = []
            index = 0
            while True:
                try:
                    name, data, value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                values.append((name, data, value_type))
            return values

    def _reg_query(self, hive: str, key_path: str, name: str) -> tuple[object, int]:
        with winreg.OpenKey(_hive(hive), key_path, 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, name)

    def _reg_set(self, hive: str, key_path: str, name: str, value_type: int, data: object) -> None:
        with winreg.CreateKeyEx(_hive(hive), key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, value_type, data)

    def _reg_delete(self, hive: str, key_path: str, name: str) -> None:
        with winreg.OpenKey(_hive(hive), key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)

    def _task_set_enabled(self, item: StartupItem, enabled: bool) -> None:
        if item.task_path is None:
            raise StartupError("item is missing task locator")
        import pythoncom
        from win32com.client import Dispatch

        pythoncom.CoInitialize()
        try:
            service = Dispatch("Schedule.Service")
            service.Connect()
            task = service.GetFolder("\\").GetTask(item.task_path)
            task.Enabled = bool(enabled)
        except Exception as e:
            raise StartupError(f"cannot change task {item.name}: {e}") from e
        finally:
            pythoncom.CoUninitialize()
