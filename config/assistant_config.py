import os

import yaml


_CONFIG_DIR = os.path.dirname(__file__)
_DEFAULT_PATH = os.path.join(_CONFIG_DIR, "assistant_config.yaml")


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def load_assistant_config(path: str | None = None) -> dict:
    cfg_path = path or os.getenv("LUNA_ASSISTANT_CONFIG_PATH") or _DEFAULT_PATH
    if not os.path.isfile(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_env_overrides(config: dict) -> None:
    if not isinstance(config, dict):
        return
    env_cfg = config.get("env", {})
    if not isinstance(env_cfg, dict):
        return
    for key, value in env_cfg.items():
        if not isinstance(key, str) or not key:
            continue
        if not _has_value(value):
            continue
        os.environ[key] = str(value)
