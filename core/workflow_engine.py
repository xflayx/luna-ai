from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from core.event_bus import Event, EventFilter, EventBus, event_bus
from core.event_queue import EventQueue
from core.skill_registry import SkillRegistry


logger = logging.getLogger("WorkflowEngine")


@dataclass(frozen=True)
class FlowEventFilter:
    event: str
    condition: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "FlowEventFilter":
        if not isinstance(data, Mapping):
            return cls(event="")
        return cls(
            event=str(data.get("event", "")).strip(),
            condition=str(data.get("condition", "")).strip(),
        )


@dataclass(frozen=True)
class FlowNode:
    id: str
    type: str
    config: dict[str, Any] = field(default_factory=dict)
    event_filters: tuple[FlowEventFilter, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "FlowNode":
        if not isinstance(data, Mapping):
            return cls(id="", type="")
        filters = data.get("event_filters")
        if filters is None:
            filters = data.get("eventFilters")
        raw_filters = filters if isinstance(filters, list) else []
        return cls(
            id=str(data.get("id", "")).strip(),
            type=str(data.get("type", "")).strip(),
            config=dict(data.get("config", {}) or {}),
            event_filters=tuple(FlowEventFilter.from_dict(item) for item in raw_filters),
        )


@dataclass(frozen=True)
class FlowConnection:
    id: str
    from_node: str
    from_port: str
    to_node: str
    to_port: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "FlowConnection":
        if not isinstance(data, Mapping):
            return cls(id="", from_node="", from_port="", to_node="", to_port="")
        from_data = data.get("from", {}) if isinstance(data.get("from"), Mapping) else {}
        to_data = data.get("to", {}) if isinstance(data.get("to"), Mapping) else {}
        return cls(
            id=str(data.get("id", "")).strip(),
            from_node=str(from_data.get("nodeId", "")).strip(),
            from_port=str(from_data.get("port", "")).strip(),
            to_node=str(to_data.get("nodeId", "")).strip(),
            to_port=str(to_data.get("port", "")).strip(),
        )


@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    name: str
    nodes: tuple[FlowNode, ...]
    connections: tuple[FlowConnection, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "WorkflowDefinition":
        if not isinstance(data, Mapping):
            return cls(id="", name="", nodes=(), connections=())
        nodes_data = data.get("nodes") if isinstance(data.get("nodes"), list) else []
        conn_data = data.get("connections") if isinstance(data.get("connections"), list) else []
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            nodes=tuple(FlowNode.from_dict(item) for item in nodes_data),
            connections=tuple(FlowConnection.from_dict(item) for item in conn_data),
        )


class WorkflowCycleError(Exception):
    def __init__(self, cycle_nodes: list[str]):
        self.cycle_nodes = cycle_nodes
        super().__init__(f"Cycle detected in workflow: {', '.join(cycle_nodes)}")


class WorkflowValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        msg = "; ".join(self.errors) if self.errors else "workflow validation failed"
        super().__init__(f"Workflow validation failed: {msg}")


class WorkflowEngine:
    def __init__(
        self,
        *,
        registry: SkillRegistry | None = None,
        bus: EventBus | None = None,
        queue_size: int = 100,
    ):
        self._registry = registry or SkillRegistry()
        self._bus = bus or event_bus
        self._queue: EventQueue[Event] = EventQueue(max_size=queue_size)
        self._workflow: WorkflowDefinition | None = None
        self._execution_order: list[FlowNode] = []
        self._subscriptions: list[str] = []
        self._worker: threading.Thread | None = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._last_error = ""
        self._started_at = 0.0
        self._events_processed = 0
        self._events_failed = 0
        self._last_event_ts = 0.0

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            running = self._running.is_set()
            started_at = self._started_at
            last_error = self._last_error
            workflow_id = self._workflow.id if self._workflow else ""
            workflow_name = self._workflow.name if self._workflow else ""
            events_processed = self._events_processed
            events_failed = self._events_failed
            last_event_ts = self._last_event_ts
            events_total = events_processed + events_failed
        return {
            "status": "running" if running else "idle",
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "started_at": started_at,
            "last_error": last_error,
            "queue_size": self._queue.qsize,
            "queue_dropped": self._queue.dropped_count,
            "queue_processing": self._queue.is_processing,
            "events_processed": events_processed,
            "events_failed": events_failed,
            "events_total": events_total,
            "last_event_ts": last_event_ts,
        }

    def validate_workflow(
        self,
        workflow_data: Mapping[str, Any],
        *,
        start_node_id: str = "",
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "ok": False,
            "errors": [],
            "workflow_id": "",
            "workflow_name": "",
            "nodes": 0,
            "connections": 0,
            "start_node_id": (start_node_id or "").strip(),
            "execution_order": [],
        }

        try:
            workflow = self._prepare_workflow(workflow_data, start_node_id=start_node_id)
        except Exception as exc:
            report["errors"] = [str(exc)]
            return report

        report["workflow_id"] = workflow.id
        report["workflow_name"] = workflow.name
        report["nodes"] = len(workflow.nodes)
        report["connections"] = len(workflow.connections)

        errors = self._collect_workflow_contract_errors(workflow)
        if errors:
            report["errors"] = errors
            return report

        try:
            order = self._get_execution_order(workflow)
        except WorkflowCycleError as exc:
            report["errors"] = [str(exc)]
            return report

        report["ok"] = True
        report["execution_order"] = [node.id for node in order]
        return report

    def _prepare_workflow(
        self,
        workflow_data: Mapping[str, Any],
        *,
        start_node_id: str = "",
    ) -> WorkflowDefinition:
        workflow = WorkflowDefinition.from_dict(workflow_data)
        start_node_id = (start_node_id or "").strip()
        if start_node_id:
            node_ids = {node.id for node in workflow.nodes}
            if start_node_id not in node_ids:
                raise ValueError(f"start_node_id '{start_node_id}' nao existe no workflow.")
            workflow = self._filter_subgraph(workflow, start_node_id)
        return workflow

    def execute_linear(
        self,
        workflow_data: Mapping[str, Any],
        *,
        start_node_id: str = "",
        initial_inputs: Mapping[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        workflow = self._prepare_workflow(workflow_data, start_node_id=start_node_id)
        self._validate_workflow_contract(workflow)
        order = self._get_execution_order(workflow)
        outputs: dict[str, dict[str, Any]] = {}
        inbound_counts = self._inbound_counts(workflow)
        initial_inputs = dict(initial_inputs or {})

        for node in order:
            inputs = self._resolve_inputs(node.id, workflow, outputs)
            if not inputs and inbound_counts.get(node.id, 0) == 0:
                inputs = dict(initial_inputs)
            if not inputs and inbound_counts.get(node.id, 0) > 0:
                continue

            node_output = self._execute_node(node, inputs, event=None)
            outputs[node.id] = node_output
        return outputs

    def start_event_driven(
        self,
        workflow_data: Mapping[str, Any],
        *,
        listen_patterns: tuple[str, ...] = ("chat.*",),
        start_node_id: str = "",
    ) -> None:
        self.stop_event_driven()

        workflow = self._prepare_workflow(workflow_data, start_node_id=start_node_id)
        self._validate_workflow_contract(workflow)
        order = self._get_execution_order(workflow)

        with self._lock:
            self._workflow = workflow
            self._execution_order = order
            self._last_error = ""
            self._started_at = time.time()
            self._events_processed = 0
            self._events_failed = 0
            self._last_event_ts = 0.0

        self._running.set()
        self._queue.clear()
        self._queue.reset_metrics(reset_dropped=True)

        self._subscriptions = []
        for pattern in listen_patterns:
            sub_id = self._bus.subscribe(pattern, self._on_event, subscriber_id="workflow_engine")
            self._subscriptions.append(sub_id)

        self._worker = threading.Thread(target=self._event_loop, daemon=True)
        self._worker.start()

    def stop_event_driven(self) -> None:
        self._running.clear()
        for sub_id in self._subscriptions:
            self._bus.unsubscribe(sub_id)
        self._subscriptions = []
        self._queue.clear()
        self._queue.is_processing = False
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1.5)
        self._worker = None

    def _on_event(self, event: Event) -> None:
        if not self._running.is_set():
            return
        added = self._queue.put(event)
        if not added:
            logger.warning("Fila de eventos cheia, descartando evento: %s", event.type)

    def _event_loop(self) -> None:
        while self._running.is_set():
            event = self._queue.get(timeout_sec=0.5)
            if event is None:
                continue
            self._queue.is_processing = True
            event_ok = False
            try:
                self._process_event(event)
                event_ok = True
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                logger.error("Erro no processamento de evento: %s", exc)
            finally:
                with self._lock:
                    if event_ok:
                        self._events_processed += 1
                    else:
                        self._events_failed += 1
                    self._last_event_ts = time.time()
                self._queue.is_processing = False
                self._queue.task_done()

    def _process_event(self, event: Event) -> None:
        workflow = self._workflow
        if not workflow:
            return
        outputs: dict[str, dict[str, Any]] = {}
        inbound_counts = self._inbound_counts(workflow)

        for node in self._execution_order:
            if not self._node_accepts_event(node, event):
                continue

            inputs = self._resolve_inputs(node.id, workflow, outputs)
            if not inputs and inbound_counts.get(node.id, 0) == 0:
                inputs = self._event_to_inputs(event)
            if not inputs and inbound_counts.get(node.id, 0) > 0:
                continue

            node_output = self._execute_node(node, inputs, event=event)
            outputs[node.id] = node_output

    def _node_accepts_event(self, node: FlowNode, event: Event) -> bool:
        if not node.event_filters:
            return True
        filters = [EventFilter(event=f.event, condition=f.condition) for f in node.event_filters if f.event]
        if not filters:
            return True
        return any(f.matches(event) for f in filters)

    def _validate_workflow_contract(self, workflow: WorkflowDefinition) -> None:
        errors = self._collect_workflow_contract_errors(workflow)
        if errors:
            raise WorkflowValidationError(errors)

    def _collect_workflow_contract_errors(self, workflow: WorkflowDefinition) -> list[str]:
        errors: list[str] = []
        if not workflow.nodes:
            errors.append("Workflow sem nodes.")
        node_map: dict[str, FlowNode] = {}
        contracts: dict[str, tuple[set[str], set[str]]] = {}

        for idx, node in enumerate(workflow.nodes, start=1):
            node_id = (node.id or "").strip()
            node_type = (node.type or "").strip()
            if not node_id:
                errors.append(f"Node #{idx} sem id.")
                continue
            if node_id in node_map:
                errors.append(f"Node duplicado com id '{node_id}'.")
                continue
            if not node_type:
                errors.append(f"Node '{node_id}' sem type.")
                continue

            node_map[node_id] = node
            inputs, outputs, err = self._resolve_node_ports_contract(node)
            if err:
                errors.append(err)
                continue
            contracts[node_id] = (inputs, outputs)

        for idx, conn in enumerate(workflow.connections, start=1):
            conn_id = (conn.id or "").strip() or f"conn#{idx}"
            from_node = (conn.from_node or "").strip()
            to_node = (conn.to_node or "").strip()
            from_port = (conn.from_port or "").strip()
            to_port = (conn.to_port or "").strip()

            if not from_node:
                errors.append(f"Conexao '{conn_id}' sem from.nodeId.")
                continue
            if not to_node:
                errors.append(f"Conexao '{conn_id}' sem to.nodeId.")
                continue
            if from_node not in node_map:
                errors.append(
                    f"Conexao '{conn_id}' referencia from.nodeId inexistente: '{from_node}'."
                )
                continue
            if to_node not in node_map:
                errors.append(
                    f"Conexao '{conn_id}' referencia to.nodeId inexistente: '{to_node}'."
                )
                continue

            source_contract = contracts.get(from_node)
            if source_contract:
                _, source_outputs = source_contract
                if from_port and source_outputs and from_port not in source_outputs:
                    errors.append(
                        f"Conexao '{conn_id}' usa porta de saida invalida '{from_port}' "
                        f"em node '{from_node}'. Portas validas: {self._format_ports(source_outputs)}."
                    )

            target_contract = contracts.get(to_node)
            if target_contract:
                target_inputs, _ = target_contract
                target_port = to_port or from_port or "input"
                if target_inputs and target_port not in target_inputs:
                    errors.append(
                        f"Conexao '{conn_id}' usa porta de entrada invalida '{target_port}' "
                        f"em node '{to_node}'. Portas validas: {self._format_ports(target_inputs)}."
                    )
        return errors

    def _resolve_node_ports_contract(
        self,
        node: FlowNode,
    ) -> tuple[set[str], set[str], str]:
        node_type = (node.type or "").strip()
        builtin = self._builtin_node_ports(node_type)
        if builtin is not None:
            return builtin[0], builtin[1], ""

        skill_name = self._resolve_skill_name(node_type)
        if not skill_name:
            return set(), set(), (
                f"Node '{node.id}' com tipo nao suportado '{node_type}'. "
                "Use tipo builtin ou skill:<id>."
            )

        manifest = self._registry.get_manifest(skill_name)
        if not manifest:
            entry = self._registry.get_entry(skill_name)
            detail = ""
            if entry and entry.last_error:
                detail = f" ({entry.last_error})"
            return set(), set(), (
                f"Node '{node.id}' referencia skill '{skill_name}' sem manifesto valido{detail}."
            )

        input_ports = {port.id for port in manifest.inputs if port.id}
        output_ports = {port.id for port in manifest.outputs if port.id}

        if not input_ports:
            input_ports = {"text", "input", "command", "prompt", "message"}
        if "text" in input_ports:
            input_ports.update({"input", "command", "prompt", "message"})

        if not output_ports:
            output_ports = {"response", "text"}
        if "response" in output_ports:
            output_ports.add("text")
        if "text" in output_ports:
            output_ports.add("response")

        return input_ports, output_ports, ""

    def _builtin_node_ports(self, node_type: str) -> tuple[set[str], set[str]] | None:
        tipo = (node_type or "").strip()
        if tipo == "start":
            return set(), {"trigger"}
        if tipo == "end":
            return {"text", "response", "input", "command", "prompt", "message"}, set()
        if tipo == "manual-input":
            return {"text", "input", "command", "prompt", "message"}, {"text"}
        if tipo == "console-output":
            return {"text", "response"}, {"text"}
        if tipo == "obs-scene-switch":
            return {"scene", "scene_name", "text", "input", "command", "message"}, {
                "response",
                "text",
                "scene",
                "ok",
            }
        if tipo == "obs-source-toggle":
            return {
                "scene",
                "scene_name",
                "source",
                "source_name",
                "enabled",
                "text",
                "input",
                "command",
                "message",
            }, {
                "response",
                "text",
                "scene",
                "source",
                "enabled",
                "ok",
            }
        return None

    def _format_ports(self, ports: set[str]) -> str:
        if not ports:
            return "(nenhuma)"
        return ", ".join(sorted(ports))

    def _pick_scene_name(
        self,
        inputs: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> str:
        for key in ("scene", "scene_name", "input", "text", "command", "message"):
            value = inputs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("sceneName", "scene"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _pick_source_name(
        self,
        inputs: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> str:
        for key in ("source", "source_name"):
            value = inputs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("sourceName", "source"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _pick_enabled_flag(
        self,
        inputs: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> bool:
        if "enabled" in inputs:
            return self._to_bool(inputs.get("enabled"), default=True)
        return self._to_bool(config.get("enabled"), default=True)

    def _to_bool(self, value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            val = value.strip().lower()
            if val in {"1", "true", "yes", "on", "sim"}:
                return True
            if val in {"0", "false", "no", "off", "nao", "não"}:
                return False
        return default

    def _execute_obs_scene_switch(
        self,
        config: Mapping[str, Any],
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        scene = self._pick_scene_name(inputs, config)
        if not scene:
            msg = "Cena OBS nao informada."
            return {"response": msg, "text": msg, "scene": "", "ok": False}
        try:
            from core import obs_client

            ok = bool(obs_client.switch_scene(scene))
        except Exception:
            ok = False
        msg = (
            f"Cena OBS alterada para '{scene}'."
            if ok
            else f"Falha ao trocar cena OBS para '{scene}'."
        )
        return {"response": msg, "text": msg, "scene": scene, "ok": ok}

    def _execute_obs_source_toggle(
        self,
        config: Mapping[str, Any],
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        scene = self._pick_scene_name(inputs, config)
        source = self._pick_source_name(inputs, config)
        enabled = self._pick_enabled_flag(inputs, config)
        if not source:
            msg = "Fonte OBS nao informada."
            return {
                "response": msg,
                "text": msg,
                "scene": scene,
                "source": "",
                "enabled": enabled,
                "ok": False,
            }
        try:
            from core import obs_client

            ok = bool(obs_client.set_source_enabled(source, enabled, scene_name=scene))
        except Exception:
            ok = False
        action = "ativada" if enabled else "desativada"
        msg = (
            f"Fonte OBS '{source}' {action}."
            if ok
            else f"Falha ao atualizar fonte OBS '{source}' ({action})."
        )
        return {
            "response": msg,
            "text": msg,
            "scene": scene,
            "source": source,
            "enabled": enabled,
            "ok": ok,
        }

    def _execute_node(
        self,
        node: FlowNode,
        inputs: dict[str, Any],
        *,
        event: Event | None,
    ) -> dict[str, Any]:
        node_type = node.type
        config = node.config

        if node_type == "start":
            return {"trigger": True}
        if node_type == "end":
            return {}
        if node_type == "manual-input":
            text = str(config.get("inputText", "") or inputs.get("text", "")).strip()
            return {"text": text}
        if node_type == "console-output":
            text = str(inputs.get("text", "") or inputs.get("response", "")).strip()
            logger.info("Workflow console output: %s", text)
            return {"text": text}
        if node_type == "obs-scene-switch":
            return self._execute_obs_scene_switch(config, inputs)
        if node_type == "obs-source-toggle":
            return self._execute_obs_source_toggle(config, inputs)

        skill_name = self._resolve_skill_name(node_type)
        if not skill_name:
            logger.warning("No executavel para tipo de node: %s", node_type)
            return {}

        entry = self._registry.load(skill_name)
        if not entry or not entry.module:
            logger.warning("Skill nao carregada para node %s (%s)", node.id, node_type)
            return {}

        comando = self._pick_command(inputs, config, event)
        if not comando:
            return {}

        resposta = entry.module.executar(comando)
        return {
            "response": resposta,
            "text": resposta,
        }

    def _resolve_skill_name(self, node_type: str) -> str:
        tipo = (node_type or "").strip()
        if not tipo:
            return ""
        if tipo.startswith("skill:"):
            return tipo.split(":", 1)[1].strip()
        if tipo.startswith("skills."):
            return tipo.rsplit(".", 1)[-1].strip()

        known = set(self._registry.list_skill_names())
        if tipo in known:
            return tipo
        return ""

    def _pick_command(
        self,
        inputs: Mapping[str, Any],
        config: Mapping[str, Any],
        event: Event | None,
    ) -> str:
        for key in ("command", "prompt", "text", "message", "input"):
            value = inputs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for key in ("command", "inputText", "text", "prompt", "message"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        if event:
            payload = event.payload if isinstance(event.payload, Mapping) else {}
            for key in ("text", "message", "command"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    def _event_to_inputs(self, event: Event) -> dict[str, Any]:
        payload = event.payload if isinstance(event.payload, dict) else {}
        data = dict(payload)
        data.setdefault("event_type", event.type)
        data.setdefault("event_source", event.source)
        data.setdefault("event", payload)
        return data

    def _resolve_inputs(
        self,
        node_id: str,
        workflow: WorkflowDefinition,
        outputs: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        for conn in workflow.connections:
            if conn.to_node != node_id:
                continue
            upstream = outputs.get(conn.from_node)
            if not upstream:
                continue

            value = None
            if conn.from_port and conn.from_port in upstream:
                value = upstream.get(conn.from_port)
            elif "text" in upstream:
                value = upstream.get("text")
            else:
                value = upstream

            target_port = conn.to_port or conn.from_port or "input"
            inputs[target_port] = value
        return inputs

    def _inbound_counts(self, workflow: WorkflowDefinition) -> dict[str, int]:
        counts = {node.id: 0 for node in workflow.nodes}
        for conn in workflow.connections:
            if conn.to_node in counts:
                counts[conn.to_node] += 1
        return counts

    def _build_adjacency(self, workflow: WorkflowDefinition) -> dict[str, list[str]]:
        adjacency = {node.id: [] for node in workflow.nodes}
        for conn in workflow.connections:
            if conn.from_node in adjacency and conn.to_node in adjacency:
                if conn.to_node not in adjacency[conn.from_node]:
                    adjacency[conn.from_node].append(conn.to_node)
        return adjacency

    def _filter_subgraph(
        self,
        workflow: WorkflowDefinition,
        start_node_id: str,
    ) -> WorkflowDefinition:
        adjacency = self._build_adjacency(workflow)
        reachable = {start_node_id}
        queue = [start_node_id]
        while queue:
            node_id = queue.pop(0)
            for nxt in adjacency.get(node_id, []):
                if nxt not in reachable:
                    reachable.add(nxt)
                    queue.append(nxt)

        nodes = tuple(node for node in workflow.nodes if node.id in reachable)
        connections = tuple(
            conn
            for conn in workflow.connections
            if conn.from_node in reachable and conn.to_node in reachable
        )
        return WorkflowDefinition(
            id=workflow.id,
            name=workflow.name,
            nodes=nodes,
            connections=connections,
        )

    def _get_execution_order(self, workflow: WorkflowDefinition) -> list[FlowNode]:
        nodes = list(workflow.nodes)
        node_map = {node.id: node for node in nodes}
        adjacency = self._build_adjacency(workflow)
        in_degree = {node.id: 0 for node in nodes}

        for conn in workflow.connections:
            if conn.from_node in in_degree and conn.to_node in in_degree:
                in_degree[conn.to_node] += 1

        queue = [node_id for node_id, deg in in_degree.items() if deg == 0]
        ordered_ids: list[str] = []
        while queue:
            node_id = queue.pop(0)
            ordered_ids.append(node_id)
            for nxt in adjacency.get(node_id, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        if len(ordered_ids) < len(nodes):
            cycle_nodes = [node_id for node_id, deg in in_degree.items() if deg > 0]
            raise WorkflowCycleError(cycle_nodes)
        return [node_map[node_id] for node_id in ordered_ids if node_id in node_map]
