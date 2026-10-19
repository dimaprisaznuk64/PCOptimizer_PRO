from __future__ import annotations

from unittest import mock
import pytest

from app.cleaner.standby import purge_standby_list, StandbyListError


def test_purge_standby_list_success():
    fake_ntdll = mock.MagicMock()
    fake_ntdll.NtSetSystemInformation.return_value = 0
    with mock.patch("ctypes.WinDLL", return_value=fake_ntdll):
        assert purge_standby_list() is True


def test_purge_standby_list_failure():
    fake_ntdll = mock.MagicMock()
    fake_ntdll.NtSetSystemInformation.return_value = 0xC0000001
    with mock.patch("ctypes.WinDLL", return_value=fake_ntdll):
        with pytest.raises(StandbyListError):
            purge_standby_list()
