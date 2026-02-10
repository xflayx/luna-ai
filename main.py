from core.voice import ouvir, falar
from core.intent import detectar_intencao
from core.router import processar_comando
from core.realtime_panel import iniciar_painel, atualizar_estado
from core.chat_ingest import start_chat_ingest
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("Luna")
logging.getLogger("comtypes").setLevel(logging.ERROR)
logging.getLogger("comtypes.client._code_cache").setLevel(logging.ERROR)

init_env()
iniciar_painel()
start_chat_ingest()


def status(msg):
    logger.info(msg)
    atualizar_estado(status=msg)


def encerrar(sig=None, frame=None):
    status("Encerrando a Luna...")
    falar("Encerrando a Luna.")

    if "processo_menu" in globals() and processo_menu:
        try:
            processo_menu.terminate()
            processo_menu.wait(timeout=3)
        except Exception:
            pass

    sys.exit(0)


signal.signal(signal.SIGINT, encerrar)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, encerrar)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

caminho_menu = os.path.join(BASE_DIR, "interface", "radial_menu_eel.py")
processo_menu = None

if os.path.exists(caminho_menu):
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

try:
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

            if not intent:
                if not cmd.lower().startswith("luna"):
                    status("Nenhuma intencao reconhecida")
                    continue
        else:
            status("✍️ Modo direto: capturando dados da sequencia...")

        resposta = processar_comando(cmd, intent)
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

        time.sleep(0.1)
except KeyboardInterrupt:
    encerrar()
