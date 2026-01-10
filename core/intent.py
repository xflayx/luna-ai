# core/intent.py

def detectar_intencao(cmd):
    cmd = cmd.lower().strip()

    # 1. ESTADO DE EXECUÇÃO (Prioridade Máxima)
    # Se houver números ou palavras de execução, tratamos como sequência
    if any(n in cmd for n in ["uma", "duas", "três", "cinco", "dez"]) or any(char.isdigit() for char in cmd):
        return "sequencia"

    if any(p in cmd for p in ["executar", "sequência", "sequencia", "gravar", "parar"]):
        return "sequencia"

    # 2. VISÃO
    if any(v in cmd for v in ["analise", "analisar", "veja", "olhe"]) and any(o in cmd for o in ["tela", "imagem"]):
        return "visao"

    # 3. PREÇO
    if any(p in cmd for p in ["preço", "valor", "cotação"]):
        return "preco"

    # 4. CONVERSA (Agora por último, para não "roubar" o comando)
    if any(p in cmd for p in ["luna", "oi", "olá", "bom dia"]):
        return "conversa"

    return None