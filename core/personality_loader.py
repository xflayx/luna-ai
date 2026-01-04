# core/personality_loader.py

import json
from pathlib import Path


PERSONALITY_PATH = Path("config/personality.json")


def carregar_personalidade() -> dict:
    if not PERSONALITY_PATH.exists():
        raise FileNotFoundError("Arquivo de personalidade não encontrado.")

    with open(PERSONALITY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
