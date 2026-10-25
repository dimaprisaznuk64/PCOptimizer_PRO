from __future__ import annotations

import time

import pytest

from app.optimizer import (
    GUID_BALANCED,
    GUID_HIGH_PERF,
    OptimizerError,
    OptimizerService,
)
from app.optimizer.service import (
    GAMEMODE_KEY,
    GAMEMODE_VALUE,
    HAGS_KEY,
    HAGS_VALUE,
    VISUAL_KEY,
    VISUAL_PERFORMANCE,
    VISUAL_VALUE,
    parse_active_guid,
)
from app.restore import STATUS_CREATED, STATUS_ERROR, RestoreResult
from app.ui.optimizer import OptimizerPage


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------- fake infrastructure ----------


class FakeSystem:
    """In-memory power plan + registry; never touches the real machine."""

    def __init__(self) -> None:
        self.power_guid = GUID_BALANCED
        self.reg: dict[tuple[str, str, str], int] = {
            ("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE): 1,
            ("HKCU", VISUAL_KEY, VISUAL_VALUE): 0,
        }
        self.commands: list[tuple[str, ...]] = []
        self.elevated: list[tuple[str, ...]] = []
        self.admin = False
        self.fail_powercfg = False
        self.fail_restore = False
        self.restore = FakeRestore()

    def run(self, args, timeout):
        args = tuple(str(a) for a in args)
        self.commands.append(args)
        if args[:2] == ("powercfg", "/getactivescheme"):
            if self.fail_powercfg:
                return 1, "error"
            return 0, f"power scheme GUID: {self.power_guid} (name)"
        if args[:2] == ("powercfg", "/setactive"):
            if self.fail_powercfg:
                return 1, "denied"
            self.power_guid = args[2].lower()
            return 0, ""
        if "Checkpoint-Computer" in " ".join(args):
            if self.fail_restore:
                return 1, "restore point service unavailable"
            return 0, ""
        return 0, ""

    def elevate(self, args) -> bool:
        args = tuple(str(a) for a in args)
        self.elevated.append(args)
        joined = " ".join(args)
        # elevated HKLM write
        if "HwSchMode" in joined and "-Value" in joined:
            for a in args:
                if "HwSchMode" in a and "-Value" in a:
                    value = int(a.split("-Value")[1].strip().strip("'\""))
                    self.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] = value
        # elevated HKLM delete
        elif "Remove-ItemProperty" in joined and "HwSchMode" in joined:
            self.reg.pop(("HKLM", HAGS_KEY, HAGS_VALUE), None)
        return True

    def reg_get(self, hive: str, key: str, name: str) -> int:
        try:
            return self.reg[(hive, key, name)]
        except KeyError:
            raise FileNotFoundError(name) from None

    def reg_set(self, hive: str, key: str, name: str, value: int) -> None:
        self.reg[(hive, key, name)] = int(value)

    def reg_delete(self, hive: str, key: str, name: str) -> None:
        try:
            del self.reg[(hive, key, name)]
        except KeyError:
            raise FileNotFoundError(name) from None

    def is_admin(self) -> bool:
        return self.admin

    def make_service(self, tmp_path) -> OptimizerService:
        return OptimizerService(
            run=self.run,
            elevate=self.elevate,
            is_admin=self.is_admin,
            reg_get=self.reg_get,
            reg_set=self.reg_set,
            reg_delete=self.reg_delete,
            backup_path=tmp_path / "backup.json",
            restore=self.restore,
        )


