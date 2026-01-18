from core.voice import ouvir, falar
from core.intent import detectar_intencao
from core.router import processar_comando
from config.state import STATE
import sys
import signal
import subprocess
import pyperclip
import logging
import os
import time

logging.getLogger("comtypes").setLevel(logging.ERROR)
logging.getLogger("comtypes.client._code_cache").setLevel(logging.ERROR)


def status(msg):
    print(msg)


def encerrar(sig=None, frame=None):
    status("🛑 Encerrando a Luna...")
    falar("Encerrando a Luna.")

    if "processo_menu" in globals() and processo_menu:
        try:
            processo_menu.terminate()
        except Exception:
            pass

    sys.exit(0)


signal.signal(signal.SIGINT, encerrar)

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
            status(f"✅ Menu radial rodando (PID: {processo_menu.pid})")
            status("🧭 Botao lateral | Alt+Q | 'abrir menu'")
        else:
            status("⚠️ Menu radial nao iniciou")
    except Exception as e:
        status(f"⚠️ Menu radial: {e}")
else:
    status("⚠️ Menu radial nao encontrado")

status("🟢 LUNA ONLINE")

try:
    while True:
        status("🎙️ Ouvindo...")

        cmd = ouvir()

        if not cmd:
            try:
                texto_clip = pyperclip.paste().strip()
                if texto_clip and texto_clip.lower().startswith("luna"):
                    cmd = texto_clip
                    pyperclip.copy("")
                    status(f"📋 Comando via Menu: {cmd}")
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
                    status("⚠️ Nenhuma intencao reconhecida")
                    continue
        else:
            status("⚠️ Modo direto: capturando dados da sequencia...")

        resposta = processar_comando(cmd, intent)

        if resposta:
            status("🗣️ Falando...")
            falar(resposta)
        else:
            status("⚠️ Nenhuma resposta gerada")

        time.sleep(0.1)
except KeyboardInterrupt:
    encerrar()
