import asyncio
from idotctl.core.device import DeviceInfo, FakeDevice


def test_fake_device_records_calls():
    dev = FakeDevice()

    async def run():
        found = await dev.scan(3.0)
        await dev.connect(found[0].address)
        await dev.send_image(b"\x89PNG\r\n\x1a\n")  # fake PNG bytes
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
    asyncio.run(dev.send_gif(b"GIF89a"))  # fake GIF bytes
    sent = [c for c in dev.calls if c[0] == "send_gif"][0]
    assert sent[0] == "send_gif"
    assert isinstance(sent[1], int)  # data length
