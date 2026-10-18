from __future__ import annotations

import time

import pytest

from app.gaming import DetectedGame, GamingError, GamingService
from app.gaming.service import _find_exe, default_steam_roots
from app.optimizer import ApplyReport, OptimizerService
from app.ui.gaming import GamingPage


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------- helpers ----------


def _make_steam(tmp_path, games: dict[str, list[str]]) -> None:
    for folder, exes in games.items():
        game_dir = tmp_path / "steamapps" / "common" / folder
        game_dir.mkdir(parents=True)
        for exe in exes:
            (game_dir / exe).write_bytes(b"MZ")


class FakeOptimizer(OptimizerService):
    def __init__(self, tmp_path) -> None:
        super().__init__(backup_path=tmp_path / "opt_backup.json")
        self.apply_calls: list[tuple[str, bool]] = []
        self.revert_calls = 0
        self.fail_restore = False
        self.fail_all = False

    def apply_profile(self, profile: str, *, with_restore_point: bool = True) -> ApplyReport:
        self.apply_calls.append((profile, with_restore_point))
        if self.fail_restore:
            return ApplyReport(applied=(), errors=("restore point failed: nope",))
        if self.fail_all:
            return ApplyReport(applied=(), errors=("powercfg failed",))
        return ApplyReport(applied=("power plan → High performance", "Game Mode → on"), errors=())

    def revert(self) -> ApplyReport:
        self.revert_calls += 1
        if self.fail_restore:
            raise RuntimeError("no backup")
        return ApplyReport(applied=("power plan → Balanced",), errors=())


def _service(tmp_path, *, fake_opt=None, roots=None, running=None, popen=None) -> GamingService:
    return GamingService(
        steam_roots=lambda: list(roots or []),
        custom_store=tmp_path / "custom.json",
        optimizer=fake_opt or FakeOptimizer(tmp_path),
        running_names=lambda: list(running or []),
        popen=popen,
    )


# ---------- detection ----------


def test_detect_known_games_from_steam(tmp_path) -> None:
    _make_steam(tmp_path, {"PUBG": ["TslGame.exe"], "dota 2": ["dota2.exe"]})
    service = _service(tmp_path, roots=[str(tmp_path)])
    games = {g.id: g for g in service.detect()}
    assert games["pubg"].installed is True
    assert games["pubg"].location.endswith("TslGame.exe")
    assert games["dota2"].installed is True
    assert games["cs2"].installed is False
    # installed games sorted first
    assert service.detect()[0].installed is True


def test_detect_missing_steam_dir(tmp_path) -> None:
    service = _service(tmp_path, roots=[str(tmp_path / "nope")])
    games = service.detect()
    assert all(not g.installed for g in games if g.source == "Steam")


def test_detect_running_flag(tmp_path) -> None:
    _make_steam(tmp_path, {"Counter-Strike Global Offensive": ["cs2.exe"]})
    service = _service(tmp_path, roots=[str(tmp_path)], running=["cs2.exe", "chrome.exe"])
    games = {g.id: g for g in service.detect()}
    assert games["cs2"].running is True
    assert games["pubg"].running is False


def test_find_exe_nested(tmp_path) -> None:
    nested = tmp_path / "bin" / "win64"
    nested.mkdir(parents=True)
    exe = nested / "TslGame.exe"
    exe.write_bytes(b"MZ")
    assert _find_exe(tmp_path, ["tslgame.exe"]) == str(exe)
    assert _find_exe(tmp_path, ["missing.exe"]) is None


def test_default_steam_roots_returns_list() -> None:
    roots = default_steam_roots()
    assert isinstance(roots, list)
    assert len(roots) == len(set(r.lower() for r in roots))


# ---------- custom games ----------


def test_add_and_remove_custom(tmp_path) -> None:
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")
    service = _service(tmp_path)

    game = service.add_custom("My Indie Game", str(exe))
    assert game.custom is True
    assert game.installed is True

    again = {g.id: g for g in service.detect()}
    assert game.id in again

    with pytest.raises(GamingError):
        service.add_custom("My Indie Game", str(exe))

    service.remove_custom(game.id)
    assert game.id not in {g.id for g in service.detect()}


