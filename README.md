# idotmatrix-controller

自己的 iDotMatrix 32×32 LED 控制工具。任意图片 → 压缩到 32×32 → BLE 上屏。

## 安装

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
```

## Web UI（推荐）

```bash
idotctl-web                # 默认 0.0.0.0:8000
idotctl-web --port 9000    # 自定义端口
```

启动后浏览器打开 `http://localhost:8000`。同 WiFi 下的手机平板也可访问（终端会打印局域网 IP）。

> **安全提示**：Web UI 无鉴权，仅限可信局域网使用。

### 功能
- 拖拽上传图片或 GIF
- 实时 32×32 预览（所见即所发）
- 调节缩放模式、抖动、亮度、对比度、饱和度
- 一键发送到屏、控制亮度与开关

## CLI

```bash
idotctl scan                       # 扫描设备
idotctl connect AA:BB:CC:DD:EE:FF  # 连接并记住
idotctl send cat.jpg               # 发送图片（默认裁剪+抖动）
idotctl send cat.jpg --fit letterbox --no-dither --brightness 1.2
idotctl gif anim.gif --fps 12      # 发送 GIF
idotctl brightness 70              # 亮度 0-100
idotctl on / idotctl off           # 开/关屏
idotctl preview cat.jpg -o out.png # 预览 32×32 效果（无需硬件）
```

## 架构

```
idotctl/
├── core/imaging.py    纯图像流水线（可单测）
├── core/device.py     设备适配层（SdkDevice / FakeDevice）
├── config.py          状态记忆
├── cli.py             CLI 命令编排
└── webserver/         Web UI 层
    ├── app.py         FastAPI 路由 + main()
    ├── session.py     DeviceSession（常驻 BLE 连接）
    ├── staging.py     ImageStaging（上传图片暂存）
    └── static/        index.html + app.js + style.css
```

## 测试

```bash
.venv/Scripts/python.exe -m pytest -v
```

## 更新日志

### 2026-06-21 修复 BLE 扫描与图片发送

- **修复 BLE 扫描超时**：原实现使用 `asyncio.wait_for(timeout=5)` 包裹 SDK 扫描，与 SDK 内部 `BleakScanner.discover()` 默认 5 秒超时冲突，导致扫描永远无法完成。现改为直接将 timeout 传给 `BleakScanner.discover()`，默认扫描时间提升至 10 秒。
- **修复图片发送协议**：原实现使用了错误的自定义 RGBA 像素协议，设备固件不识别导致图片发送"成功"但屏幕无变化。现改为设备实际期望的 **PNG/GIF 文件上传协议**（与社区版 idotmatrix 库一致），并在发送前先发送 `set_image_mode(1)` 进入 DIY 绘图模式。
- **接口变更**：`send_image` / `send_gif` 参数从 `PixelFrame` 改为 `bytes`（PNG/GIF 文件字节），更贴近设备实际通信方式。

## 硬件 smoke（需真实设备）

```bash
idotctl scan && idotctl send sample.png
```
