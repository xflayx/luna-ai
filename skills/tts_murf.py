import os, re, json, base64
from pathlib import Path
from typing import Any, Dict, Optional

import requests

SKILL_INFO = {
    "nome": "TTS Murf",
    "descricao": "Gera narracao (TTS) via Murf.ai a partir de texto ou arquivo",
    "versao": "1.0.0",
    "autor": "Luna",
    "intents": ["tts", "narrar", "narração", "murf", "voz"],
}

GATILHOS = ["tts", "narrar", "narração", "murf", "voz", "ler roteiro", "leia o roteiro"]

MURF_API_KEY = os.getenv("MURF_API_KEY", "").strip()
MURF_BASE_URL = os.getenv("MURF_BASE_URL", "https://api.murf.ai").rstrip("/")
MURF_VOICE_ID = os.getenv("LUNA_MURF_VOICE", "").strip()
MURF_FORMAT = os.getenv("MURF_FORMAT", "MP3").strip().upper()
OUTPUT_DIR = Path(os.getenv("LUNA_TTS_OUTPUT_DIR", "outputs/tts"))
MURF_MAX_CHARS = int(os.getenv("MURF_MAX_CHARS", "3000"))

def inicializar():
    print(f"✅ {SKILL_INFO['nome']} carregada")

def executar(cmd: str) -> str:
    if not MURF_API_KEY:
        return "MURF_API_KEY nao configurada."
    texto, voice_id, fmt, err = _parse(cmd)

    if err:
        return err

    if not texto:
        return "Use: 'tts: <texto>' ou 'tts arquivo: caminho.md' (opcional: voz=<id> fmt=mp3|wav)."

    voice_id = voice_id or MURF_VOICE_ID
    if not voice_id:
        return "Faltou voiceId. Defina MURF_VOICE_ID no .env ou use voz=<voiceId>."

    fmt = (fmt or MURF_FORMAT or "MP3").upper()
    if fmt not in {"MP3", "WAV"}:
        fmt = "MP3"

    texto_limpo = _limpar_texto(texto)
    if not texto_limpo:
        return "Texto vazio apos limpar marcacoes."

    partes = _split_texto(texto_limpo, MURF_MAX_CHARS)
    if not partes:
        return "Texto vazio apos limpar marcacoes."

    try:
        resp = _murf_generate(partes[0], voice_id, fmt)
    except requests.RequestException as e:
        return f"Falha ao chamar Murf: {e}"
    except Exception as e:
        return f"Erro ao gerar audio: {e}"

    slug = _slugify(texto_limpo[:48] or "narracao")
    out_dir = OUTPUT_DIR / slug
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"Erro ao criar pasta de saida '{out_dir}': {e}"

    audio_path = out_dir / f"narracao.{fmt.lower()}"
    srt_path = out_dir / "legenda.srt"
    meta_path = out_dir / "metadata.json"

    try:
        _save_audio(resp, audio_path)
    except requests.RequestException as e:
        return f"Falha ao baixar audio: {e}"
    except Exception as e:
        return f"Erro ao salvar audio: {e}"

    wd = resp.get("wordDurations") or []
    if wd:
        _word_durations_to_srt(wd, srt_path)

    try:
        meta_path.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return f"Erro ao salvar metadata: {e}"

    msg = f"Pronto. Audio: {audio_path}"
    if srt_path.exists() and srt_path.stat().st_size > 0:
        msg += f" | SRT: {srt_path}"

    if len(partes) > 1:
        extras = []
        for idx, parte in enumerate(partes[1:], start=2):
            try:
                resp_i = _murf_generate(parte, voice_id, fmt)
                part_audio = out_dir / f"narracao_parte_{idx:02d}.{fmt.lower()}"
                part_meta = out_dir / f"metadata_parte_{idx:02d}.json"
                _save_audio(resp_i, part_audio)
                part_meta.write_text(json.dumps(resp_i, ensure_ascii=False, indent=2), encoding="utf-8")
                extras.append(str(part_audio))
            except Exception as e:
                extras.append(f"parte_{idx:02d} erro: {e}")
        if extras:
            msg += " | Extras: " + ", ".join(extras)
    return msg

