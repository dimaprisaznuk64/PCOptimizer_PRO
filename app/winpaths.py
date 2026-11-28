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

_CYRILLIC_LETTERS = frozenset(
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯІЇЄҐ"
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґ"
)
_COMMON_PUNCTUATION = frozenset("—–€™©®°·№«»„“”‘’")


def _decode_score(text: str) -> int:
    score = 0
    for char in text:
        if char in _CYRILLIC_LETTERS:
            score += 2
        elif char.isspace() or char.isascii() or char in _COMMON_PUNCTUATION:
            continue
        else:
            score -= 5
    return score


def decode_process_output(raw: bytes | str) -> str:
    """Decode redirected console output written in UTF-8 or a Windows code page."""
    if isinstance(raw, str):
        return raw
    encodings = ("utf-8", "cp866", "cp1251", locale.getpreferredencoding(False))
    candidates: list[tuple[int, int, str]] = []
    for index, encoding in enumerate(encodings):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if index == 0:
            return text
        candidates.append((_decode_score(text), -index, text))
    if candidates:
        return max(candidates, key=lambda item: item[:2])[2]
    return raw.decode("utf-8", errors="replace")


__all__ = ["POWERSHELL_PATH", "PS_UTF8_PREFIX", "decode_process_output"]
