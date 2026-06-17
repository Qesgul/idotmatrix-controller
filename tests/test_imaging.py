import pytest
from PIL import Image
from idotctl.core.imaging import ImageOptions, PixelFrame, process_image
from idotctl.errors import ImageError


def _make(tmp_path, color, w=100, h=100, name="in.png"):
    p = tmp_path / name
    Image.new("RGB", (w, h), color).save(p)
    return p


def test_solid_color_no_dither(tmp_path):
    p = _make(tmp_path, (255, 0, 0))
    frame = process_image(str(p), ImageOptions(dither=False))
    assert isinstance(frame, PixelFrame)
    assert frame.size == 32
    assert len(frame.pixels) == 32 * 32 * 3
    # 纯红图缩放后仍应为红（范围检查兼容不同 Pillow 版本的重采样差异）
    r, g, b = frame.pixels[0], frame.pixels[1], frame.pixels[2]
    assert r > 200 and g < 30 and b < 30


def test_fit_modes_all_produce_32(tmp_path):
    p = _make(tmp_path, (10, 200, 30), w=200, h=80)
    for fit in ("crop", "letterbox", "stretch"):
        frame = process_image(str(p), ImageOptions(fit=fit, dither=False))
        assert frame.size == 32
        assert len(frame.pixels) == 32 * 32 * 3


def test_letterbox_has_black_border(tmp_path):
    # 宽扁图 letterbox → 上下应出现黑边(第一行像素为黑)
    p = _make(tmp_path, (255, 255, 255), w=320, h=32)
    frame = process_image(str(p), ImageOptions(fit="letterbox", dither=False))
    assert frame.pixels[0:3] == bytes((0, 0, 0))


def test_missing_file_raises_image_error(tmp_path):
    with pytest.raises(ImageError):
        process_image(str(tmp_path / "nope.png"), ImageOptions())


def test_invalid_fit_raises_value_error(tmp_path):
    p = _make(tmp_path, (100, 100, 100))
    with pytest.raises(ValueError, match="fit must be one of"):
        process_image(str(p), ImageOptions(fit="invalid"))


def test_invalid_size_raises_value_error(tmp_path):
    p = _make(tmp_path, (100, 100, 100))
    with pytest.raises(ValueError, match="size must be"):
        process_image(str(p), ImageOptions(size=0))


def test_dither_runs_and_keeps_shape(tmp_path):
    # 渐变图,dither 开启应正常产出正确尺寸帧
    img = Image.new("RGB", (64, 64))
    px = img.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = (x * 4 % 256, y * 4 % 256, (x + y) * 2 % 256)
    p = tmp_path / "grad.png"
    img.save(p)
    frame = process_image(str(p), ImageOptions(dither=True))
    assert frame.size == 32
    assert len(frame.pixels) == 32 * 32 * 3


def test_brightness_zero_yields_black(tmp_path):
    p = _make(tmp_path, (200, 100, 50))
    frame = process_image(str(p), ImageOptions(dither=False, brightness=0.0))
    assert frame.pixels[0:3] == bytes((0, 0, 0))


def test_brightness_increases_value(tmp_path):
    p = _make(tmp_path, (100, 100, 100))
    dark = process_image(str(p), ImageOptions(dither=False, brightness=0.5))
    bright = process_image(str(p), ImageOptions(dither=False, brightness=1.5))
    assert bright.pixels[0] > dark.pixels[0]


def test_process_gif_returns_all_frames(tmp_path):
    from idotctl.core.imaging import process_gif
    frames_in = []
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        frames_in.append(Image.new("RGB", (40, 40), color))
    p = tmp_path / "anim.gif"
    frames_in[0].save(p, save_all=True, append_images=frames_in[1:], duration=100, loop=0)
    frames = process_gif(str(p), ImageOptions(dither=False))
    assert len(frames) == 3
    assert all(f.size == 32 for f in frames)
    assert all(len(f.pixels) == 32 * 32 * 3 for f in frames)
