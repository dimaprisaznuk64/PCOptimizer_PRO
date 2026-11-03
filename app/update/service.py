"""Update check against the latest GitHub release.

The check is deliberately lightweight: one HTTPS request to the GitHub API,
no auto-download. The user is told that a newer version exists and can open
the release page.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from app import __version__

log = logging.getLogger("pcoptimizer.update")

REPOSITORY = "dimaprisaznuk64/PCOptimizer_PRO"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"
TIMEOUT_S = 6.0
NOTES_LIMIT = 4000

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)")

Fetcher = Callable[[str, float], dict[str, object]]


def parse_version(text: str) -> tuple[int, ...] | None:
    """`v1.6.5` / `1.6.5-beta` -> (1, 6, 5); None when there is no version."""
    match = _VERSION_RE.match(text.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    current: str
    latest: str | None = None
    available: bool = False
    url: str = RELEASES_PAGE
    notes: str = ""
    error: str | None = None


def _fetch_json(url: str, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"PCOptimizer_PRO/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
    if not isinstance(payload, dict):
        raise ValueError("unexpected GitHub response")
    return payload


class UpdateService:
    """Compares the running version with the newest published release."""

    def __init__(
        self,
        current: str = __version__,
        *,
        api_url: str = API_URL,
        timeout: float = TIMEOUT_S,
        fetcher: Fetcher | None = None,
    ) -> None:
        self._current = current
        self._api_url = api_url
        self._timeout = timeout
        self._fetcher = fetcher or _fetch_json

    @property
    def current(self) -> str:
        return self._current

    def check(self) -> UpdateInfo:
        try:
            payload = self._fetcher(self._api_url, self._timeout)
        except Exception as exc:  # network/API failures must never crash the app
            message = str(exc) or type(exc).__name__
            log.warning("update check failed: %s", message)
            return UpdateInfo(self._current, error=message)

        tag = str(payload.get("tag_name") or "").strip()
        latest = parse_version(tag)
        if latest is None:
            log.warning("update check: unexpected release tag %r", tag)
            return UpdateInfo(self._current, error=f"unexpected release tag: {tag!r}")

        current = parse_version(self._current) or ()
        url = payload.get("html_url")
        body = payload.get("body")
        info = UpdateInfo(
            current=self._current,
            latest=".".join(str(part) for part in latest),
            available=latest > current,
            url=url if isinstance(url, str) and url.startswith("https://") else RELEASES_PAGE,
            notes=body[:NOTES_LIMIT] if isinstance(body, str) else "",
        )
        log.info(
            "update check: current=%s latest=%s available=%s",
            info.current,
            info.latest,
            info.available,
        )
        return info
