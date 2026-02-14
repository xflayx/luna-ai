import os
import json
import asyncio
import ipaddress
import time
import base64
import sys
from urllib.parse import urlparse
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
try:
    from config.env import init_env
    init_env()
except Exception:
    pass


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, str(int(default))).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _normalize_b64(raw: str) -> str:
    value = (raw or "").strip()
    if value.startswith("data:"):
        _, _, value = value.partition(",")
    value = "".join(value.split())
    value = value.replace("-", "+").replace("_", "/")
    pad = len(value) % 4
    if pad:
        value += "=" * (4 - pad)
    return value


def _guess_audio_mime_from_b64(raw: str) -> tuple[str, int]:
    b64 = _normalize_b64(raw)
    if not b64:
        return "audio/mpeg", 0
    try:
        data = base64.b64decode(b64)
    except Exception:
        return "audio/mpeg", 0
    size = len(data)
    if data.startswith(b"RIFF"):
        return "audio/wav", size
    if data.startswith(b"OggS"):
        return "audio/ogg", size
    if data.startswith(b"fLaC"):
        return "audio/flac", size
    if data[:3] == b"ID3" or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg", size
    return "application/octet-stream", size


HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
PORT = _env_int("BACKEND_PORT", 18080)
TOKEN = os.environ.get("BACKEND_TOKEN", "")
LUNA_PANEL_HOST = os.environ.get("LUNA_PANEL_HOST", "127.0.0.1")
LUNA_PANEL_PORT = _env_int("LUNA_PANEL_PORT", 5055)
LUNA_PANEL_TOKEN = os.environ.get("LUNA_PANEL_TOKEN", "").strip()
LUNA_PET_FALAR = _env_bool("LUNA_PET_FALAR", True)
LUNA_COMMAND_TIMEOUT = _env_int("LUNA_COMMAND_TIMEOUT", 180)
LUNA_STATE_WAIT_SEC = _env_int("LUNA_STATE_WAIT_SEC", 600)
LUNA_STATE_POLL_SEC = float(os.environ.get("LUNA_STATE_POLL_SEC", "2"))
LUNA_PET_TTS_ENABLED = _env_bool("LUNA_PET_TTS_ENABLED", True)
LUNA_PET_TTS_PROVIDER = os.environ.get("LUNA_PET_TTS_PROVIDER", "murf").strip().lower()
MURF_API_KEY = os.environ.get("MURF_API_KEY", "").strip()
MURF_BASE_URL = os.environ.get("MURF_BASE_URL", "https://api.murf.ai").rstrip("/")
MURF_STREAM_URL = os.environ.get("MURF_STREAM_URL", "https://global.api.murf.ai/v1/speech/stream").rstrip("/")
MURF_VOICE_ID = (
    os.environ.get("LUNA_PET_MURF_VOICE", "").strip()
    or os.environ.get("LUNA_MURF_VOICE", "pt-BR-isadora").strip()
)
MURF_STYLE = (
    os.environ.get("LUNA_PET_MURF_STYLE", "").strip()
    or os.environ.get("MURF_STYLE", "Conversational").strip()
)
MURF_LOCALE = (
    os.environ.get("LUNA_PET_MURF_LOCALE", "").strip()
    or os.environ.get("MURF_LOCALE", "pt-BR").strip()
)
MURF_MODEL = (
    os.environ.get("LUNA_PET_MURF_MODEL", "").strip()
    or os.environ.get("MURF_MODEL", "FALCON").strip()
)
MURF_PET_FORMAT = os.environ.get("LUNA_PET_TTS_FORMAT", "WAV").strip().upper()
MURF_RATE = _env_int("LUNA_PET_MURF_RATE", _env_int("MURF_RATE", 15))
MURF_PITCH = _env_int("LUNA_PET_MURF_PITCH", _env_int("MURF_PITCH", 10))
MURF_SAMPLE_RATE = _env_int("LUNA_PET_MURF_SAMPLE_RATE", _env_int("MURF_SAMPLE_RATE", 24000))
MURF_CHANNEL_TYPE = (
    os.environ.get("LUNA_PET_MURF_CHANNEL_TYPE", "").strip().upper()
    or os.environ.get("MURF_CHANNEL_TYPE", "MONO").strip().upper()
)
MURF_TIMEOUT = _env_int("LUNA_PET_TTS_TIMEOUT", 120)

