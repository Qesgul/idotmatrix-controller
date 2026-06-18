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
