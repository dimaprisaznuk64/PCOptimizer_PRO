"""Update check against the latest GitHub release.

The check is deliberately lightweight: one HTTPS request to the GitHub API.
The user is told that a newer version exists and can either open the release
page or download the published installer on demand (never automatically).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app import __version__

log = logging.getLogger("pcoptimizer.update")

REPOSITORY = "dimaprisaznuk64/PCOptimizer_PRO"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"
TIMEOUT_S = 6.0
NOTES_LIMIT = 4000

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)")
_ASSET_VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)")

Fetcher = Callable[[str, float], dict[str, object]]

_GITHUB_PAGE_HOSTS = {"github.com", "www.github.com"}


def _is_github_page(url: object) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.lower() in _GITHUB_PAGE_HOSTS


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
    download_url: str = ""
    asset_name: str = ""
    sha256: str = ""
    download_unavailable: str = ""


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


def _asset_sha256(asset: dict[str, object]) -> str:
    """Return the lowercase hex digest when GitHub published a valid SHA-256."""
    value = str(asset.get("digest") or "").strip().lower()
    if not value.startswith("sha256:"):
        return ""
    digest = value.split(":", 1)[1]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        return ""
    return digest


def _asset_version(name: str) -> tuple[int, ...] | None:
    """Version embedded in an installer name, e.g. ``Setup_2.1.3.exe``."""
    match = _ASSET_VERSION_RE.search(Path(name).stem)
    return parse_version(match.group(1)) if match is not None else None


def _find_asset(
    payload: dict[str, object], latest: tuple[int, ...]
) -> tuple[str, str, str, str]:
    """Return ``(url, name, sha256, unavailable_reason)`` for this release's installer.

    An asset from an older release must never be offered as an update, and an
    installer without a valid published digest is never offered for download.
    """
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return "", "", "", "no_asset"
    has_installer = False
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not name.lower().endswith(".exe") or "setup" not in name.lower():
            continue
        has_installer = True
        if _asset_version(name) != latest:
            continue
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.netloc.lower() not in {
            "github.com", "www.github.com", "objects.githubusercontent.com"
        }:
            continue
        digest = _asset_sha256(asset)
        if not digest:
            return "", name, "", "no_checksum"
        return url, name, digest, ""
    if has_installer:
        return "", "", "", "version_mismatch"
    return "", "", "", "no_asset"


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
        download_url, asset_name, sha256, unavailable = _find_asset(payload, latest)
        info = UpdateInfo(
            current=self._current,
            latest=".".join(str(part) for part in latest),
            available=latest > current,
            url=str(url) if _is_github_page(url) else RELEASES_PAGE,
            notes=body[:NOTES_LIMIT] if isinstance(body, str) else "",
            download_url=download_url,
            asset_name=asset_name,
            sha256=sha256,
            download_unavailable=unavailable,
        )
        log.info(
            "update check: current=%s latest=%s available=%s",
            info.current,
            info.latest,
            info.available,
        )
        return info
