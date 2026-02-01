# skills/youtube_summary.py
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pyautogui
import pyperclip
import requests

from config.env import init_env
from config.state import STATE
from core.prompt_injector import (
    build_youtube_summary_prompt,
    build_youtube_summary_simple_prompt,
    build_youtube_summary_merge_prompt,
    build_youtube_summary_reforco,
)

init_env()

# ========================================
# METADADOS DA SKILL
# ========================================

SKILL_INFO = {
    "nome": "YouTube Summary",
    "descricao": "Resume videos do YouTube usando legendas",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["youtube_summary"],
}

GATILHOS = [
    "youtube",
    "yt",
    "video",
    "resuma video",
    "resumir video",
    "resumo do video",
]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("LUNA_GROQ_MODEL", "llama-3.1-8b-instant")


def inicializar():
    print(f"{SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(cmd: str) -> str:
    url = _extrair_url(cmd) or _capturar_url_atual()
    if not url:
        return "Preciso do link do YouTube para resumir o video."
    print(f"YouTube: {url}")

    video_id = _extrair_video_id(url)
    if not video_id:
        return "Nao consegui identificar o video do YouTube."

    transcricao, fonte = _buscar_transcricao(video_id, url)
    if not transcricao:
        return "Nao encontrei legendas para esse video."
    print(f"Transcricao ({fonte}): {len(transcricao)} caracteres")

    return _resumir_transcricao(transcricao, cmd, url)


def _extrair_url(cmd: str) -> str | None:
    match = re.search(r"(https?://\S+)", cmd)
    return match.group(1) if match else None


def _capturar_url_atual() -> str | None:
    try:
        pyautogui.hotkey("ctrl", "l")
        pyautogui.hotkey("ctrl", "c")
        pyautogui.click()
        url = pyperclip.paste().strip()
        return url if url.startswith("http") else None
    except Exception:
        return None


def _extrair_video_id(url: str) -> str | None:
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    if "youtube.com" in url:
        match = re.search(r"[?&]v=([^&]+)", url)
        if match:
            return match.group(1)
    return None


def _buscar_transcricao(video_id: str, url: str) -> tuple[str | None, str]:
    langs = ["pt", "pt-BR", "en"]
    for lang in langs:
        texto = _baixar_transcricao(video_id, lang, asr=False)
        if texto:
            return texto, f"timedtext:{lang}"
    for lang in langs:
        texto = _baixar_transcricao(video_id, lang, asr=True)
        if texto:
            return texto, f"timedtext_asr:{lang}"
    texto = _baixar_transcricao_ytdlp(url)
    if texto:
        return texto, "yt-dlp"
    return None, "nenhuma"


def _baixar_transcricao(video_id: str, lang: str, asr: bool) -> str | None:
    params = {
        "lang": lang,
        "v": video_id,
    }
    if asr:
        params["kind"] = "asr"
    try:
        resp = requests.get("https://video.google.com/timedtext", params=params, timeout=15)
        if resp.status_code != 200 or not resp.text.strip():
            return None
        return _parsear_transcricao(resp.text)
    except Exception:
        return None


def _parsear_transcricao(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
        partes = []
        for node in root.findall("text"):
            if node.text:
                partes.append(node.text.replace("\n", " ").strip())
        texto = " ".join(partes).strip()
        return texto if texto else None
    except Exception:
        return None


def _baixar_transcricao_ytdlp(url: str) -> str | None:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_tmpl = os.path.join(tmpdir, "legenda.%(ext)s")
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--sub-lang",
                "pt,en",
                "--sub-format",
                "vtt",
                "-o",
                out_tmpl,
                url,
            ]
            subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60)
            for name in os.listdir(tmpdir):
                if name.endswith(".vtt"):
                    path = os.path.join(tmpdir, name)
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        return _parsear_vtt(f.read())
    except Exception:
        return None
    return None


def _parsear_vtt(vtt_text: str) -> str | None:
    linhas = []
    for line in vtt_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        linhas.append(line)
    texto = " ".join(linhas).strip()
    return texto if texto else None


def _resumir_transcricao(transcricao: str, cmd: str, url: str) -> str:
    if not GROQ_API_KEY:
        return "GROQ_API_KEY nao configurada."

    contexto = STATE.obter_contexto_curto()
    prompt = build_youtube_summary_simple_prompt(transcricao, cmd, url)

    texto, erro = _groq_chat(prompt, max_tokens=420, temperature=0.6)
    if erro:
        print(f"GROQ erro: {erro}")
        if _erro_contexto(erro):
            return _resumir_em_partes(transcricao, cmd, url, contexto)
        return "Nao consegui resumir esse video."

    if _resumo_curto(texto):
        texto = _repetir_resumo(prompt)
        if _resumo_curto(texto):
            return _resumir_em_partes(transcricao, cmd, url, contexto)

    return texto


def _resumo_curto(texto: str) -> bool:
    if not texto:
        return True
    if len(texto) < 200:
        return True
    return texto.endswith((".", "!", "?")) is False


def _repetir_resumo(prompt: str) -> str:
    reforco = build_youtube_summary_reforco()
    texto, _ = _groq_chat(prompt + reforco, max_tokens=500, temperature=0.4)
    return texto


def _resumir_em_partes(transcricao: str, cmd: str, url: str, contexto: str) -> str:
    partes = _selecionar_partes(transcricao, 2000)
    resumos = []
    for parte in partes:
        prompt = build_youtube_summary_prompt(parte, cmd, url, contexto)
        resumo, _ = _groq_chat(prompt, max_tokens=240, temperature=0.6)
        if resumo:
            resumos.append(resumo)

    if not resumos:
        return "Nao consegui resumir esse video."

    prompt_final = build_youtube_summary_merge_prompt(contexto, url, resumos)
    resumo_final, _ = _groq_chat(prompt_final, max_tokens=500, temperature=0.5)
    return resumo_final or "Nao consegui resumir esse video."


def _selecionar_partes(texto: str, tamanho: int) -> list[str]:
    if len(texto) <= tamanho:
        return [texto]
    meio = len(texto) // 2
    inicio = texto[:tamanho]
    meio_parte = texto[max(0, meio - tamanho // 2):meio + tamanho // 2]
    fim = texto[-tamanho:]
    return [inicio, meio_parte, fim]


def _groq_chat(prompt: str, max_tokens: int, temperature: float) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
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
            timeout=60,
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


def _erro_contexto(erro: str) -> bool:
    texto = erro.lower()
    return any(k in texto for k in ["context", "token", "length", "too large"])
