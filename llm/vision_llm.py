import os
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_NAME = "gemini-3-flash-preview"  # pode trocar para gemini-3-flash-preview


def analisar_imagem_llm(image_path: str, prompt: str) -> str:
    """
    Envia imagem + prompt REAL para o Gemini Vision
    """

    model = genai.GenerativeModel(MODEL_NAME)

    image = Image.open(image_path)

    response = model.generate_content(
        [
            prompt,
            image  # 🚨 ISSO É O QUE FALTAVA NO SEU PROJETO
        ],
        generation_config={
            "temperature": 0.2
        }
    )

    return response.text.strip()
