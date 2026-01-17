import speech_recognition as sr
import pyttsx3

# Configurações do Reconhecedor
rec = sr.Recognizer()
mic = sr.Microphone()

def falar(texto):
    # Remove asteriscos para a Luna não ler "asterisco"
    texto_limpo = texto.replace("*", "").replace("#", "")
    """
    Converte texto em áudio. 
    Inicializa a engine localmente para evitar travamentos em loops longos.
    """
    print(f"\n🤖 LUNA: {texto}")
    
    try:
        # Inicializa a engine dentro da função para resetar o driver de áudio
        engine = pyttsx3.init()
        
        # Configurações de Voz
        engine.setProperty("rate", 180)  # Velocidade da fala
        engine.setProperty("volume", 1.0) # Volume máximo
        
        # Tenta definir uma voz em Português (Brasil)
        voices = engine.getProperty('voices')
        for voice in voices:
            if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break

        # Executa a fala
        engine.say(str(texto))
        engine.runAndWait()
        
        # Finaliza a instância para liberar o recurso de hardware
        engine.stop()
        del engine
        
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