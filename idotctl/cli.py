"""CLI 入口：解析参数 + 编排 core，不含业务细节。"""
from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path

from idotctl import config
from idotctl.core.device import DeviceAdapter, SdkDevice
from idotctl.core.imaging import ImageOptions, process_image, process_gif
from idotctl.errors import IdotError, DeviceNotFoundError


def _opts_from_args(args) -> ImageOptions:
    return ImageOptions(
        fit=args.fit,
        dither=not args.no_dither,
        brightness=args.brightness,
        contrast=args.contrast,
        saturation=args.saturation,
    )


def _resolve_address(args, config_path: Path) -> str:
    address = getattr(args, "device", None) or config.get_last_device(path=config_path)
    if not address:
        raise DeviceNotFoundError("未指定设备且无历史设备，请先 `idotctl connect <MAC>`")
    return address


async def cmd_scan(args, device: DeviceAdapter) -> int:
    found = await device.scan(args.timeout)
    if not found:
        print("未发现 iDotMatrix 设备")
        return 0
    for d in found:
        print(f"{d.name}\t{d.address}")
    return 0


async def cmd_connect(args, device: DeviceAdapter, config_path: Path = config.CONFIG_PATH) -> int:
    await device.connect(args.address)
    config.set_last_device(args.address, path=config_path)
    await device.disconnect()
    print(f"已连接并记住设备: {args.address}")
    return 0


async def cmd_send(args, device: DeviceAdapter, config_path: Path = config.CONFIG_PATH) -> int:
    frame = process_image(args.image, _opts_from_args(args))
    address = _resolve_address(args, config_path)
    await device.connect(address)
    try:
        await device.send_image(frame)
    finally:
        await device.disconnect()
    print(f"已发送图片到 {address}")
    return 0


async def cmd_gif(args, device: DeviceAdapter, config_path: Path = config.CONFIG_PATH) -> int:
    frames = process_gif(args.gif, _opts_from_args(args))
    address = _resolve_address(args, config_path)
    await device.connect(address)
    try:
        await device.send_gif(frames, args.fps)
    finally:
        await device.disconnect()
    print(f"已发送 GIF({len(frames)} 帧) 到 {address}")
    return 0


async def cmd_brightness(args, device: DeviceAdapter, config_path: Path = config.CONFIG_PATH) -> int:
    address = _resolve_address(args, config_path)
    await device.connect(address)
    try:
        await device.set_brightness(args.level)
    finally:
        await device.disconnect()
    print(f"亮度已设为 {args.level}")
    return 0


async def cmd_power(args, device: DeviceAdapter, config_path: Path = config.CONFIG_PATH) -> int:
    address = _resolve_address(args, config_path)
    await device.connect(address)
    try:
        await device.set_power(args.power)
    finally:
        await device.disconnect()
    print("已开屏" if args.power else "已关屏")
    return 0


def cmd_preview(args) -> int:
    frame = process_image(args.image, _opts_from_args(args))
    from PIL import Image
    img = Image.frombytes("RGB", (frame.size, frame.size), frame.pixels)
    img.save(args.output)
    print(f"预览已保存: {args.output}")
    return 0


def _add_image_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--fit", choices=["crop", "letterbox", "stretch"], default="crop")
    p.add_argument("--no-dither", action="store_true")
    p.add_argument("--brightness", type=float, default=1.0)
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--saturation", type=float, default=1.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idotctl", description="iDotMatrix 32x32 控制 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="扫描附近设备")
    p_scan.add_argument("--timeout", type=float, default=5.0)
    p_scan.set_defaults(func=cmd_scan)

    p_conn = sub.add_parser("connect", help="连接并记住设备")
    p_conn.add_argument("address")
    p_conn.set_defaults(func=cmd_connect)

    p_send = sub.add_parser("send", help="发送静态图片")
    p_send.add_argument("image")
    p_send.add_argument("--device", default=None)
    _add_image_opts(p_send)
    p_send.set_defaults(func=cmd_send)

    p_gif = sub.add_parser("gif", help="发送 GIF 动画")
    p_gif.add_argument("gif")
    p_gif.add_argument("--device", default=None)
    p_gif.add_argument("--fps", type=int, default=10)
    _add_image_opts(p_gif)
    p_gif.set_defaults(func=cmd_gif)

    p_br = sub.add_parser("brightness", help="设置亮度 0-100")
    p_br.add_argument("level", type=int)
    p_br.add_argument("--device", default=None)
    p_br.set_defaults(func=cmd_brightness)

    p_on = sub.add_parser("on", help="开屏")
    p_on.add_argument("--device", default=None)
    p_on.set_defaults(func=cmd_power, power=True)

    p_off = sub.add_parser("off", help="关屏")
    p_off.add_argument("--device", default=None)
    p_off.set_defaults(func=cmd_power, power=False)

    p_prev = sub.add_parser("preview", help="处理后存盘,不发送")
    p_prev.add_argument("image")
    p_prev.add_argument("-o", "--output", default="out.png")
    _add_image_opts(p_prev)
    p_prev.set_defaults(func=cmd_preview)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.func is cmd_preview:
            return cmd_preview(args)
        device = SdkDevice()
        return asyncio.run(args.func(args, device))
    except IdotError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
