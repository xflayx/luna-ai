# skills/vision.py
import hashlib
import os
import requests
import shutil
import tempfile
import threading
import time
import unicodedata

from PIL import ImageGrab

from llm.vision_llm import analisar_imagem, gerar_opiniao
from core.prompt_injector import (
    build_vision_analysis_prompt,
    build_vision_opinion_prompt,
    build_vision_opinion_reforco,
)
from config.state import STATE
from core import voice

# ========================================
# METADADOS DA SKILL
# ========================================

SKILL_INFO = {
    "nome": "Vision",
    "descricao": "Analisa imagens da tela usando Gemini Vision",
    "versao": "1.1.0",
    "autor": "Luna Team",
    "intents": ["visao", "vision"],
}

GATILHOS = [
    "analise",
    "veja",
    "olhe",
    "tela",
    "visao automatica",
    "modo automatico",
]

# ========================================
# CONFIGURACAO DO MODO AUTOMATICO
# ========================================

_AUTO_INTERVAL_SEC = float(os.getenv("LUNA_VISION_AUTO_SEC", "6"))
_auto_thread = None
_auto_stop = threading.Event()
_last_hash = None

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_GROQ_MODEL = os.getenv("LUNA_GROQ_MODEL", "llama-3.1-8b-instant")
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_CAPTURA_DIR = os.path.join(_BASE_DIR, "data", "capturas")
_ULTIMA_CAPTURA_PATH = os.path.join(_CAPTURA_DIR, "ultima_captura.png")

# ========================================
# INICIALIZACAO
# ========================================

