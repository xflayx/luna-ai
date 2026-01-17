# skills/news.py
import os
    serpapi_api_key = os.getenv("SERPAPI_API_KEY", "")
    if not serpapi_api_key:
        return "SERPAPI_API_KEY não configurada."

        "api_key": serpapi_api_key

# ========================================
# METADADOS DA SKILL (Padrão de Plugin)
# ========================================

SKILL_INFO = {
    "nome": "Notícias",
    "descricao": "Busca notícias usando SerpAPI",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["noticias", "news"]
}

# Gatilhos para esta skill
GATILHOS = ["notícia", "noticia", "news", "jornal", "acontecendo"]

# ========================================
# INICIALIZAÇÃO
# ========================================

def inicializar():
    """Chamada quando a skill é carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

# ========================================
# FUNÇÃO PRINCIPAL
# ========================================

def executar(comando: str) -> str:
    """Busca notícias baseado no comando"""
    
    # Remove palavras de ativação
    query = comando.replace("luna", "").replace("notícia", "").replace("sobre", "").strip()
    
    if not query:
        return "Quer notícias sobre o quê?"
    
    return buscar_noticias(query)

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def buscar_noticias(query: str) -> str:
    """Busca notícias usando SerpAPI"""
    
    serpapi_api_key = os.getenv("SERPAPI_API_KEY", "")
    if not serpapi_api_key:
        return "SERPAPI_API_KEY não configurada."

    params = {
        "engine": "google",
        "q": query,
        "hl": "pt-BR",
        "gl": "br",
        "api_key": serpapi_api_key
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = r.json()

        resultados = data.get("organic_results", [])[:3]
        if not resultados:
            return "Não encontrei informações relevantes sobre isso."

        titulos = " | ".join(r["title"] for r in resultados)
        return f"Encontrei isso: {titulos}"
        
    except Exception as e:
        return f"Erro ao buscar notícias: {str(e)}"
