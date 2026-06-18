# iDotMatrix Web UI 设计文档

**日期**: 2026-06-18
**状态**: 已批准,待出实现计划
**所属项目**: idotmatrix-controller(在现有 CLI 之上新增 Web UI 层)

---

## 1. 目标

为现有的 `idotctl` CLI 工具增加一个**局域网 Web UI**,让用户能在手机/平板/电脑的浏览器里:上传图片或 GIF → 实时预览 32×32 上屏效果 → 一键发送到 iDotMatrix LED 显示器,并控制亮度与开关。

**一句话**:把 CLI 的全部能力搬到浏览器,核心图像/设备逻辑零改动复用。

## 2. 范围与约束

### 范围(v1 包含)
- 传图上屏(上传 → 32×32 实时预览 → 发送)
- GIF 动图(上传 → 逐帧发送,可设 FPS)
- 设备扫描 / 连接 / 断开(记住上次设备)
- 亮度滑块(0–100)+ 开屏 / 关屏

### 约束
- **访问范围**:同局域网。服务绑定 `0.0.0.0`,手机平板同 WiFi 可访问。
- **连接模式**:保持连接(常驻 BLE 会话),连一次后续操作秒发。
- **鉴权**:v1 不做登录鉴权(局域网个人使用)。README 明确标注"仅限可信局域网使用"。绑定地址可通过参数配置。
- **复用**:`core/imaging.py`、`core/device.py`、`config.py`、`cli.py` 一行不改。
- **BLE 物理限制**:服务端进程必须跑在靠近显示器(~10m)的电脑上;浏览器可以离得很远。
- **单显示器假设**:一个全局会话对应一台显示器;多浏览器连入时共享同一会话(v1 可接受)。

### 非目标(v1 不做)
- 公网远程访问 / 内网穿透(后续可加 Cloudflare Tunnel,不在 v1)
- 多设备并发控制
- 用户登录 / 多租户
- 动画编辑器、图库管理、定时任务

## 3. 架构

新增 `idotctl/webserver/` 子包,作为 CLI 之外的第二个"前端"。后端用 FastAPI(async,与 bleak 共用事件循环),前端为原生 HTML/JS/CSS(无构建链),由 FastAPI 直接 serve 静态文件。

```
idotctl/
├── core/imaging.py      ← 不动(process_image / process_gif / ImageOptions / PixelFrame)
├── core/device.py       ← 不动(SdkDevice / FakeDevice / DeviceAdapter)
├── config.py            ← 不动(get_last_device / set_last_device)
├── cli.py               ← 不动
└── webserver/           ← 新增
    ├── __init__.py
    ├── app.py           FastAPI 应用 + 路由 + 入口 main()
    ├── session.py       DeviceSession:常驻连接管理(核心新逻辑)
    ├── staging.py       ImageStaging:暂存上传的原图,供预览/发送复用
    └── static/
        ├── index.html
        ├── app.js
        └── style.css
```

### 选型理由
- **FastAPI + 原生前端** 而非 React/Vue:个人局域网小工具,前端构建链是纯负担;三个静态文件最轻最可控。
- **服务端渲染预览** 而非浏览器 canvas:32×32 预览必须走真实的 `process_image`(含 Floyd–Steinberg 抖动),只有 Python 端能产出与上屏完全一致的结果——保证"所见即所发"。

## 4. 核心组件

### 4.1 DeviceSession (`session.py`)
"保持连接"模式的核心抽象,全局单例。

**职责**:
- 持有单个 `SdkDevice` 实例及其连接状态(当前地址、是否已连)
- 用 `asyncio.Lock` 串行化所有 BLE 操作——同一时刻只能干一件事,防止并发破坏连接
- 暴露异步方法:`connect(address)`、`disconnect()`、`scan(timeout)`、`send_image(frame)`、`send_gif(frames, fps)`、`set_brightness(level)`、`set_power(on)`
- 暴露状态查询:`is_connected`、`current_address`
- 连接意外断开时更新状态,供 `/api/status` 反映

**接口契约**:
- 消费者只需 `await session.send_image(frame)` 等方法 + 读状态属性,无需关心连接是否已建立的底层细节(未连接时方法抛 `BleConnectionError`)。
- 依赖:接受一个 `DeviceAdapter`(默认 `SdkDevice`,测试注入 `FakeDevice`)。

### 4.2 ImageStaging (`staging.py`)
暂存上传的原图,避免每次调参数都重传几 MB。

**职责**:
- `stage(data: bytes, filename: str)`:把上传的原图字节存入内存(单槽,后传覆盖前传)
- `render_preview(opts) -> bytes`:对暂存图跑 `process_image`,返回放大后的 PNG 字节(最近邻放大到约 320×320 便于肉眼看)
- `get_frame(opts) -> PixelFrame`:对暂存图跑 `process_image`,返回原始 32×32 帧(供发送)
- `get_gif_frames(opts) -> list[PixelFrame]`:对暂存 GIF 跑 `process_gif`
- `has_image -> bool`:是否已有暂存图

**接口契约**:输入原图字节 + `ImageOptions`,输出预览 PNG 或 `PixelFrame`。纯逻辑,不碰硬件。

### 4.3 FastAPI 应用 (`app.py`)
路由编排 + 依赖注入 + 静态文件 serve + `main()` 入口。

**职责**:
- 定义所有 `/api/*` 路由,把请求翻译成对 `DeviceSession` / `ImageStaging` 的调用
- 全局持有 `DeviceSession` 单例和 `ImageStaging` 单例(通过依赖注入,测试可覆盖)
- 静态文件:`GET /` 返回 `static/index.html`,`/static/*` serve 其余资源
- `main()`:解析 `--host`/`--port`,启动 uvicorn,打印本机访问地址

