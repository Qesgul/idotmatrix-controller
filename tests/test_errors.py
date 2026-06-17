import pytest
from idotctl.errors import (
    IdotError, DeviceNotFoundError, BleConnectionError,
    ImageError, FirmwareUnsupportedError,
)


def test_all_errors_subclass_base():
    for cls in (DeviceNotFoundError, BleConnectionError, ImageError, FirmwareUnsupportedError):
        assert issubclass(cls, IdotError)


def test_error_carries_message():
    err = ImageError("文件不存在")
    assert str(err) == "文件不存在"
