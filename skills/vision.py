import base64
import io
import re
import win32gui
import win32process
import psutil
import mss
from datetime import datetime
from PIL import Image, ImageGrab
from config.settings import client, MODEL_VISAO


# ===============================
# LISTAR JANELAS DO WINDOWS
# ===============================
def listar_janelas():
    janelas = []

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titulo = win32gui.GetWindowText(hwnd)
            if titulo:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid).name()
                    janelas.append({
                        "hwnd": hwnd,
                        "titulo": f"{titulo} ({proc})"
                    })
                except:
                    pass

    win32gui.EnumWindows(enum_handler, None)
    return janelas


# ===============================
# CAPTURA DE JANELA
# ===============================
def capturar_janela(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    largura = right - left
    altura = bottom - top

    with mss.mss() as sct:
        monitor = {
            "top": top,
            "left": left,
            "width": largura,
            "height": altura
        }
        img = sct.grab(monitor)
        return Image.frombytes("RGB", img.size, img.rgb)


# ===============================
# CAPTURA DE MONITOR
# ===============================
def capturar_monitor(indice=1):
    with mss.mss() as sct:
        monitor = sct.monitors[indice]
        img = sct.grab(monitor)
        return Image.frombytes("RGB", img.size, img.rgb)


# ===============================
# CHAMADA AO MODELO DE VISÃO
# ===============================
def analisar_imagem_bruta(img: Image.Image, pergunta: str) -> str:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()

    r = client.chat.completions.create(
        model=MODEL_VISAO,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": pergunta},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}"
                    }
                }
            ]
        }]
    )

    return r.choices[0].message.content


# ===============================
# EXTRAÇÃO DE NOMES PRÓPRIOS
# ===============================
import re


def extrair_nomes(texto: str) -> list:
    blacklist = {
        # Estrutura de texto
        "Elementos", "Conclusao", "Conclusão", "Analise", "Análise",
        "Imagem", "Pagina", "Página", "Resultado",

        # Sites / genéricos
        "Pinterest", "GIF", "GIFs", "Anime", "Sticker", "Dance",

        # Conectores comuns
        "Na", "No", "Da", "Do", "Em", "Para", "Com"
    }

    # candidatos com letra maiúscula real
    candidatos = re.findall(
        r"\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})*\b",
        texto
    )

    nomes_validos = []

    for nome in candidatos:
        partes = nome.split()

        # ❌ ignora blacklist direta
        if any(p in blacklist for p in partes):
            continue

        # ❌ ignora palavra única curta
        if len(partes) == 1 and len(partes[0]) < 5:
            continue

        # ✅ contexto semântico (muito importante)
        contexto = texto.lower()
        if not any(
            chave in contexto
            for chave in ["personagem", "anime", "chamada", "nome"]
        ):
            continue

        nomes_validos.append(nome)

    # remove duplicados preservando ordem
    return list(dict.fromkeys(nomes_validos))


# ===============================
# RESUMO INTELIGENTE (CURTO + NOMES)
# ===============================
def gerar_resumo(texto: str) -> str:
    texto_lower = texto.lower()
    nomes = extrair_nomes(texto)

    if "pinterest" in texto_lower:
        if nomes:
            return f"Parece uma página do Pinterest com vários GIFs da personagem {nomes[0]}."
        return "Parece uma página do Pinterest com vários GIFs de uma personagem de anime."

    if "anime" in texto_lower:
        if nomes:
            return f"A imagem mostra conteúdo de anime com foco na personagem {nomes[0]}."
        return "A imagem mostra conteúdo de anime com foco em uma personagem animada."

    if "jogo" in texto_lower or "game" in texto_lower:
        return "Parece um jogo aberto na tela, com elementos visuais ativos."

    if "twitter" in texto_lower or "x.com" in texto_lower:
        return "Vejo uma rede social aberta, com posts e imagens na tela."

    return "Vejo uma tela com vários elementos visuais, mas nada muito claro ainda."


# ===============================
# TAGS
# ===============================
def extrair_tags(texto: str) -> list:
    tags = []
    texto = texto.lower()

    palavras_chave = {
        "pinterest": "pinterest",
        "anime": "anime",
        "gif": "gif",
        "game": "game",
        "jogo": "game",
        "twitter": "social",
        "x.com": "social",
        "youtube": "video"
    }

    for palavra, tag in palavras_chave.items():
        if palavra in texto:
            tags.append(tag)

    return list(set(tags))


# ===============================
# CONFIANÇA (HEURÍSTICA)
# ===============================
def estimar_confianca(texto: str) -> float:
    score = 0.3
    sinais = ["imagem", "página", "mostra", "parece"]

    texto = texto.lower()

    for s in sinais:
        if s in texto:
            score += 0.15

    return min(score, 0.95)


# ===============================
# FUNÇÃO PRINCIPAL PARA O CORE
# ===============================
def analisar_tela(pergunta: str) -> dict:
    """
    Usado pelo core (voz / router).
    Captura a tela ativa e retorna análise estruturada.
    """
    try:
        img = ImageGrab.grab()
        raw_analysis = analisar_imagem_bruta(img, pergunta)

        return {
            "raw_analysis": raw_analysis,
            "summary": gerar_resumo(raw_analysis),
            "tags": extrair_tags(raw_analysis),
            "confidence": estimar_confianca(raw_analysis),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "raw_analysis": "",
            "summary": f"Erro ao analisar a tela: {e}",
            "tags": [],
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat()
        }
