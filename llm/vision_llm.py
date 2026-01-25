# llm/vision_llm.py
import os
import time
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

# Configurações de retry
MAX_RETRIES_PER_KEY = 2  # Tentativas por chave em caso de 503
RETRY_DELAY_BASE = 1.5  # Segundos (cresce exponencialmente)

def _extract_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        chunks = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(part_text)
        if chunks:
            return "\n".join(chunks)
    return ""

def _log_response_meta(response):
    """Loga finish_reason e usage quando disponiveis."""
    try:
        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
        usage = getattr(response, "usage_metadata", None)
        usage_info = ""
        if usage:
            prompt_tokens = getattr(usage, "prompt_token_count", None)
            response_tokens = getattr(usage, "response_token_count", None)
            total_tokens = getattr(usage, "total_token_count", None)
            usage_info = (
                f" usage(prompt={prompt_tokens}, response={response_tokens}, total={total_tokens})"
            )
        if finish_reason or usage_info:
            print(f"INFO: Gemini meta: finish_reason={finish_reason}{usage_info}")
    except Exception:
        pass

def _obter_cliente():
    """Retorna cliente Gemini com a chave atual"""
    global _current_key_index
    return genai.Client(api_key=API_KEYS[_current_key_index])

def _trocar_chave():
    """Troca para a próxima chave disponível"""
    global _current_key_index
    _current_key_index = (_current_key_index + 1) % len(API_KEYS)
    print(f"🔄 Trocando para API key {_current_key_index + 1}/{len(API_KEYS)}")

def _is_retryable_error(erro_str: str) -> bool:
    """Verifica se é um erro que vale retry (503, timeout, etc)"""
    return any(x in erro_str for x in [
        "503", "UNAVAILABLE", 
        "timeout", "Timeout",
        "temporarily unavailable",
        "overloaded"
    ])

def _is_quota_error(erro_str: str) -> bool:
    """Verifica se é erro de quota"""
    return any(x in erro_str for x in [
        "429", "quota", "RESOURCE_EXHAUSTED", "rate limit"
    ])

def analisar_imagem_llm(image_path: str, prompt: str, tentativas_max: int = None) -> str:
    """
    Analisa imagem com fallback automático de API keys e retry inteligente
    
    Args:
        image_path: Caminho da imagem
        prompt: Instrução
        tentativas_max: Máximo de chaves a tentar (padrão: todas)
    """
    
    if tentativas_max is None:
        tentativas_max = len(API_KEYS)
    
    ultimo_erro = None

    with Image.open(image_path) as image:
        
        for tentativa_key in range(tentativas_max):
            # Para cada chave, tenta até MAX_RETRIES_PER_KEY vezes em caso de 503
            for retry in range(MAX_RETRIES_PER_KEY):
                try:
                    client = _obter_cliente()
                    
                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=[prompt, image],
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=1024,
                        )
                    )
    
                    _log_response_meta(response)
                    texto = _extract_text(response).strip()
                    if not texto:
                        raise Exception("Resposta vazia do modelo")
                    
                    return texto
                    
                except Exception as e:
                    erro_str = str(e)
                    ultimo_erro = e
                    
                    # Erro de quota: pula pra próxima chave
                    if _is_quota_error(erro_str):
                        print(f"⚠️ API key {_current_key_index + 1} sem quota: {erro_str[:100]}")
                        break  # Sai do loop de retry, vai pra próxima chave
                    
                    # Erro 503/timeout: tenta retry na mesma chave
                    elif _is_retryable_error(erro_str):
                        if retry < MAX_RETRIES_PER_KEY - 1:
                            delay = RETRY_DELAY_BASE * (2 ** retry)
                            print(f"⏳ Erro 503 na key {_current_key_index + 1}, retry {retry + 1}/{MAX_RETRIES_PER_KEY} em {delay:.1f}s...")
                            time.sleep(delay)
                            continue  # Tenta novamente com a mesma chave
                        else:
                            print(f"⚠️ API key {_current_key_index + 1} com erro persistente: {erro_str[:100]}")
                            break  # Esgotou retries, vai pra próxima chave
                    
                    # Outros erros: pula pra próxima chave
                    else:
                        print(f"❌ Erro na API key {_current_key_index + 1}: {erro_str[:100]}")
                        break
            
            # Se ainda tem chaves pra tentar, troca
            if tentativa_key < tentativas_max - 1:
                _trocar_chave()
            else:
                print("❌ Todas as API keys esgotadas/falharam")
        
        # Se chegou aqui, todas falharam
        raise Exception(f"Falha após {tentativas_max} chaves. Último erro: {ultimo_erro}")
    
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


def analisar_imagem(image_path: str, prompt: str) -> str:
    return analisar_imagem_llm(image_path, prompt)


def gerar_opiniao(prompt: str) -> str:
    """
    Gera opinião textual via Gemini com fallback de API keys e retry
    """
    if not API_KEYS:
        raise ValueError("Nenhuma API key configurada no .env")
    
    ultimo_erro = None
    
    for tentativa_key in range(len(API_KEYS)):
        # Para cada chave, tenta até MAX_RETRIES_PER_KEY vezes em caso de 503
        for retry in range(MAX_RETRIES_PER_KEY):
            try:
                client = _obter_cliente()
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=1024,
                    )
                )
                _log_response_meta(response)
                texto = _extract_text(response).strip()
                
                if not texto:
                    raise Exception("Resposta vazia do modelo")
                
                return texto
                
            except Exception as e:
                erro_str = str(e)
                ultimo_erro = e
                
                # Erro de quota: pula pra próxima chave
                if _is_quota_error(erro_str):
                    print(f"⚠️ API key {_current_key_index + 1} sem quota: {erro_str[:100]}")
                    break
                
                # Erro 503/timeout: tenta retry na mesma chave
                elif _is_retryable_error(erro_str):
                    if retry < MAX_RETRIES_PER_KEY - 1:
                        delay = RETRY_DELAY_BASE * (2 ** retry)
                        print(f"⏳ Erro 503 na key {_current_key_index + 1}, retry {retry + 1}/{MAX_RETRIES_PER_KEY} em {delay:.1f}s...")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"⚠️ API key {_current_key_index + 1} com erro persistente: {erro_str[:100]}")
                        break
                
                # Outros erros: pula pra próxima chave
                else:
                    print(f"❌ Erro na API key {_current_key_index + 1}: {erro_str[:100]}")
                    break
        
        # Se ainda tem chaves pra tentar, troca
        if tentativa_key < len(API_KEYS) - 1:
            _trocar_chave()
        else:
            print(f"❌ Todas as {len(API_KEYS)} API keys falharam")
    
    # Se chegou aqui, todas falharam
    raise Exception(f"Falha após {len(API_KEYS)} chaves. Último erro: {ultimo_erro}")
