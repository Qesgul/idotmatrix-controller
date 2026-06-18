import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from idotctl.webserver.app import app, get_session, get_staging
from idotctl.webserver.session import DeviceSession
from idotctl.webserver.staging import ImageStaging
from idotctl.core.device import FakeDevice


def _make_client():
    fake = FakeDevice()
    session = DeviceSession(fake)
    staging = ImageStaging()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_staging] = lambda: staging
    return TestClient(app), session, staging, fake


def _png(color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color).save(buf, "PNG")
    return buf.getvalue()


def _gif() -> bytes:
    frames = [Image.new("RGB", (40, 40), c) for c in [(255, 0, 0), (0, 255, 0)]]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return buf.getvalue()


def test_get_root_returns_html():
    client, _, _, _ = _make_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_status_not_connected():
    client, _, _, _ = _make_client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["address"] is None


def test_scan_returns_device_list():
    client, _, _, _ = _make_client()
    resp = client.post("/api/scan")
    assert resp.status_code == 200
    devices = resp.json()
    assert isinstance(devices, list)
    assert devices[0]["address"] == "AA:BB:CC:DD:EE:FF"


def test_connect_sets_connected():
    client, session, _, _ = _make_client()
    resp = client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert session.is_connected


def test_connect_then_status_shows_connected():
    client, _, _, _ = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    data = client.get("/api/status").json()
    assert data["connected"] is True
    assert data["address"] == "AA:BB:CC:DD:EE:FF"


def test_disconnect():
    client, session, _, _ = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    resp = client.post("/api/disconnect")
    assert resp.status_code == 200
    assert not session.is_connected


def test_upload_returns_ok():
    client, _, _, _ = _make_client()
    resp = client.post("/api/upload", files={"file": ("test.png", _png(), "image/png")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["is_gif"] is False


def test_upload_gif_detects_is_gif():
    client, _, _, _ = _make_client()
    resp = client.post("/api/upload", files={"file": ("anim.gif", _gif(), "image/gif")})
    assert resp.json()["is_gif"] is True


def test_preview_returns_320x320_png():
    client, _, _, _ = _make_client()
    client.post("/api/upload", files={"file": ("test.png", _png(), "image/png")})
    resp = client.post("/api/preview", json={
        "fit": "crop", "dither": False, "brightness": 1.0, "contrast": 1.0, "saturation": 1.0
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(resp.content))
    assert img.size == (320, 320)


def test_preview_without_upload_returns_400():
    client, _, _, _ = _make_client()
    resp = client.post("/api/preview", json={
        "fit": "crop", "dither": False, "brightness": 1.0, "contrast": 1.0, "saturation": 1.0
    })
    assert resp.status_code == 400
    assert "请先上传图片" in resp.json()["error"]


def test_send_without_connection_returns_400():
    client, _, _, _ = _make_client()
    client.post("/api/upload", files={"file": ("test.png", _png(), "image/png")})
    resp = client.post("/api/send", json={
        "fit": "crop", "dither": False, "brightness": 1.0, "contrast": 1.0, "saturation": 1.0
    })
    assert resp.status_code == 400


def test_send_image_to_connected_device():
    client, _, _, fake = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    client.post("/api/upload", files={"file": ("test.png", _png(), "image/png")})
    resp = client.post("/api/send", json={
        "fit": "crop", "dither": False, "brightness": 1.0, "contrast": 1.0, "saturation": 1.0
    })
    assert resp.status_code == 200
    assert any(c[0] == "send_image" for c in fake.calls)


def test_send_gif_to_connected_device():
    client, _, _, fake = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    client.post("/api/upload", files={"file": ("anim.gif", _gif(), "image/gif")})
    resp = client.post("/api/gif", json={
        "fps": 10, "fit": "crop", "dither": False,
        "brightness": 1.0, "contrast": 1.0, "saturation": 1.0
    })
    assert resp.status_code == 200
    assert any(c[0] == "send_gif" for c in fake.calls)


def test_brightness_without_connection_returns_400():
    client, _, _, _ = _make_client()
    resp = client.post("/api/brightness", json={"level": 70})
    assert resp.status_code == 400


def test_brightness_sets_level():
    client, _, _, fake = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    resp = client.post("/api/brightness", json={"level": 70})
    assert resp.status_code == 200
    assert ("set_brightness", 70) in fake.calls


def test_power_on():
    client, _, _, fake = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    resp = client.post("/api/power", json={"on": True})
    assert resp.status_code == 200
    assert ("set_power", True) in fake.calls


def test_power_off():
    client, _, _, fake = _make_client()
    client.post("/api/connect", json={"address": "AA:BB:CC:DD:EE:FF"})
    resp = client.post("/api/power", json={"on": False})
    assert resp.status_code == 200
    assert ("set_power", False) in fake.calls


def test_power_without_connection_returns_400():
    client, _, _, _ = _make_client()
    resp = client.post("/api/power", json={"on": True})
    assert resp.status_code == 400
