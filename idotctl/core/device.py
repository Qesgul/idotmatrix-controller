"""设备适配层：DeviceAdapter 协议隔离真实 BLE。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from idotctl.core.imaging import PixelFrame


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
