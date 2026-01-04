import json, os, time, pyautogui

MACROS_FILE = "data/macros.json"

def carregar_macros():
    if not os.path.exists(MACROS_FILE):
        return {}
    return json.load(open(MACROS_FILE, encoding="utf-8"))

def executar_macro(nome):
    macros = carregar_macros()
    if nome not in macros:
        return "Macro não encontrada."

    for acao in macros[nome]:
        if acao["tipo"] == "mouse":
            pyautogui.click(acao["x"], acao["y"])
        elif acao["tipo"] == "tecla":
            pyautogui.press(acao["tecla"])
        time.sleep(1)

    return f"Macro {nome} executada."
