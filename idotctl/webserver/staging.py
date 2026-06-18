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

    def _load(self) -> Image.Image:
        return self._open(self._require_image())

    def render_preview(self, opts: ImageOptions) -> bytes:
        """返回 320×320 放大预览 PNG(最近邻插值)。所见即所发:走与发送完全相同的管道。"""
        img = self._load().convert("RGB")
        frame = _process_pil(img, opts)
        small = Image.frombytes("RGB", (frame.size, frame.size), frame.pixels)
        preview = small.resize((320, 320), Image.Resampling.NEAREST)
        buf = io.BytesIO()
        preview.save(buf, "PNG")
        return buf.getvalue()

    def get_frame(self, opts: ImageOptions) -> PixelFrame:
        """返回 32×32 PixelFrame,供 send_image 使用。"""
        return _process_pil(self._load().convert("RGB"), opts)

    def get_gif_frames(self, opts: ImageOptions) -> list[PixelFrame]:
        """返回 GIF 全部帧的 PixelFrame 列表。"""
        img = self._load()
        n = getattr(img, "n_frames", 1)
        frames: list[PixelFrame] = []
        for i in range(n):
            img.seek(i)
            frames.append(_process_pil(img.convert("RGB"), opts))
        return frames
