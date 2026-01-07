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

        # 📝 Prompt contextualizado
        prompt = (
            f"Histórico recente da conversa:\n{contexto_previo}\n"
            f"Pergunta atual do usuário: '{cmd}'\n\n"
            "Diretrizes de resposta:\n"
            "1. CONTEXTO: Se a pergunta for de seguimento (ex: 'quem é?', 'e agora?'), use o histórico para identificar o assunto.\n"
            "2. PRIORIDADE: Identifique janelas, jogos (ex: Legend of Ymir) ou sites específicos.\n"
            "3. FORMATO: Responda com uma descrição técnica curta em no máximo uma frase."
        )

        # 1. Obtém a análise técnica do Gemini
        analise_tecnica = analisar_imagem_llm(image_path, prompt).strip()

        # 2. Gera a opinião baseada na personalidade e na análise técnica
        opiniao_luna = gerar_opiniao(analise_tecnica)

        # Limpeza do arquivo temporário
        try:
            os.remove(image_path)
        except:
            pass

        # Retorna a descrição técnica + o comentário da personalidade
        return f"{analise_tecnica} {opiniao_luna}"

    except Exception as e:
        print("❌ ERRO NA VISÃO:", e)
        return "Tive um problema ao tentar processar o que estou vendo agora."