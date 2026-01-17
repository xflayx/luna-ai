# skills/vision.py
import tempfile
import os
from PIL import ImageGrab
from llm.vision_llm import analisar_imagem_llm
from config.state import STATE

# ========================================
# METADADOS DA SKILL
# ========================================

SKILL_INFO = {
    "nome": "Vision",
    "descricao": "Analisa imagens da tela usando Gemini Vision",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["visao", "vision"]
}

GATILHOS = ["analise", "veja", "olhe", "tela"]

# ========================================
# INICIALIZAÇÃO
# ========================================

def inicializar():
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

# ========================================
# FUNÇÃO PRINCIPAL
# ========================================

def executar(comando: str) -> str:
    """Captura e analisa a tela"""
    return analisar_tela(comando)

def analisar_tela(cmd: str) -> str:
    """Captura a tela, analisa via Gemini e retorna resposta"""
    try:
        image_path = "screenshot.png"
        cmd_lower = cmd.lower()

        # Captura site completo se for web_reader
        if any(p in cmd_lower for p in ["site", "página"]):
            try:
                from skills.web_reader import capturar_url_atual, capturar_site_inteiro_playwright
                url = capturar_url_atual()
                if url:
                    print(f"🌐 Luna acessando: {url}")
                    image_path = capturar_site_inteiro_playwright(url)
                else:
                    return "Não vejo nenhum site aberto."
            except:
                screenshot = ImageGrab.grab()
                screenshot.save(image_path)
                screenshot.close()
        else:
            # Captura de tela normal
            screenshot = ImageGrab.grab()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                screenshot.save(tmp.name)
                image_path = tmp.name
            screenshot.close()

        # Contexto da conversa
        contexto = STATE.obter_contexto_curto()

        # Prompt para o Gemini
        prompt = f"""Você é a Luna, VTuber e assistente IA.
Contexto: {contexto}
Comando: '{cmd}'

Analise a imagem e responda de forma:
- Natural e conversacional
- Direta (2-3 frases)
- Sem usar *, #, ou listas
- Tom amigável e levemente sarcástico

Responda como se estivesse falando ao vivo."""

        # Chama Gemini Vision
        resposta = analisar_imagem_llm(image_path, prompt).strip()

        # Limpa arquivo temporário
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass

        return resposta

    except Exception as e:
        print(f"❌ ERRO NA VISÃO: {e}")
        return "Tive um problema ao analisar a tela."