MAX_MSG = 16000

app = FastAPI()

_log(
    "[PET CFG] "
    f"tts_enabled={LUNA_PET_TTS_ENABLED} "
    f"tts_provider={LUNA_PET_TTS_PROVIDER} "
    f"falar_backend={LUNA_PET_FALAR} "
    f"voice={MURF_VOICE_ID} "
    f"style={MURF_STYLE} "
    f"locale={MURF_LOCALE} "
    f"format={MURF_PET_FORMAT}"
)


def _is_private_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False


def _validate_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.hostname or ""
    if not host:
        return None
    if _is_private_host(host):
        return None
    return url


def _fetch_url_summary(url: str) -> str:
    safe = _validate_url(url)
    if not safe:
        return "URL invalida ou bloqueada."
    try:
        resp = requests.get(
            safe,
            timeout=8,
            headers={"User-Agent": "LunaDeskPet/1.0"},
            stream=True,
        )
        if resp.status_code >= 400:
            return f"Falha ao acessar ({resp.status_code})."
        content = resp.text
        return f"Resumo basico: pagina com {len(content)} caracteres."
    except Exception as e:
        return f"Erro ao acessar: {e}"


def _is_youtube_command(text: str) -> bool:
    t = (text or "").lower()
    return "youtube.com" in t or "youtu.be/" in t


def _looks_transient_youtube_failure(resp: str) -> bool:
    t = (resp or "").lower()
    markers = [
        "nao encontrei legendas",
        "não encontrei legendas",
        "nao consegui resumir esse video",
        "não consegui resumir esse video",
    ]
    return any(m in t for m in markers)


def _get_luna_state() -> dict:
    url = f"http://{LUNA_PANEL_HOST}:{LUNA_PANEL_PORT}/state"
    headers = {}
    if LUNA_PANEL_TOKEN:
        headers["X-Panel-Token"] = LUNA_PANEL_TOKEN
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _video_id_from_text(text: str) -> str:
    t = (text or "").strip()
    parsed = urlparse(t)
    if parsed.scheme and parsed.netloc:
        q = parsed.query or ""
        for kv in q.split("&"):
            if kv.startswith("v="):
                return kv[2:]
        if "youtu.be/" in parsed.path:
            return parsed.path.rsplit("/", 1)[-1]

    for token in t.split():
        token = token.strip()
        if "youtube.com/watch" in token:
            try:
                q = urlparse(token).query
                for kv in q.split("&"):
                    if kv.startswith("v="):
                        return kv[2:]
            except Exception:
                continue
        if "youtu.be/" in token:
            try:
                return urlparse(token).path.rsplit("/", 1)[-1]
            except Exception:
                continue
    return ""


def _state_matches_command(original_cmd: str, state_cmd: str) -> bool:
    if not state_cmd:
        return False
    state_norm = state_cmd.lower().replace("[painel]", "").strip()
    cmd_norm = original_cmd.lower().strip()
    if not cmd_norm:
        return False
    if cmd_norm in state_norm:
        return True
    vid = _video_id_from_text(cmd_norm)
    return bool(vid and vid in state_norm)


def _wait_for_final_luna_response(original_cmd: str, fallback_resp: str) -> str:
    deadline = time.time() + max(1, LUNA_STATE_WAIT_SEC)
    while time.time() < deadline:
        st = _get_luna_state()
        last_resp = (st.get("ultima_resposta") or "").strip()
        last_cmd = (st.get("ultimo_comando") or "").strip()
        if not last_resp:
            time.sleep(max(0.5, LUNA_STATE_POLL_SEC))
            continue
        if not _state_matches_command(original_cmd, last_cmd):
            time.sleep(max(0.5, LUNA_STATE_POLL_SEC))
            continue
        if last_resp != fallback_resp and not _looks_transient_youtube_failure(last_resp):
            return last_resp
        time.sleep(max(0.5, LUNA_STATE_POLL_SEC))
    return fallback_resp


