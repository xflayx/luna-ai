import os
import hmac
import threading
import time
import logging
from datetime import datetime
from typing import Any, Dict, Optional


_panel_thread: Optional[threading.Thread] = None
_socketio = None
_last_state: Dict[str, Any] = {}
_start_ts = time.time()


def _panel_enabled() -> bool:
    return os.getenv("LUNA_PANEL_ENABLED", "0") == "1"


def _panel_host() -> str:
    return os.getenv("LUNA_PANEL_HOST", "127.0.0.1")


def _panel_port() -> int:
    try:
        return int(os.getenv("LUNA_PANEL_PORT", "5055"))
    except ValueError:
        return 5055


def _panel_token() -> str:
    return os.getenv("LUNA_PANEL_TOKEN", "").strip()


def _panel_require_token() -> bool:
    return os.getenv("LUNA_PANEL_REQUIRE_TOKEN", "1") == "1"


def _panel_cors_origins() -> list[str]:
    raw = os.getenv("LUNA_PANEL_CORS_ORIGINS", "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        return origins

    port = _panel_port()
    host = _panel_host().strip() or "127.0.0.1"
    defaults = [
        f"http://{host}:{port}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]
    # Remove duplicados mantendo ordem
    return list(dict.fromkeys(defaults))


def _panel_tick_sec() -> float:
    try:
        return max(0.5, float(os.getenv("LUNA_PANEL_TICK_SEC", "1.5")))
    except ValueError:
        return 1.5


def _panel_max_payload_bytes() -> int:
    try:
        return max(1024, int(os.getenv("LUNA_PANEL_MAX_PAYLOAD_BYTES", "16384")))
    except ValueError:
        return 16384


def _token_ok(request) -> bool:
    required = _panel_token()
    if not required:
        return not _panel_require_token()
    token = (request.headers.get("X-Panel-Token", "") or "").strip()
    if not token:
        token = (request.args.get("token", "") or "").strip()
    if not token:
        try:
            body = request.get_json(silent=True) or {}
            token = (body.get("token") or "").strip()
        except Exception:
            token = ""
    return hmac.compare_digest(token, required)


def _empty_manifest_coverage() -> Dict[str, Any]:
    return {
        "total_skills": 0,
        "with_external_manifest": 0,
        "without_external_manifest": 0,
        "missing_external_manifests": [],
        "skills": [],
    }


def _empty_skill_diagnostics() -> Dict[str, Any]:
    return {
        "total": 0,
        "loaded": 0,
        "failed": 0,
        "entries": [],
    }


def _get_router_instance(create: bool = False):
    try:
        from core import router as router_mod
    except Exception:
        return None

    router = getattr(router_mod, "_router", None)
    if router is None and create:
        try:
            router = router_mod.RouterLuna()
            setattr(router_mod, "_router", router)
        except Exception:
            return None
    return router


def _get_skill_registry_snapshot(
    *,
    ensure_loaded: bool = False,
    create_router: bool = False,
    include_entries: bool = False,
    include_skills: bool = False,
) -> Dict[str, Any]:
    coverage = _empty_manifest_coverage()
    diagnostics = _empty_skill_diagnostics()
    source = "none"
    error = ""

    try:
        router = _get_router_instance(create=create_router)
        registry = getattr(router, "_registry", None) if router else None

        if registry is None:
            from core.skill_registry import SkillRegistry

            registry = SkillRegistry()
            source = "standalone_registry"
        else:
            source = "router_registry"

        coverage = registry.get_manifest_coverage()
        diagnostics = registry.get_diagnostics(ensure_loaded=ensure_loaded)
    except Exception as exc:
        error = str(exc)

    if not include_skills:
        coverage = dict(coverage or {})
        coverage["skills"] = []

    if not include_entries:
        diagnostics = dict(diagnostics or {})
        diagnostics["entries"] = []

    return {
        "coverage": coverage,
        "diagnostics": diagnostics,
        "source": source,
        "error": error,
    }


def _workflow_invalid_response(report: Dict[str, Any]) -> Dict[str, Any]:
    errors = list(report.get("errors") or [])
    first_error = errors[0] if errors else "Erro desconhecido."
    return {
        "ok": False,
        "msg": f"Workflow invalido ({len(errors)} erro(s)). {first_error}",
        "workflow_validation": report,
    }


def _workflow_exception_report(
    exc: Exception,
    *,
    workflow_id: str = "",
    start_node_id: str = "",
) -> dict[str, Any]:
    return {
        "ok": False,
        "errors": [str(exc)],
        "workflow_id": (workflow_id or "").strip(),
        "workflow_name": "",
        "nodes": 0,
        "connections": 0,
        "start_node_id": (start_node_id or "").strip(),
        "execution_order": [],
    }


def _build_state(
    last_command: str | None = None,
    last_intent: str | None = None,
    last_response: str | None = None,
    status: str | None = None,
) -> Dict[str, Any]:
    from config.state import STATE
    from core import memory

    try:
        from core import voice
        tts_engine = getattr(voice, "_TTS_ENGINE", "pyttsx3")
        tts_async = bool(getattr(voice, "_TTS_ASSINCRONO", False))
        stt_engine = getattr(voice, "_STT_ENGINE", "groq")
        tts_queue_max = int(getattr(voice, "_FALA_QUEUE_MAX", 0))
    except Exception:
        tts_engine = "unknown"
        tts_async = False
        stt_engine = "unknown"
        tts_queue_max = 0

    ultima_resposta = STATE.obter_ultima_resposta() or ""
    try:
        from skills.vision import get_visao_auto_status
        visao_auto = get_visao_auto_status()
    except Exception:
        visao_auto = {
            "enabled": False,
            "interval_sec": 0,
            "cooldown_sec": 0,
            "cooldown_restante": 0,
            "ativo": False,
        }

    try:
        from core.workflow_runtime import get_runtime_status
        workflow_status = get_runtime_status()
    except Exception:
        workflow_status = {
            "status": "idle",
            "workflow_id": "",
            "workflow_name": "",
            "queue_size": 0,
            "queue_dropped": 0,
            "queue_processing": False,
            "events_processed": 0,
            "events_failed": 0,
            "events_total": 0,
            "last_event_ts": 0.0,
            "loaded_workflow": {"loaded": False},
        }

    skill_snapshot = _get_skill_registry_snapshot(
        ensure_loaded=False,
        create_router=False,
        include_entries=False,
        include_skills=False,
    )
    coverage = skill_snapshot.get("coverage", {}) or {}
    diagnostics = skill_snapshot.get("diagnostics", {}) or {}
    missing_external = coverage.get("missing_external_manifests") or []

    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modo": STATE.get_modo_ativacao(),
        "temperamento": STATE.get_temperamento(),
        "ultima_visao": STATE.get_ultima_visao() or "",
        "ultima_resposta": last_response or ultima_resposta,
        "ultima_resposta_curta": (last_response or ultima_resposta)[:200],
        "ultimo_comando": last_command or "",
        "ultima_intencao": last_intent or "",
        "status": status or "",
        "historico_len": len(STATE.historico or []),
        "memoria_curta_len": memory.contar_memoria_curta(),
        "tts_engine": tts_engine,
        "tts_async": tts_async,
        "tts_queue_max": tts_queue_max,
        "stt_engine": stt_engine,
        "visao_auto": visao_auto,
        "workflow": workflow_status,
        "skill_registry": {
            "source": skill_snapshot.get("source", "none"),
            "error": skill_snapshot.get("error", ""),
            "total_skills": int(coverage.get("total_skills", 0) or 0),
            "with_external_manifest": int(coverage.get("with_external_manifest", 0) or 0),
            "without_external_manifest": int(coverage.get("without_external_manifest", 0) or 0),
            "missing_external_manifest_count": len(missing_external),
            "loaded": int(diagnostics.get("loaded", 0) or 0),
            "failed": int(diagnostics.get("failed", 0) or 0),
        },
    }


def atualizar_estado(
    last_command: str | None = None,
    last_intent: str | None = None,
    last_response: str | None = None,
    status: str | None = None,
) -> None:
    global _last_state
    _last_state = _build_state(
        last_command=last_command,
        last_intent=last_intent,
        last_response=last_response,
        status=status,
    )
    if _socketio:
        try:
            _socketio.emit("state_update", _last_state)
        except Exception:
            pass


def _handle_control(data: Dict[str, Any]) -> Dict[str, Any]:
    from config.state import STATE
    from core import memory
    from core.command_orchestrator import processar_comando_orquestrado
    from core.voice import falar

    action = (data.get("action") or "").strip()
    payload = data.get("payload") or {}

    if action == "set_mode":
        modo = payload.get("modo", "")
        if STATE.set_modo_ativacao(modo):
            return {"ok": True, "msg": f"Modo {modo} ativado."}
        return {"ok": False, "msg": "Modo invalido."}

    if action == "limpar_memoria_curta":
        memory.limpar_memoria_curta()
        return {"ok": True, "msg": "Memoria curta limpa."}

    if action == "recarregar_skills":
        try:
            router = _get_router_instance(create=True)
            if router is None:
                return {"ok": False, "msg": "Router indisponivel para recarregar skills."}
            total = router.recarregar_todas()
            return {"ok": True, "msg": f"Recarreguei {total} skills."}
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao recarregar skills: {e}"}

    if action == "falar":
        texto = (payload.get("texto") or "").strip()
        if texto:
            falar(texto)
            return {"ok": True, "msg": "Falando texto."}
        return {"ok": False, "msg": "Texto vazio."}

    if action == "workflow_list":
        try:
            from core.workflow_runtime import list_workflows
            workflows = list_workflows()
            return {
                "ok": True,
                "msg": f"{len(workflows)} workflow(s) disponivel(is).",
                "workflows": workflows,
            }
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao listar workflows: {e}"}

    if action == "workflow_load":
        workflow_id = (payload.get("workflow_id") or "").strip()
        path = (payload.get("path") or "").strip()
        wf_data = payload.get("data")
        if wf_data is not None and not isinstance(wf_data, dict):
            return {"ok": False, "msg": "Campo 'data' precisa ser objeto JSON."}
        try:
            from core.workflow_runtime import load_workflow, get_loaded_workflow_meta
            load_workflow(
                workflow_id=workflow_id,
                path=path,
                data=wf_data,
            )
            return {
                "ok": True,
                "msg": "Workflow carregado.",
                "workflow": get_loaded_workflow_meta(),
            }
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao carregar workflow: {e}"}

    if action == "workflow_validate":
        workflow_id = (payload.get("workflow_id") or "").strip()
        path = (payload.get("path") or "").strip()
        wf_data = payload.get("data")
        if wf_data is not None and not isinstance(wf_data, dict):
            return {"ok": False, "msg": "Campo 'data' precisa ser objeto JSON."}
        start_node_id = (payload.get("start_node_id") or "").strip()
        try:
            from core.workflow_runtime import validate_workflow
            report = validate_workflow(
                workflow_id=workflow_id,
                path=path,
                data=wf_data,
                start_node_id=start_node_id,
            )
            ok = bool(report.get("ok"))
            if ok:
                order = report.get("execution_order") or []
                return {
                    "ok": True,
                    "msg": f"Workflow valido. Ordem: {', '.join(order) if order else '(vazia)'}",
                    "workflow_validation": report,
                }
            return _workflow_invalid_response(report)
        except Exception as e:
            return _workflow_invalid_response(
                _workflow_exception_report(
                    e,
                    workflow_id=workflow_id,
                    start_node_id=start_node_id,
                )
            )

    if action == "workflow_start":
        workflow_id = (payload.get("workflow_id") or "").strip()
        path = (payload.get("path") or "").strip()
        wf_data = payload.get("data")
        if wf_data is not None and not isinstance(wf_data, dict):
            return {"ok": False, "msg": "Campo 'data' precisa ser objeto JSON."}
        start_node_id = (payload.get("start_node_id") or "").strip()

        raw_patterns = payload.get("listen_patterns")
        listen_patterns: tuple[str, ...]
        if isinstance(raw_patterns, list):
            listen_patterns = tuple(str(x).strip() for x in raw_patterns if str(x).strip())
        elif isinstance(raw_patterns, str):
            listen_patterns = tuple(
                x.strip() for x in raw_patterns.split(",") if x.strip()
            )
        else:
            listen_patterns = ("chat.*",)

        report = None
        try:
            from core.workflow_runtime import validate_workflow
            report = validate_workflow(
                workflow_id=workflow_id,
                path=path,
                data=wf_data,
                start_node_id=start_node_id,
            )
        except Exception as e:
            return _workflow_invalid_response(
                _workflow_exception_report(
                    e,
                    workflow_id=workflow_id,
                    start_node_id=start_node_id,
                )
            )

        if not bool(report.get("ok")):
            return _workflow_invalid_response(report)

        try:
            from core.workflow_runtime import start_workflow
            status = start_workflow(
                workflow_id=workflow_id,
                path=path,
                data=wf_data,
                listen_patterns=listen_patterns or ("chat.*",),
                start_node_id=start_node_id,
            )
            return {
                "ok": True,
                "msg": "Workflow iniciado.",
                "workflow_status": status,
            }
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao iniciar workflow: {e}"}

    if action == "workflow_run_once":
        workflow_id = (payload.get("workflow_id") or "").strip()
        path = (payload.get("path") or "").strip()
        wf_data = payload.get("data")
        if wf_data is not None and not isinstance(wf_data, dict):
            return {"ok": False, "msg": "Campo 'data' precisa ser objeto JSON."}
        start_node_id = (payload.get("start_node_id") or "").strip()
        initial_inputs = payload.get("initial_inputs")
        if initial_inputs is not None and not isinstance(initial_inputs, dict):
            return {"ok": False, "msg": "Campo 'initial_inputs' precisa ser objeto JSON."}
        report = None
        try:
            from core.workflow_runtime import validate_workflow
            report = validate_workflow(
                workflow_id=workflow_id,
                path=path,
                data=wf_data,
                start_node_id=start_node_id,
            )
        except Exception as e:
            return _workflow_invalid_response(
                _workflow_exception_report(
                    e,
                    workflow_id=workflow_id,
                    start_node_id=start_node_id,
                )
            )

        if not bool(report.get("ok")):
            return _workflow_invalid_response(report)

        try:
            from core.workflow_runtime import run_workflow_once
            outputs = run_workflow_once(
                workflow_id=workflow_id,
                path=path,
                data=wf_data,
                start_node_id=start_node_id,
                initial_inputs=initial_inputs or {},
            )
            return {
                "ok": True,
                "msg": "Workflow executado (linear).",
                "outputs": outputs,
            }
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao executar workflow linear: {e}"}

    if action == "workflow_stop":
        try:
            from core.workflow_runtime import stop_workflow
            status = stop_workflow()
            return {"ok": True, "msg": "Workflow parado.", "workflow_status": status}
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao parar workflow: {e}"}

    if action == "workflow_status":
        try:
            from core.workflow_runtime import get_runtime_status
            return {
                "ok": True,
                "msg": "Status do workflow.",
                "workflow_status": get_runtime_status(),
            }
        except Exception as e:
            return {"ok": False, "msg": f"Falha ao obter status do workflow: {e}"}

    if action == "skill_registry_diagnostics":
        ensure_loaded = bool(payload.get("ensure_loaded"))
        snapshot = _get_skill_registry_snapshot(
            ensure_loaded=ensure_loaded,
            create_router=True,
            include_entries=True,
            include_skills=True,
        )
        if snapshot.get("error"):
            return {
                "ok": False,
                "msg": f"Falha ao gerar diagnostico de skills: {snapshot['error']}",
                "skill_registry": snapshot,
            }
        coverage = snapshot.get("coverage", {}) or {}
        diagnostics = snapshot.get("diagnostics", {}) or {}
        return {
            "ok": True,
            "msg": (
                f"Diagnostico: {diagnostics.get('loaded', 0)}/{diagnostics.get('total', 0)} "
                f"skills carregadas; manifests externos "
                f"{coverage.get('with_external_manifest', 0)}/{coverage.get('total_skills', 0)}."
            ),
            "skill_registry": snapshot,
        }

    if action == "comando":
        cmd = (payload.get("comando") or "").strip()
        if not cmd:
            return {"ok": False, "msg": "Comando vazio."}
        source = (payload.get("source") or "").strip().lower()
        falar_flag = bool(payload.get("falar"))
        print(f"[PAINEL] Origem={source or 'desconhecida'} falar={falar_flag}")
        print(f"[PAINEL] Comando recebido: {cmd}")
        try:
            from core.realtime_panel import atualizar_estado
            atualizar_estado(
                last_command=f"[painel] {cmd}",
                last_intent="painel",
                last_response="",
                status="Comando recebido pelo painel",
            )
        except Exception:
            pass
        resp = processar_comando_orquestrado(cmd, None, source=f"panel:{source or 'desconhecida'}") or ""
        if resp:
            print(f"[PAINEL] Resposta: {resp}")
        # Comandos vindos do pet nunca devem disparar TTS do backend aqui.
        if falar_flag and source != "pet":
            falar(resp)
        return {"ok": True, "msg": "Comando executado.", "resposta": resp}

    return {"ok": False, "msg": "Acao desconhecida."}


def iniciar_painel() -> None:
    global _panel_thread, _socketio
    if _panel_thread and _panel_thread.is_alive():
        return
    if not _panel_enabled():
        return

    try:
        from flask import Flask, request
        from flask_socketio import SocketIO, emit
        import flask.cli
    except Exception:
        return

    logger = logging.getLogger("Panel")

    flask.cli.show_server_banner = lambda *args, **kwargs: None
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins=_panel_cors_origins(), async_mode="threading")
    _socketio = socketio

    @app.get("/")
    def index():
        return _render_html(_panel_token())

    @app.get("/health")
    def health_check():
        from config.state import STATE
        from core import voice as voice_mod
        try:
            import psutil
        except Exception:
            psutil = None

        system = {}
        if psutil:
            try:
                system = {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                }
            except Exception:
                system = {}

        router = _get_router_instance(create=False)
        skills_loaded = len(getattr(router, "skills", {}) or {})
        skills_failed = len(getattr(router, "skill_erros", {}) or {})
        skill_registry_snapshot = _get_skill_registry_snapshot(
            ensure_loaded=False,
            create_router=False,
            include_entries=True,
            include_skills=True,
        )

        tts_queue_size = None
        try:
            q = getattr(voice_mod, "_fala_queue", None)
            if q is not None:
                tts_queue_size = q.qsize()
        except Exception:
            tts_queue_size = None

        # API checks (config only - no network calls)
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        murf_key = os.getenv("MURF_API_KEY", "").strip()
        api_checks = {
            "gemini": "configured" if gemini_key else "missing",
            "groq": "configured" if groq_key else "missing",
            "murf": "configured" if murf_key else "missing",
        }

        # Image/vision checks
        last_cap = STATE.get_ultima_captura()
        last_cap_exists = bool(last_cap and os.path.exists(last_cap))
        last_visao = STATE.get_ultima_visao() or ""
        try:
            from core.workflow_runtime import get_runtime_status
            workflow_status = get_runtime_status()
        except Exception:
            workflow_status = {"status": "idle"}

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(time.time() - _start_ts),
            "skills_loaded": skills_loaded,
            "skills_failed": skills_failed,
            "tts_queue_size": tts_queue_size,
            "apis": api_checks,
            "vision": {
                "last_capture_path": last_cap or "",
                "last_capture_exists": last_cap_exists,
                "last_vision_ts": STATE.ultima_visao_ts or "",
                "last_vision_len": len(last_visao),
            },
            "workflow": workflow_status,
            "skill_registry": skill_registry_snapshot,
            "system": system,
            "panel": {
                "host": _panel_host(),
                "port": _panel_port(),
                "enabled": _panel_enabled(),
            },
        }

    @app.post("/control")
    def control_api():
        max_payload = _panel_max_payload_bytes()
        if request.content_length and request.content_length > max_payload:
            return {"ok": False, "msg": "payload muito grande"}, 413
        if not _token_ok(request):
            return {"ok": False, "msg": "token invalido"}, 401
        data = request.get_json(silent=True) or {}
        resultado = _handle_control(data)
        try:
            atualizar_estado(status=resultado.get("msg", ""))
        except Exception:
            pass
        return resultado

    @app.get("/state")
    def state_api():
        if not _token_ok(request):
            return {"ok": False, "msg": "token invalido"}, 401
        return _last_state or _build_state()

    @socketio.on("connect")
    def on_connect():
        token = request.args.get("token", "")
        required = _panel_token()
        if (_panel_require_token() and not required) or (
            required and not hmac.compare_digest(token, required)
        ):
            return False
        emit("state_update", _last_state or _build_state())

    @socketio.on("ping")
    def on_ping():
        emit("state_update", _last_state or _build_state())

    def _ticker():
        while True:
            try:
                if _socketio:
                    _socketio.emit("state_update", _build_state())
            except Exception:
                pass
            time.sleep(_panel_tick_sec())

    @socketio.on("control")
    def on_control(data):
        resultado = _handle_control(data or {})
        emit("control_result", resultado)
        atualizar_estado(status=resultado.get("msg", ""))

    def _run():
        logger.info(
            f"Painel realtime: http://{_panel_host()}:{_panel_port()}",
        )
        socketio.run(
            app,
            host=_panel_host(),
            port=_panel_port(),
            allow_unsafe_werkzeug=True,
        )

    _panel_thread = threading.Thread(target=_run, daemon=True)
    _panel_thread.start()
    threading.Thread(target=_ticker, daemon=True).start()


