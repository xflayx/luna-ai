import os
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
        try:
            from core.router import _router, RouterLuna
            router = _router or RouterLuna()
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
        import flask.cli
    except Exception:
        return

    logger = logging.getLogger("Panel")

    flask.cli.show_server_banner = lambda *args, **kwargs: None
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    _socketio = socketio

    @app.get("/")
    def index():
        return _render_html(_panel_token())

    @app.get("/health")
    def health_check():
        from config.state import STATE
        from core import router as router_mod
        from core import voice as voice_mod
        from config import env as env_mod
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

        router = getattr(router_mod, "_router", None)
        skills_loaded = len(getattr(router, "skills", {}) or {})
        skills_failed = len(getattr(router, "skill_erros", {}) or {})

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
            "system": system,
            "panel": {
                "host": _panel_host(),
                "port": _panel_port(),
                "enabled": _panel_enabled(),
            },
        }

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

    def _ticker():
        while True:
            try:
                if _socketio:
                    _socketio.emit("state_update", _build_state())
            except Exception:
                pass
            time.sleep(1)

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
        <div class="text-xs text-gray-400 mt-1">Modo de Operação</div>
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
          <span class="text-xs px-2 py-1 bg-pink-500/20 rounded-full text-pink-300">Memória</span>
        </div>
        <div class="text-2xl font-bold" id="memoria">0</div>
        <div class="text-xs text-gray-400 mt-1">Itens na Memória Curta</div>
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
          <h3 class="text-lg font-semibold">Visão Automática</h3>
        </div>
        <div class="text-xl font-bold text-blue-300" id="visao-auto">-</div>
      </div>

    </div>

    <!-- Quick Actions -->
    <div class="glass rounded-xl p-6 mb-8">
      <h3 class="text-lg font-semibold mb-4 flex items-center">
        <i class="fas fa-bolt text-yellow-400 mr-2"></i>
        Ações Rápidas
      </h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button onclick="setModo('assistente')" class="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-user-tie mr-2"></i>Assistente
        </button>
        <button onclick="setModo('vtuber')" class="bg-gradient-to-r from-pink-600 to-pink-700 hover:from-pink-500 hover:to-pink-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-video mr-2"></i>VTuber
        </button>
        <button onclick="limparMemoria()" class="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 px-4 py-3 rounded-lg font-medium transition-all transform hover:scale-105">
          <i class="fas fa-trash mr-2"></i>Limpar Memória
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

    <!-- Activity Log -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      
      <!-- Last Command -->
      <div class="glass rounded-xl p-6">
        <h3 class="text-lg font-semibold mb-4 flex items-center">
          <i class="fas fa-history text-purple-400 mr-2"></i>
          Último Comando
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
        Última Resposta
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
      <p>Luna AI Dashboard • Desenvolvido com <i class="fas fa-heart text-pink-500"></i></p>
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
      byId("conn-text").textContent = "Erro de conexão";
      byId("status").textContent = err && err.message ? err.message : "Falha de conexão";
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
    });

    socket.on("control_result", (r) => {
      if (!r) return;
      
      const msg = r.msg || "";
      byId("resultado").textContent = msg;
      
      if (r.resposta) {
        byId("ultima-resposta").value = r.resposta;
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
      if (confirm("Tem certeza que deseja limpar a memória curta?")) {
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
