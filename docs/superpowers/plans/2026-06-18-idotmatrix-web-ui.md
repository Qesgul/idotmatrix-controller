# iDotMatrix Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI + native HTML/JS/CSS web UI to idotmatrix-controller so phones/tablets on the same WiFi can upload images, preview 32×32 output in real time, and control the LED display without installing anything.

**Architecture:** New `idotctl/webserver/` sub-package alongside the existing CLI; `core/imaging.py`, `core/device.py`, `config.py`, and `cli.py` are untouched. `DeviceSession` wraps a `DeviceAdapter` with a persistent BLE connection serialized by `asyncio.Lock`. `ImageStaging` holds the last uploaded image in memory so preview and send both process the same source bytes without re-uploading.

**Tech Stack:** FastAPI, uvicorn[standard], python-multipart, httpx (test), Pillow (existing), pytest (existing), asyncio.

---

### Task 1: Install dependencies + scaffold webserver package

**Files:**
- Modify: `pyproject.toml`
- Create: `idotctl/webserver/__init__.py`
- Create: `idotctl/webserver/session.py` (stub)
- Create: `idotctl/webserver/staging.py` (stub)
- Create: `idotctl/webserver/app.py` (stub)
- Create: `idotctl/webserver/static/index.html`
- Create: `idotctl/webserver/static/app.js`
- Create: `idotctl/webserver/static/style.css`
- Test: `tests/test_webserver_import.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webserver_import.py
def test_webserver_package_importable():
    import idotctl.webserver
    assert True

def test_session_importable():
    from idotctl.webserver.session import DeviceSession
    assert DeviceSession is not None

def test_staging_importable():
    from idotctl.webserver.staging import ImageStaging
    assert ImageStaging is not None

def test_app_importable():
    from idotctl.webserver.app import app
    assert app is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webserver_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'idotctl.webserver'`

- [ ] **Step 3: Update pyproject.toml**

```toml
[project]
name = "idotmatrix-controller"
version = "0.1.0"
description = "自己的 iDotMatrix 32x32 LED 控制 CLI"
requires-python = ">=3.10"
dependencies = [
    "idotmatrix-sdk",
    "Pillow",
    "fastapi",
    "uvicorn[standard]",
    "python-multipart",
]

[project.optional-dependencies]
dev = ["pytest", "httpx"]

[project.scripts]
idotctl = "idotctl.cli:main"
idotctl-web = "idotctl.webserver.app:main"

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["idotctl", "idotctl.core", "idotctl.webserver"]
```

- [ ] **Step 4: Install new dependencies**

Run: `.venv/Scripts/pip install -e ".[dev]"`
Expected: Successfully installed fastapi, uvicorn, python-multipart, httpx

- [ ] **Step 5: Create package and stub files**

`idotctl/webserver/__init__.py` — empty file.

`idotctl/webserver/session.py`:
```python
"""DeviceSession — 常驻 BLE 连接管理。"""
```

`idotctl/webserver/staging.py`:
```python
"""ImageStaging — 暂存上传图片供预览/发送复用。"""
```

`idotctl/webserver/app.py`:
```python
"""FastAPI 应用入口。"""
from fastapi import FastAPI
app = FastAPI()
```

`idotctl/webserver/static/index.html`:
```html
<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><title>iDotMatrix</title></head><body><p>iDotMatrix Web UI</p></body></html>
```

`idotctl/webserver/static/app.js` — empty file.
`idotctl/webserver/static/style.css` — empty file.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_webserver_import.py -v`
Expected: 4 PASS

- [ ] **Step 7: Run full suite to verify no regressions**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 31 PASS (27 existing + 4 new)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml idotctl/webserver/ tests/test_webserver_import.py
git commit -m "feat: scaffold webserver package and install fastapi deps"
```

---

### Task 2: ImageStaging

**Files:**
- Modify: `idotctl/webserver/staging.py`
- Create: `tests/test_staging.py`

**Context:** `ImageStaging` is a pure in-memory single-slot buffer. It stores the last uploaded image bytes and exposes three output methods that all call into the existing (unchanged) `_process_pil` from `idotctl/core/imaging.py`. The preview method returns a 320×320 nearest-neighbor upscale of the 32×32 frame as PNG bytes, so the browser can display it clearly while it remains pixel-perfect to what the device will render.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_staging.py
import io
import pytest
from PIL import Image
from idotctl.webserver.staging import ImageStaging
from idotctl.core.imaging import ImageOptions, PixelFrame
from idotctl.errors import ImageError