def _ask_luna(text: str) -> str:
    url = f"http://{LUNA_PANEL_HOST}:{LUNA_PANEL_PORT}/control"
    headers = {"Content-Type": "application/json"}
    if LUNA_PANEL_TOKEN:
        headers["X-Panel-Token"] = LUNA_PANEL_TOKEN

    payload = {
        "action": "comando",
        "payload": {
            "comando": text,
            "falar": False,
            "source": "pet",
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=LUNA_COMMAND_TIMEOUT)
    except Exception as e:
        return f"Nao consegui conectar na Luna ({e})."

    if resp.status_code != 200:
        return f"Luna retornou erro HTTP {resp.status_code}."

    try:
        data = resp.json()
    except Exception:
        return "Luna retornou uma resposta invalida."

    resposta = (data.get("resposta") or "").strip()
    if resposta:
        if _is_youtube_command(text) and _looks_transient_youtube_failure(resposta):
            resposta = _wait_for_final_luna_response(text, resposta)
        return resposta
    msg = (data.get("msg") or "").strip()
    return msg or "Nao houve resposta da Luna."


def _falar_luna(text: str) -> None:
    if not text:
        return
    _log("[PET AUDIO] fallback para fala da Luna (backend)")
    url = f"http://{LUNA_PANEL_HOST}:{LUNA_PANEL_PORT}/control"
    headers = {"Content-Type": "application/json"}
    if LUNA_PANEL_TOKEN:
        headers["X-Panel-Token"] = LUNA_PANEL_TOKEN
    payload = {
        "action": "falar",
        "payload": {
            "texto": text,
        },
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=45)
    except Exception:
        pass


def _pet_tts_enabled() -> bool:
    return (
        LUNA_PET_TTS_ENABLED
        and LUNA_PET_TTS_PROVIDER == "murf"
        and bool(MURF_API_KEY)
    )


def _murf_tts_base64(text: str) -> tuple[str, str]:
    if not text:
        return "", "Texto vazio."
    if not MURF_API_KEY:
        return "", "MURF_API_KEY nao configurada."

    url = f"{MURF_BASE_URL}/v1/speech/generate"
    headers = {
        "api-key": MURF_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "voiceId": MURF_VOICE_ID,
        "format": MURF_PET_FORMAT if MURF_PET_FORMAT in {"WAV", "MP3"} else "WAV",
        "encodeAsBase64": True,
    }
    if MURF_STYLE:
        payload["style"] = MURF_STYLE
    if MURF_LOCALE:
        payload["multiNativeLocale"] = MURF_LOCALE
    if MURF_MODEL:
        payload["model"] = MURF_MODEL
    if MURF_RATE:
        payload["rate"] = MURF_RATE
    if MURF_PITCH:
        payload["pitch"] = MURF_PITCH
    if MURF_SAMPLE_RATE:
        payload["sampleRate"] = MURF_SAMPLE_RATE
    if MURF_CHANNEL_TYPE:
        payload["channelType"] = MURF_CHANNEL_TYPE

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=MURF_TIMEOUT)
    except Exception as exc:
        return "", f"Falha no Murf: {exc}"

    if resp.status_code >= 400:
        # Fallback: endpoint de streaming do Murf, convertido para base64.
        return _murf_tts_stream_base64(text, f"Murf HTTP {resp.status_code}")

    try:
        data = resp.json()
    except Exception:
        return "", "Resposta invalida do Murf."

    b64_audio = (data.get("encodedAudio") or data.get("audioBase64") or "").strip()
    if b64_audio:
        if b64_audio.startswith("data:"):
            _, _, b64_audio = b64_audio.partition(",")
        return b64_audio, ""

    audio_url = (data.get("audioFile") or data.get("audioUrl") or "").strip()
    if not audio_url:
        return "", "Murf retornou sem audio."
    try:
        raw = requests.get(audio_url, timeout=45)
        if raw.status_code >= 400:
            return "", f"Falha ao baixar audio Murf ({raw.status_code})"
        return base64.b64encode(raw.content).decode("ascii"), ""
    except Exception as exc:
        return "", f"Falha ao baixar audio Murf: {exc}"


