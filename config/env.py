import os

from dotenv import load_dotenv

from config.assistant_config import apply_env_overrides, load_assistant_config

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DOTENV_PATH = os.path.join(_BASE_DIR, ".env")


def init_env(override: bool = True) -> str:
    load_dotenv(_DOTENV_PATH, override=override)
    config = load_assistant_config()
    apply_env_overrides(config)
    return _DOTENV_PATH
