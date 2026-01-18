import atexit
import asyncio
import os
import queue
import subprocess
import tempfile
import threading
import winsound

import speech_recognition as sr
import pyttsx3
import requests
from dotenv import load_dotenv

load_dotenv()

try:
    import edge_tts
except Exception:
    edge_tts = None

# Configuracoes do reconhecedor
rec = sr.Recognizer()
mic = sr.Microphone()

_fala_queue = queue.Queue()
_fala_thread = None
_fala_thread_lock = threading.Lock()
_TTS_ASSINCRONO = os.getenv("LUNA_TTS_ASYNC") == "1"
_TTS_ENGINE = os.getenv("LUNA_TTS_ENGINE", "pyttsx3").lower()
_EDGE_VOICE = os.getenv("LUNA_EDGE_VOICE", "pt-BR-FranciscaNeural")
_MURF_VOICE = os.getenv("LUNA_MURF_VOICE", "pt-BR-isadora")
_MURF_API_KEY = os.getenv("MURF_API_KEY", "")
_FFPLAY_PATH = os.getenv("LUNA_FFPLAY_PATH", "")


def _fala_worker():
    while True:
        texto = _fala_queue.get()
        try:
            if texto is None:
                _fala_queue.task_done()
                return
            _speak(texto)
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

    if _TTS_ASSINCRONO:
        _iniciar_fala_thread()
        _fala_queue.put(texto_limpo)
        return

    try:
        _speak(texto_limpo)
    except Exception as e:
        print(f"ERRO NO AUDIO: {e}")


def _speak(texto: str):
    if _TTS_ENGINE == "edge" and edge_tts:
        _speak_edge(texto)
        return
    if _TTS_ENGINE == "murf":
        _speak_murf(texto)
        return
    _speak_pyttsx3(texto)


def _speak_pyttsx3(texto: str):
    engine = pyttsx3.init()
    engine.setProperty("rate", 180)
    engine.setProperty("volume", 1.0)

    voices = engine.getProperty("voices")
    for voice in voices:
        if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
            engine.setProperty("voice", voice.id)
            break

    engine.say(str(texto))
    engine.runAndWait()
    engine.stop()
    del engine


def _speak_edge(texto: str):
    if not edge_tts:
        raise RuntimeError("edge_tts nao instalado")

    async def _run():
        communicate = edge_tts.Communicate(texto, _EDGE_VOICE)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            path = tmp.name
        try:
            await communicate.save(path)
            winsound.PlaySound(path, winsound.SND_FILENAME)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    asyncio.run(_run())


def _speak_murf(texto: str):
    if not _MURF_API_KEY:
        raise RuntimeError("MURF_API_KEY nao definido")

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

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        path = tmp.name

    try:
        with requests.post(url, headers=headers, json=data, stream=True, timeout=30) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Murf erro: {resp.status_code}")
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
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
