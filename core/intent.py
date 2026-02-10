# core/intent.py - Sistema simples sem Gemini
import re
import unicodedata

from config.state import STATE


def _normalizar_texto(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

def _eh_pergunta_visual(cmd_norm: str) -> bool:
    interrogativos = [
        "qual",
        "o que",
        "quem",
        "como",
        "qual e",
        "qual o",
    ]
    visuais = [
        "tela",
        "imagem",
        "foto",
        "print",
        "screenshot",
        "na tela",
        "na imagem",
        "visual",
        "visao",
        "o que voce ve",
        "o que tem",
        "aparece",
        "mostra",
        "personagem",
    ]
    frases_jogo = [
        "nome do jogo",
        "nome desse jogo",
        "nome deste jogo",
        "qual e o jogo",
        "qual o jogo",
        "que jogo",
        "nome do game",
    ]
    if any(p in cmd_norm for p in frases_jogo):
        return True
    return any(i in cmd_norm for i in interrogativos) and any(v in cmd_norm for v in visuais)


def _separar_termos(termos: list[str]) -> tuple[list[str], list[str]]:
    palavras = [t for t in termos if " " not in t]
    frases = [t for t in termos if " " in t]
    return palavras, frases


def _tem_palavra(cmd_norm: str, palavras: list[str]) -> bool:
    if not palavras:
        return False
    pattern = r"\b(" + "|".join(re.escape(p) for p in palavras) + r")\b"
    return re.search(pattern, cmd_norm) is not None


def _tem_frase(cmd_norm: str, frases: list[str]) -> bool:
    return any(f in cmd_norm for f in frases)


def detectar_intencao(cmd: str) -> str:
    """Detecta intencao usando apenas keywords - sem API"""

    cmd = cmd.lower().strip()
    cmd_norm = _normalizar_texto(cmd)

    # Estados de sequencia
    if STATE.esperando_nome_sequencia or STATE.gravando_sequencia:
        return "sequencia"
    if STATE.esperando_loops:
        if any(n in cmd_norm for n in ["uma vez", "duas vezes", "tres vezes", "vezes"]):
            return "sequencia"
        if any(char.isdigit() for char in cmd):
            return "sequencia"

    # Sequencias
    if _tem_palavra(cmd_norm, ["executar", "sequencia", "macro", "gravar", "parar", "grave", "rode"]):
        return "sequencia"
    if any(char.isdigit() for char in cmd):
        if any(p in cmd_norm for p in ["sequencia", "macro", "executar", "rodar", "repetir", "loop"]):
            return "sequencia"

    # Visao
    termos_foco = [
        "roupa",
        "traje",
        "vestindo",
        "look",
        "outfit",
        "vestimenta",
        "estilo",
        "mao",
        "maos",
        "na mao",
        "na maos",
        "rosto",
        "cabelo",
        "olhos",
        "expressao",
        "gesto",
        "gestos",
        "segura",
        "segurando",
        "segurar",
        "objeto",
        "objetos",
        "acessorio",
        "acessorios",
        "chapeu",
        "chapeus",
        "comida",
        "prato",
        "bebida",
        "placa",
        "texto",
    ]
    palavras_foco, frases_foco = _separar_termos(termos_foco)
    if _tem_palavra(cmd_norm, palavras_foco) or _tem_frase(cmd_norm, frases_foco):
        return "vision"
    if any(v in cmd_norm for v in ["reanalisar", "reanalise", "analise novamente", "analise de novo", "ultima captura", "ultima imagem", "ultimas imagens"]):
        return "vision"
    if _tem_palavra(cmd_norm, ["analise", "analisar", "veja", "olhe", "ve", "tela", "screenshot"]):
        if _tem_palavra(cmd_norm, ["tela", "imagem", "foto", "isso", "captura", "print"]):
            return "vision"

    if _eh_pergunta_visual(cmd_norm):
        return "vision"
    if _tem_palavra(cmd_norm, ["level", "nivel"]) and (
        _tem_palavra(cmd_norm, ["jogo"]) or _tem_palavra(cmd_norm, ["tela", "imagem", "foto", "print"])
    ):
        return "vision"

    # Preco
    if _tem_palavra(cmd_norm, ["preco", "valor", "cotacao", "bitcoin", "dolar", "real", "crypto"]):
        return "price"

    # Sistema
    if _tem_palavra(cmd_norm, ["sistema", "cpu", "memoria", "ram", "temperatura"]):
        return "system_monitor"

    # YouTube
    if any(y in cmd_norm for y in ["youtu.be", "youtube.com"]):
        return "youtube_summary"
    if _tem_palavra(cmd_norm, ["youtube", "video"]):
        return "youtube_summary"

    # Link Scraper
    if any(l in cmd_norm for l in ["coletar links", "extrair links", "listar links", "salvar links", "mapear links", "raspar links"]):
        return "link_scraper"

    # Web
    if any(w in cmd_norm for w in ["http", "x.com", "twitter.com"]):
        return "web_reader"
    if re.search(r"\b(site|pagina|link|url|leia|resuma|resumo|post|tweet)\b", cmd_norm):
        return "web_reader"

    # Game
    if _tem_palavra(cmd_norm, ["dica", "build", "guia", "tutorial"]):
        return "game_guide"

    # Menu
    if _tem_palavra(cmd_norm, ["menu", "radial", "atalho"]):
        return "atalhos_radial"

    # TTS
    if _tem_palavra(cmd_norm, ["tts", "narrar", "narracao", "murf", "voz"]):
        return "tts"
    if _tem_frase(cmd_norm, ["ler roteiro", "leia o roteiro"]):
        return "tts"
    if re.search(r"\b(arquivo|file)\s*:\s*.+", cmd_norm):
        return "tts"

    # Conversa (padrao)
    return "conversa"
