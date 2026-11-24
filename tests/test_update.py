from __future__ import annotations

import hashlib

from app.update import (
    NOTES_LIMIT,
    RELEASES_PAGE,
    UpdateDownloadError,
    UpdateInfo,
    UpdateService,
    download_installer,
    installer_path,
    parse_version,
)


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


def test_non_github_https_page_falls_back_to_release_page() -> None:
    payload = _release(url="https://example.com/insecure")
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


def test_installer_asset_is_taken_from_release_payload() -> None:
    payload = _release()
    payload["assets"] = [
        {"name": "source.zip", "browser_download_url": "https://github.com/a/source.zip"},
        {
            "name": "PCOptimizer_PRO_Setup_1.6.6.exe",
            "browser_download_url": "https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/download/v1.6.6/PCOptimizer_PRO_Setup_1.6.6.exe",
        },
    ]
    info = UpdateService("1.6.5", fetcher=lambda _u, _t: payload).check()
    assert info.available is True
    assert info.asset_name == "PCOptimizer_PRO_Setup_1.6.6.exe"
    assert info.download_url.startswith("https://github.com/")
    assert info.sha256 == ""


def test_installer_asset_sha256_is_taken_from_release_payload() -> None:
    payload = _release()
    payload["assets"] = [
        {
            "name": "PCOptimizer_PRO_Setup_1.6.6.exe",
            "browser_download_url": "https://github.com/release/setup.exe",
            "digest": "sha256:" + "a" * 64,
        }
    ]
    info = UpdateService("1.6.5", fetcher=lambda _u, _t: payload).check()
    assert info.sha256 == "a" * 64


def test_unsupported_or_malformed_digests_are_ignored() -> None:
    for digest in ("md5:" + "a" * 32, "sha256:xyz", "sha256:" + "g" * 64):
        payload = _release()
        payload["assets"] = [
            {
                "name": "PCOptimizer_PRO_Setup_1.6.6.exe",
                "browser_download_url": "https://github.com/release/setup.exe",
                "digest": digest,
            }
        ]
        info = UpdateService(
            "1.6.5", fetcher=lambda _u, _t, payload=payload: payload
        ).check()
        assert info.sha256 == ""


class _Response:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        chunk = self.data[self.pos : self.pos + size]
        self.pos += len(chunk)
        return chunk


def _info(
    url: str = "https://github.com/release/setup.exe", sha256: str = ""
) -> UpdateInfo:
    return UpdateInfo(
        current="1.6.5",
        latest="1.6.6",
        available=True,
        download_url=url,
        asset_name="PCOptimizer PRO Setup 1.6.6.exe",
        sha256=sha256,
    )


def test_download_installer_streams_and_sanitizes_name(tmp_path) -> None:
    payload = b"MZ" + b"x" * (1024 * 1024)
    target = download_installer(
        _info(), tmp_path, opener=lambda _url, timeout: _Response(payload)
    )
    assert target == installer_path(_info(), tmp_path)
    assert target.name == "PCOptimizer_PRO_Setup_1.6.6.exe"
    assert target.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


def test_download_installer_rejects_bad_payload(tmp_path) -> None:
    class Bad(_Response):
        def __init__(self) -> None:
            super().__init__(b"not an exe")

    try:
        download_installer(_info(), tmp_path, opener=lambda _url, timeout: Bad())
    except UpdateDownloadError as e:
        assert "not a valid" in str(e)
    else:
        raise AssertionError("invalid installer was accepted")
    assert not list(tmp_path.glob("*.part"))


def test_download_installer_verifies_sha256(tmp_path) -> None:
    payload = b"MZ" + b"x" * (1024 * 1024)
    digest = hashlib.sha256(payload).hexdigest()
    target = download_installer(
        _info(sha256=digest), tmp_path, opener=lambda _url, timeout: _Response(payload)
    )
    assert target.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


def test_download_installer_rejects_checksum_mismatch(tmp_path) -> None:
    payload = b"MZ" + b"x" * (1024 * 1024)
    try:
        download_installer(
            _info(sha256="0" * 64),
            tmp_path,
            opener=lambda _url, timeout: _Response(payload),
        )
    except UpdateDownloadError as e:
        assert "checksum" in str(e)
    else:
        raise AssertionError("checksum mismatch was accepted")
    assert not list(tmp_path.glob("*.part"))
    assert not list(tmp_path.glob("*.exe"))


def test_download_installer_rejects_invalid_checksum_metadata(tmp_path) -> None:
    payload = b"MZ" + b"x" * (1024 * 1024)
    try:
        download_installer(
            _info(sha256="not-a-digest"),
            tmp_path,
            opener=lambda _url, timeout: _Response(payload),
        )
    except UpdateDownloadError as e:
        assert "checksum metadata" in str(e)
    else:
        raise AssertionError("invalid checksum metadata was accepted")
    assert not list(tmp_path.glob("*.part"))


def test_download_installer_rejects_untrusted_url(tmp_path) -> None:
    try:
        download_installer(_info("http://example.com/setup.exe"), tmp_path)
    except UpdateDownloadError as e:
        assert "untrusted" in str(e)
    else:
        raise AssertionError("untrusted URL was accepted")


def test_download_installer_rejects_untrusted_https_host(tmp_path) -> None:
    try:
        download_installer(_info("https://evil.test/setup.exe"), tmp_path)
    except UpdateDownloadError as e:
        assert "untrusted" in str(e)
    else:
        raise AssertionError("untrusted HTTPS host was accepted")


def test_default_opener_rejects_cross_host_redirects() -> None:
    from app.update.download import _SafeRedirectHandler

    handler = _SafeRedirectHandler()
    try:
        handler.redirect_request(None, None, 302, "Found", {}, "https://evil.test/setup.exe")
    except UpdateDownloadError as e:
        assert "untrusted" in str(e)
    else:
        raise AssertionError("cross-host redirect was accepted")


def test_download_installer_requires_an_asset(tmp_path) -> None:
    try:
        download_installer(UpdateInfo("1.6.5"), tmp_path)
    except UpdateDownloadError as e:
        assert "no installer" in str(e)
    else:
        raise AssertionError("missing asset was accepted")