def test_add_custom_requires_existing_file(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(GamingError):
        service.add_custom("Ghost", str(tmp_path / "missing.exe"))


def test_add_custom_requires_name(tmp_path) -> None:
    exe = tmp_path / "g.exe"
    exe.write_bytes(b"MZ")
    service = _service(tmp_path)
    with pytest.raises(GamingError):
        service.add_custom("   ", str(exe))


def test_remove_unknown_custom_raises(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(GamingError):
        service.remove_custom("custom:ghost")


def test_remove_builtin_entry_raises(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(GamingError):
        service.remove_custom("pubg")


def test_custom_persists_between_instances(tmp_path) -> None:
    exe = tmp_path / "g.exe"
    exe.write_bytes(b"MZ")
    _service(tmp_path).add_custom("Persist", str(exe))
    games = _service(tmp_path).detect()
    assert any(g.name == "Persist" for g in games)


# ---------- launch ----------


def test_launch_runs_popen(tmp_path) -> None:
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")
    calls: list[dict] = []

    class FakeProc:
        pid = 4242

    def fake_popen(args, cwd=None):
        calls.append({"args": args, "cwd": cwd})
        return FakeProc()

    service = _service(tmp_path, popen=fake_popen)
    game = service.add_custom("Launchable", str(exe))
    pid = service.launch(game)
    assert pid == 4242
    assert calls[0]["args"] == [str(exe)]
    assert calls[0]["cwd"] == str(tmp_path)


def test_launch_not_installed_raises(tmp_path) -> None:
    service = _service(tmp_path)
    game = DetectedGame(
        id="cs2", name="CS2", source="Steam",
        location="", installed=False, running=False,
    )
    with pytest.raises(GamingError):
        service.launch(game)


# ---------- gaming mode ----------


def test_activate_applies_gaming_profile(tmp_path) -> None:
    fake = FakeOptimizer(tmp_path)
    service = _service(tmp_path, fake_opt=fake)
    report = service.activate()
    assert fake.apply_calls == [("GAMING", True)]
    assert service.active is True
    assert report.applied


def test_activate_without_restore_point(tmp_path) -> None:
    fake = FakeOptimizer(tmp_path)
    service = _service(tmp_path, fake_opt=fake)
    service.activate(with_restore_point=False)
    assert fake.apply_calls == [("GAMING", False)]


def test_activate_failure_keeps_mode_off(tmp_path) -> None:
    fake = FakeOptimizer(tmp_path)
    fake.fail_restore = True
    service = _service(tmp_path, fake_opt=fake)
    report = service.activate()
    assert service.active is False
    assert report.errors


def test_deactivate_reverts(tmp_path) -> None:
    fake = FakeOptimizer(tmp_path)
    service = _service(tmp_path, fake_opt=fake)
    service.activate()
    report = service.deactivate()
    assert fake.revert_calls == 1
    assert service.active is False
    assert report.applied


def test_active_restored_from_backup_after_restart(tmp_path) -> None:
    # A GAMING-profile backup surviving on disk means the mode really is still on.
    fake = FakeOptimizer(tmp_path)
    fake.backup_path.write_text('{"profile": "GAMING"}', encoding="utf-8")
    assert _service(tmp_path, fake_opt=fake).active is True


def test_inactive_after_restart_without_backup(tmp_path) -> None:
    assert _service(tmp_path).active is False


def test_inactive_after_restart_when_backup_is_other_profile(tmp_path) -> None:
    fake = FakeOptimizer(tmp_path)
    fake.backup_path.write_text('{"profile": "BALANCED"}', encoding="utf-8")
    assert _service(tmp_path, fake_opt=fake).active is False


# ---------- UI ----------


def _select_by_name(page: GamingPage, name: str) -> int:
    for row in range(page.table.rowCount()):
        if page.table.item(row, 0).text() == name:
            page.table.selectRow(row)
            return row
    raise AssertionError(f"{name} not in table")


class CannedGamingService(GamingService):
    def __init__(self, tmp_path) -> None:
        super().__init__(
            steam_roots=lambda: [],
            custom_store=tmp_path / "custom.json",
            optimizer=FakeOptimizer(tmp_path),
            running_names=lambda: ["TslGame.exe"],
        )
        self.games = [
            DetectedGame(
                id="pubg", name="PUBG: BATTLEGROUNDS", source="Steam",
                location=str(tmp_path / "TslGame.exe"), installed=True, running=True,
            ),
            DetectedGame(
                id="custom:mine", name="My Game", source="Custom",
                location=str(tmp_path / "mine.exe"), installed=True, running=False, custom=True,
            ),
        ]
        self.mode_calls: list[str] = []

    def detect(self):
        return list(self.games)

    def activate(self, *, with_restore_point: bool = True) -> ApplyReport:
        self.mode_calls.append("activate")
        self._active = True
        return ApplyReport(applied=("x",), errors=())

    def deactivate(self) -> ApplyReport:
        self.mode_calls.append("deactivate")
        self._active = False
        return ApplyReport(applied=("x",), errors=())


def test_gaming_page_loads_games(qapp, tmp_path) -> None:
    service = CannedGamingService(tmp_path)
    page = GamingPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 2)
    assert "2 installed" in page.status_label.text()
    assert "1 running" in page.status_label.text()

    _select_by_name(page, "PUBG: BATTLEGROUNDS")
    assert page.detail_name.text() == "PUBG: BATTLEGROUNDS"
    assert "Running" in page.detail_rows["status"].text()
    assert page.launch_button.isEnabled()
    assert not page.remove_button.isEnabled()


def test_gaming_page_custom_has_remove(qapp, tmp_path) -> None:
    service = CannedGamingService(tmp_path)
    page = GamingPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 2)

    _select_by_name(page, "My Game")
    assert page.remove_button.isEnabled()
    assert page.launch_button.isEnabled()


def test_gaming_page_toggle_mode(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    service = CannedGamingService(tmp_path)
    page = GamingPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 2)

    page.start_toggle_mode()
    assert _wait_until(qapp, lambda: service.mode_calls == ["activate"])
    assert _wait_until(qapp, lambda: page._task is None)
    assert page.mode_label.text() == "Mode: ON"
    assert page.mode_button.text() == "Disable gaming mode"

    page.start_toggle_mode()
    assert _wait_until(qapp, lambda: service.mode_calls == ["activate", "deactivate"])
    assert _wait_until(qapp, lambda: page._task is None)
    assert page.mode_label.text() == "Mode: OFF"


def test_gaming_page_toggle_cancelled(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    service = CannedGamingService(tmp_path)
    page = GamingPage(service=service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 2)

    page.start_toggle_mode()
    assert service.mode_calls == []
