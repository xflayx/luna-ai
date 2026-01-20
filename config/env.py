import os

from dotenv import load_dotenv


_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DOTENV_PATH = os.path.join(_BASE_DIR, ".env")


def init_env(override: bool = True) -> str:
    load_dotenv(_DOTENV_PATH, override=override)
    return _DOTENV_PATH
