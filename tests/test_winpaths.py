from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType

from app.winpaths import (
    POWERSHELL_PATH,
    PS_UTF8_PREFIX,
    decode_process_output,
)

_EXPECTED_TAIL = ("System32", "WindowsPowerShell", "v1.0", "powershell.exe")


@contextmanager
def _winpaths_with_root(root: str | None) -> Iterator[ModuleType]:
    module = importlib.import_module("app.winpaths")
    original_path = module.POWERSHELL_PATH
    original_root = os.environ.get("SystemRoot")
    try:
        if root is None:
            os.environ.pop("SystemRoot", None)
        else:
            os.environ["SystemRoot"] = root
        yield importlib.reload(module)
    finally:
        if original_root is None:
            os.environ.pop("SystemRoot", None)
        else:
            os.environ["SystemRoot"] = original_root
        importlib.reload(module)
        assert module.POWERSHELL_PATH == original_path


class _UndecodableBytes(bytes):
    def decode(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        if errors == "replace":
            return "fallback"
        raise UnicodeDecodeError(encoding, b"\xff", 0, 1, "undecodable")


def test_powershell_path_uses_systemroot() -> None:
    with _winpaths_with_root(r"D:\WinTest") as module:
        assert module.POWERSHELL_PATH == os.path.join(r"D:\WinTest", *_EXPECTED_TAIL)


def test_powershell_path_falls_back_to_windows() -> None:
    with _winpaths_with_root(None) as module:
        assert module.POWERSHELL_PATH == os.path.join(r"C:\Windows", *_EXPECTED_TAIL)


def test_module_path_is_absolute() -> None:
    assert os.path.isabs(POWERSHELL_PATH)
    assert POWERSHELL_PATH.lower().endswith("powershell.exe")
    assert os.path.join(*_EXPECTED_TAIL) in POWERSHELL_PATH


def test_utf8_prefix_sets_console_encoding() -> None:
    assert PS_UTF8_PREFIX.startswith("[Console]::OutputEncoding=")
    assert "[System.Text.Encoding]::UTF8" in PS_UTF8_PREFIX
    assert PS_UTF8_PREFIX.endswith("; ")


def test_decode_process_output_passes_str_through() -> None:
    text = "Привіт"
    assert decode_process_output(text) is text


def test_decode_process_output_decodes_utf8() -> None:
    assert decode_process_output("Привіт".encode()) == "Привіт"
    assert decode_process_output(b"Error 7023") == "Error 7023"
    assert decode_process_output(b"") == ""


def test_decode_process_output_decodes_oem_codepage() -> None:
    raw = "Служба завершена".encode("cp866")
    assert decode_process_output(raw) == "Служба завершена"


def test_decode_process_output_prefers_cp1251_for_windows_1251_text() -> None:
    for text in (
        "Роботу служби завершено",
        "Помилка доступу",
        "Завантаження",
    ):
        assert decode_process_output(text.encode("cp1251")) == text


def test_decode_process_output_prefers_cp866_for_oem_text() -> None:
    for text in ("Служба завершена", "Проверка завершена"):
        assert decode_process_output(text.encode("cp866")) == text


def test_decode_process_output_falls_back_to_replacement() -> None:
    assert decode_process_output(_UndecodableBytes(b"\xff")) == "fallback"
