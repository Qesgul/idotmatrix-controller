# idotmatrix-controller

自己的 iDotMatrix 32×32 LED 控制 CLI。任意图片 → 压缩到 32×32 → BLE 上屏。

## 安装

```bash
python -m venv .venv
.venv/Scripts/pip install -e .
```

## 使用

```bash
idotctl scan                       # 扫描设备
idotctl connect AA:BB:CC:DD:EE:FF  # 连接并记住
idotctl send cat.jpg               # 发送图片(默认裁剪+抖动)
idotctl send cat.jpg --fit letterbox --no-dither --brightness 1.2
idotctl gif anim.gif --fps 12      # 发送 GIF
idotctl brightness 70              # 亮度 0-100
idotctl on / idotctl off           # 开/关屏
idotctl preview cat.jpg -o out.png # 不发送,仅看 32x32 处理效果(无需硬件)
```

## 架构

- `idotctl/core/imaging.py` 纯图像流水线(可单测)
- `idotctl/core/device.py` 设备适配层(SdkDevice 真实 / FakeDevice 测试)
- `idotctl/cli.py` 命令编排
- `idotctl/config.py` 状态记忆

## 测试

```bash
.venv/Scripts/python -m pytest -v
```

## 硬件 smoke(需真实设备)

```bash
idotctl scan && idotctl send sample.png
```
