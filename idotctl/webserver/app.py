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
