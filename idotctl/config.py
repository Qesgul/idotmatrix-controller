"""本地状态持久化：~/.idotctl/config.json。"""
from __future__ import annotations
import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".idotctl" / "config.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_last_device(path: Path = CONFIG_PATH) -> str | None:
    return load_config(path).get("last_device")


def set_last_device(address: str, path: Path = CONFIG_PATH) -> None:
    cfg = load_config(path)
    cfg["last_device"] = address
    save_config(cfg, path)
