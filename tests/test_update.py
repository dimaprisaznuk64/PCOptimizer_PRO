from __future__ import annotations

from app.update import NOTES_LIMIT, RELEASES_PAGE, UpdateInfo, UpdateService, parse_version


def _release(
    tag: str = "v1.6.6",
    body: str = "release notes",
    url: str = "https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v1.6.6",
) -> dict[str, object]:
    return {"tag_name": tag, "body": body, "html_url": url}


def test_parse_version_accepts_optional_prefix() -> None:
    assert parse_version("v1.6.5") == (1, 6, 5)
    assert parse_version("1.6") == (1, 6)
    assert parse_version("v2.0.0-beta") == (2, 0, 0)
    assert parse_version("nightly") is None


def test_newer_release_is_offered() -> None:
    info = UpdateService("1.6.5", fetcher=lambda _url, _timeout: _release()).check()
    assert info == UpdateInfo(
        current="1.6.5",
        latest="1.6.6",
        available=True,
        url="https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v1.6.6",
        notes="release notes",
    )


def test_same_version_is_not_an_update() -> None:
    info = UpdateService("1.6.5", fetcher=lambda _url, _timeout: _release("v1.6.5")).check()
    assert info.available is False
    assert info.latest == "1.6.5"
    assert info.error is None


def test_older_release_is_not_an_update() -> None:
    info = UpdateService("1.6.5", fetcher=lambda _url, _timeout: _release("v1.5.9")).check()
    assert info.available is False


def test_network_error_is_reported_without_raising() -> None:
    def boom(_url: str, _timeout: float) -> dict[str, object]:
        raise OSError("no internet")

    info = UpdateService("1.6.5", fetcher=boom).check()
    assert info.available is False
    assert info.current == "1.6.5"
    assert "no internet" in (info.error or "")


def test_unexpected_tag_is_reported_as_error() -> None:
    info = UpdateService("1.6.5", fetcher=lambda _url, _timeout: {"tag_name": "nightly"}).check()
    assert info.error is not None
    assert "nightly" in info.error


def test_untrusted_url_falls_back_to_release_page() -> None:
    payload = _release(url="http://example.com/insecure")
    info = UpdateService("1.6.5", fetcher=lambda _url, _timeout: payload).check()
    assert info.url == RELEASES_PAGE


def test_notes_are_truncated() -> None:
    payload = _release(body="x" * (NOTES_LIMIT + 500))
    info = UpdateService("1.6.5", fetcher=lambda _url, _timeout: payload).check()
    assert len(info.notes) == NOTES_LIMIT


def test_fetcher_receives_api_url_and_timeout() -> None:
    seen: dict[str, object] = {}

    def fetch(url: str, timeout: float) -> dict[str, object]:
        seen["url"] = url
        seen["timeout"] = timeout
        return _release()

    UpdateService(
        "1.6.5", api_url="https://example.test/latest", timeout=2.5, fetcher=fetch
    ).check()
    assert seen == {"url": "https://example.test/latest", "timeout": 2.5}
