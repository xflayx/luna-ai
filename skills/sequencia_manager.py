# skills/sequencia_manager.py
import json
import os
import time
import pyautogui
import logging
from pynput import mouse, keyboard
from config.state import STATE

# ========================================
# METADADOS DA SKILL (Padrão de Plugin)
# ========================================

SKILL_INFO = {
    "nome": "Sequencia_Manager",
    "descricao": "Skill sem descrição",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ['sequencia_manager']
}



# Configuração de Log
logger = logging.getLogger("SequenciaPlugin")

# --- CONFIGURAÇÃO ---
MACROS_FILE = "data/macros.json"
acoes_temporarias = []
gravador_mouse = None
gravador_teclado = None

# --- CONTRATO DA SKILL ---
# Usando o termo "sequencia" conforme sua preferência
GATILHOS = [
    "sequencia", "sequência", "gravar", "parar gravação", "pare gravação", 
    "executar sequencia", "rodar sequencia", "salvar sequencia"
]


# ========================================
# INICIALIZAÇÃO (Opcional)
# ========================================

def inicializar():
    """Chamada quando a skill é carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

def executar(comando: str) -> str:
    """Função principal que gerencia o fluxo de sequências."""
    # Remove o termo 'luna' apenas se ele existir, mas aceita o comando sem ele
    cmd = comando.lower().replace("luna", "").strip()

    # PRIORIDADE 1: Se estiver esperando o nome da sequência
    if STATE.esperando_nome_sequencia:
        return finalizar_salvamento(cmd)

    # PRIORIDADE 2: Se estiver gravando, aceita 'parar gravação' sem o nome Luna
    if STATE.gravando_sequencia:
        if "parar" in cmd or "encerrar" in cmd:
            return parar_gravacao_sequencia()
        else:
            # Enquanto grava, ignora outros comandos de voz para não sujar a lógica
            return "" 

    # 3. Iniciar Gravação (Comando inicial)
    if "gravar" in cmd or "iniciar" in cmd:
        return iniciar_gravacao_sequencia()

    # 4. Execução e Loops
    if STATE.esperando_loops:
        return executar_com_loop(cmd)

    if "executar" in cmd or "rodar" in cmd:
        nome = cmd.replace("executar", "").replace("sequencia", "").replace("sequência", "").replace(",", "").strip()
        return preparar_execucao(nome)

    return "Comando de sequência não reconhecido."

# --- FUNÇÕES DE LÓGICA ---

def carregar_macros():
    if not os.path.exists("data"): os.makedirs("data")
    if not os.path.exists(MACROS_FILE): return {}
    with open(MACROS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def iniciar_gravacao_sequencia():
    global acoes_temporarias, gravador_mouse, gravador_teclado
    acoes_temporarias = []
    
    def on_click(x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            acoes_temporarias.append({"tipo": "mouse", "x": x, "y": y})
            
    def on_press(key):
        try: tecla = key.char
        except: tecla = str(key).replace("Key.", "")
        acoes_temporarias.append({"tipo": "tecla", "tecla": tecla})

    gravador_mouse = mouse.Listener(on_click=on_click); gravador_mouse.start()
    gravador_teclado = keyboard.Listener(on_press=on_press); gravador_teclado.start()
    
    STATE.gravando_sequencia = True
    return "Iniciando gravação. Pode começar os movimentos."

def parar_gravacao_sequencia():
    global gravador_mouse, gravador_teclado
    if gravador_mouse: gravador_mouse.stop()
    if gravador_teclado: gravador_teclado.stop()
    
    STATE.gravando_sequencia = False
    STATE.esperando_nome_sequencia = True
    return "Gravação parada. Qual o nome da sequência?"

def preparar_execucao(nome_sequencia):
    macros = carregar_macros()
    nome_limpo = nome_sequencia.strip()
    if nome_limpo in macros:
        STATE.esperando_loops = True
        STATE.sequencia_pendente = nome_limpo
        return f"Com certeza. Quantas vezes devo executar a sequência {nome_limpo}?"
    return f"Não encontrei a sequência {nome_limpo}."

def executar_com_loop(quantidade_texto):
    nome = STATE.sequencia_pendente
    macros = carregar_macros()
    
    # Extrai o número da fala do usuário
    nums = [int(s) for s in quantidade_texto.split() if s.isdigit()]
    vezes = nums[0] if nums else 1
    
    if nome in macros:
        logger.info(f"▶️ Executando {nome} por {vezes} vezes.")
        for i in range(vezes):
            for acao in macros[nome]:
                if acao["tipo"] == "mouse":
                    pyautogui.click(acao["x"], acao["y"])
                elif acao["tipo"] == "tecla":
                    pyautogui.press(acao["tecla"])
                time.sleep(0.5)       
        
        STATE.limpar_estados_sequencia()
        return f"Executei a sequência {nome} {vezes} vezes."
    return "Erro ao executar."

def finalizar_salvamento(nome):
    global acoes_temporarias
    if not acoes_temporarias: 
        STATE.limpar_estados_sequencia()
        return "Nada gravado."
    
    macros = carregar_macros()
    macros[nome.strip()] = acoes_temporarias
    with open(MACROS_FILE, "w", encoding="utf-8") as f:
        json.dump(macros, f, indent=4)
    
    STATE.limpar_estados_sequencia()
    return f"Sequência {nome} salva com sucesso."