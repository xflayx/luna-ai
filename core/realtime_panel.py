import os
import threading
import time
from typing import Any, Dict, Optional


_panel_thread: Optional[threading.Thread] = None
_socketio = None
_last_state: Dict[str, Any] = {}


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

    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modo": STATE.get_modo_ativacao(),
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
    from core.router import processar_comando
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
        from core.router import _router
        if _router:
            total = _router.recarregar_todas()
            return {"ok": True, "msg": f"Recarreguei {total} skills."}
        return {"ok": False, "msg": "Router nao inicializado."}

    if action == "falar":
        texto = (payload.get("texto") or "").strip()
        if texto:
            falar(texto)
            return {"ok": True, "msg": "Falando texto."}
        return {"ok": False, "msg": "Texto vazio."}

    if action == "comando":
        cmd = (payload.get("comando") or "").strip()
        if not cmd:
            return {"ok": False, "msg": "Comando vazio."}
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
        resp = processar_comando(cmd, None) or ""
        if payload.get("falar"):
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
    except Exception:
        return

    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    _socketio = socketio

    @app.get("/")
    def index():
        return _render_html(_panel_token())

    @socketio.on("connect")
    def on_connect():
        token = request.args.get("token", "")
        required = _panel_token()
        if required and token != required:
            return False
        emit("state_update", _last_state or _build_state())

    @socketio.on("ping")
    def on_ping():
        emit("state_update", _last_state or _build_state())

    @socketio.on("control")
    def on_control(data):
        resultado = _handle_control(data or {})
        emit("control_result", resultado)
        atualizar_estado(status=resultado.get("msg", ""))

    def _run():
        socketio.run(
            app,
            host=_panel_host(),
            port=_panel_port(),
            allow_unsafe_werkzeug=True,
        )

    _panel_thread = threading.Thread(target=_run, daemon=True)
    _panel_thread.start()


def _render_html(token: str) -> str:
    html = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Painel Luna</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0e0f12; color: #e7e7ea; margin: 0; }
    .wrap { max-width: 980px; margin: 24px auto; padding: 16px; }
    .card { background: #171a21; border: 1px solid #2a2f3a; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    h1 { margin: 0 0 8px; font-size: 22px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; }
    .btn { background: #2f3a52; color: #fff; border: 0; padding: 8px 12px; border-radius: 8px; cursor: pointer; }
    .btn:hover { background: #3a4764; }
    .tag { display: inline-block; padding: 4px 8px; border-radius: 8px; background: #232b3d; margin-right: 6px; }
    input, textarea { width: 100%; background: #0f1116; color: #fff; border: 1px solid #2a2f3a; border-radius: 8px; padding: 8px; }
    textarea { min-height: 90px; }
    .muted { color: #9aa3b2; font-size: 12px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Painel Realtime - Luna</h1>
    <div class="card">
      <div class="row">
        <div class="tag">Conexao: <span id="conn">offline</span></div>
        <div class="tag">Modo: <span id="modo">-</span></div>
        <div class="tag">STT: <span id="stt">-</span></div>
        <div class="tag">TTS: <span id="tts">-</span></div>
        <div class="tag">Memoria curta: <span id="mem">0</span></div>
      </div>
      <div class="muted">Ultima atualizacao: <span id="ts">-</span></div>
    </div>

    <div class="card">
      <div class="row">
        <button class="btn" onclick="setModo('assistente')">Modo Assistente</button>
        <button class="btn" onclick="setModo('vtuber')">Modo VTuber</button>
        <button class="btn" onclick="limparMemoria()">Limpar memoria curta</button>
        <button class="btn" onclick="recarregar()">Recarregar skills</button>
      </div>
    </div>

    <div class="card">
      <label>Comando</label>
      <input id="cmd" placeholder="Digite um comando para a Luna"/>
      <div class="row" style="margin-top: 8px;">
        <button class="btn" onclick="enviarComando(false)">Enviar (sem falar)</button>
        <button class="btn" onclick="enviarComando(true)">Enviar e falar</button>
      </div>
      <div class="muted" id="resultado"></div>
    </div>

    <div class="card">
      <label>Ultimo comando</label>
      <div id="ultimo_cmd" class="muted">-</div>
      <label style="margin-top: 8px; display: block;">Ultima resposta</label>
      <textarea id="ultima_resposta" readonly></textarea>
      <label style="margin-top: 8px; display: block;">Status</label>
      <div id="status" class="muted">-</div>
    </div>
  </div>

  <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
  <script>
    const PANEL_TOKEN = "__PANEL_TOKEN__";
    const socket = io({
      transports: ["polling", "websocket"],
      path: "/socket.io",
      query: { token: PANEL_TOKEN },
    });
    const byId = (id) => document.getElementById(id);
    socket.on("connect", () => byId("conn").textContent = "online");
    socket.on("disconnect", () => byId("conn").textContent = "offline");
    socket.on("connect_error", (err) => {
      byId("conn").textContent = "erro";
      byId("status").textContent = (err && err.message) ? err.message : "falha de conexao";
    });
    socket.on("state_update", (s) => {
      if (!s) return;
      byId("modo").textContent = s.modo || "-";
      byId("stt").textContent = s.stt_engine || "-";
      byId("tts").textContent = (s.tts_engine || "-") + (s.tts_async ? " (async)" : "");
      byId("mem").textContent = s.memoria_curta_len || 0;
      byId("ts").textContent = s.ts || "-";
      byId("ultimo_cmd").textContent = s.ultimo_comando || "-";
      byId("ultima_resposta").value = s.ultima_resposta || "";
      byId("status").textContent = s.status || "";
    });
    socket.on("control_result", (r) => {
      byId("resultado").textContent = r && r.msg ? r.msg : "";
      if (r && r.resposta) {
        byId("ultima_resposta").value = r.resposta;
      }
    });

    function setModo(modo) {
      socket.emit("control", { action: "set_mode", payload: { modo } });
    }
    function limparMemoria() {
      socket.emit("control", { action: "limpar_memoria_curta", payload: {} });
    }
    function recarregar() {
      socket.emit("control", { action: "recarregar_skills", payload: {} });
    }
    function enviarComando(falar) {
      const cmd = byId("cmd").value.trim();
      if (!cmd) return;
      socket.emit("control", { action: "comando", payload: { comando: cmd, falar: falar } });
    }
  </script>
</body>
</html>"""
    return html.replace("__PANEL_TOKEN__", token)
