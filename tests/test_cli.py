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
