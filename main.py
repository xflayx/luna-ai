from core.voice import ouvir, falar
from core.intent import detectar_intencao
from core.router import processar_comando
from config.state import STATE 
import sys, signal, subprocess
import pyperclip
import logging
import os
import time

# Silencia logs de cache
logging.getLogger('comtypes').setLevel(logging.ERROR)
logging.getLogger('comtypes.client._code_cache').setLevel(logging.ERROR)

# =========================
# Funções de estado visual
# =========================

def status(msg):
    print(msg)

def encerrar(sig=None, frame=None):
    status("🔴 Encerrando a Luna...")
    falar("Encerrando a Luna.")
    
    # Encerra AutoHotkey
    if 'processo_ahk' in globals() and processo_ahk:
        try:
            processo_ahk.terminate()
        except:
            pass
    
    # Encerra o menu radial
    if 'processo_menu' in globals() and processo_menu:
        try:
            processo_menu.terminate()
        except:
            pass
    
    sys.exit(0)

signal.signal(signal.SIGINT, encerrar)

# =========================
# Inicia AutoHotkey (Hotkeys globais)
# =========================

# Caminho absoluto baseado na localização do main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
caminho_ahk = os.path.join(BASE_DIR, "interface", "luna_hotkeys.ahk")
processo_ahk = None

if os.path.exists(caminho_ahk):
    try:
        # Inicia AutoHotkey script
        processo_ahk = subprocess.Popen(
            [caminho_ahk],
            shell=True
        )
        
        time.sleep(0.5)
        
        if processo_ahk.poll() is None:
            status(f"✅ AutoHotkey rodando (PID: {processo_ahk.pid})")
        else:
            status("⚠️ AutoHotkey não iniciou")
    except Exception as e:
        status(f"⚠️ AutoHotkey: {e}")
        status("   Certifique-se que AutoHotkey está instalado")
else:
    status(f"⚠️ luna_hotkeys.ahk não encontrado")
    status(f"   Caminho esperado: {caminho_ahk}")

# =========================
# Inicia Menu Radial Eel (PROCESSO SEPARADO)
# =========================

caminho_menu = os.path.join(BASE_DIR, "interface", "radial_menu_eel.py")
processo_menu = None

if os.path.exists(caminho_menu):
    try:
        # Flags para Windows
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        
        processo_menu = subprocess.Popen(
            [sys.executable, caminho_menu],
            creationflags=flags
        )
        
        time.sleep(1.5)
        
        if processo_menu.poll() is None:
            status(f"✅ Menu radial rodando (PID: {processo_menu.pid})")
            status("🖱️  Botão lateral | ⌨️ Alt+Q | 🎤 'abrir menu'")
        else:
            status("⚠️ Menu radial não iniciou")
    except Exception as e:
        status(f"⚠️ Menu radial: {e}")
else:
    status(f"⚠️ Menu radial não encontrado")
    status(f"   Caminho esperado: {caminho_menu}")

# =========================
# Loop principal
# =========================

status("🟢 LUNA ONLINE")

while True:
    status("🎧 Ouvindo...")
    
    # 1. Tenta capturar comando por VOZ
    cmd = ouvir()

    # 2. Se a voz falhar, tenta capturar pelo CLIPBOARD (para o Menu Radial)
    if not cmd:
        try:
            texto_clip = pyperclip.paste().strip()
            if texto_clip and texto_clip.lower().startswith("luna"):
                cmd = texto_clip
                pyperclip.copy("")  # Limpa para não repetir
                status(f"📋 Comando via Menu: {cmd}")
        except:
            pass

    if not cmd:
        continue

    if "encerrar" in cmd.lower():
        encerrar()

    # --- LÓGICA DE BYPASS PARA PLUGINS ---
    em_espera = (STATE.esperando_nome_sequencia or 
                 STATE.esperando_loops or 
                 STATE.gravando_sequencia)

    intent = None
    if not em_espera:
        status("🧠 Processando intenção...")
        intent = detectar_intencao(cmd)

        if not intent:
            if not cmd.lower().startswith("luna"):
                status("😶 Nenhuma intenção reconhecida")
                continue
    else:
        status("🔄 Modo Direto: Capturando dados da sequência...")

    # Envia para o Router
    resposta = processar_comando(cmd, intent)

    if resposta:
        status("🗣️ Falando...")
        falar(resposta)
    else:
        status("⚠️ Nenhuma resposta gerada")

    time.sleep(0.1)

    time.sleep(0.1)
