# core/intent.py - Sistema SIMPLES sem Gemini
from config.state import STATE

def detectar_intencao(cmd: str) -> str:
    """Detecta intenção usando apenas keywords - SEM API"""
    
    cmd = cmd.lower().strip()
    
    # Estados de sequência
    if STATE.esperando_nome_sequencia or STATE.esperando_loops or STATE.gravando_sequencia:
        return "sequencia"
    
    # Sequências
    if any(p in cmd for p in ["executar", "sequência", "sequencia", "macro", "gravar", "parar", "grave", "rode"]):
        return "sequencia"
    if any(n in cmd for n in ["uma vez", "duas vezes", "três vezes", "vezes"]):
        return "sequencia"
    if any(char.isdigit() for char in cmd):
        if not any(p in cmd for p in ["preço", "valor", "cotação", "bitcoin", "dólar"]):
            return "sequencia"
    
    # Visão
    if any(v in cmd for v in ["analise", "analisar", "veja", "olhe", "vê", "tela", "screenshot"]):
        if any(t in cmd for t in ["tela", "imagem", "foto", "isso"]):
            return "visao"
    
    # Preço
    if any(p in cmd for p in ["preço", "valor", "cotação", "bitcoin", "dólar", "real", "crypto"]):
        return "preco"
    
    # Sistema
    if any(s in cmd for s in ["sistema", "cpu", "memória", "ram", "temperatura"]):
        return "system_monitor"
    
    # Web
    if any(w in cmd for w in ["site", "página", "link", "url", "http", "leia", "resuma"]):
        return "web_reader"
    
    # Game
    if any(g in cmd for g in ["jogo", "game", "dica", "build", "guia"]):
        return "game_guide"
    
    # Menu
    if any(m in cmd for m in ["menu", "radial", "atalho"]):
        return "atalhos_radial"
    
    # Conversa (padrão)
    return "conversa"