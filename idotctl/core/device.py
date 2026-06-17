"""设备适配层：DeviceAdapter 协议隔离真实 BLE。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from idotctl.core.imaging import PixelFrame
from idotctl.errors import (
    DeviceNotFoundError,
    ConnectionError as IdotConnectionError,
    FirmwareUnsupportedError,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    address: str


@runtime_checkable
class DeviceAdapter(Protocol):
    async def scan(self, timeout: float) -> list[DeviceInfo]: ...
    async def connect(self, address: str) -> None: ...
    async def disconnect(self) -> None: ...
    async def send_image(self, frame: PixelFrame) -> None: ...
    async def send_gif(self, frames: list[PixelFrame], fps: int) -> None: ...
    async def set_brightness(self, level: int) -> None: ...
    async def set_power(self, on: bool) -> None: ...


class FakeDevice:
    """测试替身：记录调用,不碰硬件。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.connected_address: str | None = None

    async def scan(self, timeout: float) -> list[DeviceInfo]:
        self.calls.append(("scan", timeout))
        return [DeviceInfo(name="FakeMatrix", address="AA:BB:CC:DD:EE:FF")]

    async def connect(self, address: str) -> None:
        self.calls.append(("connect", address))
        self.connected_address = address

    async def disconnect(self) -> None:
        self.calls.append(("disconnect",))
        self.connected_address = None

    async def send_image(self, frame: PixelFrame) -> None:
        self.calls.append(("send_image", frame))

    async def send_gif(self, frames: list[PixelFrame], fps: int) -> None:
        self.calls.append(("send_gif", len(frames), fps))

    async def set_brightness(self, level: int) -> None:
        self.calls.append(("set_brightness", level))

    async def set_power(self, on: bool) -> None:
        self.calls.append(("set_power", on))


# ---------------------------------------------------------------------------
# iDotMatrix BLE pixel-upload helpers
# ---------------------------------------------------------------------------

# On-wire format for a 32×32 image upload (derived from open iDotMatrix BLE
# protocol; packet structure used by all known idotmatrix community clients).
#
# Packet layout for a raw-pixel upload:
#   Byte 0:   total length of this BLE write (including itself), low byte
#   Byte 1:   total length of this BLE write, high byte
#   Byte 2:   command family  (0x00 = display/image)
#   Byte 3:   sub-command     (0x0A = upload image data)
#   Byte 4:   frame-number low byte
#   Byte 5:   frame-number high byte
#   Bytes 6+: pixel data as RGBA (4 bytes per pixel, A always 0xFF)
#
# Before streaming pixels, send a "begin upload" command:
#   [0x09, 0x00, 0x00, 0x0B, num_frames_low, num_frames_high,
#    size, size, speed_low, speed_high]
# where size = frame.size (e.g. 32), speed = round(1000/fps) in ms.

_BLE_CHUNK = 20  # conservative MTU; BlueZ default is 20 usable bytes


def _image_begin_packet(num_frames: int, size: int, speed_ms: int) -> bytearray:
    """Header that tells the device how many frames/size/speed are coming."""
    data = bytearray(
        [
            0x09,
            0x00,
            0x00,
            0x0B,
            num_frames & 0xFF,
            (num_frames >> 8) & 0xFF,
            size & 0xFF,
            size & 0xFF,
            speed_ms & 0xFF,
            (speed_ms >> 8) & 0xFF,
        ]
    )
    return data