def _parse(cmd: str):
    voice_id = _kv(cmd, "voz") or _kv(cmd, "voice") or ""
    fmt = (_kv(cmd, "fmt") or _kv(cmd, "format") or "").upper()

    m = re.search(r"(arquivo|file)\s*:\s*(.+)$", cmd, flags=re.I)
    if m:
        p = Path(m.group(2).strip().strip('"').strip("'"))
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.exists():
            return p.read_text(encoding="utf-8").strip(), voice_id, fmt, None
        return "", voice_id, fmt, f"Arquivo nao encontrado: {p}"

    m = re.search(r"(tts|narrar|narração|murf)\s*:\s*(.+)$", cmd, flags=re.I)
    if m:
        return m.group(2).strip(), voice_id, fmt, None

    return cmd.strip(), voice_id, fmt, None

def _kv(text: str, key: str) -> Optional[str]:
    m = re.search(rf"\b{re.escape(key)}\s*=\s*([^\s]+)", text, flags=re.I)
    return m.group(1).strip() if m else None

def _limpar_texto(texto: str) -> str:
    t = (texto or "").strip()
    if not t:
        return ""

    # Remove code blocks
    t = re.sub(r"```.*?```", " ", t, flags=re.S)

    # Remove markdown headings and blockquotes
    t = re.sub(r"^\s*#+\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*>\s*", "", t, flags=re.M)

    # Remove [pause 500ms] and similar markers
    t = re.sub(r"\[\s*pause\s*\d+\s*ms\s*\]", " ", t, flags=re.I)

    # Remove common markdown emphasis
    t = t.replace("**", " ").replace("__", " ").replace("*", " ").replace("_", " ")

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _split_texto(texto: str, max_chars: int) -> list[str]:
    if len(texto) <= max_chars:
        return [texto]

    parts: list[str] = []
    paragraphs = [p.strip() for p in texto.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [texto]

    def flush(buffer: str):
        if buffer:
            parts.append(buffer.strip())

    buf = ""
    for p in paragraphs:
        if len(p) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", p)
            for s in sentences:
                if not s:
                    continue
                if len(s) > max_chars:
                    for i in range(0, len(s), max_chars):
                        flush(s[i:i+max_chars])
                    buf = ""
                    continue
                if len(buf) + len(s) + 1 > max_chars:
                    flush(buf)
                    buf = s
                else:
                    buf = (buf + " " + s).strip()
            flush(buf)
            buf = ""
            continue

        if len(buf) + len(p) + 1 > max_chars:
            flush(buf)
            buf = p
        else:
            buf = (buf + " " + p).strip()
    flush(buf)
    return [p for p in parts if p]

def _murf_generate(texto: str, voice_id: str, fmt: str) -> Dict[str, Any]:
    url = f"{MURF_BASE_URL}/v1/speech/generate"
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": texto,
        "voiceId": voice_id,
        "format": fmt,
        "encodeAsBase64": True,
        "wordDurations": True,
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Murf HTTP {r.status_code}: {r.text[:200]}")
    return r.json()

def _save_audio(resp: Dict[str, Any], path: Path) -> None:
    b64 = resp.get("encodedAudio") or resp.get("audioBase64")
    if b64:
        path.write_bytes(base64.b64decode(b64))
        return
    url = resp.get("audioFile") or resp.get("audioUrl")
    if url:
        ar = requests.get(url, timeout=120)
        ar.raise_for_status()
        path.write_bytes(ar.content)
        return
    raise RuntimeError("Resposta do Murf sem audio.")

def _word_durations_to_srt(wd, path: Path, max_words=6, max_ms=1800):
    items = []
    for w in wd:
        word = str(w.get("word") or w.get("text") or "").strip()
        if not word:
            continue
        s = int(w.get("startMs", 0))
        e = int(w.get("endMs", s + 80))
        items.append((word, s, e))
    if not items:
        path.write_text("", encoding="utf-8")
        return

    def ts(ms: int) -> str:
        h = ms // 3600000; ms %= 3600000
        m = ms // 60000; ms %= 60000
        s = ms // 1000; ms %= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out = []
    i = 0
    idx = 1
    while i < len(items):
        start = items[i][1]
        end = items[i][2]
        words = [items[i][0]]
        j = i + 1
        while j < len(items):
            if (j - i + 1) > max_words: break
            if (items[j][2] - start) > max_ms: break
            words.append(items[j][0])
            end = items[j][2]
            j += 1
        out += [str(idx), f"{ts(start)} --> {ts(end)}", " ".join(words), ""]
        idx += 1
        i = j

    path.write_text("\n".join(out), encoding="utf-8")

def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:50] or "narracao"