def _render_html(token: str) -> str:
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Luna AI - Painel de Controle</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @keyframes pulse-glow {
      0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
      50% { box-shadow: 0 0 30px rgba(139, 92, 246, 0.6); }
    }
    .pulse-glow { animation: pulse-glow 2s ease-in-out infinite; }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .fade-in { animation: fadeIn 0.3s ease-out; }
    .glass {
      background: rgba(17, 24, 39, 0.8);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(139, 92, 246, 0.2);
    }
    .gradient-text {
      background: linear-gradient(135deg, #a78bfa 0%, #ec4899 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
  </style>
</head>
<body class="bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 min-h-screen text-white">
  
  <!-- Header -->
  <div class="glass border-b border-purple-500/20 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-6 py-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
          <div class="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center pulse-glow">
            <i class="fas fa-moon text-white text-xl"></i>
          </div>
          <div>
            <h1 class="text-2xl font-bold gradient-text">Luna AI</h1>
            <p class="text-sm text-gray-400">Painel de Controle em Tempo Real</p>
          </div>
        </div>
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <div id="conn-indicator" class="w-3 h-3 bg-red-500 rounded-full"></div>
            <span id="conn-text" class="text-sm text-gray-400">Desconectado</span>
          </div>
          <div class="text-sm text-gray-400" id="timestamp">--:--:--</div>
        </div>
      </div>
    </div>
  </div>

  <div class="max-w-7xl mx-auto px-6 py-8">
    
    <!-- Status Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      
      <!-- Modo Card -->
      <div class="glass rounded-xl p-6 fade-in hover:border-purple-500/40 transition-all">
        <div class="flex items-center justify-between mb-2">
          <i class="fas fa-robot text-purple-400 text-2xl"></i>
          <span class="text-xs px-2 py-1 bg-purple-500/20 rounded-full text-purple-300">Modo</span>
        </div>
        <div class="text-2xl font-bold" id="modo">-</div>
        <div class="text-xs text-gray-400 mt-1">Modo de Operacao</div>
      </div>

      <!-- STT Card -->
      <div class="glass rounded-xl p-6 fade-in hover:border-purple-500/40 transition-all">
        <div class="flex items-center justify-between mb-2">
          <i class="fas fa-microphone text-blue-400 text-2xl"></i>
          <span class="text-xs px-2 py-1 bg-blue-500/20 rounded-full text-blue-300">STT</span>
        </div>
        <div class="text-2xl font-bold" id="stt">-</div>
        <div class="text-xs text-gray-400 mt-1">Speech to Text</div>
      </div>

      <!-- TTS Card -->
      <div class="glass rounded-xl p-6 fade-in hover:border-purple-500/40 transition-all">
        <div class="flex items-center justify-between mb-2">
          <i class="fas fa-volume-up text-green-400 text-2xl"></i>
          <span class="text-xs px-2 py-1 bg-green-500/20 rounded-full text-green-300">TTS</span>
        </div>
        <div class="text-2xl font-bold" id="tts">-</div>
        <div class="text-xs text-gray-400 mt-1">Text to Speech</div>
      </div>

      <!-- Memory Card -->
      <div class="glass rounded-xl p-6 fade-in hover:border-purple-500/40 transition-all">
        <div class="flex items-center justify-between mb-2">
          <i class="fas fa-brain text-pink-400 text-2xl"></i>
          <span class="text-xs px-2 py-1 bg-pink-500/20 rounded-full text-pink-300">Memoria</span>
        </div>
        <div class="text-2xl font-bold" id="memoria">0</div>
        <div class="text-xs text-gray-400 mt-1">Itens na Memoria Curta</div>
      </div>

    </div>

    <!-- Additional Status -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
      
      <div class="glass rounded-xl p-6">
        <div class="flex items-center mb-4">
          <i class="fas fa-palette text-purple-400 mr-3"></i>
          <h3 class="text-lg font-semibold">Temperamento</h3>
        </div>
        <div class="text-xl font-bold text-purple-300" id="temperamento">-</div>
      </div>

      <div class="glass rounded-xl p-6">
        <div class="flex items-center mb-4">
          <i class="fas fa-eye text-blue-400 mr-3"></i>
          <h3 class="text-lg font-semibold">Visao Automatica</h3>
        </div>
        <div class="text-xl font-bold text-blue-300" id="visao-auto">-</div>
      </div>

    </div>

    <!-- Quick Actions -->
    <div class="glass rounded-xl p-6 mb-8">
      <h3 class="text-lg font-semibold mb-4 flex items-center">
        <i class="fas fa-bolt text-yellow-400 mr-2"></i>
        Acoes Rapidas
      </h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button onclick="setModo('assistente')" class="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-user-tie mr-2"></i>Assistente
        </button>
        <button onclick="setModo('vtuber')" class="bg-gradient-to-r from-pink-600 to-pink-700 hover:from-pink-500 hover:to-pink-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-video mr-2"></i>VTuber
        </button>
        <button onclick="limparMemoria()" class="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-trash mr-2"></i>Limpar Memoria
        </button>
        <button onclick="recarregar()" class="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-sync mr-2"></i>Recarregar Skills
        </button>
      </div>
    </div>

    <!-- Command Panel -->
    <div class="glass rounded-xl p-6 mb-8">
      <h3 class="text-lg font-semibold mb-4 flex items-center">
        <i class="fas fa-terminal text-green-400 mr-2"></i>
        Enviar Comando
      </h3>
      <div class="space-y-4">
        <input 
          id="cmd" 
          type="text" 
          placeholder="Digite um comando para a Luna..."
          class="w-full bg-gray-800/50 border border-purple-500/30 rounded-lg px-4 py-3 focus:outline-none focus:border-purple-500 transition-all"
          onkeypress="if(event.key==='Enter') enviarComando(false)"
        >
        <div class="flex space-x-3">
          <button onclick="enviarComando(false)" class="flex-1 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-500 hover:to-green-600 px-6 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
            <i class="fas fa-paper-plane mr-2"></i>Enviar (Silencioso)
          </button>
          <button onclick="enviarComando(true)" class="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 px-6 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
            <i class="fas fa-volume-up mr-2"></i>Enviar e Falar
          </button>
        </div>
        <div id="resultado" class="text-sm text-gray-400 min-h-[20px]"></div>
      </div>
    </div>

    <!-- Workflow Controls -->
    <div class="glass rounded-xl p-6 mb-8">
      <h3 class="text-lg font-semibold mb-4 flex items-center">
        <i class="fas fa-diagram-project text-cyan-400 mr-2"></i>
        Workflow Engine
      </h3>
      <div class="space-y-4">
        <input
          id="wf-id"
          type="text"
          placeholder="ID ou caminho em workflows/ (ex: templates/manual_system_monitor.json)"
          class="w-full bg-gray-800/50 border border-purple-500/30 rounded-lg px-4 py-3 focus:outline-none focus:border-purple-500 transition-all"
        >
        <div class="grid grid-cols-2 md:grid-cols-6 gap-3">
          <button onclick="workflowList()" class="bg-gradient-to-r from-cyan-700 to-cyan-800 hover:from-cyan-600 hover:to-cyan-700 px-4 py-2 rounded-lg font-medium transition-all">Listar</button>
          <button onclick="workflowLoad()" class="bg-gradient-to-r from-cyan-700 to-cyan-800 hover:from-cyan-600 hover:to-cyan-700 px-4 py-2 rounded-lg font-medium transition-all">Carregar</button>
          <button onclick="workflowValidate()" class="bg-gradient-to-r from-amber-700 to-amber-800 hover:from-amber-600 hover:to-amber-700 px-4 py-2 rounded-lg font-medium transition-all">Validar</button>
          <button onclick="workflowStart()" class="bg-gradient-to-r from-emerald-700 to-emerald-800 hover:from-emerald-600 hover:to-emerald-700 px-4 py-2 rounded-lg font-medium transition-all">Iniciar</button>
          <button onclick="workflowRunOnce()" class="bg-gradient-to-r from-indigo-700 to-indigo-800 hover:from-indigo-600 hover:to-indigo-700 px-4 py-2 rounded-lg font-medium transition-all">Rodar 1x</button>
          <button onclick="workflowStop()" class="bg-gradient-to-r from-rose-700 to-rose-800 hover:from-rose-600 hover:to-rose-700 px-4 py-2 rounded-lg font-medium transition-all">Parar</button>
        </div>
        <div id="wf-status" class="text-sm text-cyan-300">Status: -</div>
        <div id="wf-result" class="text-sm text-gray-400 min-h-[20px]"></div>
        <pre id="wf-validation" class="bg-gray-800/50 border border-amber-500/20 rounded-lg p-3 text-xs text-amber-200 whitespace-pre-wrap hidden"></pre>
      </div>
    </div>

    <!-- Activity Log -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      
      <!-- Last Command -->
      <div class="glass rounded-xl p-6">
        <h3 class="text-lg font-semibold mb-4 flex items-center">
          <i class="fas fa-history text-purple-400 mr-2"></i>
          Ultimo Comando
        </h3>
        <div class="bg-gray-800/50 rounded-lg p-4 font-mono text-sm text-gray-300" id="ultimo-cmd">-</div>
      </div>

      <!-- Status -->
      <div class="glass rounded-xl p-6">
        <h3 class="text-lg font-semibold mb-4 flex items-center">
          <i class="fas fa-info-circle text-blue-400 mr-2"></i>
          Status
        </h3>
        <div class="bg-gray-800/50 rounded-lg p-4 text-sm text-gray-300" id="status">Aguardando...</div>
      </div>

    </div>

    <!-- Last Response -->
    <div class="glass rounded-xl p-6 mt-4">
      <h3 class="text-lg font-semibold mb-4 flex items-center">
        <i class="fas fa-comment-dots text-green-400 mr-2"></i>
        Ultima Resposta
      </h3>
      <textarea 
        id="ultima-resposta" 
        readonly
        class="w-full bg-gray-800/50 border border-purple-500/30 rounded-lg px-4 py-3 min-h-[120px] focus:outline-none text-gray-300 font-mono text-sm"
      ></textarea>
    </div>

  </div>

  <!-- Footer -->
  <div class="glass border-t border-purple-500/20 mt-12">
    <div class="max-w-7xl mx-auto px-6 py-4 text-center text-sm text-gray-400">
      <p>Luna AI Dashboard - Desenvolvido com <i class="fas fa-heart text-pink-500"></i></p>
    </div>
  </div>

  <script>
    const PANEL_TOKEN = "__PANEL_TOKEN__";
    const socket = io({
      transports: ["polling", "websocket"],
      path: "/socket.io",
      query: { token: PANEL_TOKEN },
    });

    const byId = (id) => document.getElementById(id);

    // Connection handlers
    socket.on("connect", () => {
      byId("conn-indicator").className = "w-3 h-3 bg-green-500 rounded-full animate-pulse";
      byId("conn-text").textContent = "Conectado";
      showNotification("Conectado ao servidor", "success");
    });

    socket.on("disconnect", () => {
      byId("conn-indicator").className = "w-3 h-3 bg-red-500 rounded-full";
      byId("conn-text").textContent = "Desconectado";
      showNotification("Desconectado do servidor", "error");
    });

    socket.on("connect_error", (err) => {
      byId("conn-indicator").className = "w-3 h-3 bg-yellow-500 rounded-full animate-pulse";
      byId("conn-text").textContent = "Erro de conexao";
      byId("status").textContent = err && err.message ? err.message : "Falha de conexao";
    });

    // State updates
    socket.on("state_update", (s) => {
      if (!s) return;
      
      byId("modo").textContent = s.modo || "-";
      byId("temperamento").textContent = s.temperamento || "-";
      byId("stt").textContent = s.stt_engine || "-";
      byId("tts").textContent = (s.tts_engine || "-") + (s.tts_async ? " (async)" : "");
      byId("memoria").textContent = s.memoria_curta_len || 0;
      byId("timestamp").textContent = s.ts || "-";
      byId("ultimo-cmd").textContent = s.ultimo_comando || "-";
      byId("ultima-resposta").value = s.ultima_resposta || "";
      
      if (s.status) {
        byId("status").textContent = s.status;
      }
      
      if (s.visao_auto) {
        const v = s.visao_auto;
        const rest = Math.ceil(v.cooldown_restante || 0);
        const label = v.ativo ? `Ativo (${rest}s restantes)` : "Inativo";
        byId("visao-auto").textContent = label;
      } else {
        byId("visao-auto").textContent = "-";
      }
      if (s.workflow) {
        const w = s.workflow;
        const loaded = (w.loaded_workflow && w.loaded_workflow.loaded) ? (w.loaded_workflow.id || "sim") : "nao";
        const processing = w.queue_processing ? "on" : "off";
        byId("wf-status").textContent = `Status: ${w.status || "-"} | loaded=${loaded} | queue=${w.queue_size || 0} | dropped=${w.queue_dropped || 0} | processing=${processing} | proc=${w.events_processed || 0} | fail=${w.events_failed || 0}`;
      } else {
        byId("wf-status").textContent = "Status: -";
      }
    });

    socket.on("control_result", (r) => {
      if (!r) return;
      
      const msg = r.msg || "";
      byId("resultado").textContent = msg;
      
      if (r.resposta) {
        byId("ultima-resposta").value = r.resposta;
      }

      const validationBox = byId("wf-validation");
      if (validationBox && !r.workflow_validation) {
        validationBox.classList.add("hidden");
      }

      if (r.workflow_status) {
        const ws = r.workflow_status;
        const processing = ws.queue_processing ? "on" : "off";
        byId("wf-result").textContent = `status=${ws.status || "-"} queue=${ws.queue_size || 0} dropped=${ws.queue_dropped || 0} processing=${processing} proc=${ws.events_processed || 0} fail=${ws.events_failed || 0}`;
      } else if (Array.isArray(r.workflows)) {
        byId("wf-result").textContent = r.workflows.map(w => `${w.id} (${w.nodes}n)`).join(", ");
      } else if (r.workflow_validation) {
        const v = r.workflow_validation || {};
        const errors = Array.isArray(v.errors) ? v.errors : [];
        const order = Array.isArray(v.execution_order) ? v.execution_order : [];
        byId("wf-result").textContent = v.ok
          ? `valido | nodes=${v.nodes || 0} | conexoes=${v.connections || 0}`
          : `invalido | erros=${errors.length}`;
        const box = validationBox;
        if (box) {
          if (v.ok) {
            box.textContent = `Workflow valido\\nOrdem: ${order.join(" -> ") || "(vazia)"}`;
          } else {
            box.textContent = `Workflow invalido\\n` + errors.map((e, i) => `${i + 1}. ${e}`).join("\\n");
          }
          box.classList.remove("hidden");
        }
      } else if (r.workflow) {
        byId("wf-result").textContent = `carregado: ${r.workflow.id || "-"} (${r.workflow.nodes || 0} nodes)`;
      } else if (r.outputs) {
        const keys = Object.keys(r.outputs || {});
        byId("wf-result").textContent = `nodes executados: ${keys.join(", ")}`;
      }
      
      if (r.ok) {
        showNotification(msg, "success");
      } else {
        showNotification(msg, "error");
      }
    });

    // Control functions
    function setModo(modo) {
      socket.emit("control", { action: "set_mode", payload: { modo } });
    }

    function limparMemoria() {
      if (confirm("Tem certeza que deseja limpar a memoria curta?")) {
        socket.emit("control", { action: "limpar_memoria_curta", payload: {} });
      }
    }

    function recarregar() {
      socket.emit("control", { action: "recarregar_skills", payload: {} });
    }

    function enviarComando(falar) {
      const cmd = byId("cmd").value.trim();
      if (!cmd) {
        showNotification("Digite um comando primeiro", "error");
        return;
      }
      socket.emit("control", { action: "comando", payload: { comando: cmd, falar: falar } });
      byId("cmd").value = "";
    }

    function _wfPayloadFromInput() {
      const value = byId("wf-id").value.trim();
      if (!value) return {};
      if (value.includes("/") || value.includes("\\\\") || value.endsWith(".json")) {
        return { path: value };
      }
      return { workflow_id: value };
    }

    function workflowList() {
      socket.emit("control", { action: "workflow_list", payload: {} });
    }
    function workflowLoad() {
      socket.emit("control", { action: "workflow_load", payload: _wfPayloadFromInput() });
    }
    function workflowValidate() {
      socket.emit("control", { action: "workflow_validate", payload: _wfPayloadFromInput() });
    }
    function workflowStart() {
      const payload = _wfPayloadFromInput();
      payload.listen_patterns = ["chat.*"];
      socket.emit("control", { action: "workflow_start", payload });
    }
    function workflowRunOnce() {
      socket.emit("control", { action: "workflow_run_once", payload: _wfPayloadFromInput() });
    }
    function workflowStop() {
      socket.emit("control", { action: "workflow_stop", payload: {} });
    }

    // Notification system
    function showNotification(message, type = "info") {
      const colors = {
        success: "bg-green-500",
        error: "bg-red-500",
        info: "bg-blue-500"
      };
      
      const notif = document.createElement("div");
      notif.className = `fixed top-20 right-6 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 fade-in`;
      notif.textContent = message;
      
      document.body.appendChild(notif);
      
      setTimeout(() => {
        notif.style.opacity = "0";
        notif.style.transform = "translateX(100%)";
        notif.style.transition = "all 0.3s ease-out";
        setTimeout(() => notif.remove(), 300);
      }, 3000);
    }
  </script>

</body>
</html>"""
    return html.replace("__PANEL_TOKEN__", token)

