import tempfile
import os
from PIL import ImageGrab
from llm.vision_llm import analisar_imagem_llm
from core.opinion_engine import gerar_opiniao
from config.state import STATE

def analisar_tela(cmd: str) -> str:
    """
    Captura a tela, analisa o conteúdo via Gemini considerando o contexto 
    da conversa e gera uma resposta com a personalidade da Luna.
    """
    try:
        # 📸 Captura de tela
        screenshot = ImageGrab.grab()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            screenshot.save(tmp.name)
            image_path = tmp.name

        # 🧠 Recupera o contexto da memória para o prompt
        contexto_previo = STATE.obter_contexto_curto()

        # 📝 PROMPT AJUSTADO PARA RESUMOS E PERGUNTAS ESPECÍFICAS
        prompt = (
        f"Você é a Luna. Contexto: {contexto_previo}\n"
        f"Instrução do usuário: '{cmd}'\n\n"
        "REGRAS CRÍTICAS DE RESPOSTA:\n"
        "1. PROIBIDO usar símbolos como '*', '#', ou '-' para listas. Use apenas texto corrido.\n"
        "2. CURTO E DIRETO: Responda em no máximo dois parágrafos pequenos.\n"
        "3. PERSONALIDADE: Mantenha o sarcasmo, mas sem enrolação.\n"
        "4. VOZ: Escreva exatamente como deve ser falado. Não use formatação visual (Markdown).\n"
        "5. Se for um resumo, seja concisa e ignore detalhes irrelevantes da interface."
    )

        # 1. Obtém a resposta completa do Gemini (que já deve vir com a personalidade)
        resposta_luna = analisar_imagem_llm(image_path, prompt).strip()

        # Limpeza
        try:
            os.remove(image_path)
        except:
            pass

        return resposta_luna

    except Exception as e:
        print("❌ ERRO NA VISÃO:", e)
        return "Tive um problema ao tentar processar o que estou vendo agora."