def inicializar():
    print(f"{SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

# ========================================
# FUNCAO PRINCIPAL
# ========================================

def executar(comando: str) -> str:
    cmd = (comando or "").strip()
    cmd_lower = cmd.lower()

    if _eh_comando_auto_start(cmd_lower):
        return _iniciar_visao_automatica()
    if _eh_comando_auto_stop(cmd_lower):
        return _parar_visao_automatica()

    return analisar_tela(cmd)


def analisar_tela(cmd: str) -> str:
    """Captura a tela, analisa via Gemini e retorna resposta"""
    cmd_lower = (cmd or "").lower()
    image_path = None
    deletar_original = True
    try:
        reanalise_focada = _eh_reanalise_focada(cmd_lower)
        if _eh_reanalise(cmd_lower) or reanalise_focada:
            image_path = _obter_ultima_captura()
            if not image_path:
                image_path = _capturar_tela(cmd)
                _persistir_ultima_captura(image_path)
            else:
                deletar_original = False
        else:
            image_path = _capturar_tela(cmd)
            _persistir_ultima_captura(image_path)
        return _analisar_imagem_e_reagir(image_path, cmd)
    except Exception as e:
        print(f"ERRO NA VISAO: {e}")
        return "Tive um problema ao analisar a tela."
    finally:
        if deletar_original and image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

# ========================================
# MODO AUTOMATICO
# ========================================

def _iniciar_visao_automatica() -> str:
    global _auto_thread
    if _auto_thread and _auto_thread.is_alive():
        return "Visao automatica ja esta ativa."
    _auto_stop.clear()
    _auto_thread = threading.Thread(target=_loop_automatico, daemon=True)
    _auto_thread.start()
    return f"Visao automatica ativada. Vou reagir a cada {_AUTO_INTERVAL_SEC:.0f}s quando a cena mudar."


def _parar_visao_automatica() -> str:
    _auto_stop.set()
    return "Visao automatica desativada."


def _loop_automatico():
    while not _auto_stop.is_set():
        try:
            resposta = _processar_automatico()
            if resposta:
                voice.falar(resposta)
        except Exception as e:
            print(f"ERRO NA VISAO AUTOMATICA: {e}")
        time.sleep(_AUTO_INTERVAL_SEC)


def _processar_automatico() -> str | None:
    global _last_hash
    image_path = None
    try:
        image_path = _capturar_tela("visao automatica")
        atual_hash = _hash_arquivo(image_path)
        if _last_hash == atual_hash:
            return None
        _last_hash = atual_hash
        return _analisar_imagem_e_reagir(image_path, "visao automatica")
    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

# ========================================
# FLUXO DE ANALISE
# ========================================

def _analisar_imagem_e_reagir(image_path: str, cmd: str) -> str:
    contexto = STATE.obter_contexto_curto()
    cmd_lower = (cmd or "").lower()
    detalhado = _pede_detalhe(cmd_lower)
    foco = _extrair_foco(cmd_lower)

    prompt_analise = build_vision_analysis_prompt(contexto, cmd, foco)

    analise = analisar_imagem(image_path, prompt_analise).strip()
    if analise:
        STATE.set_ultima_visao(analise)

    prompt_opiniao = build_vision_opinion_prompt(cmd, analise, foco)

    try:
        resposta = gerar_opiniao(prompt_opiniao).strip()
    except Exception as e:
        print(f"ERRO GEMINI OPINIAO: {e}")
        resposta = _gerar_opiniao_groq(prompt_opiniao).strip()
    if _precisa_reforco(resposta, detalhado):
        reforco = build_vision_opinion_reforco()
        try:
            resposta = gerar_opiniao(prompt_opiniao + "\n\n" + reforco).strip()
        except Exception as e:
            print(f"ERRO GEMINI OPINIAO: {e}")
            resposta = _gerar_opiniao_groq(prompt_opiniao + "\n\n" + reforco).strip()
    if not resposta:
        return analise or "Nao consegui analisar a tela agora."
    return _limitar_resposta(resposta)

# ========================================
# UTILITARIOS
# ========================================

def _capturar_tela(cmd: str) -> str:
    cmd_lower = (cmd or "").lower()
    image_path = "screenshot.png"

    if any(p in cmd_lower for p in ["site", "pagina"]):
        try:
            from skills.web_reader import capturar_url_atual, capturar_site_inteiro_playwright
            url = capturar_url_atual()
            if url:
                print(f"Luna acessando: {url}")
                image_path = capturar_site_inteiro_playwright(url)
                return image_path
        except Exception:
            pass

    screenshot = ImageGrab.grab()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        screenshot.save(tmp.name)
        image_path = tmp.name
    screenshot.close()
    return image_path


def _hash_arquivo(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _persistir_ultima_captura(image_path: str):
    try:
        os.makedirs(_CAPTURA_DIR, exist_ok=True)
        shutil.copyfile(image_path, _ULTIMA_CAPTURA_PATH)
        file_hash = _hash_arquivo(_ULTIMA_CAPTURA_PATH)
        STATE.set_ultima_captura(_ULTIMA_CAPTURA_PATH, file_hash)
    except Exception as e:
        print(f"ERRO AO PERSISTIR CAPTURA: {e}")


def _obter_ultima_captura() -> str | None:
    path = STATE.get_ultima_captura()
    if not path or not os.path.exists(path):
        return None
    return path


def _eh_reanalise(cmd_lower: str) -> bool:
    termos = [
        "reanalisar",
        "reanalise",
        "reanalisa",
        "analise novamente",
        "analise de novo",
        "ultima captura",
        "ultima imagem",
        "ultima tela",
    ]
    return any(t in cmd_lower for t in termos)

def _eh_reanalise_focada(cmd_lower: str) -> bool:
    if _eh_comando_captura(cmd_lower):
        return False
    return bool(_extrair_foco(cmd_lower))


def _eh_comando_captura(cmd_lower: str) -> bool:
    termos = [
        "analise",
        "analisar",
        "tela",
        "captura",
        "capturar",
        "print",
        "screenshot",
        "capture",
    ]
    return any(t in cmd_lower for t in termos)


def _eh_comando_auto_start(cmd_lower: str) -> bool:
    termos = [
        "ativar visao automatica",
        "ligar visao automatica",
        "visao automatica",
        "modo automatico",
        "ativar modo automatico",
    ]
    return any(t in cmd_lower for t in termos)


def _eh_comando_auto_stop(cmd_lower: str) -> bool:
    termos = [
        "parar visao automatica",
        "desativar visao automatica",
        "desligar visao automatica",
        "parar modo automatico",
        "desativar modo automatico",
    ]
    return any(t in cmd_lower for t in termos)


def _pede_detalhe(cmd_lower: str) -> bool:
    termos = [
        "detalhe",
        "detalhada",
        "mais detalhes",
        "mais completo",
        "aprofundar",
        "descreva",
        "descricao",
    ]
    return any(t in cmd_lower for t in termos)


def _extrair_foco(cmd_lower: str) -> str | None:
    cmd_norm = _normalizar_texto(cmd_lower)
    termos = [
        "roupa",
        "traje",
        "vestindo",
        "look",
        "outfit",
        "vestimenta",
        "estilo",
        "mao",
        "maos",
        "na mao",
        "na maos",
        "rosto",
        "cabelo",
        "olhos",
        "expressao",
        "expressao facial",
        "gesto",
        "gestos",
        "segura",
        "segurando",
        "segurar",
        "objeto",
        "objetos",
        "acessorio",
        "acessorios",
        "chapeu",
        "chapeus",
        "comida",
        "prato",
        "bebida",
        "placa",
        "texto",
    ]
    for termo in termos:
        if termo in cmd_norm:
            return termo
    return None


def _normalizar_texto(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

def _limitar_resposta(resposta: str) -> str:
    texto = (resposta or "").strip()
    if not texto:
        return texto
    # Limita a no maximo 1 frase ou 25 palavras, o que vier primeiro.
    palavras = texto.split()
    if len(palavras) > 25:
        texto = " ".join(palavras[:25]).rstrip()
    frases = [f.strip() for f in texto.replace("!", ".").replace("?", ".").split(".") if f.strip()]
    if len(frases) > 1:
        texto = frases[0].strip()
    if texto and not texto.endswith((".", "!", "?")):
        texto += "."
    return texto


def _precisa_reforco(resposta: str, detalhado: bool) -> bool:
    texto = (resposta or "").strip()
    if not texto:
        return True
    if detalhado and len(texto) < 140:
        return True
    return False


def _gerar_opiniao_groq(prompt: str) -> str:
    if not _GROQ_API_KEY:
        return ""
    texto, erro = _groq_chat(prompt, max_tokens=350, temperature=0.6)
    if erro:
        print(f"GROQ erro: {erro}")
        return ""
    return texto


def _groq_chat(prompt: str, max_tokens: int, temperature: float) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {_GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=45,
        )
        if resp.status_code != 200:
            return "", f"status_{resp.status_code}:{resp.text}"
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return "", "empty_response"
        content = choices[0].get("message", {}).get("content", "").strip()
        return content, ""
    except Exception as e:
        return "", str(e)
