import json
import os
import re
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEMORY_PATH = os.path.join(DATA_DIR, "memoria.json")


def _load_all():
    if not os.path.isfile(MEMORY_PATH):
        return []
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_all(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def adicionar_memoria(texto, origem="usuario"):
    texto_limpo = (texto or "").strip()
    if not texto_limpo:
        return False
    items = _load_all()
    items.append(
        {
            "timestamp": datetime.now().isoformat(),
            "origem": origem,
            "texto": texto_limpo,
        }
    )
    _save_all(items)
    return True


def listar_memorias(limit=10):
    items = _load_all()
    return items[-limit:]


def buscar_memorias(consulta, limit=3):
    items = _load_all()
    if not items:
        return []
    texto = (consulta or "").lower()
    tokens = re.findall(r"[a-z0-9]{3,}", texto)
    if not tokens:
        return []

    scored = []
    for item in items:
        t = str(item.get("texto", "")).lower()
        score = sum(1 for tok in tokens if tok in t)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:limit]]
