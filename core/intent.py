# core/intent.py

def detectar_intencao(cmd):
    """
    Analisa o comando para identificar a intenção, priorizando ações de estado (gravação)
    sobre ações de execução.
    """
    cmd = cmd.lower()

    # 1. PRIORIDADE: Gravação de Sequência (Ações de Estado)
    # Verificamos primeiro 'parar' ou 'gravar' para evitar que caia na execução normal
    if any(p in cmd for p in ["pare a gravação", "parar gravação", "parar gravação"]):
        return "sequencia" # O router tratará o comando 'pare'
    
    if "gravar" in cmd:
        return "sequencia" # O router tratará o início da gravação

    # 2. VISÃO (Analise de tela) - Restaurado e Isolado
    if any(p in cmd for p in ["analise", "analisar", "veja", "olhe", "o que é isso", "está vendo"]):
        return "visao"

    # 3. PREÇO (Criptomoedas/Mercado)
    if any(p in cmd for p in ["preço", "valor", "quanto está", "cotação"]):
        return "preco"

    # 4. SEQUENCIA (Execução de automação)
    # Agora só chega aqui se não for um comando de 'gravar' ou 'parar'
    if any(p in cmd for p in ["sequência", "sequencia", "executar"]):
        return "sequencia"

    # 5. NOTÍCIA
    if any(p in cmd for p in ["notícia", "pesquise", "saiba sobre", "aconteceu"]):
        return "noticia"

    # 6. CONVERSA (Presença e Personalidade)
    if any(p in cmd for p in ["ouvindo", "oi", "olá", "luna", "está aí", "bom dia", "boa noite"]):
        return "conversa"

    return None