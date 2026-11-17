from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app.settings import data_root

from .service import UpdateInfo

MAX_INSTALLER_BYTES = 250 * 1024 * 1024
MIN_INSTALLER_BYTES = 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_HOSTS = {"github.com", "www.github.com", "objects.githubusercontent.com"}


class UpdateDownloadError(RuntimeError):
    pass


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
    parsed = urllib.parse.urlparse(info.download_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in _ALLOWED_HOSTS:
        raise UpdateDownloadError("untrusted installer URL")

    target = installer_path(info, directory)
    temp = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    open_url = opener or urllib.request.urlopen
    written = 0
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
                    out.write(chunk)
        if written < MIN_INSTALLER_BYTES or temp.read_bytes()[:2] != b"MZ":
            raise UpdateDownloadError("downloaded file is not a valid Windows installer")
        temp.replace(target)
    except (OSError, ValueError, UpdateDownloadError) as e:
        temp.unlink(missing_ok=True)
        if isinstance(e, UpdateDownloadError):
            raise
        raise UpdateDownloadError(str(e)) from e
    return target
