import json, os, time, pyautogui
from pynput import mouse, keyboard

MACROS_FILE = "data/macros.json"
acoes_temporarias = []
gravador_mouse = None
gravador_teclado = None

def carregar_macros():
    if not os.path.exists(MACROS_FILE):
        return {}
    with open(MACROS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# SUA FUNÇÃO ORIGINAL (Consertada para o seu JSON)
def executar_macro(nome):
    macros = carregar_macros()
    if nome not in macros:
        return f"Não encontrei a sequência {nome}."

    for acao in macros[nome]:
        if acao["tipo"] == "mouse":
            pyautogui.click(acao["x"], acao["y"])
        elif acao["tipo"] == "tecla":
            pyautogui.press(acao["tecla"])
        time.sleep(1)
    return f"Sequência {nome} executada."

# FUNÇÕES DE GRAVAÇÃO
def iniciar_gravacao_sequencia():
    global acoes_temporarias, gravador_mouse, gravador_teclado
    acoes_temporarias = []
    
    def on_click(x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            acoes_temporarias.append({"tipo": "mouse", "x": x, "y": y})

    def on_press(key):
        try: tecla = key.char
        except AttributeError: tecla = str(key).replace("Key.", "")
        acoes_temporarias.append({"tipo": "tecla", "tecla": tecla})

    gravador_mouse = mouse.Listener(on_click=on_click)
    gravador_teclado = keyboard.Listener(on_press=on_press)
    gravador_mouse.start()
    gravador_teclado.start()
    return "Iniciando gravação. Pode começar os movimentos."

def parar_gravacao_sequencia():
    global gravador_mouse, gravador_teclado
    if gravador_mouse: gravador_mouse.stop()
    if gravador_teclado: gravador_teclado.stop()
    return "Gravação parada. Qual o nome da sequência?"

def finalizar_salvamento(nome):
    global acoes_temporarias
    if not acoes_temporarias: return "Nada foi gravado."
    macros = carregar_macros()
    macros[nome.strip()] = acoes_temporarias
    os.makedirs("data", exist_ok=True)
    with open(MACROS_FILE, "w", encoding="utf-8") as f:
        json.dump(macros, f, indent=4)
    return f"Sequência {nome} salva."