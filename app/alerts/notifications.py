from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

NotificationLevel = Literal["info", "success", "warning", "danger"]


@dataclass(frozen=True, slots=True)
class Notification:
    id: str
    title: str
    body: str
    level: NotificationLevel
    timestamp: float
    read: bool = False


class NotificationService:
    """In-memory store for app-wide notifications and warning history."""

    def __init__(self, max_items: int = 50) -> None:
        self._max_items = max_items
        self._items: list[Notification] = []

    def notify(
        self, title: str, body: str, level: NotificationLevel = "info"
    ) -> Notification:
        import uuid

        notif = Notification(
            id=str(uuid.uuid4()),
            title=title,
            body=body,
            level=level,
            timestamp=time.time(),
            read=False,
        )
        self._items.insert(0, notif)
        if len(self._items) > self._max_items:
            self._items.pop()
        return notif

    def all(self) -> tuple[Notification, ...]:
        return tuple(self._items)

    def unread_count(self) -> int:
        return sum(1 for n in self._items if not n.read)

    def mark_all_read(self) -> None:
        self._items = [
            Notification(
                id=n.id,
                title=n.title,
                body=n.body,
                level=n.level,
                timestamp=n.timestamp,
                read=True,
            )
            for n in self._items
        ]

    def clear(self) -> None:
        self._items.clear()