def _murf_tts_stream_base64(text: str, reason: str = "") -> tuple[str, str]:
    headers = {
        "api-key": MURF_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "voice_id": MURF_VOICE_ID,
        "style": MURF_STYLE or "Conversational",
        "text": text,
        "rate": MURF_RATE,
        "pitch": MURF_PITCH,
        "multi_native_locale": MURF_LOCALE or "pt-BR",
        "model": MURF_MODEL or "FALCON",
        "format": MURF_PET_FORMAT if MURF_PET_FORMAT in {"WAV", "MP3"} else "MP3",
        "sampleRate": MURF_SAMPLE_RATE,
        "channelType": MURF_CHANNEL_TYPE or "MONO",
    }
    try:
        with requests.post(
            MURF_STREAM_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=MURF_TIMEOUT,
        ) as resp:
            if resp.status_code >= 400:
                detail = f"stream HTTP {resp.status_code}"
                if reason:
                    detail = f"{reason}; {detail}"
                return "", f"Murf falhou: {detail}"
            chunks = []
            for chunk in resp.iter_content(chunk_size=4096):
                if chunk:
                    chunks.append(chunk)
            if not chunks:
                return "", "Murf stream sem dados de audio."
            raw = b"".join(chunks)
            return base64.b64encode(raw).decode("ascii"), ""
    except Exception as exc:
        detail = f"{reason}; {exc}" if reason else str(exc)
        return "", f"Murf stream falhou: {detail}"


def _build_pet_audio_event(text: str) -> tuple[dict | None, str]:
    if not _pet_tts_enabled():
        _log("[PET AUDIO] TTS do pet desativado ou sem API key")
        return None, ""
    audio_b64, err = _murf_tts_base64(text)
    if not audio_b64:
        return None, err or "Falha ao gerar audio."
    audio_b64 = _normalize_b64(audio_b64)
    mime, size = _guess_audio_mime_from_b64(audio_b64)
    _log(f"[PET AUDIO] mime={mime} bytes={size}")
    event = {
        "type": "audio",
        "provider": "murf",
        "mime": mime,
        "base64": audio_b64,
    }
    return event, ""


async def _stream_text(ws: WebSocket, text: str):
    for ch in text:
        await ws.send_text(json.dumps({"type": "delta", "text": ch}))
        await asyncio.sleep(0.004)
    await ws.send_text(json.dumps({"type": "done"}))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
        msg = json.loads(raw)
        if msg.get("type") != "auth" or msg.get("token") != TOKEN:
            await ws.close(code=1008)
            return
    except Exception:
        await ws.close(code=1008)
        return

    await ws.send_text(json.dumps({"type": "state", "value": "idle"}))

    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_MSG:
                await ws.close(code=1009)
                return
            data = json.loads(raw)
            if data.get("type") != "user_message":
                continue
            text = (data.get("text") or "").strip()
            if not text:
                continue
            await ws.send_text(json.dumps({"type": "state", "value": "thinking"}))
            resposta = await asyncio.to_thread(_ask_luna, text)
            if not resposta and ("http://" in text or "https://" in text):
                resposta = await asyncio.to_thread(_fetch_url_summary, text)

            await _stream_text(ws, resposta)

            audio_sent = False
            event, err = await asyncio.to_thread(_build_pet_audio_event, resposta)
            if event:
                await ws.send_text(json.dumps(event))
                audio_sent = True
                _log("[PET AUDIO] audio enviado para renderer")
            elif err:
                _log(f"[PET AUDIO] {err}")
                await ws.send_text(json.dumps({"type": "audio_error", "message": err}))

            if LUNA_PET_FALAR:
                await asyncio.to_thread(_falar_luna, resposta)

            if not audio_sent:
                await ws.send_text(json.dumps({"type": "state", "value": "idle"}))
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    print(f"READY {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
