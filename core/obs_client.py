import os
import threading
from typing import Optional

from config.env import init_env

init_env()

try:
    import obsws_python as obs
except Exception:  # pragma: no cover - depende de lib externa
    obs = None


_lock = threading.Lock()
_client: Optional["obs.ReqClient"] = None
_connected = False
_clear_timer: Optional[threading.Timer] = None


def _enabled() -> bool:
    if os.getenv("LUNA_OBS_ENABLED", "0") == "1":
        return True
    return bool(_text_source())


def _enabled_for_control() -> bool:
    if os.getenv("LUNA_OBS_ENABLED", "0") == "1":
        return True
    return bool(_text_source()) or bool(_scene_name())


def _host() -> str:
    return os.getenv("LUNA_OBS_HOST", "127.0.0.1")


def _port() -> int:
    try:
        return int(os.getenv("LUNA_OBS_PORT", "4455"))
    except ValueError:
        return 4455


def _password() -> str:
    return os.getenv("LUNA_OBS_PASSWORD", "")


def _text_source() -> str:
    return os.getenv("LUNA_OBS_TEXT_SOURCE", "").strip()


def _scene_name() -> str:
    return os.getenv("LUNA_OBS_SCENE", "").strip()


def _clear_sec() -> float:
    try:
        return float(os.getenv("LUNA_OBS_CLEAR_SEC", "0"))
    except ValueError:
        return 0.0


def _clear_hide() -> bool:
    return os.getenv("LUNA_OBS_CLEAR_HIDE", "0") == "1"


def _wrap_chars() -> int:
    try:
        return int(os.getenv("LUNA_OBS_WRAP_CHARS", "0"))
    except ValueError:
        return 0


def _wrap_text(texto: str) -> str:
    limite = _wrap_chars()
    if limite <= 0:
        return texto
    palavras = texto.split()
    if not palavras:
        return texto
    linhas: list[str] = []
    linha = ""
    for p in palavras:
        if not linha:
            linha = p
            continue
        if len(linha) + 1 + len(p) <= limite:
            linha += " " + p
            continue
        linhas.append(linha)
        linha = p
    if linha:
        linhas.append(linha)
    return "\n".join(linhas)


def _connect() -> bool:
    global _client, _connected
    if not obs:
        return False
    if _client and _connected:
        return True
    try:
        _client = obs.ReqClient(host=_host(), port=_port(), password=_password())
        _connected = True
        return True
    except Exception as e:
        _client = None
        _connected = False
        return False


def _disconnect():
    global _client, _connected
    _client = None
    _connected = False


def update_text(texto: str, source_name: Optional[str] = None) -> None:
    if not _enabled():
        return
    source = (source_name or _text_source()).strip()
    if not source or not texto:
        return
    texto = _wrap_text(texto)
    with _lock:
        if not _connect():
            return
        try:
            _client.set_input_settings(
                name=source,
                settings={"text": texto},
                overlay=True,
            )
        except Exception as e:
            _disconnect()
    _schedule_clear(source)


def switch_scene(scene_name: str) -> bool:
    if not _enabled_for_control():
        return False
    scene = (scene_name or "").strip()
    if not scene:
        return False
    with _lock:
        if not _connect():
            return False
        try:
            try:
                _client.set_current_program_scene(scene_name=scene)
            except TypeError:
                _client.set_current_program_scene(scene)
            return True
        except Exception:
            _disconnect()
            return False


def set_source_enabled(source_name: str, enabled: bool, scene_name: str = "") -> bool:
    if not _enabled_for_control():
        return False
    source = (source_name or "").strip()
    if not source:
        return False
    scene = (scene_name or "").strip()
    with _lock:
        if not _connect():
            return False
        try:
            resolved_scene = scene or _scene_name() or _get_current_scene()
            if not resolved_scene:
                return False
            item_resp = _client.get_scene_item_id(
                scene_name=resolved_scene,
                source_name=source,
            )
            item_id = _get_attr(item_resp, "scene_item_id") or _get_attr(item_resp, "sceneItemId")
            if not item_id:
                return False
            _client.set_scene_item_enabled(
                scene_name=resolved_scene,
                item_id=item_id,
                enabled=bool(enabled),
            )
            return True
        except Exception:
            _disconnect()
            return False


def _schedule_clear(source: str) -> None:
    global _clear_timer
    delay = _clear_sec()
    if delay <= 0:
        return
    if _clear_timer:
        try:
            _clear_timer.cancel()
        except Exception:
            pass
    _clear_timer = threading.Timer(delay, _clear_text, args=(source,))
    _clear_timer.daemon = True
    _clear_timer.start()


def _clear_text(source: str) -> None:
    if not _enabled():
        return
    if not source:
        return
    
    # CORREÇÃO 1: O lock estava sendo chamado DEPOIS de verificar _clear_hide()
    # mas _toggle_visibility também precisa do lock
    if _clear_hide():
        with _lock:
            if not _connect():
                return
            _toggle_visibility(source)
        return
    
    # Modo texto em branco
    with _lock:
        if not _connect():
            return
        try:
            _client.set_input_settings(
                name=source,
                settings={"text": ""},  # CORREÇÃO 2: Mudei de " " para "" (string vazia)
                overlay=True,
            )
        except Exception as e:
            _disconnect()


def _toggle_visibility(source: str) -> None:
    # CORREÇÃO 3: Esta função agora é chamada COM o lock já adquirido
    try:
        scene = _scene_name() or _get_current_scene()
        if not scene:
            return
        
        item_resp = _client.get_scene_item_id(scene_name=scene, source_name=source)
        item_id = _get_attr(item_resp, "scene_item_id") or _get_attr(item_resp, "sceneItemId")
        
        if not item_id:
            return
        
        # Desabilita o item (esconde)
        _client.set_scene_item_enabled(
            scene_name=scene,
            item_id=item_id,
            enabled=False,
        )
        
        # CORREÇÃO 4: Timer para reabilitar com daemon=True
        timer = threading.Timer(0.4, _set_item_enabled, args=(scene, item_id, True))
        timer.daemon = True
        timer.start()
        
    except Exception as e:
        _disconnect()


def _set_item_enabled(scene: str, item_id: int, enabled: bool) -> None:
    with _lock:
        if not _connect():
            return
        try:
            _client.set_scene_item_enabled(
                scene_name=scene,
                item_id=item_id,
                enabled=enabled,
            )
        except Exception as e:
            _disconnect()


def _get_current_scene() -> Optional[str]:
    try:
        resp = _client.get_current_program_scene()
        scene = (
            _get_attr(resp, "current_program_scene_name")
            or _get_attr(resp, "currentProgramSceneName")  # CORREÇÃO 5: Adicionei variação camelCase
            or _get_attr(resp, "scene_name")
            or _get_attr(resp, "sceneName")
        )
        return scene
    except Exception as e:
        return None


def _get_attr(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
