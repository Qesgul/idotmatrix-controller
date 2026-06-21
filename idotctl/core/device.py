"""设备适配层：DeviceAdapter 协议隔离真实 BLE。"""
from __future__ import annotations

import asyncio
import logging
import struct
import zlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from idotctl.errors import (
    DeviceNotFoundError,
    BleConnectionError,
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
    async def send_image(self, png_bytes: bytes) -> None: ...
    async def send_gif(self, gif_bytes: bytes) -> None: ...
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

    async def send_image(self, png_bytes: bytes) -> None:
        self.calls.append(("send_image", len(png_bytes)))

    async def send_gif(self, gif_bytes: bytes) -> None:
        self.calls.append(("send_gif", len(gif_bytes)))

    async def set_brightness(self, level: int) -> None:
        self.calls.append(("set_brightness", level))

    async def set_power(self, on: bool) -> None:
        self.calls.append(("set_power", on))


# ---------------------------------------------------------------------------
# iDotMatrix BLE file-upload helpers
# ---------------------------------------------------------------------------
# The device expects *file data* (PNG or GIF), not raw pixel bytes.
# The on-wire format is derived from the open-source idotmatrix community
# client (https://github.com/8none1/iDotMatrix).
#
# PNG upload: each BLE write contains a 9-byte header + file chunk.
#   Header: [total_len(2,LE)] [0x00, 0x00, flag(1)] [png_len(4,LE)]
#   flag = 0 for first chunk, 2 for subsequent chunks.
#
# GIF upload: each BLE write contains a 16-byte header + file chunk.
#   Header: [chunk_len(2,LE)] [0xFF, 0xFF] [flag(1)]
#           [gif_len(4,LE)] [crc32(4,LE)] [0xFF, 0x05, 0x00, 0x0D]
#   flag = 0 for first chunk, 2 for subsequent chunks.
#
# Before uploading an image, the device must be switched to DIY image
# mode via the command [5, 0, 4, 1, 1].

_PNG_CHUNK_SIZE = 4096
_GIF_CHUNK_SIZE = 4096


def _png_packets(png_data: bytes) -> list[bytearray]:
    """Encode PNG file data into one or more BLE write payloads.

    Protocol (from community client):
      For each 4096-byte chunk of PNG data:
        idk = len(png_data) + num_chunks   (16-bit signed, LE)
        header = idk(2) + [0x00, 0x00, flag(1)] + png_len(4, LE)
        payload = header + chunk
    """
    chunks = [bytearray(png_data[i:i + _PNG_CHUNK_SIZE])
              for i in range(0, len(png_data), _PNG_CHUNK_SIZE)]
    idk = len(png_data) + len(chunks)
    idk_bytes = struct.pack("<h", idk)
    png_len_bytes = struct.pack("<i", len(png_data))

    packets: list[bytearray] = []
    for i, chunk in enumerate(chunks):
        flag = 2 if i > 0 else 0
        header = idk_bytes + bytearray([0, 0, flag]) + png_len_bytes
        packets.append(header + chunk)
    return packets


def _gif_packets(gif_data: bytes) -> list[bytearray]:
    """Encode GIF file data into one or more BLE write payloads.

    Protocol (from community client):
      For each 4096-byte chunk of GIF data:
        header (16 bytes) = chunk_len(2,LE) + [0xFF,0xFF] + flag(1)
                            + gif_len(4,LE) + crc32(4,LE) + [0xFF,0x05,0x00,0x0D]
        payload = header + chunk
    """
    header_template = bytearray([
        0xFF, 0xFF,       # magic bytes
        0,                 # flag: 0=first chunk, 2=subsequent
        0xFF, 0xFF, 0xFF, 0xFF,  # gif_len (filled below)
        0xFF, 0xFF, 0xFF, 0xFF,  # crc32  (filled below)
        0xFF, 0x05, 0x00, 0x0D,
    ])

    gif_len = len(gif_data)
    crc = zlib.crc32(gif_data) & 0xFFFFFFFF
    header_template[3:7] = struct.pack("<I", gif_len)
    header_template[7:11] = struct.pack("<I", crc)

    chunks = [bytearray(gif_data[i:i + _GIF_CHUNK_SIZE])
              for i in range(0, len(gif_data), _GIF_CHUNK_SIZE)]

    packets: list[bytearray] = []
    for i, chunk in enumerate(chunks):
        header = bytearray(header_template)  # copy
        header[2] = 2 if i > 0 else 0
        chunk_len = len(header) + len(chunk)
        full = struct.pack("<H", chunk_len) + header + chunk
        packets.append(full)
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
        """Discover iDotMatrix devices via BLE."""
        try:
            from bleak import BleakScanner
            from bleak.backends.scanner import AdvertisementData

            response = await BleakScanner.discover(
                return_adv=True, timeout=timeout,
            )
            raw: list[DeviceInfo] = []
            for _, (device, advertisement) in response.items():
                if (
                    isinstance(advertisement, AdvertisementData)
                    and advertisement.local_name
                    and advertisement.local_name.startswith("IDM-")
                ):
                    raw.append(DeviceInfo(name=advertisement.local_name, address=device.address))
        except Exception as exc:
            raise DeviceNotFoundError(f"BLE scan failed: {exc}") from exc

        if not raw:
            raise DeviceNotFoundError("No iDotMatrix devices found nearby")

        return raw

    # ------------------------------------------------------------------
    # connect / disconnect
    # ------------------------------------------------------------------

    async def connect(self, address: str) -> None:
        """Connect to device at *address* with up to 3 retries (exponential back-off)."""
        from idotmatrix_sdk import IDotMatrix

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
                    await asyncio.sleep(2 ** attempt)

        raise BleConnectionError(
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

    async def _enter_image_mode(self) -> None:
        """Switch the device to DIY image mode (required before upload)."""
        dev = self._device
        if dev is None:
            raise BleConnectionError("Not connected")
        # Command: enter DIY draw mode = [5, 0, 4, 1, 1]
        await dev.write(bytearray([5, 0, 4, 1, 1]))

    async def send_image(self, png_bytes: bytes) -> None:
        """Upload a single static image (PNG file bytes) to the device."""
        dev = self._device
        if dev is None:
            raise BleConnectionError("Not connected")

        try:
            await self._enter_image_mode()
            for pkt in _png_packets(png_bytes):
                await dev.write(pkt, response=True)
        except BleConnectionError:
            raise
        except Exception as exc:
            raise FirmwareUnsupportedError(
                f"Image upload failed — firmware may be unsupported: {exc}"
            ) from exc

    async def send_gif(self, gif_bytes: bytes) -> None:
        """Upload an animated GIF (file bytes) to the device."""
        dev = self._device
        if dev is None:
            raise BleConnectionError("Not connected")

        try:
            await self._enter_image_mode()
            for pkt in _gif_packets(gif_bytes):
                await dev.write(pkt, response=True)
        except BleConnectionError:
            raise
        except Exception as exc:
            raise FirmwareUnsupportedError(
                f"GIF upload failed — firmware may be unsupported: {exc}"
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
            raise BleConnectionError("Not connected")

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
            raise BleConnectionError("Not connected")

        try:
            if on:
                await dev.turn_on()
            else:
                await dev.turn_off()
        except Exception as exc:
            raise FirmwareUnsupportedError(
                f"set_power failed: {exc}"
            ) from exc
