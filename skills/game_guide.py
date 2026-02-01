# skills/game_guide.py
import urllib.parse
from llm.vision_llm import analisar_imagem_llm
from core.prompt_injector import build_game_guide_prompt
from config.state import STATE
import os
import tempfile
from playwright.sync_api import sync_playwright

# ========================================
# METADADOS DA SKILL
# ========================================

SKILL_INFO = {
    "nome": "Game Guide",
    "descricao": "Busca guias e tutoriais de jogos",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["game_guide"]
}

GATILHOS = ["guia", "tutorial", "como conseguir", "como passar", "dicas de"]

# ========================================
# INICIALIZAÇÃO
# ========================================

def inicializar():
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

# ========================================
# FUNÇÃO PRINCIPAL
# ========================================

def executar(comando: str) -> str:
    """Busca guia de jogo"""
    
    # Limpa o comando para criar a busca
    busca = comando.replace("busque um", "").replace("luna", "").strip()
    url_busca = f"https://www.google.com/search?q={urllib.parse.quote(busca + ' guia tutorial')}"
    
    print(f"🎮 Luna procurando guia para: {busca}")
    
    # Captura a página de resultados
    caminho_imagem = _capturar_pagina(url_busca)
    
    if not caminho_imagem:
        return "Não consegui acessar a central de guias agora. Tente novamente."

    contexto = STATE.obter_contexto_curto()
    
    prompt = build_game_guide_prompt(contexto, busca)

    try:
        resposta = analisar_imagem_llm(caminho_imagem, prompt)
        return resposta
    finally:
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)

# ========================================
# FUNÇÃO AUXILIAR
# ========================================

def _capturar_pagina(url: str) -> str:
    """Captura screenshot de uma página"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            path = tmp.name
            tmp.close()
            
            page.screenshot(path=path, full_page=False)
            browser.close()
            
            return path
    except Exception as e:
        print(f"❌ Erro ao capturar página: {e}")
        return None
