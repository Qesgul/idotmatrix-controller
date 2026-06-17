import asyncio
from PIL import Image
from idotctl.cli import build_parser, cmd_scan, cmd_connect, cmd_send, cmd_gif, cmd_brightness, cmd_power
from idotctl.core.device import FakeDevice


def _img(tmp_path, name="x.png", color=(0, 200, 0)):
    p = tmp_path / name
    Image.new("RGB", (20, 20), color).save(p)
    return str(p)


def test_scan_lists_devices(capsys):
    dev = FakeDevice()
    args = build_parser().parse_args(["scan"])
    rc = asyncio.run(cmd_scan(args, dev))
    assert rc == 0
    assert ("scan", 5.0) in dev.calls
    assert "FakeMatrix" in capsys.readouterr().out


def test_connect_remembers_device(tmp_path):
    cfgp = tmp_path / "c.json"
    dev = FakeDevice()
    args = build_parser().parse_args(["connect", "AA:BB:CC"])
    rc = asyncio.run(cmd_connect(args, dev, config_path=cfgp))
    assert rc == 0
    from idotctl import config
    assert config.get_last_device(path=cfgp) == "AA:BB:CC"


def test_send_processes_connects_and_sends(tmp_path):
    img = _img(tmp_path)
    dev = FakeDevice()
    args = build_parser().parse_args(["send", img, "--device", "AA:BB", "--no-dither"])
    rc = asyncio.run(cmd_send(args, dev, config_path=tmp_path / "c.json"))
    assert rc == 0
    assert dev.connected_address is None  # 结束断开
    names = [c[0] for c in dev.calls]
    assert names == ["connect", "send_image", "disconnect"]


def test_send_without_device_uses_last(tmp_path):
    cfgp = tmp_path / "c.json"
    from idotctl import config
    config.set_last_device("ZZ:YY", path=cfgp)
    dev = FakeDevice()
    args = build_parser().parse_args(["send", _img(tmp_path), "--no-dither"])
    rc = asyncio.run(cmd_send(args, dev, config_path=cfgp))
    assert rc == 0
    assert ("connect", "ZZ:YY") in dev.calls


def test_brightness_and_power(tmp_path):
    cfgp = tmp_path / "c.json"
    from idotctl import config
    config.set_last_device("ZZ:YY", path=cfgp)
    dev = FakeDevice()
    a1 = build_parser().parse_args(["brightness", "70"])
    assert asyncio.run(cmd_brightness(a1, dev, config_path=cfgp)) == 0
    assert ("set_brightness", 70) in dev.calls
    a2 = build_parser().parse_args(["off"])
    assert asyncio.run(cmd_power(a2, dev, config_path=cfgp)) == 0
    assert ("set_power", False) in dev.calls


def test_gif_sends_frames(tmp_path):
    from PIL import Image as PILImage
    from idotctl.cli import cmd_gif
    # create a 3-frame GIF
    frames = [PILImage.new("RGB", (20, 20), c) for c in [(255,0,0),(0,255,0),(0,0,255)]]
    p = tmp_path / "a.gif"
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=100, loop=0)
    cfgp = tmp_path / "c.json"
    from idotctl import config
    config.set_last_device("AA:BB", path=cfgp)
    dev = FakeDevice()
    args = build_parser().parse_args(["gif", str(p), "--no-dither"])
    rc = asyncio.run(cmd_gif(args, dev, config_path=cfgp))
    assert rc == 0
    gif_call = [c for c in dev.calls if c[0] == "send_gif"][0]
    assert gif_call[1] == 3   # 3 frames sent
    assert gif_call[2] == 10  # default fps


def test_preview_writes_png(tmp_path):
    from idotctl.cli import cmd_preview
    img = _img(tmp_path, color=(123, 50, 200))
    out = tmp_path / "preview.png"
    args = build_parser().parse_args(["preview", img, "-o", str(out)])
    rc = cmd_preview(args)
    assert rc == 0
    assert out.exists()
    from PIL import Image
    got = Image.open(out)
    assert got.size == (32, 32)


def test_main_preview_end_to_end(tmp_path):
    from idotctl.cli import main
    img = _img(tmp_path)
    out = tmp_path / "e2e.png"
    rc = main(["preview", img, "-o", str(out), "--no-dither"])
    assert rc == 0
    assert out.exists()


def test_main_returns_1_on_image_error(tmp_path):
    from unittest.mock import patch
    from idotctl.cli import main
    from idotctl.core.device import FakeDevice
    with patch("idotctl.cli.SdkDevice", FakeDevice):
        rc = main(["send", str(tmp_path / "nope.png"), "--device", "AA:BB"])
    assert rc == 1


def test_send_without_device_raises_error(tmp_path):
    import pytest
    from idotctl.errors import DeviceNotFoundError
    cfgp = tmp_path / "empty.json"
    dev = FakeDevice()
    img = _img(tmp_path)
    args = build_parser().parse_args(["send", img, "--no-dither"])
    with pytest.raises(DeviceNotFoundError):
        asyncio.run(cmd_send(args, dev, config_path=cfgp))
