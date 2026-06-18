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

## 硬件 smoke（需真实设备）

```bash
idotctl scan && idotctl send sample.png
```
