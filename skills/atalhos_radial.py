# skills/atalhos_radial.py
import os
import tempfile

SKILL_INFO = {
    "nome": "Atalhos Radial",
    "descricao": "Abre menu radial de atalhos",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["atalhos_radial"]
}

GATILHOS = ["menu", "abrir menu", "atalhos", "radial"]

def inicializar():
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

def executar(comando: str) -> str:
    """Envia sinal para abrir o menu"""
    arquivo_sinal = os.path.join(tempfile.gettempdir(), "luna_menu_open.signal")
    
    try:
        with open(arquivo_sinal, 'w') as f:
            f.write('1')
        return "Abrindo menu de atalhos."
    except:
        return "Erro ao abrir menu."