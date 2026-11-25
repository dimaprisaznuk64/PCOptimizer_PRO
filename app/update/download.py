from __future__ import annotations

import hashlib
import hmac
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app.settings import data_root

from .service import RELEASES_PAGE, UpdateInfo

MAX_INSTALLER_BYTES = 250 * 1024 * 1024
MIN_INSTALLER_BYTES = 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_HOSTS = {"github.com", "www.github.com", "objects.githubusercontent.com"}


class UpdateDownloadError(RuntimeError):
    pass


def _is_trusted_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.lower() in _ALLOWED_HOSTS


def _expected_digest(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise UpdateDownloadError("invalid checksum metadata for this release")
    return text


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_trusted_url(newurl):
            raise UpdateDownloadError("redirect to an untrusted host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def installer_path(info: UpdateInfo, directory: str | Path | None = None) -> Path:
    name = _SAFE_NAME.sub("_", Path(info.asset_name).name).strip("._")
    if not name.lower().endswith(".exe"):
        name = f"PCOptimizer_PRO_Setup_{info.latest or 'latest'}.exe"
    root = Path(directory) if directory is not None else data_root() / "updates"
    return root / name


def download_installer(
    info: UpdateInfo,
    directory: str | Path | None = None,
    *,
    opener: Any = None,
    timeout: float = 30.0,
    chunk_size: int = 64 * 1024,
) -> Path:
    """Download a published installer to *directory*, atomically and with checks."""
    if not info.download_url:
        raise UpdateDownloadError("this release has no installer asset")
    if not _is_trusted_url(info.download_url):
        raise UpdateDownloadError("untrusted installer URL")

    expected = _expected_digest(getattr(info, "sha256", ""))
    if not expected:
        raise UpdateDownloadError(
            f"no verified SHA-256 checksum for this release; see {info.url or RELEASES_PAGE}"
        )

    target = installer_path(info, directory)
    temp = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    open_url = opener or urllib.request.build_opener(_SafeRedirectHandler()).open
    written = 0
    digest = hashlib.sha256()
    try:
        with open_url(info.download_url, timeout=timeout) as response:
            headers = getattr(response, "headers", None)
            declared = headers.get("Content-Length") if headers is not None else None
            if declared is not None and int(declared) > MAX_INSTALLER_BYTES:
                raise UpdateDownloadError("installer is unexpectedly large")
            with temp.open("wb") as out:
                while chunk := response.read(chunk_size):
                    written += len(chunk)
                    if written > MAX_INSTALLER_BYTES:
                        raise UpdateDownloadError("installer download exceeded the size limit")
                    digest.update(chunk)
                    out.write(chunk)
        with temp.open("rb") as downloaded:
            magic = downloaded.read(2)
        if written < MIN_INSTALLER_BYTES or magic != b"MZ":
            raise UpdateDownloadError("downloaded file is not a valid Windows installer")
        if not hmac.compare_digest(digest.hexdigest(), expected):
            raise UpdateDownloadError("checksum mismatch: installer was not saved")
        temp.replace(target)
    except UpdateDownloadError:
        _discard(temp)
        raise
    except Exception as exc:
        _discard(temp)
        raise UpdateDownloadError(str(exc) or type(exc).__name__) from exc
    return target


def _discard(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
