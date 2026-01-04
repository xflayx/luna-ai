# core/opinion_engine.py

import random
from core.personality_loader import carregar_personalidade


def gerar_opiniao(vision_context: dict) -> str:
    """
    Gera uma opinião baseada:
    - no contexto visual
    - na personalidade da LUNA
    """

    if not vision_context:
        return "Não tenho contexto suficiente para opinar."

    personalidade = carregar_personalidade()

    summary = vision_context.get("summary", "")
    tags = vision_context.get("tags", [])
    confidence = vision_context.get("confidence", 0.0)

    frases = []

    # ===============================
    # TOM BASE
    # ===============================
    if personalidade["speech_style"]["likes_short_sentences"]:
        frases.append(summary.split(".")[0] + ".")

    # ===============================
    # OPINIÃO POR TAG
    # ===============================
    bias = personalidade.get("opinion_bias", {})

    for tag in tags:
        if tag in bias:
            if bias[tag] == "gosta":
                frases.append(random.choice(personalidade["phrases"]["positive"]))
            elif bias[tag] == "neutra":
                frases.append(random.choice(personalidade["phrases"]["neutral"]))
            elif bias[tag] == "analitica":
                frases.append("Parece ter sido feito com alguma intenção por trás.")
            elif bias[tag] == "observadora":
                frases.append("Isso parece pensado para chamar atenção rápida.")

    # ===============================
    # INCERTEZA (HUMANA)
    # ===============================
    if confidence < 0.5:
        frases.append(random.choice(personalidade["phrases"]["cautious"]))

    # ===============================
    # CONTROLE DE VERBOSIDADE
    # ===============================
    return " ".join(frases[:2])
