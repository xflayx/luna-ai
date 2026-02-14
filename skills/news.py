# skills/news.py
import os
import re
import unicodedata

import requests


SKILL_INFO = {
    "nome": "Noticias",
    "descricao": "Busca noticias usando SerpAPI",
    "versao": "1.1.0",
    "autor": "Luna Team",
    "intents": ["noticias", "news"],
}

GATILHOS = ["noticia", "noticias", "news", "jornal", "acontecendo"]


def inicializar():
    """Chamada quando a skill e carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    """Busca noticias baseado no comando"""
    query = _extrair_query(comando)
    if not query:
        return "Quer noticias sobre o que?"
    return buscar_noticias(query)


def buscar_noticias(query: str) -> str:
    """Busca noticias usando SerpAPI"""
    serpapi_api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY", "")
    if not serpapi_api_key:
        return "SERPAPI_API_KEY nao configurada."

    params = {
        "engine": "google",
        "q": query,
        "hl": "pt-BR",
        "gl": "br",
        "api_key": serpapi_api_key,
        "tbm": "nws",
    }

    try:
        r = SESSION.get("https://serpapi.com/search", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        resultados = data.get("organic_results", [])[:3]
        if not resultados:
            return "Nao encontrei informacoes relevantes sobre isso."

        titulos = " | ".join(r.get("title", "").strip() for r in resultados if r.get("title"))
        if not titulos:
            return "Nao encontrei informacoes relevantes sobre isso."
        return f"Encontrei isso: {titulos}"
    except Exception as e:
        return f"Erro ao buscar noticias: {e}"


def _extrair_query(comando: str) -> str:
    texto = (comando or "").strip()
    if not texto:
        return ""

    texto = _normalizar(texto.lower())
    tokens_remover = [
        "luna",
        "noticia",
        "noticias",
        "news",
        "jornal",
        "acontecendo",
        "sobre",
        "do",
        "da",
        "de",
        "dos",
        "das",
        "no",
        "na",
        "nos",
        "nas",
    ]
    pattern = r"\b(" + "|".join(re.escape(t) for t in tokens_remover) + r")\b"
    texto = re.sub(pattern, " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _normalizar(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
from core.http_client import SESSION
