import copy
import json
import os
import re
import tempfile
import threading
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
SHORT_MEMORY_PATH = os.path.join(MEMORY_DIR, "short_term.json")
LONG_MEMORY_PATH = os.path.join(MEMORY_DIR, "long_term.json")
LEGACY_MEMORY_PATH = os.path.join(BASE_DIR, "data", "memoria.json")
_STORE_LOCK = threading.RLock()
_STORE_CACHE: dict[str, tuple[float, dict]] = {}


def _now_iso():
    return datetime.now().isoformat()


def _empty_store():
    return {"items": [], "meta": {"created_at": "", "updated_at": "", "version": 1}}


def _clone_store(store: dict) -> dict:
    return copy.deepcopy(store)


def _load_store(path):
    if not os.path.isfile(path):
        return _empty_store()
    with _STORE_LOCK:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return _empty_store()

        cached = _STORE_CACHE.get(path)
        if cached and cached[0] == mtime:
            return _clone_store(cached[1])

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                store = data
            elif isinstance(data, list):
                store = _empty_store()
                store["items"] = data
            else:
                store = _empty_store()
        except Exception:
            store = _empty_store()

        _STORE_CACHE[path] = (mtime, _clone_store(store))
        return _clone_store(store)


def _save_store(path, store):
    with _STORE_LOCK:
        target_dir = os.path.dirname(path) or MEMORY_DIR
        os.makedirs(target_dir, exist_ok=True)
        now = _now_iso()
        meta = store.get("meta") or {}
        if not meta.get("created_at"):
            meta["created_at"] = now
        meta["updated_at"] = now
        meta["version"] = meta.get("version", 1)
        store["meta"] = meta

        fd, tmp_path = tempfile.mkstemp(
            prefix="luna_mem_",
            suffix=".tmp",
            dir=target_dir,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(store, f, ensure_ascii=True, separators=(",", ":"))
            os.replace(tmp_path, path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = -1.0
        _STORE_CACHE[path] = (mtime, _clone_store(store))


def _load_legacy_items():
    if not os.path.isfile(LEGACY_MEMORY_PATH):
        return []
    try:
        with open(LEGACY_MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data.get("items", [])
    except Exception:
        pass
    return []


def _ensure_long_memory_initialized():
    with _STORE_LOCK:
        if os.path.isfile(LONG_MEMORY_PATH):
            return
        legacy_items = _load_legacy_items()
        if not legacy_items:
            return
        store = _empty_store()
        store["items"] = legacy_items
        _save_store(LONG_MEMORY_PATH, store)


def _add_item(path, texto, origem="usuario", max_items=None):
    texto_limpo = (texto or "").strip()
    if not texto_limpo:
        return False
    with _STORE_LOCK:
        store = _load_store(path)
        store.setdefault("items", []).append(
            {
                "timestamp": _now_iso(),
                "origem": origem,
                "texto": texto_limpo,
            }
        )
        if max_items is not None and len(store["items"]) > max_items:
            store["items"] = store["items"][-max_items:]
        _save_store(path, store)
    return True


def adicionar_memoria(texto, origem="usuario"):
    _ensure_long_memory_initialized()
    return _add_item(LONG_MEMORY_PATH, texto, origem=origem)


def adicionar_memoria_curta(texto, origem="usuario", max_items=50):
    return _add_item(SHORT_MEMORY_PATH, texto, origem=origem, max_items=max_items)


def listar_memorias(limit=10):
    _ensure_long_memory_initialized()
    items = _load_store(LONG_MEMORY_PATH).get("items", [])
    return items[-limit:]


def listar_memorias_curtas(limit=10):
    items = _load_store(SHORT_MEMORY_PATH).get("items", [])
    return items[-limit:]


def contar_memoria_curta() -> int:
    items = _load_store(SHORT_MEMORY_PATH).get("items", [])
    return len(items)


def limpar_memoria_curta() -> bool:
    store = _empty_store()
    _save_store(SHORT_MEMORY_PATH, store)
    return True


def buscar_memorias(consulta, limit=3):
    _ensure_long_memory_initialized()
    items = _load_store(LONG_MEMORY_PATH).get("items", [])
    return _buscar_itens(items, consulta, limit=limit)


def buscar_memorias_curtas(consulta, limit=3):
    items = _load_store(SHORT_MEMORY_PATH).get("items", [])
    return _buscar_itens(items, consulta, limit=limit)


def _buscar_itens(items, consulta, limit=3):
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
