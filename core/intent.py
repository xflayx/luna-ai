# core/intent.py - Sistema simples sem Gemini
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
    if any(p in cmd_norm for p in ["executar", "sequencia", "macro", "gravar", "parar", "grave", "rode"]):
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
    if any(t in cmd_norm for t in termos_foco):
        return "vision"
    if any(v in cmd_norm for v in ["reanalisar", "reanalise", "analise novamente", "analise de novo", "ultima captura", "ultima imagem", "ultimas imagens"]):
        return "vision"
    if any(v in cmd_norm for v in ["analise", "analisar", "veja", "olhe", "ve", "tela", "screenshot"]):
        if any(t in cmd_norm for t in ["tela", "imagem", "foto", "isso", "captura", "print"]):
            return "vision"

    if _eh_pergunta_visual(cmd_norm):
        return "vision"

    # Preco
    if any(p in cmd_norm for p in ["preco", "valor", "cotacao", "bitcoin", "dolar", "real", "crypto"]):
        return "price"

    # Sistema
    if any(s in cmd_norm for s in ["sistema", "cpu", "memoria", "ram", "temperatura"]):
        return "system_monitor"

    # YouTube
    if any(y in cmd_norm for y in ["youtube", "youtu.be", "video"]):
        return "youtube_summary"

    # Link Scraper
    if any(l in cmd_norm for l in ["coletar links", "extrair links", "listar links", "salvar links", "mapear links", "raspar links"]):
        return "link_scraper"

    # Web
    if any(w in cmd_norm for w in ["site", "pagina", "link", "url", "http", "leia", "resuma", "resumo", "post", "tweet", "x.com", "twitter.com"]):
        return "web_reader"

    # Game
    if any(g in cmd_norm for g in ["jogo", "game", "dica", "build", "guia"]):
        return "game_guide"

    # Menu
    if any(m in cmd_norm for m in ["menu", "radial", "atalho"]):
        return "atalhos_radial"

    # Conversa (padrao)
    return "conversa"
