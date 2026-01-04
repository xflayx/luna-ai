import requests
from config.settings import SERPAPI_API_KEY

def buscar_noticias(cmd):
    query = " ".join(cmd.split()[1:])

    params = {
        "engine": "google",
        "q": query,
        "hl": "pt-BR",
        "gl": "br",
        "api_key": SERPAPI_API_KEY
    }

    r = requests.get("https://serpapi.com/search", params=params, timeout=10)
    data = r.json()

    resultados = data.get("organic_results", [])[:3]
    if not resultados:
        return "Não encontrei informações relevantes."

    return " | ".join(r["title"] for r in resultados)
