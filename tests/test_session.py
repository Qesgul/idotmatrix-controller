import asyncio
import pytest
from idotctl.webserver.session import DeviceSession
from idotctl.core.device import FakeDevice
from idotctl.core.imaging import PixelFrame
from idotctl.errors import BleConnectionError


def test_not_connected_initially():
    session = DeviceSession(FakeDevice())
    assert not session.is_connected
    assert session.current_address is None


def test_connect_sets_state():
    async def _run():
        fake = FakeDevice()
        session = DeviceSession(fake)
        await session.connect("AA:BB:CC:DD:EE:FF")
        assert session.is_connected
        assert session.current_address == "AA:BB:CC:DD:EE:FF"
        assert ("connect", "AA:BB:CC:DD:EE:FF") in fake.calls
    asyncio.run(_run())


def test_disconnect_clears_state():
    async def _run():
        fake = FakeDevice()
        session = DeviceSession(fake)
        await session.connect("AA:BB:CC:DD:EE:FF")
        await session.disconnect()
        assert not session.is_connected
        assert session.current_address is None
    asyncio.run(_run())


def test_scan_returns_devices():
    async def _run():
        session = DeviceSession(FakeDevice())
        result = await session.scan(5.0)
        assert len(result) == 1
        assert result[0].address == "AA:BB:CC:DD:EE:FF"
    asyncio.run(_run())


def test_send_image_raises_when_not_connected():
    async def _run():
        session = DeviceSession(FakeDevice())
        frame = PixelFrame(size=32, pixels=bytes(32 * 32 * 3))
        with pytest.raises(BleConnectionError):
            await session.send_image(frame)
    asyncio.run(_run())


def test_send_image_delegates_to_device():
    async def _run():
        fake = FakeDevice()
        session = DeviceSession(fake)
        await session.connect("AA:BB:CC:DD:EE:FF")
        frame = PixelFrame(size=32, pixels=bytes(32 * 32 * 3))
        await session.send_image(frame)
        assert ("send_image", frame) in fake.calls
    asyncio.run(_run())


def test_send_gif_delegates_to_device():
    async def _run():
        fake = FakeDevice()
        session = DeviceSession(fake)
        await session.connect("AA:BB:CC:DD:EE:FF")
        frames = [PixelFrame(size=32, pixels=bytes(32 * 32 * 3))]
        await session.send_gif(frames, fps=10)
        assert ("send_gif", 1, 10) in fake.calls
    asyncio.run(_run())


def test_set_brightness_raises_when_not_connected():
    async def _run():
        session = DeviceSession(FakeDevice())
        with pytest.raises(BleConnectionError):
            await session.set_brightness(50)
    asyncio.run(_run())


def test_set_power_raises_when_not_connected():
    async def _run():
        session = DeviceSession(FakeDevice())
        with pytest.raises(BleConnectionError):
            await session.set_power(True)
    asyncio.run(_run())


def test_set_brightness_delegates():
    async def _run():
        fake = FakeDevice()
        session = DeviceSession(fake)
        await session.connect("AA:BB:CC:DD:EE:FF")
        await session.set_brightness(70)
        assert ("set_brightness", 70) in fake.calls
    asyncio.run(_run())


def test_set_power_delegates():
    async def _run():
        fake = FakeDevice()
        session = DeviceSession(fake)
        await session.connect("AA:BB:CC:DD:EE:FF")
        await session.set_power(False)
        assert ("set_power", False) in fake.calls
    asyncio.run(_run())
