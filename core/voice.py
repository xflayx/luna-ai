import speech_recognition as sr
import pyttsx3

engine = pyttsx3.init()
engine.setProperty("rate", 175)

rec = sr.Recognizer()
mic = sr.Microphone()

def falar(texto):
    print("TIPO:", type(texto))
    print(f"\n🤖 LUNA: {texto}")
    engine.say(str(texto))
    engine.runAndWait()


def ouvir():
    with mic as source:
        rec.adjust_for_ambient_noise(source)
        audio = rec.listen(source)
    try:
        texto = rec.recognize_google(audio, language="pt-BR").lower()
        print(f"[OUVIDO]: {texto}")
        return texto
    except:
        return ""
