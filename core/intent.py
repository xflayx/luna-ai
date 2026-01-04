def detectar_intencao(cmd):
    if any(p in cmd for p in ["por que", "motivo", "caiu", "subiu", "notícia", "pesquise"]):
        return "noticia"

    if any(p in cmd for p in ["preço", "preco", "valor", "quanto"]):
        return "preco"

    if "analise" in cmd or "analisar" in cmd:
        return "visao"

    if "executar" in cmd:
        return "macro"

    if "encerrar" in cmd:
        return "encerrar"

    return None
