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