def _png(color=(255, 0, 0), size=(100, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _gif(colors=None) -> bytes:
    colors = colors or [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    frames = [Image.new("RGB", (40, 40), c) for c in colors]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return buf.getvalue()


def test_has_image_false_initially():
    assert not ImageStaging().has_image


def test_stage_sets_has_image():
    s = ImageStaging()
    s.stage(_png(), "test.png")
    assert s.has_image


def test_stage_overwrites_previous():
    s = ImageStaging()
    s.stage(_png((255, 0, 0)), "red.png")
    s.stage(_png((0, 255, 0)), "green.png")
    assert s.has_image  # still has an image (second one)


def test_render_preview_raises_when_no_image():
    with pytest.raises(ImageError, match="请先上传图片"):
        ImageStaging().render_preview(ImageOptions())


def test_get_frame_raises_when_no_image():
    with pytest.raises(ImageError, match="请先上传图片"):
        ImageStaging().get_frame(ImageOptions())


def test_get_gif_frames_raises_when_no_image():
    with pytest.raises(ImageError, match="请先上传图片"):
        ImageStaging().get_gif_frames(ImageOptions())


def test_render_preview_returns_320x320_png():
    s = ImageStaging()
    s.stage(_png(), "test.png")
    result = s.render_preview(ImageOptions(dither=False))
    img = Image.open(io.BytesIO(result))
    assert img.size == (320, 320)
    assert img.format == "PNG"


def test_get_frame_returns_32x32_pixelframe():
    s = ImageStaging()
    s.stage(_png(), "test.png")
    frame = s.get_frame(ImageOptions(dither=False))
    assert isinstance(frame, PixelFrame)
    assert frame.size == 32
    assert len(frame.pixels) == 32 * 32 * 3


def test_get_gif_frames_returns_all_frames():
    s = ImageStaging()
    s.stage(_gif(), "anim.gif")
    frames = s.get_gif_frames(ImageOptions(dither=False))
    assert len(frames) == 3
    assert all(f.size == 32 for f in frames)
    assert all(len(f.pixels) == 32 * 32 * 3 for f in frames)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staging.py -v`
Expected: FAIL with `ImportError` (class not defined yet)

- [ ] **Step 3: Implement staging.py**

```python
"""ImageStaging — 暂存上传图片供预览/发送复用。"""
from __future__ import annotations
import io
from PIL import Image, UnidentifiedImageError
from idotctl.core.imaging import ImageOptions, PixelFrame, _process_pil
from idotctl.errors import ImageError


class ImageStaging:
    """单槽图片暂存:后传覆盖前传。纯逻辑,不碰硬件。"""

    def __init__(self) -> None:
        self._data: bytes | None = None
        self._filename: str = ""

    @property
    def has_image(self) -> bool:
        return self._data is not None

    def stage(self, data: bytes, filename: str) -> None:
        self._data = data
        self._filename = filename

    def _require_image(self) -> bytes:
        if self._data is None:
            raise ImageError("请先上传图片")
        return self._data

    def _open(self, data: bytes) -> Image.Image:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
        except (UnidentifiedImageError, OSError) as exc:
            raise ImageError("无法识别的图片格式") from exc

    def render_preview(self, opts: ImageOptions) -> bytes:
        """返回 320×320 放大预览 PNG(最近邻插值)。所见即所发:走与发送完全相同的管道。"""
        data = self._require_image()
        img = self._open(data).convert("RGB")
        frame = _process_pil(img, opts)
        small = Image.frombytes("RGB", (frame.size, frame.size), frame.pixels)
        preview = small.resize((320, 320), Image.NEAREST)
        buf = io.BytesIO()
        preview.save(buf, "PNG")
        return buf.getvalue()

    def get_frame(self, opts: ImageOptions) -> PixelFrame:
        """返回 32×32 PixelFrame,供 send_image 使用。"""
        data = self._require_image()
        img = self._open(data).convert("RGB")
        return _process_pil(img, opts)

    def get_gif_frames(self, opts: ImageOptions) -> list[PixelFrame]:
        """返回 GIF 全部帧的 PixelFrame 列表。"""
        data = self._require_image()
        img = self._open(data)
        n = getattr(img, "n_frames", 1)
        frames: list[PixelFrame] = []
        for i in range(n):
            img.seek(i)
            frames.append(_process_pil(img.convert("RGB"), opts))
        return frames
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staging.py -v`
Expected: 10 PASS

- [ ] **Step 5: Run full suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 41 PASS

- [ ] **Step 6: Commit**

```bash
git add idotctl/webserver/staging.py tests/test_staging.py
git commit -m "feat: add ImageStaging for in-memory image buffering and server-side preview"
```

---

### Task 3: DeviceSession

**Files:**
- Modify: `idotctl/webserver/session.py`
- Create: `tests/test_session.py`

**Context:** `DeviceSession` wraps any `DeviceAdapter` (injected at construction) with a persistent connection and `asyncio.Lock` to prevent concurrent BLE writes. All tests must run their async operations in a single `asyncio.run()` call so they share one event loop — the Lock binds to the first loop that uses it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_session.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_session.py -v`
Expected: FAIL

- [ ] **Step 3: Implement session.py**

```python
"""DeviceSession — 常驻 BLE 连接管理。"""
from __future__ import annotations
import asyncio
from idotctl.core.device import DeviceAdapter, DeviceInfo
from idotctl.core.imaging import PixelFrame
from idotctl.errors import BleConnectionError


class DeviceSession:
    """全局单例:持有一个常驻 BLE 连接,asyncio.Lock 串行化所有操作。"""

    def __init__(self, device: DeviceAdapter) -> None:
        self._device = device
        self._lock = asyncio.Lock()
        self._connected = False
        self._address: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def current_address(self) -> str | None:
        return self._address

    async def scan(self, timeout: float = 5.0) -> list[DeviceInfo]:
        async with self._lock:
            return await self._device.scan(timeout)

    async def connect(self, address: str) -> None:
        async with self._lock:
            await self._device.connect(address)
            self._connected = True
            self._address = address

    async def disconnect(self) -> None:
        async with self._lock:
            await self._device.disconnect()
            self._connected = False
            self._address = None

    async def send_image(self, frame: PixelFrame) -> None:
        async with self._lock:
            if not self._connected:
                raise BleConnectionError("请先连接设备")
            await self._device.send_image(frame)

    async def send_gif(self, frames: list[PixelFrame], fps: int) -> None:
        async with self._lock:
            if not self._connected:
                raise BleConnectionError("请先连接设备")
            await self._device.send_gif(frames, fps)

    async def set_brightness(self, level: int) -> None:
        async with self._lock:
            if not self._connected:
                raise BleConnectionError("请先连接设备")
            await self._device.set_brightness(level)

    async def set_power(self, on: bool) -> None:
        async with self._lock:
            if not self._connected:
                raise BleConnectionError("请先连接设备")
            await self._device.set_power(on)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_session.py -v`
Expected: 11 PASS

- [ ] **Step 5: Run full suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 52 PASS

- [ ] **Step 6: Commit**

```bash
git add idotctl/webserver/session.py tests/test_session.py
git commit -m "feat: add DeviceSession with persistent BLE connection and asyncio serialization"
```

---

### Task 4: FastAPI app — scaffold + connection APIs

**Files:**
- Modify: `idotctl/webserver/app.py`
- Create: `tests/test_app.py`

**Context:** The app uses `Depends()` for `DeviceSession` and `ImageStaging` so tests can override them via `app.dependency_overrides`. All API tests use `TestClient` (synchronous wrapper around the async app — no `asyncio.run()` needed). The `_make_client()` helper creates fresh session/staging/fake per test to avoid state leakage.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app.py -v`
Expected: FAIL (app stub has no routes)

- [ ] **Step 3: Implement full app.py**

```python
"""FastAPI 应用:路由 + 依赖注入 + 静态文件 + main()。"""
from __future__ import annotations
import argparse
import socket
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from idotctl import config
from idotctl.core.device import SdkDevice
from idotctl.core.imaging import ImageOptions
from idotctl.errors import (
    BleConnectionError,
    DeviceNotFoundError,
    FirmwareUnsupportedError,
    IdotError,
    ImageError,
)
from idotctl.webserver.session import DeviceSession
from idotctl.webserver.staging import ImageStaging

_STATIC = Path(__file__).parent / "static"

app = FastAPI(title="iDotMatrix Web UI")
app.mount("/static", StaticFiles(directory=_STATIC), name="static")

_session: DeviceSession = DeviceSession(SdkDevice())
_staging: ImageStaging = ImageStaging()


def get_session() -> DeviceSession:
    return _session


def get_staging() -> ImageStaging:
    return _staging


@app.exception_handler(IdotError)
async def _idot_error_handler(request, exc: IdotError):
    if isinstance(exc, DeviceNotFoundError):
        status = 404
    elif isinstance(exc, (BleConnectionError, ImageError)):
        status = 400
    elif isinstance(exc, FirmwareUnsupportedError):
        status = 502
    else:
        status = 500
    return JSONResponse(status_code=status, content={"error": str(exc)})


class ConnectRequest(BaseModel):
    address: str


class ImageParams(BaseModel):
    fit: str = "crop"
    dither: bool = True
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0


class GifParams(BaseModel):
    fps: int = 10
    fit: str = "crop"
    dither: bool = True
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0


class BrightnessRequest(BaseModel):
    level: int


class PowerRequest(BaseModel):
    on: bool


@app.get("/", response_class=HTMLResponse)
async def index():
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
async def api_status(session: Annotated[DeviceSession, Depends(get_session)]):
    return {
        "connected": session.is_connected,
        "address": session.current_address,
        "last_device": config.get_last_device(),
    }


@app.post("/api/scan")
async def api_scan(session: Annotated[DeviceSession, Depends(get_session)]):
    devices = await session.scan(timeout=5.0)
    return [{"name": d.name, "address": d.address} for d in devices]


@app.post("/api/connect")
async def api_connect(
    req: ConnectRequest,
    session: Annotated[DeviceSession, Depends(get_session)],
):
    await session.connect(req.address)
    config.set_last_device(req.address)
    return {"ok": True}


@app.post("/api/disconnect")
async def api_disconnect(session: Annotated[DeviceSession, Depends(get_session)]):
    await session.disconnect()
    return {"ok": True}


@app.post("/api/upload")
async def api_upload(
    file: Annotated[UploadFile, File()],
    staging: Annotated[ImageStaging, Depends(get_staging)],
):
    data = await file.read()
    filename = file.filename or "upload"
    staging.stage(data, filename)
    return {"ok": True, "filename": filename, "is_gif": filename.lower().endswith(".gif")}


@app.post("/api/preview")
async def api_preview(
    req: ImageParams,
    staging: Annotated[ImageStaging, Depends(get_staging)],
):
    opts = ImageOptions(
        fit=req.fit, dither=req.dither, brightness=req.brightness,
        contrast=req.contrast, saturation=req.saturation,
    )
    return Response(content=staging.render_preview(opts), media_type="image/png")


@app.post("/api/send")
async def api_send(
    req: ImageParams,
    session: Annotated[DeviceSession, Depends(get_session)],
    staging: Annotated[ImageStaging, Depends(get_staging)],
):
    opts = ImageOptions(
        fit=req.fit, dither=req.dither, brightness=req.brightness,
        contrast=req.contrast, saturation=req.saturation,
    )
    await session.send_image(staging.get_frame(opts))
    return {"ok": True}


@app.post("/api/gif")
async def api_gif(
    req: GifParams,
    session: Annotated[DeviceSession, Depends(get_session)],
    staging: Annotated[ImageStaging, Depends(get_staging)],
):
    opts = ImageOptions(
        fit=req.fit, dither=req.dither, brightness=req.brightness,
        contrast=req.contrast, saturation=req.saturation,
    )
    await session.send_gif(staging.get_gif_frames(opts), fps=req.fps)
    return {"ok": True}


@app.post("/api/brightness")
async def api_brightness(
    req: BrightnessRequest,
    session: Annotated[DeviceSession, Depends(get_session)],
):
    await session.set_brightness(req.level)
    return {"ok": True}


@app.post("/api/power")
async def api_power(
    req: PowerRequest,
    session: Annotated[DeviceSession, Depends(get_session)],
):
    await session.set_power(req.on)
    return {"ok": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description="iDotMatrix Web UI")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "localhost"
    print(f"本机访问:   http://localhost:{args.port}")
    print(f"局域网访问: http://{local_ip}:{args.port}")
    uvicorn.run("idotctl.webserver.app:app", host=args.host, port=args.port)
```

- [ ] **Step 4: Run connection tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app.py -v`
Expected: 6 PASS

- [ ] **Step 5: Run full suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 58 PASS

- [ ] **Step 6: Commit**

```bash
git add idotctl/webserver/app.py tests/test_app.py
git commit -m "feat: add FastAPI app with all routes, dependency injection, and error handler"
```

---

### Task 5: Image API tests (upload / preview / send / gif)

**Files:**
- Modify: `tests/test_app.py` (add image endpoint tests)

**Context:** `_make_client()`, `_png()`, and `_gif()` are already defined in `test_app.py` from Task 4. Just append the new test functions below the existing ones.

- [ ] **Step 1: Add failing tests — append to tests/test_app.py**

```python
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
```

- [ ] **Step 2: Run tests — all should pass immediately**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app.py -v`
Expected: All 13 PASS — the image routes were already written in app.py during Task 4; these tests verify existing behavior.

- [ ] **Step 4: Run full suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 65 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_app.py
git commit -m "test: add image API endpoint tests (upload/preview/send/gif)"
```

---

### Task 6: Device control API tests (brightness / power)

**Files:**
- Modify: `tests/test_app.py` (add device control tests)

- [ ] **Step 1: Add failing tests — append to tests/test_app.py**

```python
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
```

- [ ] **Step 2: Run to verify they pass (routes already in app.py)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app.py -v`
Expected: All 18 PASS

- [ ] **Step 3: Run full suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 70 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "test: add device control API tests (brightness/power)"
```

---

### Task 7: Frontend — HTML + JS + CSS

**Files:**
- Modify: `idotctl/webserver/static/index.html`
- Modify: `idotctl/webserver/static/app.js`
- Modify: `idotctl/webserver/static/style.css`

**Context:** No build chain. Pure HTML/JS/CSS served by FastAPI's StaticFiles. No tests (manual smoke). All API calls use `fetch()`. Preview refresh is debounced 300 ms.

- [ ] **Step 1: Write index.html**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>iDotMatrix 控制器</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>

<header id="topbar">
  <div id="status-info">
    <span id="status-dot" class="dot dot-off"></span>
    <span id="status-text">未连接</span>
    <span id="status-addr"></span>
  </div>
  <div id="header-btns">
    <button id="btn-scan">扫描设备</button>
    <button id="btn-disconnect" disabled>断开</button>
  </div>
</header>

<div id="scan-modal" class="modal hidden">
  <div class="modal-box">
    <p class="modal-title">发现的设备</p>
    <ul id="device-list"></ul>
    <button id="btn-modal-close">关闭</button>
  </div>
</div>

<main>
  <section id="upload-card" class="card">
    <div id="drop-zone">
      <span id="drop-label">拖入图片 / GIF 或点击上传</span>
      <span id="drop-filename"></span>
      <input type="file" id="file-input" accept="image/*,.gif">
    </div>
    <div id="gif-fps" class="hidden">
      FPS <input type="number" id="fps" value="10" min="1" max="30">
    </div>
    <div id="send-btns">
      <button id="btn-send" disabled>发送到屏</button>
      <button id="btn-gif" disabled>发送 GIF</button>
    </div>
  </section>

  <section id="preview-card" class="card">
    <p class="card-label">32×32 实时预览（所见即所发）</p>
    <div id="preview-wrap">
      <span id="preview-placeholder">上传图片后显示预览</span>
      <img id="preview-img" alt="32x32 预览">
    </div>
    <p class="card-note">放大显示 · 实际 32×32 像素</p>
  </section>
</main>

<section id="options-card" class="card">
  <div class="opts-row">
    <span class="opts-label">缩放</span>
    <button class="fit-btn active" data-fit="crop">裁剪</button>
    <button class="fit-btn" data-fit="letterbox">留边</button>
    <button class="fit-btn" data-fit="stretch">拉伸</button>
    <label class="dither-lbl">
      <input type="checkbox" id="dither" checked> 抖动
    </label>
  </div>
  <div class="sliders-row">
    <div class="slider-item">
      <label>亮度 <span id="v-brightness">1.0</span></label>
      <input type="range" id="s-brightness" min="0" max="2" step="0.1" value="1">
    </div>
    <div class="slider-item">
      <label>对比度 <span id="v-contrast">1.0</span></label>
      <input type="range" id="s-contrast" min="0" max="2" step="0.1" value="1">
    </div>
    <div class="slider-item">
      <label>饱和度 <span id="v-saturation">1.0</span></label>
      <input type="range" id="s-saturation" min="0" max="2" step="0.1" value="1">
    </div>
  </div>
</section>

<section id="device-card" class="card">
  <span class="opts-label">屏幕亮度</span>
  <input type="range" id="s-dev-brightness" min="0" max="100" step="1" value="70">
  <span id="v-dev-brightness">70</span>
  <div id="power-btns">
    <button id="btn-on" disabled>开屏</button>
    <button id="btn-off" disabled>关屏</button>
  </div>
</section>

<div id="toast"></div>

<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write style.css**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  background: #f0f0f0;
  color: #1a1a1a;
  min-height: 100vh;
  font-size: 14px;
}

/* ── Top bar ── */
#topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  padding: 10px 20px;
  position: sticky;
  top: 0;
  z-index: 10;
}
#status-info { display: flex; align-items: center; gap: 8px; }
.dot {
  width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0;
}
.dot-on { background: #1D9E75; }
.dot-off { background: #bbb; }
#status-text { font-weight: 500; }
#status-addr { color: #666; font-family: monospace; font-size: 13px; }
#header-btns { display: flex; gap: 8px; }

/* ── Cards ── */
.card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 16px;
}

/* ── Main 2-col ── */
main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  padding: 14px 20px;
}
@media (max-width: 600px) { main { grid-template-columns: 1fr; } }

/* ── Upload / drop zone ── */
#drop-zone {
  border: 1.5px dashed #ccc;
  border-radius: 8px;
  padding: 28px 16px;
  text-align: center;
  cursor: pointer;
  color: #666;
  transition: border-color .15s, background .15s;
  position: relative;
}
#drop-zone.drag-over { border-color: #1D9E75; background: #f0faf6; }
#drop-zone input[type=file] {
  position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
}
#drop-label { display: block; font-size: 13px; }
#drop-filename { display: block; font-size: 12px; color: #1D9E75; margin-top: 6px; min-height: 16px; }
#gif-fps {
  display: flex; align-items: center; gap: 8px;
  margin: 10px 0 0; font-size: 13px; color: #555;
}
#gif-fps input { width: 58px; padding: 4px 6px; border: 1px solid #ccc; border-radius: 6px; }
#send-btns { display: flex; gap: 8px; margin-top: 12px; }
#send-btns button { flex: 1; }

