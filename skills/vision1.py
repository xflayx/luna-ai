import tempfile
import os
from PIL import ImageGrab
from llm.vision_llm import analisar_imagem_llm

def analisar_tela(cmd: str) -> str:
    try:
        # 📸 Captura de tela
        screenshot = ImageGrab.grab()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            screenshot.save(tmp.name)
            image_path = tmp.name

        # 🧠 PROMPT DE ALTA FIDELIDADE (Universal e Direto)
        prompt = (
            f"Pergunta do usuário: '{cmd}'\n\n"
            "Siga estas diretrizes para uma resposta curta e precisa:\n"
            "1. PRIORIDADE TEXTUAL: Se houver texto em barras de título (janelas), menus ou legendas, use-os como fonte primária de verdade. "
            "Exemplo: Se a janela diz 'YmirGL', identifique como 'Legend of Ymir' e não confunda com jogos visualmente similares.\n"
            "2. ANÁLISE DE CONTEXTO: Identifique se o estilo é Cinema (Live Action), Anime (Desenho) ou Jogo (Interface/HUD).\n"
            "3. RESUMO EXECUTIVO: Não faça listas ou tópicos longos. Responda em no máximo 1 frases objetivas.\n"
            "4. FOCO: Responda exatamente o que foi perguntado. Se perguntarem 'que jogo é esse', diga o nome e o que está acontecendo brevemente."
        )

        # Chama o Gemini-1.5-Flash (que é excelente em OCR e resumo)
        resposta = analisar_imagem_llm(image_path, prompt).strip()

        try:
            os.remove(image_path)
        except:
            pass

        return resposta

    except Exception as e:
        print("❌ ERRO NA VISÃO:", e)
        return "Erro ao analisar a imagem."