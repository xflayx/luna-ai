from core.voice import ouvir, falar
from core.intent import detectar_intencao
from core.router import processar_comando
import sys, signal

# =========================
# Funções de estado visual
# =========================

def status(msg):
    print(msg)

def encerrar(sig=None, frame=None):
    status("🔴 Encerrando a Luna...")
    falar("Encerrando a Luna.")
    sys.exit(0)

signal.signal(signal.SIGINT, encerrar)

# =========================
# Loop principal
# =========================

status("🟢 LUNA ONLINE")

while True:
    status("🎧 Ouvindo...")
    cmd = ouvir()

    if not cmd:
        status("😶 Nenhum comando detectado")
        continue

    if "encerrar" in cmd:
        encerrar()

    status("🧠 Processando intenção...")
    intent = detectar_intencao(cmd)

    if not intent:
        status("😶 Nenhuma intenção reconhecida")
        continue

    resposta = processar_comando(cmd, intent)

    if resposta:
        status("🗣️ Falando...")
        falar(resposta)  # pyttsx3
    else:
        status("⚠️ Nenhuma resposta gerada")
