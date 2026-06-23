"""纯图像流水线：任意图片 → size×size RGB 帧。零硬件依赖。"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

from idotctl.errors import ImageError

# unsharp 基准:sharpen=1.0 → 此 percent + 半径。
# 实测:32×32 上 radius>=1、percent>=120 会沿每条边炸出青白光晕,反而毁图;
# 改为小半径低强度,默认 1.0 档对应"清晰而不振铃"。
_SHARPEN_BASE_PERCENT = 60
_SHARPEN_RADIUS = 0.6
_SHARPEN_THRESHOLD = 2

# sRGB ↔ 线性光 8-bit LUT。缩小=对邻域像素求平均,必须在线性光空间做才物理正确;
# 直接平均 sRGB 编码值会让缩小后的图发暗发灰、暗部细节糊成一团(肉眼实测明显)。
_GAMMA = 2.2
_SRGB_TO_LINEAR = [round((i / 255) ** _GAMMA * 255) for i in range(256)]
_LINEAR_TO_SRGB = [round((i / 255) ** (1 / _GAMMA) * 255) for i in range(256)]


def _to_linear(img: Image.Image) -> Image.Image:
    """sRGB → 线性光(RGB 三通道共用同一 LUT)。"""
    return img.point(_SRGB_TO_LINEAR * 3)


def _to_srgb(img: Image.Image) -> Image.Image:
    """线性光 → sRGB。"""
    return img.point(_LINEAR_TO_SRGB * 3)


@dataclass(frozen=True)
class ImageOptions:
    fit: Literal["crop", "letterbox", "stretch"] = "crop"
    autocontrast: bool = True   # 缩小后自动拉满动态范围,改善偏灰原图主体清晰度
    dither: bool = False        # Floyd–Steinberg;32×32 上会制造噪点,默认关
    sharpen: float = 1.0        # 缩小后 unsharp 强度倍率,0=关,1.0=标准
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.1     # 轻微增艳,LED 点阵远看更醒目
    size: int = 32

    def __post_init__(self) -> None:
        _VALID_FIT = {"crop", "letterbox", "stretch"}
        if self.fit not in _VALID_FIT:
            raise ValueError(f"fit must be one of {_VALID_FIT}, got {self.fit!r}")
        if self.size < 1:
            raise ValueError(f"size must be >= 1, got {self.size!r}")
        if self.sharpen < 0:
            raise ValueError(f"sharpen must be >= 0, got {self.sharpen!r}")


@dataclass(frozen=True)
class PixelFrame:
    """设备无关的中间表示：size×size、RGB row-major bytes。"""
    size: int
    pixels: bytes


def _open_rgb(path: str) -> Image.Image:
    try:
        img = Image.open(path)
        img.load()
    except FileNotFoundError as e:
        raise ImageError(f"图片不存在: {path}") from e
    except (UnidentifiedImageError, OSError) as e:
        raise ImageError(f"无法识别的图片格式: {path}") from e
    return img.convert("RGB")


def _fit(img: Image.Image, opts: ImageOptions) -> Image.Image:
    # 在线性光空间完成缩放(裁剪/留边的几何操作不受色彩空间影响),最后转回 sRGB。
    n = opts.size
    lin = _to_linear(img)
    if opts.fit == "stretch":
        out = lin.resize((n, n), Image.LANCZOS)
    elif opts.fit == "letterbox":
        fitted = ImageOps.contain(lin, (n, n), Image.LANCZOS)
        out = Image.new("RGB", (n, n), (0, 0, 0))
        off = ((n - fitted.width) // 2, (n - fitted.height) // 2)
        out.paste(fitted, off)
    else:  # 默认 crop：覆盖式缩放 + 居中裁剪
        out = ImageOps.fit(lin, (n, n), Image.LANCZOS)
    return _to_srgb(out)


def _adjust(img: Image.Image, opts: ImageOptions) -> Image.Image:
    # 先把动态范围拉满,再让用户的亮度/对比/饱和在此基础上微调。
    if opts.autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    if opts.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(opts.brightness)
    if opts.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(opts.contrast)
    if opts.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(opts.saturation)
    return img


def _sharpen(img: Image.Image, amount: float) -> Image.Image:
    """缩小后用 unsharp mask 把被低通糊掉的边缘轻微提回来(小半径,避免光晕)。"""
    if amount <= 0:
        return img
    percent = round(amount * _SHARPEN_BASE_PERCENT)
    return img.filter(ImageFilter.UnsharpMask(
        radius=_SHARPEN_RADIUS, percent=percent, threshold=_SHARPEN_THRESHOLD))


def _dither(img: Image.Image) -> Image.Image:
    """自适应调色板 + Floyd–Steinberg 误差扩散,缓解低分屏色带。"""
    return img.convert(
        "P", palette=Image.ADAPTIVE, colors=64, dither=Image.FLOYDSTEINBERG
    ).convert("RGB")


def _process_pil(img: Image.Image, opts: ImageOptions) -> PixelFrame:
    img = _fit(img, opts)
    img = _adjust(img, opts)
    img = _sharpen(img, opts.sharpen)
    if opts.dither:
        img = _dither(img)
    img = img.convert("RGB")
    return PixelFrame(size=opts.size, pixels=img.tobytes())


def process_image(path: str, opts: ImageOptions) -> PixelFrame:
    """任意图片 → size×size RGB 帧。纯函数,无硬件。"""
    img = _open_rgb(path)
    return _process_pil(img, opts)


def process_gif(path: str, opts: ImageOptions) -> list[PixelFrame]:
    """GIF → 多帧 PixelFrame，逐帧走同一条流水线。"""
    try:
        img = Image.open(path)
        img.load()
    except FileNotFoundError as e:
        raise ImageError(f"图片不存在: {path}") from e
    except (UnidentifiedImageError, OSError) as e:
        raise ImageError(f"无法识别的图片格式: {path}") from e

    frames: list[PixelFrame] = []
    n_frames = getattr(img, "n_frames", 1)
    for i in range(n_frames):
        img.seek(i)
        frames.append(_process_pil(img.convert("RGB"), opts))
    return frames
