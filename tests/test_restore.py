from __future__ import annotations

import base64
import re

from app.restore import (
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_DISABLED,
    STATUS_ERROR,
    STATUS_SKIPPED,
    RestorePointService,
)

_B64_RE = re.compile(r"-EncodedCommand['\"]?,\s*'([A-Za-z0-9+/=]+)'")


def _decode(args: tuple[str, ...]) -> str | None:
    if "-EncodedCommand" in args:
        i = args.index("-EncodedCommand")
        return base64.b64decode(args[i + 1]).decode("utf-16-le")
    match = _B64_RE.search(" ".join(args))
    if match:
        return base64.b64decode(match.group(1)).decode("utf-16-le")
    return None


class FakeRunner:
    """Emulates powershell + Windows restore points in memory."""

    def __init__(self, *, admin: bool = True) -> None:
        self.admin = admin
        self.points: list[tuple[int, str]] = []
        self.calls: list[tuple[str, ...]] = []
        self.last_script: str | None = None
        self.checkpoint_error = False
        self.checkpoint_code = 1
        self.checkpoint_msg = ""
        self.add_point = True
        self.uac_cancel = False
        self.enable_disabled = False
        self.enabled = False
        self._seq = 100

    def run(self, args, timeout):
        args = tuple(str(a) for a in args)
        self.calls.append(args)
        joined = " ".join(args)

        if self.uac_cancel and "Start-Process" in joined:
            return 1223, "The operation was canceled by the user."
        if "Get-ComputerRestorePoint" in joined:
            return 0, "\n".join(f"{seq}\t{desc}" for seq, desc in self.points)

        script = _decode(args)
        if script is not None and "Checkpoint-Computer" in script:
            self.last_script = script
            if self.checkpoint_error:
                return self.checkpoint_code, self.checkpoint_msg
            if self.add_point:
                self._seq += 1
                self.points.append((self._seq, "PCOptimizer_PRO test"))
            return 0, "OK"
        if script is not None and "Enable-ComputerRestore" in script:
            self.last_script = script
            if self.enable_disabled:
                return 1, "system protection is still disabled"
            self.enabled = True
            return 0, "OK"
        return 0, ""

    def make_service(self) -> RestorePointService:
        return RestorePointService(run=self.run, is_admin=lambda: self.admin)


# ---------- script generation ----------


def test_create_script_contains_required_tokens() -> None:
    script = RestorePointService._build_create_script("PCOptimizer_PRO 'x'", True)
    assert "Checkpoint-Computer" in script
    assert "MODIFY_SETTINGS" in script
    assert "SystemRestorePointCreationFrequency" in script
    assert "'PCOptimizer_PRO ''x'''" in script  # single quotes escaped
    assert "$true" in script


def test_create_script_force_off_omits_frequency_toggle() -> None:
    script = RestorePointService._build_create_script("label", False)
    assert "$false" in script


# ---------- list ----------


def test_list_points_parses_output() -> None:
    runner = FakeRunner()
    runner.points = [(509, "Windows Update"), (510, "My point")]
    points = runner.make_service().list_points()
    assert [(p.sequence, p.description) for p in points] == [(509, "Windows Update"), (510, "My point")]


# ---------- create ----------


def test_create_admin_creates_point() -> None:
    runner = FakeRunner(admin=True)
    result = runner.make_service().create("PCOptimizer_PRO test")
    assert result.ok
    assert result.status == STATUS_CREATED
    assert result.sequence == 101
    # went straight through powershell, no UAC wrapper
    assert all("Start-Process" not in " ".join(c) for c in runner.calls)


def test_create_non_admin_uses_runas_wrapper() -> None:
    runner = FakeRunner(admin=False)
    result = runner.make_service().create("PCOptimizer_PRO test")
    assert result.ok and result.status == STATUS_CREATED
    assert any("Start-Process" in " ".join(c) and "RunAs" in " ".join(c) for c in runner.calls)


def test_create_skipped_when_no_new_point() -> None:
    runner = FakeRunner(admin=True)
    runner.points = [(100, "old point")]
    runner.add_point = False  # Checkpoint "succeeds" but Windows makes no point
    result = runner.make_service().create("PCOptimizer_PRO test")
    assert not result.ok
    assert result.status == STATUS_SKIPPED


def test_create_detects_disabled_protection() -> None:
    runner = FakeRunner(admin=True)
    runner.checkpoint_error = True
    runner.checkpoint_msg = "System Restore is disabled for this drive."
    result = runner.make_service().create("PCOptimizer_PRO test")
    assert not result.ok
    assert result.status == STATUS_DISABLED


def test_create_reports_uac_cancel() -> None:
    runner = FakeRunner(admin=False)
    runner.uac_cancel = True
    result = runner.make_service().create("PCOptimizer_PRO test")
    assert not result.ok
    assert result.status == STATUS_CANCELLED


# ---------- enable protection ----------


def test_enable_protection_non_admin() -> None:
    runner = FakeRunner(admin=False)
    result = runner.make_service().enable_protection("C:")
    assert result.ok
    assert runner.enabled
    assert any("Start-Process" in " ".join(c) for c in runner.calls)
    # The script must verify the change actually landed, not just run it.
    assert runner.last_script is not None
    assert "DisableSR" in runner.last_script


def test_enable_protection_reports_still_disabled() -> None:
    # Enable-ComputerRestore returned success but the master switch stayed on:
    # we must report an error instead of a false positive.
    runner = FakeRunner(admin=True)
    runner.enable_disabled = True
    result = runner.make_service().enable_protection("C:")
    assert not result.ok
    assert result.status == STATUS_ERROR
    assert "still disabled" in result.message
