from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.optimizer import ApplyReport, OptimizerService
from app.settings import data_root


class GamingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GameSpec:
    id: str
    name: str
    steam_folder: str
    exe_names: tuple[str, ...]
    appid: str = ""


KNOWN_GAMES: tuple[GameSpec, ...] = (
    GameSpec("pubg", "PUBG: BATTLEGROUNDS", "PUBG", ("TslGame.exe",), "578080"),
    GameSpec(
        "cs2", "Counter-Strike 2", "Counter-Strike Global Offensive", ("cs2.exe",), "730"
    ),
    GameSpec("dota2", "Dota 2", "dota 2", ("dota2.exe",), "570"),
)


@dataclass(frozen=True, slots=True)
class DetectedGame:
    id: str
    name: str
    source: str
    location: str
    installed: bool
    running: bool
    custom: bool = False
    cover: str = ""
    appid: str = ""


def default_steam_roots() -> list[str]:
    roots: list[str] = []
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path, _vtype = winreg.QueryValueEx(key, "SteamPath")
        roots.append(str(steam_path))
    except OSError:
        pass
    for candidate in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        if os.path.isdir(candidate):
            roots.append(candidate)

    libraries: list[str] = []
    for root in roots:
        vdf = Path(root) / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s*"([^"]+)"', text):
            path = match.group(1).encode("utf-8").decode("unicode_escape")
            libraries.append(path)
    roots.extend(libraries)

    seen: set[str] = set()
    unique: list[str] = []
    for root in roots:
        normalized = str(Path(root)).lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(root)
    return unique


