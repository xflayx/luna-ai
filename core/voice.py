import os
import queue
import threading
import speech_recognition as sr
import pyttsx3

# Configurações do Reconhecedor
rec = sr.Recognizer()
mic = sr.Microphone()

_fala_queue = queue.Queue()
_fala_thread = None
_fala_thread_lock = threading.Lock()
_engine = None
_engine_lock = threading.Lock()

_FORCAR_TTS_ASSINCRONO = os.getenv("LUNA_TTS_ASYNC")
_TTS_ASSINCRONO = _FORCAR_TTS_ASSINCRONO == "1" or (
    _FORCAR_TTS_ASSINCRONO is None and os.name != "nt"
)

def _configurar_engine(engine):
    engine.setProperty("rate", 180)  # Velocidade da fala
    engine.setProperty("volume", 1.0)  # Volume máximo

    # Tenta definir uma voz em Português (Brasil)
    voices = engine.getProperty("voices")
    for voice in voices:
        if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
            engine.setProperty("voice", voice.id)
            break

def _obter_engine_sincrono():
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            _engine = pyttsx3.init()
            _configurar_engine(_engine)
    return _engine

def _fala_worker():
    engine = None
    try:
        # Inicializa a engine uma única vez na thread
        engine = pyttsx3.init()

        _configurar_engine(engine)
    except Exception as e:
        print(f"❌ ERRO NO ÁUDIO: {e}")

    while True:
        texto = _fala_queue.get()
        try:
            if not engine:
                _fala_queue.task_done()
                continue
            engine.say(str(texto))
            engine.runAndWait()
        except Exception as e:
            print(f"❌ ERRO NO ÁUDIO: {e}")
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

def falar(texto):
    # Remove asteriscos para a Luna não ler "asterisco"
    texto_limpo = texto.replace("*", "").replace("#", "")
    """
    Converte texto em áudio. 
    Inicializa a engine localmente para evitar travamentos em loops longos.
    """
    print(f"\n🤖 LUNA: {texto}")

    if _TTS_ASSINCRONO:
        _iniciar_fala_thread()
        _fala_queue.put(texto_limpo)
        return

    try:
        engine = _obter_engine_sincrono()
        with _engine_lock:
            engine.say(str(texto_limpo))
            engine.runAndWait()
    except Exception as e:
        print(f"❌ ERRO NO ÁUDIO: {e}")


def ouvir():
    """
    Captura o áudio do microfone e converte para texto.
    """
    with mic as source:
        # Ajusta para o ruído ambiente antes de ouvir
        rec.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = rec.listen(source, timeout=5, phrase_time_limit=15)
            # Converte para texto usando a API do Google (em português)
            texto = rec.recognize_google(audio, language="pt-BR").lower()
            print(f"[OUVIDO]: {texto}")
            return texto
        except sr.UnknownValueError:
            # Caso não entenda nada, retorna vazio sem erro
            return ""
        except sr.RequestError:
            print("❌ Erro de conexão com o serviço de reconhecimento.")
            return ""
        except Exception:
            return ""

# Teste rápido se o arquivo for executado diretamente
if __name__ == "__main__":
    falar("Sistema de voz da Luna inicializado com sucesso.")
