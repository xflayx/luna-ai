from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Mapping

from core.skill_registry import SkillRegistry
from core.workflow_engine import WorkflowEngine


_LOCK = threading.RLock()
_REGISTRY = SkillRegistry()
_ENGINE = WorkflowEngine(registry=_REGISTRY)
_LOADED_WORKFLOW: dict[str, Any] | None = None
_LOADED_WORKFLOW_PATH: str = ""
logger = logging.getLogger("WorkflowRuntime")


def _base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def workflow_dir() -> Path:
    raw = os.getenv("LUNA_WORKFLOW_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return (_base_dir() / "workflows").resolve()


def _templates_dir() -> Path:
    return (workflow_dir() / "templates").resolve()


def _ensure_dirs() -> None:
    workflow_dir().mkdir(parents=True, exist_ok=True)
    _templates_dir().mkdir(parents=True, exist_ok=True)


def _is_safe_under_workflow_dir(path: Path) -> bool:
    try:
        path.resolve().relative_to(workflow_dir())
        return True
    except Exception:
        return False


def _parse_workflow_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Workflow invalido: raiz precisa ser objeto JSON.")
    return data


def list_workflows() -> list[dict[str, Any]]:
    _ensure_dirs()
    items: list[dict[str, Any]] = []
    root = workflow_dir()
    for path in sorted(root.rglob("*.json")):
        if not path.is_file():
            continue
        if not _is_safe_under_workflow_dir(path):
            continue
        try:
            data = _parse_workflow_file(path)
            items.append(
                {
                    "id": str(data.get("id", "")).strip() or path.stem,
                    "name": str(data.get("name", "")).strip() or path.stem,
                    "path": str(path),
                    "nodes": len(data.get("nodes", []) or []),
                    "connections": len(data.get("connections", []) or []),
                }
            )
        except Exception:
            continue
    return items


def _resolve_path(path_or_name: str) -> Path:
    value = (path_or_name or "").strip()
    if not value:
        raise ValueError("Caminho do workflow vazio.")

    raw_path = Path(value)
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (workflow_dir() / raw_path).resolve()

    if resolved.suffix.lower() != ".json":
        raise ValueError("Workflow precisa ser arquivo .json.")
    if not resolved.exists():
        raise FileNotFoundError(f"Workflow nao encontrado: {resolved}")
    if not _is_safe_under_workflow_dir(resolved):
        raise ValueError("Caminho fora do diretorio de workflows.")
    return resolved


def load_workflow(
    *,
    workflow_id: str = "",
    path: str = "",
    data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    global _LOADED_WORKFLOW, _LOADED_WORKFLOW_PATH
    _ensure_dirs()

    with _LOCK:
        if data is not None:
            payload = dict(data)
            _LOADED_WORKFLOW = payload
            _LOADED_WORKFLOW_PATH = ""
            return payload

        if path:
            resolved = _resolve_path(path)
            payload = _parse_workflow_file(resolved)
            _LOADED_WORKFLOW = payload
            _LOADED_WORKFLOW_PATH = str(resolved)
            return payload

        wf_id = (workflow_id or "").strip()
        if wf_id:
            candidates = list_workflows()
            chosen = None
            for item in candidates:
                if item.get("id") == wf_id:
                    chosen = item
                    break
                if Path(item.get("path", "")).stem == wf_id:
                    chosen = item
                    break
            if not chosen:
                raise FileNotFoundError(f"Workflow '{wf_id}' nao encontrado.")
            resolved = _resolve_path(chosen["path"])
            payload = _parse_workflow_file(resolved)
            _LOADED_WORKFLOW = payload
            _LOADED_WORKFLOW_PATH = str(resolved)
            return payload

        raise ValueError("Informe workflow_id, path ou data para carregar workflow.")


def get_loaded_workflow() -> dict[str, Any] | None:
    with _LOCK:
        if _LOADED_WORKFLOW is None:
            return None
        return dict(_LOADED_WORKFLOW)


def get_loaded_workflow_meta() -> dict[str, Any]:
    with _LOCK:
        if _LOADED_WORKFLOW is None:
            return {
                "loaded": False,
                "id": "",
                "name": "",
                "path": "",
                "nodes": 0,
                "connections": 0,
            }
        wf = _LOADED_WORKFLOW
        return {
            "loaded": True,
            "id": str(wf.get("id", "")).strip(),
            "name": str(wf.get("name", "")).strip(),
            "path": _LOADED_WORKFLOW_PATH,
            "nodes": len(wf.get("nodes", []) or []),
            "connections": len(wf.get("connections", []) or []),
        }


def start_workflow(
    *,
    workflow_id: str = "",
    path: str = "",
    data: Mapping[str, Any] | None = None,
    listen_patterns: tuple[str, ...] = ("chat.*",),
    start_node_id: str = "",
) -> dict[str, Any]:
    payload = load_workflow(workflow_id=workflow_id, path=path, data=data)
    patterns = tuple(p for p in (listen_patterns or ()) if str(p).strip()) or ("chat.*",)
    _ENGINE.start_event_driven(
        payload,
        listen_patterns=patterns,
        start_node_id=(start_node_id or "").strip(),
    )
    return get_runtime_status()


def run_loaded_workflow_once(
    *,
    start_node_id: str = "",
    initial_inputs: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    payload = get_loaded_workflow()
    if payload is None:
        raise ValueError("Nenhum workflow carregado.")
    outputs = _ENGINE.execute_linear(
        payload,
        start_node_id=(start_node_id or "").strip(),
        initial_inputs=initial_inputs or {},
    )
    return outputs


def run_workflow_once(
    *,
    workflow_id: str = "",
    path: str = "",
    data: Mapping[str, Any] | None = None,
    start_node_id: str = "",
    initial_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = load_workflow(workflow_id=workflow_id, path=path, data=data)
    outputs = _ENGINE.execute_linear(
        payload,
        start_node_id=(start_node_id or "").strip(),
        initial_inputs=initial_inputs or {},
    )
    return outputs


def validate_workflow(
    *,
    workflow_id: str = "",
    path: str = "",
    data: Mapping[str, Any] | None = None,
    start_node_id: str = "",
) -> dict[str, Any]:
    payload = load_workflow(workflow_id=workflow_id, path=path, data=data)
    report = _ENGINE.validate_workflow(
        payload,
        start_node_id=(start_node_id or "").strip(),
    )
    return report


def stop_workflow() -> dict[str, Any]:
    _ENGINE.stop_event_driven()
    return get_runtime_status()


def get_runtime_status() -> dict[str, Any]:
    status = _ENGINE.get_status()
    status["loaded_workflow"] = get_loaded_workflow_meta()
    return status


def _env_patterns(raw: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in (raw or "").split(",") if item.strip())
    return values or ("chat.*",)


def autostart_workflow_from_env() -> dict[str, Any]:
    enabled = os.getenv("LUNA_WORKFLOW_AUTOSTART", "0").strip() == "1"
    workflow_id = os.getenv("LUNA_WORKFLOW_AUTO_ID", "").strip()
    path = os.getenv("LUNA_WORKFLOW_AUTO_PATH", "").strip()
    start_node_id = os.getenv("LUNA_WORKFLOW_AUTO_START_NODE_ID", "").strip()
    listen_patterns = _env_patterns(
        os.getenv("LUNA_WORKFLOW_AUTO_LISTEN_PATTERNS", "chat.*").strip()
    )

    result: dict[str, Any] = {
        "enabled": enabled,
        "started": False,
        "workflow_id": workflow_id,
        "path": path,
        "start_node_id": start_node_id,
        "listen_patterns": listen_patterns,
        "status": {},
        "error": "",
    }

    if not enabled:
        return result

    if not workflow_id and not path:
        msg = (
            "LUNA_WORKFLOW_AUTOSTART=1, mas nenhum workflow foi informado. "
            "Configure LUNA_WORKFLOW_AUTO_ID ou LUNA_WORKFLOW_AUTO_PATH."
        )
        result["error"] = msg
        logger.warning(msg)
        return result

    try:
        status = start_workflow(
            workflow_id=workflow_id,
            path=path,
            listen_patterns=listen_patterns,
            start_node_id=start_node_id,
        )
        result["started"] = True
        result["status"] = status
        return result
    except Exception as exc:
        result["error"] = str(exc)
        logger.warning("Falha no autostart de workflow: %s", exc)
        return result

