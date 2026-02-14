import base64
import os
from pathlib import Path

import requests

IMAGE_PATH = Path(r"C:\Users\peter\OneDrive\Imagens\download.jpg")
PROMPT = (
    "Descreva a imagem em português do Brasil, com detalhes objetivos. "
    "Fale do que aparece (objetos, pessoas, cenário, ações, textos e cores). "
    "Não copie o enunciado. Responda em 3 a 5 frases completas."
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_VISION_MODEL = os.getenv(
    "LUNA_GROQ_VISION_MODEL",
    "meta-llama/llama-4-scout-17b-16e-instruct",
)

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY nao configurada no .env")

img_b64 = base64.b64encode(IMAGE_PATH.read_bytes()).decode("ascii")
data_url = f"data:image/jpeg;base64,{img_b64}"

payload = {
    "model": GROQ_VISION_MODEL,
    "input": [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": data_url},
            ],
        }
    ],
}

resp = requests.post(
    "https://api.groq.com/openai/v1/responses",
    headers={
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    },
    json=payload,
    timeout=60,
)

resp.raise_for_status()
data = resp.json()

texto = data.get("output_text")
if not texto:
    out = data.get("output", [])
    for item in out:
        for part in item.get("content", []):
            if part.get("type") == "output_text" and part.get("text"):
                texto = part["text"]
                break
        if texto:
            break

print(texto or data)
