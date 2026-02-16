from core.voice import ouvir, falar
from core.intent import detectar_intencao
from core.command_orchestrator import processar_comando_orquestrado
from core.workflow_runtime import autostart_workflow_from_env
from core.realtime_panel import iniciar_painel, atualizar_estado
from core.chat_ingest import start_chat_ingest
from core.push_to_talk import iniciar_push_to_talk, parar_push_to_talk
from config.state import STATE
from config.env import init_env
import sys
import signal
import subprocess
import pyperclip
import logging
import os
import time
import warnings

warnings.filterwarnings(
    "ignore",
    message=r".*ArbitraryTypeWarning: <built-in function any>.*",
)

from core.logging_setup import init_logging

init_logging()
logger = logging.getLogger("Luna")

init_env()
iniciar_painel()

def status(msg, **extra):
    logger.info(msg, extra=extra)
    atualizar_estado(status=msg)


_workflow_autostart = autostart_workflow_from_env()
if _workflow_autostart.get("enabled"):
    if _workflow_autostart.get("started"):
        wf_ref = (
            _workflow_autostart.get("workflow_id")
            or _workflow_autostart.get("path")
            or "(workflow)"
        )
        patterns = ", ".join(_workflow_autostart.get("listen_patterns") or ())
        status(f"🔁 Workflow auto-start ativo: {wf_ref} ({patterns})")
    else:
        erro = _workflow_autostart.get("error") or "erro desconhecido"
        status(f"⚠️ Workflow auto-start falhou: {erro}")

start_chat_ingest()


def encerrar(sig=None, frame=None):
    status("Encerrando a Luna...")
    falar("Encerrando a Luna.")

    if "processo_menu" in globals() and processo_menu:
        try:
            processo_menu.terminate()
            processo_menu.wait(timeout=3)
        except Exception:
            pass

    try:
        parar_push_to_talk()
    except Exception:
        pass

    sys.exit(0)


signal.signal(signal.SIGINT, encerrar)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, encerrar)

if os.getenv("LUNA_VISION_AUTO_ENABLED", "1") == "1":
    try:
        from skills.vision import iniciar_visao_automatica_sempre
        iniciar_visao_automatica_sempre()
        status("Visao automatica ligada")
    except Exception as e:
        status(f"Falha ao iniciar visao automatica: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

caminho_menu = os.path.join(BASE_DIR, "interface", "radial_menu_eel.py")
processo_menu = None

if os.getenv("LUNA_RADIAL_MENU_ENABLED", "1") == "1" and os.path.exists(caminho_menu):
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

        processo_menu = subprocess.Popen(
            [sys.executable, caminho_menu],
            creationflags=flags,
        )

        time.sleep(1.5)

        if processo_menu.poll() is None:
            status(f"Menu radial rodando (PID: {processo_menu.pid})")
        else:
            status("Menu radial nao iniciou")
    except Exception as e:
        status(f"Menu radial: {e}")
else:
    status("Menu radial nao encontrado")

status("🟢 LUNA ONLINE")

PTT_ENABLED = os.getenv("LUNA_PTT_ENABLED", "0") == "1"


def handle_command(cmd: str):
    if not cmd:
        return

    if "encerrar" in cmd.lower():
        encerrar()

    em_espera = (
        STATE.esperando_nome_sequencia
        or STATE.esperando_loops
        or STATE.gravando_sequencia
    )

    intent = None
    if not em_espera:
        status("🧠 Processando intencao...")
        intent = detectar_intencao(cmd)
        if intent:
            logger.info("Intent detectada", extra={"intent": intent})

        if not intent and STATE.get_modo_ativacao() == "assistente":
            if not cmd.lower().startswith("luna"):
                status("Nenhuma intencao reconhecida")
                return
    else:
        status("✍️ Modo direto: capturando dados da sequencia...")

    try:
        resposta = processar_comando_orquestrado(cmd, intent, source="voice")
    except Exception:
        logger.warning("Falha ao processar comando")
        resposta = "Tive um problema ao processar isso. Tenta de novo?"

    atualizar_estado(
        last_command=cmd,
        last_intent=intent,
        last_response=resposta or "",
    )

    if resposta:
        status("🗣️ Falando...")
        falar(resposta)
    else:
        status("Nenhuma resposta gerada")


try:
    if PTT_ENABLED:
        STATE.set_modo_ativacao("vtuber")
        status("🎙️ Push-to-Talk ativo")
        iniciar_push_to_talk(on_audio_ready=handle_command)
        while True:
            time.sleep(1)
    else:
        while True:
            status("🎙️ Ouvindo...")

            cmd = ouvir()

            if not cmd:
                try:
                    texto_clip = pyperclip.paste().strip()
                    menu_prefix = "@menu:"
                    if texto_clip and texto_clip.lower().startswith(menu_prefix):
                        cmd = texto_clip[len(menu_prefix):].strip()
                        pyperclip.copy("")
                        status(f"📌 Comando via menu: {cmd}")
                except Exception:
                    pass

            if not cmd:
                continue

            handle_command(cmd)
            time.sleep(0.1)
except KeyboardInterrupt:
    encerrar()

