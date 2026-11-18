from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QFileDialog

from app.i18n import I18nService, tr
from app.reports.system import (
    REDACTED,
    SECTION_HEADINGS,
    SystemReportConfig,
    build_system_report,
    redact_identifier,
    render_system_report,
)
from app.ui.system_report import SystemReportPage


def _wait_for(qapp, predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False



def test_config_and_redact_identifier_defaults() -> None:
    config = SystemReportConfig()
    assert config.include_identifiers is False
    assert config.output == "html"
    with pytest.raises(AttributeError):
        config.include_identifiers = True
    assert redact_identifier("DESKTOP-SECRET") == REDACTED
    assert redact_identifier("DESKTOP-SECRET", include_identifiers=True) == "DESKTOP-SECRET"
    assert redact_identifier("") == ""


def test_build_report_redacts_identifiers_by_default() -> None:
    text = build_system_report(
        system={"hostname": "DESKTOP-SECRET", "os_name": "Windows 11"},
        hardware={
            "board": {"serial": "BOARD-123"},
            "disks": [{"model": "SSD", "serial": "DISK-456"}],
        },
        generated="2026-11-18T10:00:00",
    )
    for value in ("DESKTOP-SECRET", "BOARD-123", "DISK-456"):
        assert value not in text
    assert text.count(REDACTED) >= 3
    assert "Windows 11" in text
    assert "SSD" in text


def test_build_report_includes_identifiers_with_explicit_consent() -> None:
    text = build_system_report(
        system={"hostname": "DESKTOP-SECRET"},
        hardware={"board": {"serial": "BOARD-123"}},
        config=SystemReportConfig(include_identifiers=True),
        generated="T",
    )
    assert "DESKTOP-SECRET" in text
    assert "BOARD-123" in text


def test_build_report_never_includes_secrets_even_with_identifier_consent() -> None:
    text = build_system_report(
        system={
            "hostname": "DESKTOP-SECRET",
            "password": "hunter2",
            "token": "tok-abc",
            "api_key": "key-xyz",
            "note": "Authorization: Bearer secretbearer",
        },
        config=SystemReportConfig(include_identifiers=True),
        generated="T",
    )
    for secret in ("hunter2", "tok-abc", "key-xyz", "secretbearer"):
        assert secret not in text
    assert "DESKTOP-SECRET" in text
    assert text.count(REDACTED) >= 4


def test_build_report_with_missing_providers_shows_all_headings() -> None:
    text = build_system_report(generated="T", config=SystemReportConfig(output="text"))
    for heading in SECTION_HEADINGS:
        assert f"\n{heading}\n" in text
    assert text.count("Unavailable") == len(SECTION_HEADINGS)


def test_system_report_headings_have_stable_order() -> None:
    text = build_system_report(generated="T", config=SystemReportConfig(output="text"))
    positions = [text.index(f"\n{heading}\n") for heading in SECTION_HEADINGS]
    assert positions == sorted(positions)


def test_provider_callables_and_failures_are_resolved() -> None:
    def system_provider():
        return {"os_name": "Windows 11"}

    def broken():
        raise RuntimeError("sensor offline")

    text = build_system_report(
        system=system_provider,
        health=broken,
        generated="T",
        config=SystemReportConfig(output="text"),
    )
    assert "Windows 11" in text
    assert "Unavailable: sensor offline" in text


def test_render_system_report_supports_text_and_html() -> None:
    sections = {"system": {"hostname": "PC-1"}}
    text = render_system_report(sections, config=SystemReportConfig(output="text"), generated="T")
    assert "\nSystem\n" in text
    assert f"Hostname: {REDACTED}" in text
    rendered = render_system_report(sections, generated="<x>")
    assert "<h2>System</h2>" in rendered
    assert "&lt;x&gt;" in rendered


def test_render_system_report_rejects_unknown_output() -> None:
    with pytest.raises(ValueError):
        render_system_report({}, config=SystemReportConfig(output="pdf"))


def _providers() -> dict[str, object]:
    return {
        "system": {"hostname": "PC-SECRET", "os_name": "Windows 11"},
        "hardware": {"cpu": "Ryzen 7 5800H"},
    }


def test_system_report_page_generates_redacted_report(qapp) -> None:
    page = SystemReportPage(providers=_providers())
    page.start_generate()
    assert _wait_for(qapp, lambda: "Report ready" in page.status_label.text())
    assert "Windows 11" in page.preview.toPlainText()
    assert "PC-SECRET" not in page.preview.toPlainText()
    assert page.save_button.isEnabled()


def test_system_report_page_text_format_and_identifier_consent(qapp) -> None:
    page = SystemReportPage(providers=_providers())
    page.ids_check.setChecked(True)
    page.format_combo.setCurrentIndex(1)
    page.start_generate()
    assert _wait_for(qapp, lambda: "Report ready" in page.status_label.text())
    text = page.preview.toPlainText()
    assert "SYSTEM REPORT" in text
    assert "PC-SECRET" in text


def test_system_report_page_saves_selected_format(qapp, tmp_path, monkeypatch) -> None:
    target = tmp_path / "report.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))
    page = SystemReportPage(providers=_providers())
    page.format_combo.setCurrentIndex(1)
    page.start_generate()
    assert _wait_for(qapp, lambda: "Report ready" in page.status_label.text())
    page.save_report()
    assert target.exists()
    assert "Windows 11" in target.read_text(encoding="utf-8")


def test_system_report_page_retranslate(qapp) -> None:
    page = SystemReportPage(providers=_providers())
    I18nService.instance().set_language("UA", emit=False)
    try:
        page.retranslate()
        assert page.generate_button.text() == tr("sys_generate")
        assert page.preview.toPlainText() == tr("sys_empty")
    finally:
        I18nService.instance().set_language("EN", emit=False)
