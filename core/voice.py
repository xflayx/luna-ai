import atexit
import base64
import audioop
import os
import queue
import subprocess
import tempfile
import threading
import time
import winsound
import logging

import speech_recognition as sr
import pyttsx3
import requests
try:
    import sounddevice as sd
    import soundfile as sf
except Exception:
    sd = None
    sf = None

from config.env import init_env
from core.obs_client import update_text

init_env()

# Silencia logs verbosos do httpx/httpcore (usado pelo SDK da Groq).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Configuracoes do reconhecedor
rec = sr.Recognizer()
mic = sr.Microphone()

_FALA_QUEUE_MAX = int(os.getenv("LUNA_TTS_QUEUE_MAX", "5"))
_fala_queue = queue.Queue(maxsize=_FALA_QUEUE_MAX)
_fala_thread = None
_fala_thread_lock = threading.Lock()
_TTS_ASSINCRONO = os.getenv("LUNA_TTS_ASYNC") == "1"
_TTS_ENGINE = os.getenv("LUNA_TTS_ENGINE", "pyttsx3").lower()
_TTS_DEBUG_TIMER = os.getenv("LUNA_TTS_DEBUG_TIMER") == "1"
_MURF_VOICE = os.getenv("LUNA_MURF_VOICE", "pt-BR-isadora")
_MURF_API_KEY = os.getenv("MURF_API_KEY", "")
_MURF_FORMAT = os.getenv("MURF_FORMAT", "MP3").strip().upper()
_MURF_STYLE = os.getenv("MURF_STYLE", "Conversational").strip()
_MURF_LOCALE = os.getenv("MURF_LOCALE", "pt-BR").strip()
_MURF_MODEL = os.getenv("MURF_MODEL", "").strip()
_MURF_BASE_URL = os.getenv("MURF_BASE_URL", "https://api.murf.ai").rstrip("/")
_MURF_STREAM_URL = os.getenv("MURF_STREAM_URL", "https://global.api.murf.ai/v1/speech/stream").rstrip("/")
_FFPLAY_PATH = os.getenv("LUNA_FFPLAY_PATH", "")
_AUDIO_DEVICE = os.getenv("LUNA_AUDIO_DEVICE", "").strip()
_STT_ENGINE = os.getenv("LUNA_STT_ENGINE", "groq").lower()
_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_GROQ_STT_MODEL = os.getenv("LUNA_GROQ_STT_MODEL", "whisper-large-v3")
_STT_MIN_RMS = int(os.getenv("LUNA_STT_MIN_RMS", "200"))
_STT_MIN_DURATION_SEC = float(os.getenv("LUNA_STT_MIN_DURATION_SEC", "0.9"))
_STT_RMS_FACTOR = float(os.getenv("LUNA_STT_RMS_FACTOR", "2.5"))
_VAD_ENABLED = os.getenv("LUNA_VAD_ENABLED", "1") == "1"
_VAD_MODE = int(os.getenv("LUNA_VAD_MODE", "2"))
_VAD_FRAME_MS = int(os.getenv("LUNA_VAD_FRAME_MS", "30"))
_VAD_MIN_SPEECH_FRAMES = int(os.getenv("LUNA_VAD_MIN_SPEECH_FRAMES", "8"))


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


_MURF_RATE = _env_int("MURF_RATE", 15)
_MURF_PITCH = _env_int("MURF_PITCH", 10)
_MURF_SAMPLE_RATE = _env_int("MURF_SAMPLE_RATE", 24000)
_MURF_CHANNEL_TYPE = os.getenv("MURF_CHANNEL_TYPE", "MONO").strip().upper()



def _fala_worker():
    while True:
        item = _fala_queue.get()
        try:
            if item is None:
                return
            texto, start_ts = item
            _speak(texto, start_ts)
        except Exception as e:
            print(f"ERRO NO AUDIO: {e}")
        finally:
            _fala_queue.task_done()


def _iniciar_fala_thread():
    global _fala_thread
    if _fala_thread and _fala_thread.is_alive():
        return
    with _fala_thread_lock:
        if _fala_thread and _fala_thread.is_alive():
            return
        _fala_thread = threading.Thread(target=_fala_worker, daemon=True)
        _fala_thread.start()


def _encerrar_fala_thread():
    if _fala_thread and _fala_thread.is_alive():
        _fala_queue.put(None)
        _fala_thread.join(timeout=5)


atexit.register(_encerrar_fala_thread)


def falar(texto):
    texto_limpo = texto.replace("*", "").replace("#", "")
    print(f"\nLUNA: {texto}")
    start_ts = time.perf_counter()
    try:
        update_text(texto_limpo)
    except Exception:
        pass

    if _TTS_ASSINCRONO:
        _iniciar_fala_thread()
        if _fala_queue.full():
            try:
                _fala_queue.get_nowait()
                _fala_queue.task_done()
            except queue.Empty:
                pass
        _fala_queue.put((texto_limpo, start_ts))
        return

    try:
        _speak(texto_limpo, start_ts)
    except Exception as e:
        print(f"ERRO NO AUDIO: {e}")


