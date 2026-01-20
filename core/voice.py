import atexit
import os
import queue
import subprocess
import tempfile
import threading
import time
import winsound

import speech_recognition as sr
import pyttsx3
import requests

from config.env import init_env

init_env()

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
_FFPLAY_PATH = os.getenv("LUNA_FFPLAY_PATH", "")



def _fala_worker():
    while True:
        item = _fala_queue.get()
        try:
            if item is None:
                _fala_queue.task_done()
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

    if not _tem_ffplay():
        raise RuntimeError("ffplay nao encontrado no PATH (instale ffmpeg)")

    url = "https://global.api.murf.ai/v1/speech/stream"
    headers = {
        "api-key": _MURF_API_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "voice_id": _MURF_VOICE,
        "style": "Conversational",
        "text": texto,
        "rate": 15,
        "pitch": 10,
        "multi_native_locale": "pt-BR",
        "model": "FALCON",
        "format": "MP3",
        "sampleRate": 24000,
        "channelType": "MONO",
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


def ouvir():
    with mic as source:
        rec.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = rec.listen(source, timeout=5, phrase_time_limit=15)
            texto = rec.recognize_google(audio, language="pt-BR").lower()
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
