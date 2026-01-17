# llm/vision_llm.py
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

# Configuração de múltiplas API keys
API_KEYS = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
# Remove chaves vazias
API_KEYS = [k for k in API_KEYS if k]

if not API_KEYS:
    raise ValueError("❌ Nenhuma API key configurada no .env")

MODEL_NAME = "gemini-3-flash-preview"

# Índice da chave atual
_current_key_index = 0

def _obter_cliente():
    """Retorna cliente Gemini com a chave atual"""
    global _current_key_index
    return genai.Client(api_key=API_KEYS[_current_key_index])

def _trocar_chave():
    """Troca para a próxima chave disponível"""
    global _current_key_index
    _current_key_index = (_current_key_index + 1) % len(API_KEYS)
    print(f"🔄 Trocando para API key {_current_key_index + 1}/{len(API_KEYS)}")

def analisar_imagem_llm(image_path: str, prompt: str, tentativas_max: int = None) -> str:
    """
    Analisa imagem com fallback automático de API keys
    
    Args:
        image_path: Caminho da imagem
        prompt: Instrução
        tentativas_max: Máximo de chaves a tentar (padrão: todas)
    """
    
    if tentativas_max is None:
        tentativas_max = len(API_KEYS)
    
    image = Image.open(image_path)
    ultimo_erro = None
    
    for tentativa in range(tentativas_max):
        try:
            client = _obter_cliente()
            
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt, image],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            erro_str = str(e)
            ultimo_erro = e
            
            # Erros que justificam trocar de chave
            if any(x in erro_str for x in ["429", "quota", "RESOURCE_EXHAUSTED", "rate limit"]):
                print(f"⚠️ API key {_current_key_index + 1} esgotada: {erro_str[:100]}")
                
                if tentativa < tentativas_max - 1:
                    _trocar_chave()
                    continue
                else:
                    print("❌ Todas as API keys esgotadas")
            else:
                # Erro diferente, não vale tentar outra chave
                print(f"❌ Erro na API: {erro_str[:100]}")
                break
    
    # Se chegou aqui, todas falharam
    raise Exception(f"Falha após {tentativas_max} tentativas. Último erro: {ultimo_erro}")

def analisar_imagem_detalhada(image_path: str) -> str:
    """Análise detalhada padrão"""
    prompt = """Analise esta imagem em detalhes:
1. O que você vê
2. Cores predominantes
3. Texto visível
4. Contexto

Use 4-6 frases."""
    return analisar_imagem_llm(image_path, prompt)

def extrair_texto_imagem(image_path: str) -> str:
    """OCR - extrai texto da imagem"""
    prompt = """Extraia TODO o texto visível.
Retorne apenas o texto.
Se não houver: 'Nenhum texto encontrado'."""
    return analisar_imagem_llm(image_path, prompt)