## 5. 数据流

**传图上屏典型流程**:
```
浏览器选图
  → POST /api/upload (multipart)         ImageStaging.stage(),返回 {ok: true}
  → POST /api/preview {fit,dither,...}    ImageStaging.render_preview(),返回 PNG
  → 用户拖滑块,前端防抖(~300ms)重发 /api/preview  右侧预览刷新
  → POST /api/send {同样的参数}           ImageStaging.get_frame() → DeviceSession.send_image()
```

**GIF 流程**:`/api/upload` 暂存 GIF → `/api/gif {fps,...}` → `ImageStaging.get_gif_frames()` → `DeviceSession.send_gif()`。

**控制流程**:`/api/brightness`、`/api/power` 直接调 `DeviceSession` 对应方法,无需暂存图。

## 6. API 接口清单

| 方法 | 路径 | 请求 | 响应 | 作用 |
|------|------|------|------|------|
| GET | `/` | — | HTML | 返回 index.html |
| GET | `/api/status` | — | `{connected, address, last_device}` | 连接状态 |
| POST | `/api/scan` | — | `[{name, address}]` | 扫描 BLE 设备(~5s) |
| POST | `/api/connect` | `{address}` | `{ok}` | 连接 + 写入 config |
| POST | `/api/disconnect` | — | `{ok}` | 断开 |
| POST | `/api/upload` | multipart file | `{ok, filename, is_gif}` | 暂存原图/GIF |
| POST | `/api/preview` | `{fit,dither,brightness,contrast,saturation}` | PNG bytes | 渲染 32×32 预览(不发设备) |
| POST | `/api/send` | 同 preview 参数 | `{ok}` | 处理并发送到屏 |
| POST | `/api/gif` | `{fps, ...同上}` | `{ok}` | 逐帧发送 GIF |
| POST | `/api/brightness` | `{level: 0-100}` | `{ok}` | 设置亮度 |
| POST | `/api/power` | `{on: bool}` | `{ok}` | 开/关屏 |

## 7. 错误处理 & 并发

- **串行化**:所有 BLE 操作经 `DeviceSession` 的 `asyncio.Lock`,杜绝并发冲突。
- **错误映射**:`IdotError` 及子类 → HTTP 4xx/5xx + JSON `{error: "中文消息"}`;前端弹 toast。
  - 未连接调发送类接口 → 400 `{error: "请先连接设备"}`,前端按钮置灰。
  - 扫描不到设备 → `DeviceNotFoundError` → 404。
  - 图片无法识别 → `ImageError` → 400。
  - 协议不匹配 → `FirmwareUnsupportedError` → 502(关键风险点显式信号)。
- **断开检测**:连接意外断开 → `is_connected` 转 false → `/api/status` 反映 → 顶部状态灯变灰。
- **未暂存图**:调 preview/send 但无暂存图 → 400 `{error: "请先上传图片"}`。

## 8. 界面布局

单页布局,四区(详见已批准的草图):
1. **顶部连接栏**:状态灯(绿=已连/灰=断开)、设备地址、扫描 / 断开按钮。
2. **左区图片**:拖拽上传区 + "发送到屏" / "发送 GIF" 按钮。
3. **右区预览**:服务端真实管道渲染的 32×32 放大图,标注"所见即所发"。
4. **图像调节**:缩放模式(裁剪/留边/拉伸)单选、抖动开关、亮度/对比度/饱和度滑块(调参数防抖刷新预览)。
5. **底部**:设备亮度滑块(0–100)+ 开屏 / 关屏按钮。

交互:改任意图像参数 → 防抖 300ms → 自动重渲染预览。点"发送到屏"才真正下发。

## 9. 测试策略

| 层 | 测试方式 |
|----|---------|
| `DeviceSession` | 注入 `FakeDevice` 单测:连接/断开改变状态、锁串行化、各操作正确转发、未连接时抛错 |
| `ImageStaging` | 暂存 PNG → `render_preview` 返回合法 PNG、`get_frame` 返回正确尺寸帧、未暂存时报错、GIF 多帧 |
| API 路由 | FastAPI `TestClient` + 依赖覆盖注入 `FakeDevice`,覆盖所有端点含错误路径(未连接、未上传、坏图片) |
| 静态 serve | `GET /` 返回 200 + HTML |
| 核心层 | 现有 27 个测试不动,继续保证 imaging/device/config 正确 |
| 前端 JS | 原生 JS 不做单测,依赖手动冒烟测试 |

## 10. 依赖与入口

**新增依赖**:`fastapi`、`uvicorn[standard]`、`python-multipart`(文件上传)、`httpx`(测试 TestClient)。

**入口命令**:`pyproject.toml` 加 `idotctl-web = "idotctl.webserver.app:main"`。启动:
```bash
idotctl-web                  # 默认 0.0.0.0:8000
idotctl-web --port 9000      # 自定义端口
```
启动后终端打印 `http://<本机IP>:8000`,手机浏览器打开即用。

## 11. 安全与自主边界(沿用项目契约)

- 只在 `D:\code\idotmatrix-controller\` 内动文件;依赖装进 `.venv`,不污染全局。
- 不做外发网络请求(除 pip 安装依赖)。
- 只 scan/connect iDotMatrix 设备。
- Web 服务仅绑定局域网,README 标注"仅限可信网络"。
- 不改环境变量、系统设置、注册表。
- 只在本项目仓库内 commit,不 push(除非用户要求)。
