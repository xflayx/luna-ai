from core.voice import ouvir, falar
from core.intent import detectar_intencao
from core.router import processar_comando
import sys, signal

def encerrar(sig=None, frame=None):
    falar("Encerrando a Luna.")
    sys.exit(0)

signal.signal(signal.SIGINT, encerrar)

print("🟢 LUNA ONLINE")

while True:
    cmd = ouvir()
    if not cmd:
        continue

    if "encerrar" in cmd:
        encerrar()

    intent = detectar_intencao(cmd)

    if not intent:
        continue  # silêncio total

    resposta = processar_comando(cmd, intent)

    if resposta:
        falar(resposta) # Isso aciona o pyttsx3
    else:
        print("⚠️ Nenhuma resposta gerada para falar.")
