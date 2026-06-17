from idotctl import config


def test_roundtrip_save_load(tmp_path):
    path = tmp_path / "config.json"
    config.save_config({"last_device": "AA:BB", "brightness": 80}, path=path)
    loaded = config.load_config(path=path)
    assert loaded["last_device"] == "AA:BB"
    assert loaded["brightness"] == 80


def test_load_missing_returns_empty(tmp_path):
    assert config.load_config(path=tmp_path / "nope.json") == {}


def test_last_device_helpers(tmp_path):
    path = tmp_path / "config.json"
    assert config.get_last_device(path=path) is None
    config.set_last_device("CC:DD:EE", path=path)
    assert config.get_last_device(path=path) == "CC:DD:EE"