def _log_tts_delay(start_ts: float, etapa: str):
    if not _TTS_DEBUG_TIMER:
        return
    if start_ts is None:
        return
    delta = time.perf_counter() - start_ts
    print(f"[TTS DEBUG] {etapa}: {delta:.3f}s")


def _log_tts_duration(etapa: str, delta: float):
    if not _TTS_DEBUG_TIMER:
        return
    print(f"[TTS DEBUG] {etapa}: {delta:.3f}s")


def _speak(texto: str, start_ts: float | None = None):
    if _TTS_ENGINE == "murf":
        _speak_murf(texto, start_ts)
        return
    _speak_pyttsx3(texto, start_ts)


def _speak_pyttsx3(texto: str, start_ts: float | None = None):
    engine = pyttsx3.init()
    engine.setProperty("rate", 180)
    engine.setProperty("volume", 1.0)

    voices = engine.getProperty("voices")
    for voice in voices:
        if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
            engine.setProperty("voice", voice.id)
            break

    engine.say(str(texto))
    _log_tts_delay(start_ts, "inicio_fala_pyttsx3")
    engine.runAndWait()
    engine.stop()
    del engine


def _speak_murf(texto: str, start_ts: float | None = None):
    if not _MURF_API_KEY:
        raise RuntimeError("MURF_API_KEY nao definido")

    print(f"[TTS MURF TEXTO]: {texto}")

    fmt = (_MURF_FORMAT or "MP3").upper()

    if fmt == "WAV":
        path = None
        try:
            t0 = time.perf_counter()
            resp = _murf_generate_audio(texto, fmt)
            t_headers = time.perf_counter()
            path = _murf_save_audio(resp, fmt)
            _log_tts_duration("murf_resposta", t_headers - t0)
            _log_tts_delay(start_ts, "inicio_fala_murf")
            _tocar_audio_arquivo(path, fmt)
        finally:
            if path:
                try:
                    os.remove(path)
                except Exception:
                    pass
        return

    if not _tem_ffplay():
        raise RuntimeError("ffplay nao encontrado no PATH (instale ffmpeg)")

    url = _MURF_STREAM_URL or "https://global.api.murf.ai/v1/speech/stream"
    headers = {
        "api-key": _MURF_API_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "voice_id": _MURF_VOICE,
        "style": _MURF_STYLE or "Conversational",
        "text": texto,
        "rate": _MURF_RATE,
        "pitch": _MURF_PITCH,
        "multi_native_locale": _MURF_LOCALE or "pt-BR",
        "model": _MURF_MODEL or "FALCON",
        "format": "MP3",
        "sampleRate": _MURF_SAMPLE_RATE,
        "channelType": _MURF_CHANNEL_TYPE or "MONO",
    }

    try:
        t0 = time.perf_counter()
        with requests.post(url, headers=headers, json=data, stream=True, timeout=30) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Murf erro: {resp.status_code}")
            t_headers = time.perf_counter()
            t_download = _tocar_mp3_ffplay_stream(resp, start_ts)
        _log_tts_duration("murf_resposta", t_headers - t0)
        _log_tts_duration("murf_total", t_download - t0)
    except Exception:
        # Fallback para arquivo local se streaming falhar.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            path = tmp.name
        try:
            t0 = time.perf_counter()
            with requests.post(url, headers=headers, json=data, stream=True, timeout=30) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"Murf erro: {resp.status_code}")
                t_headers = time.perf_counter()
                with open(path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=4096):
                        if chunk:
                            f.write(chunk)
            t_download = time.perf_counter()
            _log_tts_duration("murf_resposta", t_headers - t0)
            _log_tts_duration("murf_download", t_download - t_headers)
            _log_tts_duration("murf_total", t_download - t0)
            _log_tts_delay(start_ts, "inicio_fala_murf")
            _tocar_mp3_ffplay(path)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass


