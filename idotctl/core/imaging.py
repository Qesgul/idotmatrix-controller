"""纯图像流水线：任意图片 → size×size RGB 帧。零硬件依赖。"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from idotctl.errors import ImageError


@dataclass(frozen=True)
class ImageOptions:
    fit: Literal["crop", "letterbox", "stretch"] = "crop"
    dither: bool = True         # Floyd–Steinberg
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    size: int = 32

    def __post_init__(self) -> None:
        _VALID_FIT = {"crop", "letterbox", "stretch"}
        if self.fit not in _VALID_FIT:
            raise ValueError(f"fit must be one of {_VALID_FIT}, got {self.fit!r}")
        if self.size < 1:
            raise ValueError(f"size must be >= 1, got {self.size!r}")


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
    n = opts.size
    if opts.fit == "stretch":
        return img.resize((n, n), Image.LANCZOS)
    if opts.fit == "letterbox":
        fitted = ImageOps.contain(img, (n, n), Image.LANCZOS)
        canvas = Image.new("RGB", (n, n), (0, 0, 0))
        off = ((n - fitted.width) // 2, (n - fitted.height) // 2)
        canvas.paste(fitted, off)
        return canvas
    # 默认 crop：覆盖式缩放 + 居中裁剪
    return ImageOps.fit(img, (n, n), Image.LANCZOS)


def _adjust(img: Image.Image, opts: ImageOptions) -> Image.Image:
    if opts.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(opts.brightness)
    if opts.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(opts.contrast)
    if opts.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(opts.saturation)
    return img


def _dither(img: Image.Image) -> Image.Image:
    """自适应调色板 + Floyd–Steinberg 误差扩散,缓解低分屏色带。"""
    return img.convert(
        "P", palette=Image.ADAPTIVE, colors=64, dither=Image.FLOYDSTEINBERG
    ).convert("RGB")


def _process_pil(img: Image.Image, opts: ImageOptions) -> PixelFrame:
    img = _fit(img, opts)
    img = _adjust(img, opts)
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
