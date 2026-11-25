from __future__ import annotations

import json
import os
import time
import uuid
import winreg
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.changes import (
    ChangeJournal,
    ChecksumResult,
    checksum_path,
    verify_checksum,
    write_checksum,
)
from app.settings import data_root
from app.wincom import run_in_com

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
    def work() -> str:
        from win32com.client import Dispatch

        shortcut = Dispatch("WScript.Shell").CreateShortCut(path)
        target = shortcut.Targetpath or ""
        arguments = shortcut.Arguments or ""
        return f"{target} {arguments}".strip()

    try:
        return run_in_com(work)
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
        journal: ChangeJournal | None = None,
    ) -> None:
        appdata = os.environ.get("APPDATA", "")
        program_data = os.environ.get("PROGRAMDATA", "")
        self.user_startup_dir = user_startup_dir or os.path.join(
            appdata, r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        self.common_startup_dir = common_startup_dir or os.path.join(
            program_data, r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        self.backup_dir = Path(backup_dir) if backup_dir else (
            data_root() / "startup_backup"
        )
        self.run_sources = tuple(run_sources) if run_sources is not None else RUN_SOURCES
        self._journal = journal or ChangeJournal.instance()

    def backup_integrity(self) -> ChecksumResult:
        """Checksum status for the startup undo history."""
        return verify_checksum(self._history_path())

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
        task_items, task_errors = self._task_items()
        items.extend(task_items)
        errors.extend(task_errors)
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

    def _task_items(self) -> tuple[list[StartupItem], list[str]]:
        items: list[StartupItem] = []
        errors: list[str] = []
        collect_errors: list[str] = []

        def work() -> None:
            from win32com.client import Dispatch

            service = Dispatch("Schedule.Service")
            service.Connect()
            self._collect_tasks(service.GetFolder("\\"), items, collect_errors)

        try:
            run_in_com(work)
        except Exception as e:
            errors.append(f"Task Scheduler: {e}")
        if collect_errors:
            errors.append(f"Task Scheduler: partial enumeration ({len(collect_errors)} item(s) skipped)")
        if errors:
            try:
                from app.logs import get_logger

                get_logger("startup").warning("task scheduler enumeration failed: %s", "; ".join(errors))
            except Exception:
                pass
        return items, errors

    def _collect_tasks(
        self, folder, items: list[StartupItem], errors: list[str] | None = None
    ) -> None:
        error_list = errors if errors is not None else []
        try:
            tasks = folder.GetTasks(0)
            count = tasks.Count
            for index in range(1, count + 1):
                try:
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
                except Exception as e:
                    error_list.append(str(e))
                    continue
        except Exception as e:
            error_list.append(str(e))
            return
        try:
            subfolders = folder.GetFolders(0)
            for index in range(1, subfolders.Count + 1):
                try:
                    self._collect_tasks(subfolders.Item(index), items, error_list)
                except Exception as e:
                    error_list.append(str(e))
                    continue
        except Exception as e:
            error_list.append(str(e))
            return

    def set_enabled(self, item: StartupItem, enabled: bool) -> None:
        operation = "startup.enable" if enabled else "startup.disable"
        try:
            self._set_enabled(item, enabled)
        except StartupError as exc:
            self._journal.record(
                operation=operation,
                outcome="error",
                detail=str(exc)[:400],
                source="startup",
                target=item.name,
            )
            raise
        self._journal.record(
            operation=operation,
            outcome="ok",
            detail=item.source,
            source="startup",
            target=item.name,
        )

    def _set_enabled(self, item: StartupItem, enabled: bool) -> None:
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
        try:
            message = self._remove(item)
        except StartupError as exc:
            self._journal.record(
                operation="startup.remove",
                outcome="error",
                detail=str(exc)[:400],
                source="startup",
                target=item.name,
            )
            raise
        self._journal.record(
            operation="startup.remove",
            outcome="ok",
            detail=message[:400],
            source="startup",
            target=item.name,
        )
        return message

    def _remove(self, item: StartupItem) -> str:
        if item.kind == "registry":
            return self._remove_registry(item)
        if item.kind == "folder":
            return self._remove_folder(item)
        raise StartupError("scheduled tasks can only be disabled, not removed")

    def undo_last(self) -> str:
        try:
            message = self._undo_last()
        except StartupError as exc:
            self._journal.record(
                operation="startup.undo",
                outcome="error",
                detail=str(exc)[:400],
                source="startup",
            )
            raise
        self._journal.record(
            operation="startup.undo",
            outcome="ok",
            detail=message[:400],
            source="startup",
        )
        return message

    def _undo_last(self) -> str:
        lines = self._history_lines()
        if not lines:
            raise StartupError("no backup history yet")
        try:
            entry = json.loads(lines[-1])
            if not isinstance(entry, dict):
                raise ValueError("journal entry is not an object")
        except ValueError as e:
            # A crash mid-append can leave a partial last line. Drop only that
            # line so every earlier, valid undo entry stays available.
            self._write_history_lines(lines[:-1])
            raise StartupError(f"last undo entry is corrupt: {e}; older entries remain available") from e

        action = entry.get("action")
        if action == "registry":
            data: object = str(entry.get("data")) if entry.get("data") is not None else ""
            if entry.get("data_hex") is not None:
                data = bytes.fromhex(str(entry["data_hex"]))
            try:
                self._reg_set(
                    str(entry["hive"]), str(entry["key_path"]), str(entry["name"]),
                    int(entry["type"]), data,
                )
            except (OSError, KeyError, TypeError, ValueError) as e:
                raise StartupError(f"cannot restore {entry.get('name', 'item')}: {e}") from e
        elif action == "folder":
            source = Path(str(entry["stored"]))
            target = Path(str(entry["original"]))
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                source.replace(target)
            elif not target.exists():
                raise StartupError(f"backup file missing: {source}")
        else:
            self._write_history_lines(lines[:-1])
            raise StartupError(f"unknown backup action {action}")

        # Restore the previous enabled/disabled marker as part of the same undo.
        self._restore_approved(entry)
        self._write_history_lines(lines[:-1])
        return str(entry.get("description", "restored"))

    def _restore_approved(self, entry: dict) -> None:
        hive = entry.get("approved_hive")
        key_path = entry.get("approved_key")
        name = entry.get("approved_name")
        if not hive or not key_path or not name:
            return
        data_hex = entry.get("approved_data")
        try:
            if data_hex is None:
                self._approved_delete(str(hive), str(key_path), str(name))
            else:
                self._approved_set(str(hive), str(key_path), str(name), bytes.fromhex(str(data_hex)))
        except (OSError, ValueError) as e:
            raise StartupError(f"cannot restore enabled state for {name}: {e}") from e

    def _remove_registry(self, item: StartupItem) -> str:
        if item.hive is None or item.key_path is None or item.approved_name is None:
            raise StartupError("item is missing registry locators")
        try:
            data, value_type = self._reg_query(item.hive, item.key_path, item.approved_name)
        except OSError as e:
            raise StartupError(f"cannot read {item.name}: {e}") from e
        data_hex = data.hex() if isinstance(data, (bytes, bytearray)) else None
        try:
            approved_data, _approved_type = self._reg_query(
                item.hive, APPROVED_RUN, item.approved_name
            )
        except FileNotFoundError:
            approved_hex = None
        except OSError as e:
            raise StartupError(f"cannot read disabled state of {item.name}: {e}") from e
        else:
            approved_hex = (
                bytes(approved_data).hex() if isinstance(approved_data, (bytes, bytearray)) else None
            )
        entry = {
            "action": "registry",
            "ts": time.time(),
            "hive": item.hive,
            "key_path": item.key_path,
            "name": item.approved_name,
            "type": value_type,
            "data": None if data_hex is not None else str(data),
            "data_hex": data_hex,
            "approved_hive": item.hive,
            "approved_key": APPROVED_RUN,
            "approved_name": item.approved_name,
            "approved_data": approved_hex,
            "description": f"registry value {item.name}",
        }
        # Record the undo data BEFORE the destructive step, so a crash between
        # the write and the journal entry can never lose the original value.
        self._append_history(entry)
        try:
            self._reg_delete(item.hive, item.key_path, item.approved_name)
        except OSError as e:
            self._drop_last_history()
            raise StartupError(f"cannot remove {item.name}: {e} (administrator rights may be required)") from e
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
        stored = removed_dir / f"{stamp}_{uuid.uuid4().hex[:8]}_{source.name}"
        try:
            approved_data, _approved_type = (
                self._reg_query("HKCU", APPROVED_FOLDER, item.approved_name)
                if item.approved_name is not None
                else (None, None)
            )
        except FileNotFoundError:
            approved_hex = None
        except OSError as e:
            raise StartupError(f"cannot read disabled state of {item.name}: {e}") from e
        else:
            approved_hex = (
                bytes(approved_data).hex() if isinstance(approved_data, (bytes, bytearray)) else None
            )
        entry = {
            "action": "folder",
            "ts": time.time(),
            "original": str(source),
            "stored": str(stored),
            "approved_hive": "HKCU",
            "approved_key": APPROVED_FOLDER,
            "approved_name": item.approved_name,
            "approved_data": approved_hex,
            "description": f"startup shortcut {item.name}",
        }
        # Journal before moving the file so the undo data exists even if the
        # move itself fails midway.
        self._append_history(entry)
        try:
            source.replace(stored)
        except OSError as e:
            self._drop_last_history()
            raise StartupError(f"cannot move {item.name}: {e}") from e
        return f"removed {item.name} (backup saved)"

    def _history_path(self) -> Path:
        return self.backup_dir / "history.jsonl"

    def _history_lines(self) -> list[str]:
        history = self._history_path()
        if not history.exists():
            return []
        check = verify_checksum(history)
        if not check.valid:
            quarantine = self._quarantine_history()
            hint = f" (saved as {quarantine})" if quarantine else ""
            raise StartupError(
                f"undo history checksum {check.status}: {check.detail}{hint} — refusing to use it"
            )
        try:
            return [line for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError as e:
            raise StartupError(f"cannot read undo history: {e}") from e

    def _write_history_lines(self, lines: list[str]) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        history = self._history_path()
        tmp = history.with_name(f".{history.name}.{os.getpid()}.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                if lines:
                    f.write("\n".join(lines) + "\n")
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(history)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            raise StartupError(f"cannot write undo history: {e}") from e
        try:
            write_checksum(history)
        except OSError:
            checksum_path(history).unlink(missing_ok=True)

    def _quarantine_history(self) -> str | None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        history = self._history_path()
        target = history.with_name(f"{history.name}.corrupt-{stamp}")
        try:
            history.replace(target)
            try:
                checksum_path(history).replace(target.with_name(f"{target.name}.sha256"))
            except OSError:
                pass
            return str(target)
        except OSError:
            return None

    def _append_history(self, entry: dict) -> None:
        lines = self._history_lines()
        lines.append(json.dumps(entry, ensure_ascii=False))
        self._write_history_lines(lines)

    def _drop_last_history(self) -> None:
        """Roll back the most recent journal entry (the change it describes failed)."""
        lines = self._history_lines()
        if lines:
            self._write_history_lines(lines[:-1])

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
            winreg.SetValueEx(key, name, 0, value_type, data)  # type: ignore[call-overload]

    def _reg_delete(self, hive: str, key_path: str, name: str) -> None:
        with winreg.OpenKey(_hive(hive), key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)

    def _task_set_enabled(self, item: StartupItem, enabled: bool) -> None:
        if item.task_path is None:
            raise StartupError("item is missing task locator")

        def work() -> None:
            from win32com.client import Dispatch

            service = Dispatch("Schedule.Service")
            service.Connect()
            task = service.GetFolder("\\").GetTask(item.task_path)
            task.Enabled = bool(enabled)

        try:
            run_in_com(work)
        except Exception as e:
            raise StartupError(f"cannot change task {item.name}: {e}") from e
