# core/intent.py - Sistema simples sem Gemini
import unicodedata

from config.state import STATE


def _normalizar_texto(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def detectar_intencao(cmd: str) -> str:
    """Detecta intencao usando apenas keywords - sem API"""

    cmd = cmd.lower().strip()
    cmd_norm = _normalizar_texto(cmd)

    # Estados de sequencia
    if STATE.esperando_nome_sequencia or STATE.esperando_loops or STATE.gravando_sequencia:
        return "sequencia"

    # Sequencias
    if any(p in cmd_norm for p in ["executar", "sequencia", "macro", "gravar", "parar", "grave", "rode"]):
        return "sequencia"
    if any(n in cmd_norm for n in ["uma vez", "duas vezes", "tres vezes", "vezes"]):
        return "sequencia"
    if any(char.isdigit() for char in cmd):
        if not any(p in cmd_norm for p in ["preco", "valor", "cotacao", "bitcoin", "dolar"]):
            return "sequencia"

    # Visao
    if any(v in cmd_norm for v in ["analise", "analisar", "veja", "olhe", "ve", "tela", "screenshot"]):
        if any(t in cmd_norm for t in ["tela", "imagem", "foto", "isso"]):
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