def _frame_packets(frame_idx: int, frame: PixelFrame) -> list[bytearray]:
    """Convert one PixelFrame into a sequence of BLE write payloads."""
    # Build full RGBA buffer for this frame
    raw = frame.pixels  # RGB bytes, len = size*size*3
    rgba = bytearray(len(raw) // 3 * 4)
    for i in range(len(raw) // 3):
        rgba[i * 4 + 0] = raw[i * 3 + 0]  # R
        rgba[i * 4 + 1] = raw[i * 3 + 1]  # G
        rgba[i * 4 + 2] = raw[i * 3 + 2]  # B
        rgba[i * 4 + 3] = 0xFF              # A

    packets: list[bytearray] = []
    # Split RGBA data into BLE-sized chunks; each chunk gets a 6-byte header
    # so usable payload per packet = _BLE_CHUNK - 6
    payload_size = _BLE_CHUNK - 6
    offset = 0
    while offset < len(rgba):
        chunk = rgba[offset : offset + payload_size]
        pkt_len = 6 + len(chunk)
        pkt = bytearray(
            [
                pkt_len & 0xFF,
                (pkt_len >> 8) & 0xFF,
                0x00,
                0x0A,
                frame_idx & 0xFF,
                (frame_idx >> 8) & 0xFF,
            ]
        )
        pkt.extend(chunk)
        packets.append(pkt)
        offset += payload_size
    return packets


# ---------------------------------------------------------------------------
# SdkDevice — real BLE adapter wrapping idotmatrix-sdk
# ---------------------------------------------------------------------------


class SdkDevice:
    """Real BLE adapter backed by ``idotmatrix-sdk`` (``IDotMatrix`` class).

    All SDK calls are natively async (bleak-based), so no
    ``asyncio.to_thread`` wrapping is needed.
    """

    def __init__(self) -> None:
        self._device: "IDotMatrix | None" = None  # noqa: F821  (imported lazily)

    # ------------------------------------------------------------------
    # scan
    # ------------------------------------------------------------------

    async def scan(self, timeout: float) -> list[DeviceInfo]:
        """Discover iDotMatrix devices via BLE.

        The SDK's ``BleakScanner.discover()`` does not accept a timeout
        kwarg directly — it uses the default (5 s).  We honour *timeout*
        by running with ``asyncio.wait_for``.
        """
        try:
            from idotmatrix_sdk import IDotMatrix  # lazy import — SDK optional at test time

            raw = await asyncio.wait_for(IDotMatrix.search_devices(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise DeviceNotFoundError("BLE scan timed out") from exc
        except Exception as exc:
            raise DeviceNotFoundError(f"BLE scan failed: {exc}") from exc

        if not raw:
            raise DeviceNotFoundError("No iDotMatrix devices found nearby")

        return [DeviceInfo(name=d.name, address=d.address) for d in raw]

    # ------------------------------------------------------------------
    # connect / disconnect
    # ------------------------------------------------------------------

    async def connect(self, address: str) -> None:
        """Connect to device at *address* with up to 3 retries (exponential back-off)."""
        from idotmatrix_sdk import IDotMatrix  # lazy import

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                dev = IDotMatrix(address)
                await dev.connect()
                self._device = dev
                return
            except Exception as exc:
                last_exc = exc
                log.warning("Connect attempt %d failed: %s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # 0 s, 1 s, 2 s

        raise IdotConnectionError(
            f"Could not connect to {address} after 3 attempts: {last_exc}"
        ) from last_exc

    async def disconnect(self) -> None:
        """Disconnect from the current device (no-op if not connected)."""
        if self._device is not None:
            try:
                await self._device.disconnect()
            finally:
                self._device = None

    # ------------------------------------------------------------------
    # send_image / send_gif
    # ------------------------------------------------------------------

    async def send_image(self, frame: PixelFrame) -> None:
        """Upload a single static image to the device."""
        await self.send_gif([frame], fps=1)

    async def send_gif(self, frames: list[PixelFrame], fps: int) -> None:
        """Upload an animated GIF (one or more frames) to the device."""
        dev = self._device
        if dev is None:
            raise IdotConnectionError("Not connected")

        try:
            speed_ms = max(1, round(1000 / max(1, fps)))
            size = frames[0].size if frames else 32

            # Tell the device how many frames are coming
            begin = _image_begin_packet(len(frames), size, speed_ms)
            await dev.write(begin, response=True)

            # Stream each frame
            for idx, frame in enumerate(frames):
                for pkt in _frame_packets(idx, frame):
                    await dev.write(pkt)
        except IdotConnectionError:
            raise
        except Exception as exc:
            raise FirmwareUnsupportedError(
                f"Image upload failed — firmware may be unsupported: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # set_brightness / set_power
    # ------------------------------------------------------------------

    async def set_brightness(self, level: int) -> None:
        """Set screen brightness (0–100).

        The SDK clamps to [5, 100]; values below 5 are promoted to 5.
        """
        dev = self._device
        if dev is None:
            raise IdotConnectionError("Not connected")

        clamped = max(5, min(100, level))
        try:
            await dev.set_brightness(clamped)
        except Exception as exc:
            raise FirmwareUnsupportedError(
                f"set_brightness failed: {exc}"
            ) from exc

    async def set_power(self, on: bool) -> None:
        """Turn the screen on or off."""
        dev = self._device
        if dev is None:
            raise IdotConnectionError("Not connected")

        try:
            if on:
                await dev.turn_on()
            else:
                await dev.turn_off()
        except Exception as exc:
            raise FirmwareUnsupportedError(
                f"set_power failed: {exc}"
            ) from exc
