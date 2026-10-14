from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.gaming import DetectedGame, GamingService, LauncherService
from app.gaming.service import _find_cover
from app.optimizer import ApplyReport, OptimizerService
from app.ui.launcher import GameTile, LauncherPage


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class FakeOptimizer(OptimizerService):
    def __init__(self, tmp_path) -> None:
        super().__init__(backup_path=tmp_path / "opt_backup.json")

    def apply_profile(self, profile: str, *, with_restore_point: bool = True) -> ApplyReport:
        return ApplyReport(applied=(), errors=())


_GAMES = [
    DetectedGame("pubg", "PUBG: BATTLEGROUNDS", "Steam", "C:/g/TslGame.exe", True, False),
    DetectedGame("cs2", "Counter-Strike 2", "Steam", "C:/g/cs2.exe", True, True),
    DetectedGame("custom:mine", "My Game", "Custom", "C:/g/mine.exe", True, False, custom=True),
]


class FakeGaming(GamingService):
    def __init__(self, tmp_path, games=None) -> None:
        super().__init__(
            steam_roots=lambda: [],
            custom_store=tmp_path / "custom.json",
            optimizer=FakeOptimizer(tmp_path),
            running_names=lambda: [],
        )
        self._games = list(_GAMES if games is None else games)
        self.launched: list[str] = []

    def detect(self):
        return list(self._games)

    def launch(self, game: DetectedGame) -> int:
        self.launched.append(game.id)
        return 4321


def _launcher(tmp_path, *, games=None, now=None) -> LauncherService:
    return LauncherService(
        gaming=FakeGaming(tmp_path, games),
        favorites_store=tmp_path / "fav.json",
        history_store=tmp_path / "hist.json",
        now=now,
    )


# ---------- cover art ----------


def test_find_cover_prefers_portrait_then_header(tmp_path) -> None:
    cache = tmp_path / "appcache" / "librarycache" / "730"
    cache.mkdir(parents=True)
    assert _find_cover(tmp_path, "730") == ""
    (cache / "header.jpg").write_bytes(b"x")
    assert _find_cover(tmp_path, "730").endswith("header.jpg")
    (cache / "library_600x900.jpg").write_bytes(b"x")
    assert _find_cover(tmp_path, "730").endswith("library_600x900.jpg")


def test_detect_resolves_cover_for_steam_game(tmp_path) -> None:
    game_dir = tmp_path / "steamapps" / "common" / "PUBG"
    game_dir.mkdir(parents=True)
    (game_dir / "TslGame.exe").write_bytes(b"MZ")
    cache = tmp_path / "appcache" / "librarycache" / "578080"
    cache.mkdir(parents=True)
    (cache / "header.jpg").write_bytes(b"x")
    service = GamingService(
        steam_roots=lambda: [str(tmp_path)],
        custom_store=tmp_path / "custom.json",
        optimizer=FakeOptimizer(tmp_path),
        running_names=lambda: [],
    )
    games = {g.id: g for g in service.detect()}
    assert games["pubg"].cover.endswith("header.jpg")
    assert games["cs2"].cover == ""


# ---------- service: favourites ----------


def test_favorites_toggle_and_persist(tmp_path) -> None:
    service = _launcher(tmp_path)
    assert service.favorites() == set()
    assert service.toggle_favorite("cs2") is True
    assert service.is_favorite("cs2") is True
    fresh = _launcher(tmp_path)
    assert fresh.favorites() == {"cs2"}
    assert service.toggle_favorite("cs2") is False
    assert service.is_favorite("cs2") is False


def test_games_sort_favorites_first(tmp_path) -> None:
    service = _launcher(tmp_path)
    service.toggle_favorite("custom:mine")
    ids = [g.id for g in service.games()]
    assert ids[0] == "custom:mine"


# ---------- service: history ----------


