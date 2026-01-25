# skills/web_reader.py
import pyperclip
import pyautogui
import time
import os
import tempfile
from playwright.sync_api import sync_playwright
from llm.vision_llm import analisar_imagem_llm
from config.state import STATE

# ========================================
# METADADOS DA SKILL
# ========================================

SKILL_INFO = {
    "nome": "Web Reader",
    "descricao": "Lê e resume sites usando Playwright",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["web_reader"]
}

GATILHOS = ["site", "página", "pagina", "link", "url", "leia", "resuma", "resumo", "tweet", "post"]

# ========================================
# INICIALIZAÇÃO
# ========================================

def inicializar():
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

# ========================================
# FUNÇÃO PRINCIPAL
# ========================================

def executar(cmd: str) -> str:
    """Lê e resume sites"""
    url = capturar_url_atual()
    
    if not url:
        return "Você quer que eu leia o quê? Não tem nenhum link aberto."
    
    print(f"🌐 Acessando: {url}")
    caminho_imagem = capturar_site_inteiro_playwright(url)
    
    if not caminho_imagem:
        return "Problema ao acessar o site."

    contexto = STATE.obter_contexto_curto()
    
    # Prompt específico por tipo - CURTO para evitar cortes
    if "x.com" in url or "twitter.com" in url:
        prompt = f"""Luna, VTuber. Contexto: {contexto}

Leia o post do X/Twitter. Responda em NO MAXIMO 3 frases curtas:
- Quem postou e o que disse
- Se tiver imagem, descreva brevemente
- Se aparecer tela de login: "O Elon trancou."

Sem listas, sem *, sem #. Resposta COMPLETA em 3 frases."""
    else:
        prompt = f"""Luna, assistente. Contexto: {contexto}

Resuma esta pagina em NO MAXIMO 4 frases curtas:
- Tema principal
- 2-3 pontos importantes
- Ignore menus e anuncios

Sem listas, sem *, sem #. Resposta COMPLETA em 4 frases."""

    try:
        resposta = analisar_imagem_llm(caminho_imagem, prompt)
        return resposta.replace("*", "").replace("#", "")
    finally:
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)

# ========================================
# FUNÇÕES AUXILIARES (EXPORTADAS)
# ========================================

def capturar_url_atual():
    """Captura URL do navegador"""
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.2)
    pyautogui.click()
    url = pyperclip.paste().strip()
    return url if url.startswith("http") else None

def capturar_site_inteiro_playwright(url):
    """Captura screenshot completo do site"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={'width': 1280, 'height': 800},
            )
            page = context.new_page()
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                if "x.com" in url or "twitter.com" in url:
                    time.sleep(5)
                    try:
                        page.evaluate("""() => {
                            document.querySelectorAll('[data-testid="SheetDialog"]').forEach(el => el.remove());
                            document.body.style.overflow = 'auto';
                        }""")
                    except:
                        pass
                else:
                    time.sleep(3)
            except:
                pass
            
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            path = tmp.name
            tmp.close()
            
            if "x.com" in url or "twitter.com" in url:
                page.screenshot(path=path, full_page=False)
            else:
                page.screenshot(path=path, full_page=True)
            
            browser.close()
            return path
    except Exception as e:
        print(f"❌ Erro Playwright: {e}")
        return None