class FakeRestore:
    """Records restore-point requests without touching Windows."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail = False

    def create(self, label: str) -> RestoreResult:
        self.calls.append(label)
        if self.fail:
            return RestoreResult(False, STATUS_ERROR, "restore point service unavailable", label=label)
        return RestoreResult(True, STATUS_CREATED, "created", label=label, sequence=1)

    def list_points(self):
        return []

    def enable_protection(self) -> RestoreResult:
        return RestoreResult(True, STATUS_CREATED, "enabled")


@pytest.fixture()
def fake(tmp_path):
    return FakeSystem()


# ---------- parsing ----------


def test_parse_active_guid_english() -> None:
    out = "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)"
    assert parse_active_guid(out) == GUID_BALANCED


def test_parse_active_guid_ukrainian_localized() -> None:
    out = "GUID схеми живлення: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (Висока продуктивність)"
    assert parse_active_guid(out) == GUID_HIGH_PERF


def test_parse_active_guid_no_match() -> None:
    assert parse_active_guid("something went wrong") is None


# ---------- state ----------


def test_state_reads_power_and_registry(fake, tmp_path) -> None:
    service = fake.make_service(tmp_path)
    state = service.state()
    assert state.power_guid == GUID_BALANCED
    assert state.power_name == "Balanced"
    assert state.game_mode is True
    assert state.hags is None  # not set
    assert state.visual_fx == 0
    assert state.errors == ()


def test_state_hags_true_when_2(fake, tmp_path) -> None:
    fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] = 2
    fake.admin = True
    state = fake.make_service(tmp_path).state()
    assert state.hags is True


def test_state_powercfg_failure_reports_error(fake, tmp_path) -> None:
    fake.fail_powercfg = True
    state = fake.make_service(tmp_path).state()
    assert state.power_guid is None
    assert any("power plan" in e for e in state.errors)


# ---------- apply profiles ----------


def test_apply_gaming_sets_all(fake, tmp_path) -> None:
    fake.admin = True
    service = fake.make_service(tmp_path)
    report = service.apply_profile("GAMING")
    assert report.errors == ()
    assert fake.power_guid == GUID_HIGH_PERF
    assert fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] == 1
    assert fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] == 2
    assert any("power plan" in a for a in report.applied)
    assert any("Game Mode" in a for a in report.applied)
    assert any("GPU scheduling" in a for a in report.applied)


def test_apply_performance_sets_visual(fake, tmp_path) -> None:
    fake.admin = True
    service = fake.make_service(tmp_path)
    report = service.apply_profile("PERFORMANCE")
    assert report.errors == ()
    assert fake.reg[("HKCU", VISUAL_KEY, VISUAL_VALUE)] == VISUAL_PERFORMANCE
    assert fake.power_guid == GUID_HIGH_PERF


def test_apply_balanced_only_power(fake, tmp_path) -> None:
    fake.power_guid = GUID_HIGH_PERF
    service = fake.make_service(tmp_path)
    report = service.apply_profile("BALANCED")
    assert report.errors == ()
    assert fake.power_guid == GUID_BALANCED
    assert fake.reg[("HKCU", VISUAL_KEY, VISUAL_VALUE)] == 0
    assert len(report.applied) == 2


def test_apply_unknown_profile_raises(fake, tmp_path) -> None:
    with pytest.raises(OptimizerError):
        fake.make_service(tmp_path).apply_profile("TURBO")


def test_apply_without_restore_point(fake, tmp_path) -> None:
    service = fake.make_service(tmp_path)
    report = service.apply_profile("BALANCED", with_restore_point=False)
    assert report.restore_point is None
    assert fake.restore.calls == []


def test_restore_point_created_before_changes(fake, tmp_path) -> None:
    service = fake.make_service(tmp_path)
    report = service.apply_profile("BALANCED")
    assert fake.restore.calls, "a restore point should be requested"
    assert "PCOptimizer_PRO BALANCED" in fake.restore.calls[0]
    assert report.restore_point is not None
    assert report.restore_status == STATUS_CREATED
    # restore point happens before any actual change
    assert any(c[:2] == ("powercfg", "/setactive") for c in fake.commands)


def test_restore_point_failure_blocks_apply(fake, tmp_path) -> None:
    fake.restore.fail = True
    service = fake.make_service(tmp_path)
    report = service.apply_profile("GAMING")
    assert report.applied == ()
    assert any("restore point" in e for e in report.errors)
    assert report.restore_status == STATUS_ERROR
    # nothing was changed
    assert fake.power_guid == GUID_BALANCED


def test_hags_without_admin_uses_elevation(fake, tmp_path) -> None:
    fake.admin = False
    service = fake.make_service(tmp_path)
    report = service.apply_profile("GAMING")
    assert report.errors == ()
    assert fake.elevated  # elevation requested
    assert fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] == 2


def test_hags_uac_cancel_reports_error(fake, tmp_path) -> None:
    fake.admin = False

    def refuse(args) -> bool:
        fake.elevated.append(tuple(str(a) for a in args))
        return False

    fake.elevate = refuse
    service = fake.make_service(tmp_path)
    report = service.apply_profile("GAMING")
    assert report.applied  # power + game mode still applied
    assert any("UAC" in e for e in report.errors)


def test_hags_write_not_applied_reports_error(fake, tmp_path) -> None:
    # Elevation "succeeds" but the value stays off — we must not claim success.
    fake.admin = False

    def ignored_write(args) -> bool:
        fake.elevated.append(tuple(str(a) for a in args))
        fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] = 1  # still disabled
        return True

    fake.elevate = ignored_write
    service = fake.make_service(tmp_path)
    report = service.apply_profile("GAMING", with_restore_point=False)
    assert any("HAGS" in e for e in report.errors)
    assert not any("GPU scheduling" in a for a in report.applied)


# ---------- revert ----------


def test_revert_restores_backup(fake, tmp_path) -> None:
    fake.admin = True
    fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] = 1
    fake.reg[("HKCU", VISUAL_KEY, VISUAL_VALUE)] = 3
    fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] = 0
    service = fake.make_service(tmp_path)

    service.apply_profile("GAMING")
    assert fake.power_guid == GUID_HIGH_PERF
    assert fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] == 1

    report = service.revert()
    assert report.errors == ()
    assert fake.power_guid == GUID_BALANCED
    assert fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] == 0
    assert fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] == 1


def test_revert_removes_values_that_were_absent(fake, tmp_path) -> None:
    # HAGS and Game Mode were not present before applying; after revert the
    # values the profile created must be removed, not left behind.
    fake.admin = True
    fake.reg.pop(("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE), None)
    fake.reg.pop(("HKLM", HAGS_KEY, HAGS_VALUE), None)
    assert ("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE) not in fake.reg
    service = fake.make_service(tmp_path)
    service.apply_profile("GAMING")
    assert fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] == 1
    assert fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] == 2

    report = service.revert()
    assert report.errors == ()
    assert ("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE) not in fake.reg
    assert ("HKLM", HAGS_KEY, HAGS_VALUE) not in fake.reg
    assert any("removed" in a for a in report.applied)


def test_revert_removes_hags_without_admin(fake, tmp_path) -> None:
    fake.admin = False
    service = fake.make_service(tmp_path)
    service.apply_profile("GAMING")
    assert ("HKLM", HAGS_KEY, HAGS_VALUE) in fake.reg

    report = service.revert()
    assert report.errors == ()
    assert ("HKLM", HAGS_KEY, HAGS_VALUE) not in fake.reg
    assert any("Remove-ItemProperty" in " ".join(a) for a in fake.elevated)


def test_revert_without_backup_raises(fake, tmp_path) -> None:
    with pytest.raises(OptimizerError):
        fake.make_service(tmp_path).revert()


def test_backup_exists(fake, tmp_path) -> None:
    service = fake.make_service(tmp_path)
    assert not service.backup_exists()
    service.apply_profile("BALANCED", with_restore_point=False)
    assert service.backup_exists()


def test_revert_clears_backup_when_clean(fake, tmp_path) -> None:
    fake.admin = True
    service = fake.make_service(tmp_path)
    service.apply_profile("GAMING")
    assert service.backup_exists()
    service.revert()
    assert not service.backup_exists()


def test_revert_keeps_backup_on_errors(fake, tmp_path) -> None:
    fake.admin = True
    service = fake.make_service(tmp_path)
    service.apply_profile("GAMING")
    fake.fail_powercfg = True
    report = service.revert()
    assert report.errors
    # A partial revert must keep the backup so the user can retry.
    assert service.backup_exists()


def test_revert_restores_original_state_after_switching_profiles(fake, tmp_path) -> None:
    fake.admin = True
    fake.power_guid = GUID_BALANCED
    fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] = 1
    fake.reg[("HKCU", VISUAL_KEY, VISUAL_VALUE)] = 3
    fake.reg.pop(("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE), None)
    service = fake.make_service(tmp_path)

    service.apply_profile("GAMING", with_restore_point=False)
    assert service.original_profile() == "GAMING"
    assert service.backup_profile() == "GAMING"
    # GAMING should have changed things
    assert fake.power_guid == GUID_HIGH_PERF
    assert fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] == 2
    assert fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] == 1

    # Switching to another profile must NOT overwrite the original backup
    service.apply_profile("PERFORMANCE", with_restore_point=False)
    assert service.original_profile() == "GAMING"
    assert service.backup_profile() == "PERFORMANCE"

    report = service.revert()
    assert report.errors == ()
    # Must restore back to original Windows state captured on first apply()
    assert fake.power_guid == GUID_BALANCED
    assert fake.reg[("HKLM", HAGS_KEY, HAGS_VALUE)] == 1
    assert fake.reg[("HKCU", VISUAL_KEY, VISUAL_VALUE)] == 3
    assert ("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE) not in fake.reg
    assert not service.backup_exists()


def test_backup_profile_recorded(fake, tmp_path) -> None:
    service = fake.make_service(tmp_path)
    assert service.backup_profile() is None
    service.apply_profile("GAMING", with_restore_point=False)
    assert service.backup_profile() == "GAMING"


def test_second_profile_apply_keeps_original_backup(fake, tmp_path) -> None:
    # Switching profiles must not overwrite the snapshot of the original state.
    fake.admin = True
    service = fake.make_service(tmp_path)
    service.apply_profile("GAMING", with_restore_point=False)
    service.apply_profile("PERFORMANCE", with_restore_point=False)

    assert service.original_profile() == "GAMING"
    assert service.backup_profile() == "PERFORMANCE"

    report = service.revert()
    assert report.errors == ()
    assert fake.power_guid == GUID_BALANCED
    assert fake.reg[("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)] == 1
    assert ("HKLM", HAGS_KEY, HAGS_VALUE) not in fake.reg
    assert fake.reg[("HKCU", VISUAL_KEY, VISUAL_VALUE)] == 0


def test_default_elevate_waits_for_the_elevated_process(monkeypatch) -> None:
    import base64

    captured: dict[str, tuple[str, ...]] = {}

    def fake_run(args, timeout):
        captured["args"] = tuple(str(a) for a in args)
        return 0, ""

    monkeypatch.setattr(OptimizerService, "_default_run", staticmethod(fake_run))
    ok = OptimizerService._default_elevate(
        ("powershell", "-NoProfile", "-Command", "Set-ItemProperty -Name HwSchMode -Value 2")
    )
    assert ok is True
    args = captured["args"]
    encoded = args[args.index("-EncodedCommand") + 1]
    script = base64.b64decode(encoded).decode("utf-16-le")
    assert "Start-Process" in script
    assert "-Verb RunAs" in script
    assert "-Wait" in script
    assert "Set-ItemProperty -Name HwSchMode -Value 2" in script


def test_default_elevate_reports_cancelled_uac(monkeypatch) -> None:
    monkeypatch.setattr(
        OptimizerService,
        "_default_run",
        staticmethod(lambda args, timeout: (1, "The operation was canceled by the user")),
    )
    assert OptimizerService._default_elevate(("powershell", "-Command", "exit 0")) is False


# ---------- UI ----------


class FakeOptimizerService(OptimizerService):
    def __init__(self, tmp_path) -> None:
        from app.optimizer import OptimizerState

        super().__init__(
            run=lambda args, timeout: (0, f"Power Scheme GUID: {GUID_BALANCED}  (Balanced)"),
            elevate=lambda args: True,
            is_admin=lambda: False,
            backup_path=tmp_path / "backup.json",
        )
        self.fixed_state = OptimizerState(
            power_guid=GUID_BALANCED,
            power_name="Balanced",
            game_mode=True,
            hags=None,
            visual_fx=0,
            visual_name="Let Windows decide",
            is_admin=False,
        )
        self.apply_calls: list[str] = []
        self.revert_calls = 0
        self._backed_up = False

    def state(self):
        return self.fixed_state

    def backup_exists(self) -> bool:
        return self._backed_up

    def apply_profile(self, profile: str, *, with_restore_point: bool = True):
        from app.optimizer import ApplyReport

        self.apply_calls.append(profile)
        self._backed_up = True
        return ApplyReport(applied=(f"{profile} ok",), errors=())

    def revert(self):
        from app.optimizer import ApplyReport

        self.revert_calls += 1
        return ApplyReport(applied=("reverted",), errors=())


def test_optimizer_page_loads_state(qapp, tmp_path) -> None:
    service = FakeOptimizerService(tmp_path)
    page = OptimizerPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page._state is not None)
    assert "Balanced" in page.state_rows["power"].text()
    assert "on" in page.state_rows["game_mode"].text()
    assert not page.state_errors.isVisible()


def test_optimizer_page_apply_calls_service(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    service = FakeOptimizerService(tmp_path)
    page = OptimizerPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page._state is not None)

    page.start_apply("GAMING")
    assert _wait_until(qapp, lambda: service.apply_calls == ["GAMING"])
    assert _wait_until(qapp, lambda: page._task is None)


def test_optimizer_page_apply_cancelled(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    service = FakeOptimizerService(tmp_path)
    page = OptimizerPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page._state is not None)

    page.start_apply("GAMING")
    assert service.apply_calls == []


def test_optimizer_page_revert_button_state(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    service = FakeOptimizerService(tmp_path)
    page = OptimizerPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page._state is not None)
    assert not page.revert_button.isEnabled()  # no backup yet

    page.start_apply("BALANCED")
    assert _wait_until(qapp, lambda: service.apply_calls == ["BALANCED"])
    assert _wait_until(qapp, lambda: page._task is None and page.revert_button.isEnabled())

    page.start_revert()
    assert _wait_until(qapp, lambda: service.revert_calls == 1)
    assert _wait_until(qapp, lambda: page._task is None)


def test_default_backup_path_uses_data_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path))
    service = OptimizerService()
    assert service.backup_path == tmp_path / "optimizer_backup.json"
