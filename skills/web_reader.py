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
    
    # Prompt específico por tipo
    if "x.com" in url or "twitter.com" in url:
        prompt = f"""Você é a Luna, VTuber fofoqueira.
Contexto: {contexto}

Leia este POST DO TWITTER/X:
1. Quem postou (nome e @)
2. O que disse (2-4 frases)
3. Se tem imagem/meme, descreva
4. Dê sua opinião sarcástica se for polêmico
5. Se aparecer só login: "O Elon trancou, não consigo ver."

Texto corrido, sem *, -, #. 3-5 frases."""
    else:
        prompt = f"""Você é a Luna, assistente IA.
Contexto: {contexto}

Faça um RESUMO COMPLETO desta página:
1. Tema/assunto principal
2. 3-5 pontos mais importantes
3. Dados, números, datas relevantes
4. Ignore menus, ads, cookies

Seja clara e objetiva. Use 4-8 frases para cobrir o conteúdo.
Texto corrido, sem *, -, #."""

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