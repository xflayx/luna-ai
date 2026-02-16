import os
import sys

from dotenv import load_dotenv

from config.assistant_config import apply_env_overrides, load_assistant_config

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DOTENV_PATH = os.path.join(_BASE_DIR, ".env")


def _configure_console_utf8() -> None:
    if os.getenv("LUNA_FORCE_UTF8_CONSOLE", "1") != "1":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


def init_env(override: bool = True) -> str:
    _configure_console_utf8()
    load_dotenv(_DOTENV_PATH, override=override)
    config = load_assistant_config()
    apply_env_overrides(config)
    return _DOTENV_PATH
