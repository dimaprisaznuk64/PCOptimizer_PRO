"""Windows executable paths and PowerShell invocation tokens."""

from __future__ import annotations

import locale
import os

POWERSHELL_PATH = os.path.join(
    os.environ.get("SystemRoot") or r"C:\Windows",
    "System32",
    "WindowsPowerShell",
    "v1.0",
    "powershell.exe",
)
PS_UTF8_PREFIX = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "


def decode_process_output(raw: bytes | str) -> str:
    """Decode redirected console output written in UTF-8 or an OEM code page."""
    if isinstance(raw, str):
        return raw
    encodings = ("utf-8", "cp866", "cp1251", locale.getpreferredencoding(False))
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


__all__ = ["POWERSHELL_PATH", "PS_UTF8_PREFIX", "decode_process_output"]
