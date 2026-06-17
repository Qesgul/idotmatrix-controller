import asyncio
from idotctl.core.device import DeviceInfo, FakeDevice
from idotctl.core.imaging import PixelFrame


def test_fake_device_records_calls():
    dev = FakeDevice()
    frame = PixelFrame(size=32, pixels=bytes(32 * 32 * 3))

    async def run():
        found = await dev.scan(3.0)
        await dev.connect(found[0].address)
        await dev.send_image(frame)
        await dev.set_brightness(50)
        await dev.set_power(False)
        await dev.disconnect()
        return found

    found = asyncio.run(run())
    assert isinstance(found[0], DeviceInfo)
    assert dev.connected_address is None  # disconnect 后清空
    names = [c[0] for c in dev.calls]
    assert names == ["scan", "connect", "send_image", "set_brightness", "set_power", "disconnect"]


def test_fake_device_send_gif():
    dev = FakeDevice()
    frames = [PixelFrame(size=32, pixels=bytes(32 * 32 * 3)) for _ in range(3)]
    asyncio.run(dev.send_gif(frames, fps=10))
    sent = [c for c in dev.calls if c[0] == "send_gif"][0]
    assert sent[1] == 3   # 帧数
    assert sent[2] == 10  # fps