def _tem_ffplay() -> bool:
    if _FFPLAY_PATH and os.path.isfile(_FFPLAY_PATH):
        return True
    try:
        result = subprocess.run(
            ["ffplay", "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _resolver_dispositivo_audio():
    if not _AUDIO_DEVICE or not sd:
        return None
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    target = _AUDIO_DEVICE.lower()
    for idx, dev in enumerate(devices):
        name = str(dev.get("name", "")).lower()
        if dev.get("max_output_channels", 0) > 0 and target in name:
            return idx
    return None


def _tocar_mp3_ffplay(path: str):
    if _FFPLAY_PATH and os.path.isfile(_FFPLAY_PATH):
        cmd = [_FFPLAY_PATH, "-nodisp", "-autoexit", "-loglevel", "error", path]
    else:
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", path]
    subprocess.run(
        cmd,
        check=False,
    )


def _tocar_mp3_ffplay_stream(resp, start_ts: float | None = None) -> float:
    if _FFPLAY_PATH and os.path.isfile(_FFPLAY_PATH):
        cmd = [_FFPLAY_PATH, "-nodisp", "-autoexit", "-loglevel", "error", "-i", "pipe:0"]
    else:
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-i", "pipe:0"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    started = False
    try:
        for chunk in resp.iter_content(chunk_size=4096):
            if not chunk:
                continue
            if proc.stdin is None:
                break
            proc.stdin.write(chunk)
            if not started:
                started = True
                _log_tts_delay(start_ts, "inicio_fala_murf")
        if proc.stdin:
            proc.stdin.close()
        proc.wait()
    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        if proc.poll() is None:
            proc.kill()
    return time.perf_counter()


def _tocar_audio_arquivo(path: str, fmt: str) -> None:
    fmt = (fmt or "").upper()
    if fmt == "WAV":
        if sd and sf:
            try:
                data, samplerate = sf.read(path, dtype="float32")
                device = _resolver_dispositivo_audio()
                if _AUDIO_DEVICE and device is None:
                    logging.warning(
                        "Dispositivo de audio '%s' nao encontrado. Usando padrao.",
                        _AUDIO_DEVICE,
                    )
                sd.play(data, samplerate, device=device)
                sd.wait()
                return
            except Exception as e:
                logging.warning("Falha ao tocar WAV via sounddevice: %s", e)
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME)
            return
        except Exception:
            pass
    if not _tem_ffplay():
        raise RuntimeError("ffplay nao encontrado no PATH (instale ffmpeg)")
    _tocar_mp3_ffplay(path)


def _murf_generate_audio(texto: str, fmt: str) -> dict:
    url = f"{_MURF_BASE_URL}/v1/speech/generate"
    headers = {"api-key": _MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": texto,
        "voiceId": _MURF_VOICE,
        "format": fmt,
        "encodeAsBase64": True,
    }
    if _MURF_STYLE:
        payload["style"] = _MURF_STYLE
    if _MURF_LOCALE:
        payload["multiNativeLocale"] = _MURF_LOCALE
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Murf HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def _murf_save_audio(resp: dict, fmt: str) -> str:
    suffix = ".wav" if fmt.upper() == "WAV" else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        path = tmp.name

    b64 = resp.get("encodedAudio") or resp.get("audioBase64")
    if b64:
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path

    url = resp.get("audioFile") or resp.get("audioUrl")
    if url:
        ar = requests.get(url, timeout=120)
        ar.raise_for_status()
        with open(path, "wb") as f:
            f.write(ar.content)
        return path

    raise RuntimeError("Resposta do Murf sem audio.")


def _vad_rejeitar_audio(audio: sr.AudioData) -> bool:
    if not _VAD_ENABLED:
        return False
    try:
        import webrtcvad
    except Exception:
        return False
    try:
        vad = webrtcvad.Vad(_VAD_MODE)
    except Exception:
        return False
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    if not raw:
        return True
    frame_ms = _VAD_FRAME_MS
    if frame_ms not in (10, 20, 30):
        frame_ms = 30
    frame_size = int(16000 * frame_ms / 1000) * 2
    if frame_size <= 0:
        return False
    total = 0
    voiced = 0
    for i in range(0, len(raw) - frame_size + 1, frame_size):
        frame = raw[i:i + frame_size]
        total += 1
        try:
            if vad.is_speech(frame, 16000):
                voiced += 1
        except Exception:
            return False
    if total == 0:
        return True
    return voiced < _VAD_MIN_SPEECH_FRAMES


def _transcrever_groq(audio: sr.AudioData) -> str:
    if not _GROQ_API_KEY:
        return ""
    try:
        from groq import Groq
    except Exception as e:
        print(f"ERRO STT: groq sdk nao encontrado ({e})")
        return ""
    raw = audio.get_raw_data()
    try:
        rms = audioop.rms(raw, audio.sample_width)
    except Exception:
        rms = 0
    dur = 0.0
    try:
        dur = len(raw) / float(audio.sample_rate * audio.sample_width)
    except Exception:
        dur = 0.0
    dyn_rms_min = max(_STT_MIN_RMS, int(rec.energy_threshold * _STT_RMS_FACTOR))
    if rms < dyn_rms_min or dur < _STT_MIN_DURATION_SEC:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio.get_wav_data())
        path = tmp.name
    try:
        client = Groq(api_key=_GROQ_API_KEY)
        with open(path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(path, f.read()),
                model=_GROQ_STT_MODEL,
                temperature=0,
                response_format="verbose_json",
                language="pt",
            )
        return getattr(transcription, "text", "") or ""
    except Exception as e:
        print(f"ERRO STT GROQ: {e}")
        return ""
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def ouvir():
    with mic as source:
        rec.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = rec.listen(source, timeout=5, phrase_time_limit=15)
            texto = ""
            if _STT_ENGINE == "groq":
                if _vad_rejeitar_audio(audio):
                    return ""
                texto = _transcrever_groq(audio)
                if not texto:
                    texto = rec.recognize_google(audio, language="pt-BR")
            else:
                if _vad_rejeitar_audio(audio):
                    return ""
                texto = rec.recognize_google(audio, language="pt-BR")
            texto = (texto or "").lower()
            print(f"[OUVIDO]: {texto}")
            return texto
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            print("ERRO: conexao com o servico de reconhecimento.")
            return ""
        except Exception:
            return ""


if __name__ == "__main__":
    falar("Sistema de voz da Luna inicializado com sucesso.")
