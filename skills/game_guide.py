# skills/game_guide.py
import os
import tempfile
import urllib.parse

from playwright.sync_api import sync_playwright

from config.state import STATE
from core.prompt_injector import build_game_guide_prompt
from llm.vision_llm import analisar_imagem_llm


SKILL_INFO = {
    "nome": "Game Guide",
    "descricao": "Busca guias e tutoriais de jogos",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["game_guide"],
}

GATILHOS = ["guia", "tutorial", "como conseguir", "como passar", "dicas de"]


def inicializar():
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    """Busca guia de jogo."""
    busca = comando.replace("busque um", "").replace("luna", "").strip()
    url_busca = f"https://www.google.com/search?q={urllib.parse.quote(busca + ' guia tutorial')}"

    print(f"🎮 Luna procurando guia para: {busca}")

    caminho_imagem = _capturar_pagina(url_busca)
    if not caminho_imagem:
        return "Não consegui acessar a central de guias agora. Tente novamente."

    contexto = STATE.obter_contexto_curto()
    prompt = build_game_guide_prompt(contexto, busca)

    try:
        return analisar_imagem_llm(caminho_imagem, prompt)
    finally:
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)


def _capturar_pagina(url: str) -> str | None:
    """Captura screenshot de uma página."""
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
