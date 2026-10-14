from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.gaming.service import DetectedGame, GamingService
from app.settings import data_root

_HISTORY_LIMIT = 200


@dataclass(frozen=True, slots=True)
class LaunchRecord:
    id: str
    name: str
    exe: str
    when: str
    pid: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "exe": self.exe, "when": self.when, "pid": self.pid}


class LauncherService:
    """Game launcher on top of :class:`GamingService`.

    Adds favourites (pinned games) and a launch history, both stored as small
    JSON files next to the other portable runtime data.
    """

    def __init__(
        self,
        *,
        gaming: GamingService | None = None,
        favorites_store: str | Path | None = None,
        history_store: str | Path | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._gaming = gaming or GamingService()
        self.favorites_store = (
            Path(favorites_store) if favorites_store else data_root() / "gaming_favorites.json"
        )
        self.history_store = (
            Path(history_store) if history_store else data_root() / "gaming_history.json"
        )
        self._now = now or time.time

    @property
    def gaming(self) -> GamingService:
        return self._gaming

    # ---------- games ----------

    def games(self) -> list[DetectedGame]:
        games = self._gaming.detect()
        favs = self.favorites()
        games.sort(key=lambda g: (not g.installed, g.id not in favs, g.name.lower()))
        return games

    # ---------- favourites ----------

    def favorites(self) -> set[str]:
        return {item for item in self._read_list(self.favorites_store) if isinstance(item, str)}

    def is_favorite(self, game_id: str) -> bool:
        return game_id in self.favorites()

    def toggle_favorite(self, game_id: str) -> bool:
        favs = self.favorites()
        if game_id in favs:
            favs.discard(game_id)
            enabled = False
        else:
            favs.add(game_id)
            enabled = True
        self._write(self.favorites_store, sorted(favs))
        return enabled

    # ---------- history ----------

    def history(self, limit: int = 20) -> list[LaunchRecord]:
        records: list[LaunchRecord] = []
        for entry in self._read_list(self.history_store):
            if not isinstance(entry, dict):
                continue
            if not {"id", "name", "exe", "when"} <= set(entry):
                continue
            records.append(
                LaunchRecord(
                    id=str(entry["id"]),
                    name=str(entry["name"]),
                    exe=str(entry.get("exe", "")),
                    when=str(entry["when"]),
                    pid=int(entry.get("pid", 0) or 0),
                )
            )
        records.reverse()
        return records[:limit] if limit else records

    def launch_count(self, game_id: str) -> int:
        return sum(1 for r in self.history(limit=0) if r.id == game_id)

    def last_played(self, game_id: str) -> str | None:
        for record in self.history(limit=0):
            if record.id == game_id:
                return record.when
        return None

    def record_launch(self, game: DetectedGame, pid: int = 0) -> LaunchRecord:
        when = datetime.fromtimestamp(self._now()).isoformat(timespec="seconds")
        record = LaunchRecord(id=game.id, name=game.name, exe=game.location, when=when, pid=pid)
        data = self._read_list(self.history_store)
        data.append(record.to_dict())
        self._write(self.history_store, data[-_HISTORY_LIMIT:])
        return record

    def clear_history(self) -> None:
        self._write(self.history_store, [])

    # ---------- launch ----------

    def launch(self, game: DetectedGame) -> int:
        pid = self._gaming.launch(game)
        self.record_launch(game, pid)
        return pid

    # ---------- custom games ----------

    def add_custom(self, name: str, exe: str) -> DetectedGame:
        return self._gaming.add_custom(name, exe)

    def remove_custom(self, game_id: str) -> str:
        return self._gaming.remove_custom(game_id)

    # ---------- storage ----------

    @staticmethod
    def _read_list(path: Path) -> list:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    @staticmethod
    def _write(path: Path, data: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
