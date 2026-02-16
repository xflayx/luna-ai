from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from config.state import STATE
from core.router import processar_comando as processar_comando_router
from core.workflow_runtime import get_loaded_workflow, run_loaded_workflow_once


logger = logging.getLogger("CommandOrchestrator")


def _is_control_command(cmd: str) -> bool:
    cmd_lower = (cmd or "").lower().strip()
    if not cmd_lower:
        return False

    cmd_limpo = cmd_lower.replace("luna", "").strip()
    if "modo vtuber" in cmd_limpo or "ativar vtuber" in cmd_limpo:
        return True
    if "modo assistente" in cmd_limpo or "ativar assistente" in cmd_limpo:
        return True
    if "recarregar" in cmd_limpo and ("skill" in cmd_limpo or "skills" in cmd_limpo):
        return True
    return False


def _workflow_accepts_command_path(workflow_data: Mapping[str, Any]) -> bool:
    nodes = workflow_data.get("nodes")
    if not isinstance(nodes, list):
        return False

    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        raw_filters = node.get("event_filters")
        if raw_filters is None:
            raw_filters = node.get("eventFilters")
        if isinstance(raw_filters, list) and raw_filters:
            return False
    return True


def _extract_workflow_response(
    outputs: Mapping[str, Any] | None,
    *,
    original_command: str,
) -> Optional[str]:
    if not isinstance(outputs, Mapping) or not outputs:
        return None

    original = (original_command or "").strip().lower()

    for _, node_output in reversed(list(outputs.items())):
        if isinstance(node_output, Mapping):
            for key in ("response", "text", "message", "result"):
                value = node_output.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    if text.lower() != original:
                        return text
            for value in node_output.values():
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    if text.lower() != original:
                        return text
        elif isinstance(node_output, str) and node_output.strip():
            text = node_output.strip()
            if text.lower() != original:
                return text
    return None


def processar_comando_orquestrado(
    cmd: str,
    intent: Optional[str] = None,
    *,
    source: str = "main",
) -> Optional[str]:
    cmd_text = (cmd or "").strip()
    if not cmd_text:
        return None

    if (
        _is_control_command(cmd_text)
        or STATE.esperando_nome_sequencia
        or STATE.esperando_loops
        or STATE.gravando_sequencia
    ):
        return processar_comando_router(cmd_text, intent)

    workflow_data: dict[str, Any] | None = None
    try:
        loaded = get_loaded_workflow()
        if isinstance(loaded, dict):
            workflow_data = loaded
    except Exception as exc:
        logger.warning("Falha ao obter workflow carregado: %s", exc)

    if workflow_data and _workflow_accepts_command_path(workflow_data):
        initial_inputs = {
            "text": cmd_text,
            "input": cmd_text,
            "command": cmd_text,
            "message": cmd_text,
            "prompt": cmd_text,
            "intent": intent or "",
            "source": source or "",
        }
        try:
            outputs = run_loaded_workflow_once(initial_inputs=initial_inputs)
            resposta = _extract_workflow_response(outputs, original_command=cmd_text)
            if resposta:
                STATE.adicionar_ao_historico(cmd_text, resposta)
                return resposta
        except Exception as exc:
            logger.warning("Workflow run_once falhou (%s); fallback para router.", exc)

    return processar_comando_router(cmd_text, intent)
