"""统一异常类型：CLI 顶层捕获后输出友好提示。"""


class IdotError(Exception):
    """本项目所有异常的基类。"""


class DeviceNotFoundError(IdotError):
    """扫描不到设备 / 未指定且无历史设备 / 连接失败。"""


class ConnectionError(IdotError):
    """BLE 连接中断。"""


class ImageError(IdotError):
    """图片无法读取 / 格式不支持。"""


class FirmwareUnsupportedError(IdotError):
    """SDK 报协议不匹配——关键风险点的显式信号。"""