def test_history_records_and_orders_newest_first(tmp_path) -> None:
    times = iter([1000.0, 2000.0])
    service = _launcher(tmp_path, now=lambda: next(times))
    service.record_launch(_GAMES[0], pid=10)
    service.record_launch(_GAMES[1], pid=20)
    history = service.history()
    assert [r.id for r in history] == ["cs2", "pubg"]
    assert history[0].pid == 20
    assert history[0].when == datetime.fromtimestamp(2000.0).isoformat(timespec="seconds")
    assert service.launch_count("pubg") == 1
    assert service.last_played("cs2") == datetime.fromtimestamp(2000.0).isoformat(timespec="seconds")
    assert service.last_played("nope") is None


def test_launch_delegates_and_records(tmp_path) -> None:
    service = _launcher(tmp_path)
    pid = service.launch(_GAMES[0])
    assert pid == 4321
    assert service.gaming.launched == ["pubg"]
    assert service.history()[0].exe == "C:/g/TslGame.exe"


def test_clear_history(tmp_path) -> None:
    service = _launcher(tmp_path)
    service.record_launch(_GAMES[0])
    assert service.history()
    service.clear_history()
    assert service.history() == []


def test_corrupt_store_is_ignored(tmp_path) -> None:
    (tmp_path / "fav.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "hist.json").write_text("42", encoding="utf-8")
    service = _launcher(tmp_path)
    assert service.favorites() == set()
    assert service.history() == []


# ---------- UI ----------


class CannedLauncher(LauncherService):
    def __init__(self, tmp_path, games=None) -> None:
        super().__init__(
            gaming=FakeGaming(tmp_path, games),
            favorites_store=tmp_path / "fav.json",
            history_store=tmp_path / "hist.json",
        )
        self._canned = list(_GAMES if games is None else games)

    def games(self):
        return list(self._canned)


def test_page_builds_tiles(qapp, tmp_path) -> None:
    page = LauncherPage(CannedLauncher(tmp_path))
    page.start_refresh()
    assert _wait_until(qapp, lambda: len(page._tiles) == 3)
    assert set(page._tiles) == {"pubg", "cs2", "custom:mine"}
    assert "installed" in page.status_label.text()
    assert page.detail_name.text() == "PUBG: BATTLEGROUNDS"


def test_page_selection_updates_details(qapp, tmp_path) -> None:
    page = LauncherPage(CannedLauncher(tmp_path))
    page.start_refresh()
    assert _wait_until(qapp, lambda: len(page._tiles) == 3)
    page.select_game("cs2")
    assert page.detail_name.text() == "Counter-Strike 2"
    assert "Running" in page.detail_rows["status"].text()
    assert page._tiles["cs2"].property("selected") is True
    assert page._tiles["pubg"].property("selected") is False


def test_page_launch_records_history(qapp, tmp_path) -> None:
    service = CannedLauncher(tmp_path)
    page = LauncherPage(service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: len(page._tiles) == 3)
    page.start_launch("pubg")
    assert _wait_until(qapp, lambda: bool(service.history()))
    assert service.history()[0].id == "pubg"
    assert page.history_list.count() == 1


def test_page_toggle_favorite(qapp, tmp_path) -> None:
    service = CannedLauncher(tmp_path)
    page = LauncherPage(service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: len(page._tiles) == 3)
    page.toggle_favorite("cs2")
    assert service.is_favorite("cs2") is True
    assert page._tiles["cs2"].star_button.isChecked() is True
    assert "cs2" in page.status_label.text() or "Counter" in page.status_label.text()


def test_page_retranslate_safe(qapp, tmp_path) -> None:
    page = LauncherPage(CannedLauncher(tmp_path))
    page.start_refresh()
    assert _wait_until(qapp, lambda: len(page._tiles) == 3)
    page.retranslate()
    assert page._title.text()


def test_tile_click_emits_game_id(qapp) -> None:
    tile = GameTile()
    tile.set_game(_GAMES[0], pinned=False)
    received: list[str] = []
    tile.clicked.connect(received.append)
    QTest.mouseClick(tile, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    assert received == ["pubg"]
