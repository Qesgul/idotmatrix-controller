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
