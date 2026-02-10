# skills/web_reader.py
import os
import signal
import tempfile
import time

import pyautogui
import pyperclip
from playwright.sync_api import sync_playwright

from llm.vision_llm import analisar_imagem_llm
from core.prompt_injector import build_web_reader_prompt
from config.state import STATE


SKILL_INFO = {
    "nome": "Web Reader",
    "descricao": "Lê e resume sites usando Playwright",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["web_reader"],
}

GATILHOS = [
    "site",
    "página",
    "pagina",
    "link",
    "url",
    "leia",
    "resuma",
    "resumo",
    "tweet",
    "post",
]


def inicializar():
    """Chamada quando a skill é carregada."""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(cmd: str) -> str:
    """Lê e resume sites."""
    url = capturar_url_atual()
    if not url:
        return "Você quer que eu leia o quê? Não tem nenhum link aberto."

    print(f"🌐 Acessando: {url}")
    caminho_imagem = capturar_site_inteiro_playwright(url)
    if not caminho_imagem:
        return "Problema ao acessar o site."

    contexto = STATE.obter_contexto_curto()
    is_twitter = "x.com" in url or "twitter.com" in url
    prompt = build_web_reader_prompt(contexto, is_twitter)

    try:
        resposta = analisar_imagem_llm(
            caminho_imagem,
            prompt,
            max_output_tokens=2000,
        )
        texto = resposta.replace("*", "").replace("#", "")
        if _precisa_reforco(texto, min_frases=3):
            prompt_reforco = (
                prompt
                + "\n\nINSTRUÇÃO EXTRA: Entregue um resumo completo com 4 a 6 frases curtas."
            )
            resposta = analisar_imagem_llm(
                caminho_imagem,
                prompt_reforco,
                max_output_tokens=2000,
            )
            texto = resposta.replace("*", "").replace("#", "")
        return _limitar_resumo(texto, max_frases=6, max_palavras=140)
    finally:
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)


def capturar_url_atual() -> str | None:
    """Captura a URL do navegador."""
    old_handler = None
    try:
        old_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        old_handler = None

    try:
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        pyautogui.click()
        url = pyperclip.paste().strip()
        return url if url.startswith("http") else None
    finally:
        if old_handler is not None:
            try:
                signal.signal(signal.SIGINT, old_handler)
            except Exception:
                pass


def _limitar_resumo(texto: str, max_frases: int, max_palavras: int) -> str:
    texto = (texto or "").strip()
    if not texto:
        return texto
    palavras = texto.split()
    if len(palavras) > max_palavras:
        texto = " ".join(palavras[:max_palavras]).rstrip()
    frases = [
        f.strip()
        for f in texto.replace("!", ".").replace("?", ".").split(".")
        if f.strip()
    ]
    if len(frases) > max_frases:
        texto = ". ".join(frases[:max_frases]).strip()
    if texto and not texto.endswith((".", "!", "?")):
        texto += "."
    return texto


def _contar_frases(texto: str) -> int:
    if not texto:
        return 0
    frases = [
        f.strip()
        for f in texto.replace("!", ".").replace("?", ".").split(".")
        if f.strip()
    ]
    return len(frases)


def _precisa_reforco(texto: str, min_frases: int) -> bool:
    return _contar_frases(texto) < min_frases


def capturar_site_inteiro_playwright(url: str) -> str | None:
    """Captura screenshot completo do site."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if "x.com" in url or "twitter.com" in url:
                    time.sleep(5)
                    try:
                        page.evaluate(
                            """() => {
                                document.querySelectorAll('[data-testid="SheetDialog"]').forEach(el => el.remove());
                                document.body.style.overflow = 'auto';
                            }"""
                        )
                    except Exception:
                        pass
                else:
                    time.sleep(3)
            except Exception:
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