def _find_cover(root: Path, appid: str) -> str:
    """Best-effort Steam cover art lookup (portrait capsule first, then header)."""
    if not appid:
        return ""
    cache = root / "appcache" / "librarycache"
    candidates = (
        cache / appid / "library_600x900.jpg",
        cache / appid / "header.jpg",
        cache / f"{appid}_header.jpg",
        cache / f"{appid}_library_600x900.jpg",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def _find_exe(folder: Path, exe_names: Sequence[str], depth: int = 5) -> str | None:
    wanted = {name.lower() for name in exe_names}
    level = [folder]
    for _ in range(depth):
        next_level: list[Path] = []
        for directory in level:
            try:
                for child in directory.iterdir():
                    if child.is_file() and child.name.lower() in wanted:
                        return str(child)
                    if child.is_dir():
                        next_level.append(child)
            except OSError:
                continue
        level = next_level
    return None


def _default_open_uri(uri: str) -> None:
    import os

    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise OSError("opening URIs is not supported on this platform")
    startfile(uri)


class GamingService:
    def __init__(
        self,
        *,
        steam_roots: Callable[[], list[str]] | None = None,
        custom_store: str | Path | None = None,
        optimizer: OptimizerService | None = None,
        running_names: Callable[[], Sequence[str]] | None = None,
        popen: Callable[..., object] | None = None,
        open_uri: Callable[[str], object] | None = None,
    ) -> None:
        self.custom_store = Path(custom_store) if custom_store else (
            data_root() / "gaming_custom.json"
        )
        self._steam_roots = steam_roots or default_steam_roots
        self._optimizer = optimizer or OptimizerService()
        self._running_names = running_names or self._psutil_running_names
        self._popen = popen or subprocess.Popen
        self._open_uri = open_uri or _default_open_uri
        # The applied-profile backup survives restarts; if it was a GAMING profile
        # the mode really is still on, so restore the flag instead of lying "off".
        self._active = self._optimizer.backup_profile() == "GAMING"
        self.last_report: ApplyReport | None = None

    @property
    def active(self) -> bool:
        return self._active

    # ---------- detection ----------

    def detect(self) -> list[DetectedGame]:
        running = {name.lower() for name in self._running_names()}
        roots = [Path(r) for r in self._steam_roots()]
        games: list[DetectedGame] = []

        for spec in KNOWN_GAMES:
            exe_path: str | None = None
            location = ""
            cover = ""
            for root in roots:
                folder = root / "steamapps" / "common" / spec.steam_folder
                if folder.is_dir():
                    location = str(folder)
                    exe_path = _find_exe(folder, spec.exe_names)
                    cover = _find_cover(root, spec.appid)
                    break
            games.append(
                DetectedGame(
                    id=spec.id,
                    name=spec.name,
                    source="Steam",
                    location=exe_path or location,
                    installed=bool(location),
                    running=any(name.lower() in running for name in spec.exe_names),
                    cover=cover,
                    appid=spec.appid,
                )
            )

        for entry in self._load_custom():
            exe = Path(entry["exe"])
            games.append(
                DetectedGame(
                    id=entry["id"],
                    name=entry["name"],
                    source="Custom",
                    location=entry["exe"],
                    installed=exe.exists(),
                    running=exe.name.lower() in running,
                    custom=True,
                )
            )

        games.sort(key=lambda g: (not g.installed, g.name.lower()))
        return games

    def game_by_id(self, games: list[DetectedGame], game_id: str) -> DetectedGame | None:
        for game in games:
            if game.id == game_id:
                return game
        return None

    # ---------- custom games ----------

    def add_custom(self, name: str, exe: str) -> DetectedGame:
        name = name.strip()
        if not name:
            raise GamingError("game name is required")
        path = Path(exe)
        if not path.is_file():
            raise GamingError(f"executable not found: {exe}")
        game_id = f"custom:{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}"
        entries = self._load_custom()
        if any(e["id"] == game_id for e in entries):
            raise GamingError(f"{name} is already added")
        entries.append({"id": game_id, "name": name, "exe": str(path)})
        self._save_custom(entries)
        return DetectedGame(
            id=game_id,
            name=name,
            source="Custom",
            location=str(path),
            installed=True,
            running=False,
            custom=True,
        )

    def remove_custom(self, game_id: str) -> str:
        if not game_id.startswith("custom:"):
            raise GamingError("only custom entries can be removed")
        entries = self._load_custom()
        remaining = [e for e in entries if e["id"] != game_id]
        if len(remaining) == len(entries):
            raise GamingError("custom game not found")
        self._save_custom(remaining)
        return game_id

    # ---------- launch ----------

    def launch(self, game: DetectedGame) -> int:
        if not game.installed or not game.location:
            raise GamingError(f"{game.name} is not installed")
        if game.appid:
            try:
                self._open_uri(f"steam://rungameid/{game.appid}")
                return 0
            except OSError:
                pass
        path = Path(game.location)
        if not path.is_file():
            raise GamingError(f"{game.name} executable missing: {game.location}")
        try:
            process = self._popen([str(path)], cwd=str(path.parent))
        except OSError as e:
            raise GamingError(f"cannot start {game.name}: {e}") from e
        return int(getattr(process, "pid", 0) or 0)

    # ---------- gaming mode ----------

    def activate(self, *, with_restore_point: bool = True) -> ApplyReport:
        report = self._optimizer.apply_profile("GAMING", with_restore_point=with_restore_point)
        self.last_report = report
        self._active = bool(report.applied)
        return report

    def deactivate(self) -> ApplyReport:
        report = self._optimizer.revert()
        self.last_report = report
        self._active = False
        return report

    # ---------- internals ----------

    @staticmethod
    def _psutil_running_names() -> Sequence[str]:
        import psutil

        names: list[str] = []
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if name:
                names.append(str(name))
        return names

    def _load_custom(self) -> list[dict]:
        if not self.custom_store.exists():
            return []
        try:
            data = json.loads(self.custom_store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise GamingError(f"cannot read custom games: {e}") from e
        if not isinstance(data, list):
            raise GamingError("custom games file is corrupt")
        return [e for e in data if isinstance(e, dict) and {"id", "name", "exe"} <= set(e)]

    def _save_custom(self, entries: list[dict]) -> None:
        try:
            self.custom_store.parent.mkdir(parents=True, exist_ok=True)
            self.custom_store.write_text(
                json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as e:
            raise GamingError(f"cannot save custom games: {e}") from e