/* ── Preview ── */
#preview-card { display: flex; flex-direction: column; align-items: center; }
.card-label { font-size: 12px; color: #666; margin-bottom: 10px; }
#preview-wrap {
  background: #111;
  border-radius: 6px;
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 188px;
  height: 188px;
}
#preview-img { width: 168px; height: 168px; image-rendering: pixelated; display: none; }
#preview-placeholder { color: #555; font-size: 12px; text-align: center; }
.card-note { font-size: 11px; color: #999; margin-top: 8px; }

/* ── Options ── */
#options-card { margin: 0 20px 14px; }
.opts-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.opts-label { font-size: 13px; color: #555; min-width: 36px; }
.fit-btn {
  padding: 5px 12px; border-radius: 6px; font-size: 13px;
  border: 1px solid #ddd; background: #f5f5f5; cursor: pointer; color: #333;
}
.fit-btn.active { background: #1D9E75; color: #fff; border-color: #1D9E75; }
.dither-lbl { margin-left: 12px; font-size: 13px; display: flex; align-items: center; gap: 5px; cursor: pointer; }
.sliders-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
@media (max-width: 500px) { .sliders-row { grid-template-columns: 1fr; } }
.slider-item label { font-size: 12px; color: #555; display: block; margin-bottom: 4px; }
.slider-item input[type=range] { width: 100%; }

/* ── Device control ── */
#device-card {
  margin: 0 20px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
#s-dev-brightness { flex: 1; min-width: 120px; }
#v-dev-brightness { font-size: 13px; font-weight: 500; min-width: 24px; }
#power-btns { display: flex; gap: 8px; }

/* ── Buttons ── */
button {
  padding: 7px 14px;
  border: 1px solid #d0d0d0;
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #333;
  transition: background .12s;
}
button:hover:not(:disabled) { background: #f0f0f0; }
button:active:not(:disabled) { transform: scale(0.97); }
button:disabled { opacity: 0.45; cursor: default; }

/* ── Modal ── */
.modal {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.modal.hidden { display: none; }
.modal-box {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  min-width: 280px;
  max-width: 360px;
  width: 90%;
}
.modal-title { font-weight: 500; margin-bottom: 12px; }
#device-list { list-style: none; }
#device-list li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 0; border-bottom: 1px solid #f0f0f0;
}
#device-list li:last-child { border-bottom: none; }
.device-info { font-size: 13px; }
.device-addr { font-size: 11px; color: #888; font-family: monospace; }
#btn-modal-close { margin-top: 14px; width: 100%; }

/* ── Toast ── */
#toast {
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: #222; color: #fff;
  padding: 10px 18px; border-radius: 8px;
  font-size: 13px; max-width: 320px; text-align: center;
  opacity: 0; transition: opacity .25s;
  pointer-events: none; z-index: 200;
}
#toast.show { opacity: 1; }
#toast.error { background: #c0392b; }
```

- [ ] **Step 3: Write app.js**

```javascript
/* iDotMatrix Web UI — app.js */

let _hasImage = false;
let _isGif = false;
let _debounceTimer = null;

/* ── Utilities ── */
function debounce(fn, ms) {
  return function (...args) {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(() => fn(...args), ms);
  };
}

let _toastTimer = null;
function toast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show' + (isError ? ' error' : '');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.className = ''; }, 2800);
}

async function api(method, path, body = null, isFile = false) {
  const opts = { method };
  if (body && !isFile) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  } else if (isFile) {
    opts.body = body;
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `错误 ${res.status}`;
    try { const j = await res.json(); msg = j.error || msg; } catch {}
    throw new Error(msg);
  }
  return res;
}

/* ── State collection ── */
function getParams() {
  const fit = document.querySelector('.fit-btn.active')?.dataset.fit || 'crop';
  return {
    fit,
    dither: document.getElementById('dither').checked,
    brightness: parseFloat(document.getElementById('s-brightness').value),
    contrast: parseFloat(document.getElementById('s-contrast').value),
    saturation: parseFloat(document.getElementById('s-saturation').value),
  };
}

/* ── Status polling ── */
async function fetchStatus() {
  try {
    const res = await api('GET', '/api/status');
    const data = await res.json();
    updateStatusUI(data);
  } catch {}
}

function updateStatusUI(data) {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  const addr = document.getElementById('status-addr');
  const btnDisc = document.getElementById('btn-disconnect');
  const btnOn = document.getElementById('btn-on');
  const btnOff = document.getElementById('btn-off');
  if (data.connected) {
    dot.className = 'dot dot-on';
    text.textContent = '已连接';
    addr.textContent = data.address || '';
    btnDisc.disabled = false;
    btnOn.disabled = false;
    btnOff.disabled = false;
  } else {
    dot.className = 'dot dot-off';
    text.textContent = '未连接';
    addr.textContent = data.last_device ? `上次: ${data.last_device}` : '';
    btnDisc.disabled = true;
    btnOn.disabled = true;
    btnOff.disabled = true;
  }
  updateSendButtons();
}

function updateSendButtons() {
  const connected = document.getElementById('status-dot').classList.contains('dot-on');
  document.getElementById('btn-send').disabled = !(_hasImage && !_isGif && connected);
  document.getElementById('btn-gif').disabled = !(_hasImage && _isGif && connected);
}

/* ── Scan + connect ── */
document.getElementById('btn-scan').addEventListener('click', async () => {
  toast('扫描中(约5秒)...');
  try {
    const res = await api('POST', '/api/scan');
    const devices = await res.json();
    const list = document.getElementById('device-list');
    list.innerHTML = '';
    if (!devices.length) { list.innerHTML = '<li>未发现设备</li>'; }
    devices.forEach(d => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="device-info">${d.name}<br><span class="device-addr">${d.address}</span></span>`;
      const btn = document.createElement('button');
      btn.textContent = '连接';
      btn.onclick = () => connectDevice(d.address);
      li.appendChild(btn);
      list.appendChild(li);
    });
    document.getElementById('scan-modal').classList.remove('hidden');
  } catch (e) { toast(e.message, true); }
});

document.getElementById('btn-modal-close').addEventListener('click', () => {
  document.getElementById('scan-modal').classList.add('hidden');
});

async function connectDevice(address) {
  document.getElementById('scan-modal').classList.add('hidden');
  try {
    await api('POST', '/api/connect', { address });
    toast(`已连接 ${address}`);
    fetchStatus();
  } catch (e) { toast(e.message, true); }
}

document.getElementById('btn-disconnect').addEventListener('click', async () => {
  try {
    await api('POST', '/api/disconnect');
    toast('已断开连接');
    fetchStatus();
  } catch (e) { toast(e.message, true); }
});

/* ── Upload ── */
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', e => { if (e.target.files[0]) handleFile(e.target.files[0]); });

async function handleFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await api('POST', '/api/upload', fd, true);
    const data = await res.json();
    _hasImage = true;
    _isGif = data.is_gif;
    document.getElementById('drop-filename').textContent = file.name;
    document.getElementById('gif-fps').classList.toggle('hidden', !_isGif);
    updateSendButtons();
    refreshPreview();
  } catch (e) { toast(e.message, true); }
}

/* ── Preview (debounced) ── */
const refreshPreview = debounce(async function () {
  if (!_hasImage) return;
  try {
    const res = await api('POST', '/api/preview', getParams());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const img = document.getElementById('preview-img');
    img.src = url;
    img.style.display = 'block';
    document.getElementById('preview-placeholder').style.display = 'none';
  } catch (e) { toast(e.message, true); }
}, 300);

/* ── Image options → trigger preview ── */
document.querySelectorAll('.fit-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.fit-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    refreshPreview();
  });
});
document.getElementById('dither').addEventListener('change', refreshPreview);

function bindSlider(sliderId, valId) {
  const s = document.getElementById(sliderId);
  const v = document.getElementById(valId);
  s.addEventListener('input', () => { v.textContent = parseFloat(s.value).toFixed(1); refreshPreview(); });
}
bindSlider('s-brightness', 'v-brightness');
bindSlider('s-contrast', 'v-contrast');
bindSlider('s-saturation', 'v-saturation');

/* ── Send ── */
document.getElementById('btn-send').addEventListener('click', async () => {
  try {
    await api('POST', '/api/send', getParams());
    toast('已发送到屏');
  } catch (e) { toast(e.message, true); }
});

document.getElementById('btn-gif').addEventListener('click', async () => {
  const fps = parseInt(document.getElementById('fps').value) || 10;
  try {
    await api('POST', '/api/gif', { fps, ...getParams() });
    toast('GIF 已发送到屏');
  } catch (e) { toast(e.message, true); }
});

/* ── Device brightness ── */
const devBrightness = document.getElementById('s-dev-brightness');
const devBrightnessVal = document.getElementById('v-dev-brightness');
devBrightness.addEventListener('input', () => {
  devBrightnessVal.textContent = devBrightness.value;
});
devBrightness.addEventListener('change', async () => {
  try {
    await api('POST', '/api/brightness', { level: parseInt(devBrightness.value) });
  } catch (e) { toast(e.message, true); }
});

/* ── Power ── */
document.getElementById('btn-on').addEventListener('click', async () => {
  try { await api('POST', '/api/power', { on: true }); toast('开屏'); } catch (e) { toast(e.message, true); }
});
document.getElementById('btn-off').addEventListener('click', async () => {
  try { await api('POST', '/api/power', { on: false }); toast('关屏'); } catch (e) { toast(e.message, true); }
});

/* ── Init ── */
fetchStatus();
setInterval(fetchStatus, 3000);
```

- [ ] **Step 4: Manually smoke test the UI**

Start the server:
```bash
.venv/Scripts/python.exe -m idotctl.webserver.app
```
Expected output:
```
本机访问:   http://localhost:8000
局域网访问: http://<本机IP>:8000
```

Open `http://localhost:8000` in a browser. Verify:
- Top bar shows "未连接"
- Click "扫描设备" — should show loading toast then modal
- Upload a PNG by drag-and-drop — preview should appear
- Adjust brightness slider — preview should refresh after 300 ms

- [ ] **Step 5: Run full automated test suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 70 PASS (no change — frontend has no automated tests)

- [ ] **Step 6: Commit**

```bash
git add idotctl/webserver/static/
git commit -m "feat: add web UI frontend (HTML/JS/CSS) with real-time 32x32 preview"
```

---

### Task 8: Entry point verification + README update

**Files:**
- Verify: `pyproject.toml` (entry point already added in Task 1)
- Modify: `README.md`

- [ ] **Step 1: Verify entry point works**

Run: `.venv/Scripts/pip install -e .`
Run: `.venv/Scripts/idotctl-web.exe --help`
Expected output:
```
usage: idotctl-web [-h] [--host HOST] [--port PORT]
```

- [ ] **Step 2: Update README.md**

Replace the existing `README.md` content with:

```markdown
# idotmatrix-controller

自己的 iDotMatrix 32×32 LED 控制工具。任意图片 → 压缩到 32×32 → BLE 上屏。

## 安装

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
```

## Web UI(推荐)

```bash
idotctl-web                # 默认 0.0.0.0:8000
idotctl-web --port 9000    # 自定义端口
```

启动后浏览器打开 `http://localhost:8000`。同 WiFi 下的手机平板也可访问(终端会打印局域网 IP)。

> **安全提示**:Web UI 无鉴权,仅限可信局域网使用。

### 功能
- 拖拽上传图片或 GIF
- 实时 32×32 预览(所见即所发)
- 调节缩放模式、抖动、亮度、对比度、饱和度
- 一键发送到屏、控制亮度与开关

## CLI

```bash
idotctl scan                       # 扫描设备
idotctl connect AA:BB:CC:DD:EE:FF  # 连接并记住
idotctl send cat.jpg               # 发送图片(默认裁剪+抖动)
idotctl send cat.jpg --fit letterbox --no-dither --brightness 1.2
idotctl gif anim.gif --fps 12      # 发送 GIF
idotctl brightness 70              # 亮度 0-100
idotctl on / idotctl off           # 开/关屏
idotctl preview cat.jpg -o out.png # 预览 32×32 效果(无需硬件)
```

## 架构

```
idotctl/
├── core/imaging.py    纯图像流水线(可单测)
├── core/device.py     设备适配层(SdkDevice / FakeDevice)
├── config.py          状态记忆
├── cli.py             CLI 命令编排
└── webserver/         Web UI 层
    ├── app.py         FastAPI 路由 + main()
    ├── session.py     DeviceSession(常驻 BLE 连接)
    ├── staging.py     ImageStaging(上传图片暂存)
    └── static/        index.html + app.js + style.css
```

## 测试

```bash
.venv/Scripts/python.exe -m pytest -v
```

## 硬件 smoke(需真实设备)

```bash
idotctl scan && idotctl send sample.png
```
```

- [ ] **Step 3: Run full test suite one final time**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 70 PASS

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README with Web UI usage and architecture"
```
