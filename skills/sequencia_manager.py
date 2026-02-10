# skills/sequencia_manager.py
import json
import logging
import os
import time

import pyautogui
from pynput import keyboard, mouse

from config.state import STATE


SKILL_INFO = {
    "nome": "Sequencia_Manager",
    "descricao": "Grava e executa sequências de teclado/mouse",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["sequencia_manager"],
}

GATILHOS = [
    "sequencia",
    "sequência",
    "gravar",
    "parar gravação",
    "pare gravação",
    "executar sequencia",
    "rodar sequencia",
    "salvar sequencia",
]

logger = logging.getLogger("SequenciaPlugin")

MACROS_FILE = "data/macros.json"
acoes_temporarias: list[dict] = []
gravador_mouse = None
gravador_teclado = None
_ultimo_ts = None


def inicializar():
    """Chamada quando a skill é carregada."""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    """Função principal que gerencia o fluxo de sequências."""
    cmd = (comando or "").lower().replace("luna", "").strip()

    if STATE.esperando_nome_sequencia:
        return finalizar_salvamento(cmd)

    if STATE.gravando_sequencia:
        if "parar" in cmd or "encerrar" in cmd:
            return parar_gravacao_sequencia()
        return ""

    if "gravar" in cmd or "iniciar" in cmd:
        return iniciar_gravacao_sequencia()

    if STATE.esperando_loops:
        return executar_com_loop(cmd)

    if "executar" in cmd or "rodar" in cmd:
        nome = (
            cmd.replace("executar", "")
            .replace("sequencia", "")
            .replace("sequência", "")
            .replace(",", "")
            .strip()
        )
        return preparar_execucao(nome)

    return "Comando de sequência não reconhecido."


def carregar_macros():
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(MACROS_FILE):
        return {}
    with open(MACROS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def iniciar_gravacao_sequencia() -> str:
    global acoes_temporarias, gravador_mouse, gravador_teclado, _ultimo_ts
    acoes_temporarias = []
    _ultimo_ts = time.perf_counter()

    def _registrar_acao(acao: dict):
        global _ultimo_ts
        agora = time.perf_counter()
        delay = max(0.0, agora - _ultimo_ts) if _ultimo_ts else 0.0
        _ultimo_ts = agora
        acao["delay"] = round(delay, 3)
        acoes_temporarias.append(acao)

    def on_click(x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            _registrar_acao({"tipo": "mouse", "x": x, "y": y})

    def on_press(key):
        try:
            tecla = key.char
        except Exception:
            tecla = str(key).replace("Key.", "")
        _registrar_acao({"tipo": "tecla", "tecla": tecla})

    gravador_mouse = mouse.Listener(on_click=on_click)
    gravador_mouse.start()
    gravador_teclado = keyboard.Listener(on_press=on_press)
    gravador_teclado.start()

    STATE.gravando_sequencia = True
    return "Iniciando gravação. Pode começar os movimentos."


def parar_gravacao_sequencia() -> str:
    global gravador_mouse, gravador_teclado
    if gravador_mouse:
        gravador_mouse.stop()
    if gravador_teclado:
        gravador_teclado.stop()

    STATE.gravando_sequencia = False
    STATE.esperando_nome_sequencia = True
    return "Gravação parada. Qual o nome da sequência?"


def preparar_execucao(nome_sequencia: str) -> str:
    macros = carregar_macros()
    nome_limpo = nome_sequencia.strip()
    if nome_limpo in macros:
        STATE.esperando_loops = True
        STATE.sequencia_pendente = nome_limpo
        return f"Com certeza. Quantas vezes devo executar a sequência {nome_limpo}?"
    return f"Não encontrei a sequência {nome_limpo}."


def executar_com_loop(quantidade_texto: str) -> str:
    nome = STATE.sequencia_pendente
    macros = carregar_macros()

    nums = [int(s) for s in quantidade_texto.split() if s.isdigit()]
    vezes = nums[0] if nums else 1

    if nome in macros:
        logger.info("▶️ Executando %s por %s vezes.", nome, vezes)
        for _ in range(vezes):
            for acao in macros[nome]:
                time.sleep(acao.get("delay", 0.5))
                if acao["tipo"] == "mouse":
                    pyautogui.click(acao["x"], acao["y"])
                elif acao["tipo"] == "tecla":
                    pyautogui.press(acao["tecla"])

        STATE.limpar_estados_sequencia()
        return f"Executei a sequência {nome} {vezes} vezes."
    return "Erro ao executar."


def finalizar_salvamento(nome: str) -> str:
    global acoes_temporarias
    if not acoes_temporarias:
        STATE.limpar_estados_sequencia()
        return "Nada gravado."

    macros = carregar_macros()
    macros[nome.strip()] = acoes_temporarias
    with open(MACROS_FILE, "w", encoding="utf-8") as f:
        json.dump(macros, f, indent=4, ensure_ascii=False)

    STATE.limpar_estados_sequencia()
    return f"Sequência {nome} salva com sucesso."
