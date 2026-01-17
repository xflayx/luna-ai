# skills/price.py
import os
import requests
import unicodedata
import logging

# ========================================
# METADADOS DA SKILL (Padrão de Plugin)
# ========================================

SKILL_INFO = {
    "nome": "Price",
    "descricao": "Consulta preços de criptomoedas",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ['preco', 'price']
}



# Configuração de Log para o plugin
logger = logging.getLogger("PricePlugin")

# --- CONFIGURAÇÃO ---
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1"
HEADERS = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY,
    "Accepts": "application/json"
}

# --- CONTRATO DA SKILL ---
GATILHOS = ["preço", "valor", "cotação", "quanto está", "preco", "cotacao"]


# ========================================
# INICIALIZAÇÃO (Opcional)
# ========================================

def inicializar():
    """Chamada quando a skill é carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

def executar(comando: str) -> str:
    """Função principal chamada pelo Router."""
    cripto_alvo = extrair_nome_cripto(comando)
    
    if not cripto_alvo:
        return "Você não disse qual moeda quer. Eu não leio mentes, pelo menos não sem cobrar extra."

    logger.info(f"💰 Buscando preço para: {cripto_alvo}")
    resultado = buscar_preco(cripto_alvo)

    if not resultado:
        return f"Não encontrei dados para '{cripto_alvo}'. Tem certeza que isso não é um golpe ou uma moeda de chocolate?"

    tendencia = "subindo 📈" if resultado["change_24h"] > 0 else "caindo 📉"
    
    texto_base = (
        f"O {resultado['name']} está custando {resultado['price']} dólares, "
        f"com uma variação de {resultado['change_24h']}% nas últimas 24 horas, ou seja, está {tendencia}."
    )
    return f"{texto_base}"

# --- UTILIDADES ---
CRYPTO_MAP = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
    "avalanche": "AVAX", "avax": "AVAX",
    "sui": "SUI"
}

def extrair_nome_cripto(frase: str) -> str | None:
    frase = frase.lower().replace("luna", "").strip()
    texto = unicodedata.normalize("NFD", frase)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    
    remover = [
        "preco", "preço", "valor", "cotacao", "cotação",
        "token", "moeda", "cripto", "criptomoeda",
        "qual", "quanto", "hoje", "atual", "do", "da", "de",
        "está", "esta", "agora", "me", "diga", "resumo"
    ]
    
    palavras = texto.split()
    candidatos = [p for p in palavras if p not in remover]
    
    if not candidatos:
        return None
        
    for p in candidatos:
        if p in CRYPTO_MAP:
            return CRYPTO_MAP[p]
            
    return candidatos[-1]

def buscar_preco(nome_ou_simbolo: str) -> dict | None:
    url_quotes = f"{CMC_BASE_URL}/cryptocurrency/quotes/latest"
    
    # 1. Busca Direta por Símbolo
    try:
        r = requests.get(url_quotes, headers=HEADERS, params={"symbol": nome_ou_simbolo.upper()}, timeout=10)
        data = r.json()
        if data.get("status", {}).get("error_code") == 0 and data.get("data"):
            crypto = next(iter(data["data"].values()))
            return formatar_data(crypto)
    except:
        pass

    # 2. Busca por Nome (Map)
    try:
        r_map = requests.get(f"{CMC_BASE_URL}/cryptocurrency/map", headers=HEADERS, timeout=10)
        if r_map.status_code == 200:
            map_data = r_map.json().get("data", [])
            candidatos = [
                c for c in map_data 
                if nome_ou_simbolo.lower() == c["name"].lower() or nome_ou_simbolo.lower() == c["symbol"].lower()
            ]
            
            if candidatos:
                escolhido = sorted(candidatos, key=lambda x: x.get("rank", 99999))[0]
                r_final = requests.get(url_quotes, headers=HEADERS, params={"id": escolhido["id"]}, timeout=10)
                final_data = r_final.json()
                if final_data.get("status", {}).get("error_code") == 0:
                    crypto = next(iter(final_data["data"].values()))
                    return formatar_data(crypto)
    except:
        pass
    return None

def formatar_data(crypto: dict) -> dict | None:
    try:
        quote = crypto["quote"]["USD"]
        return {
            "name": crypto["name"],
            "symbol": crypto["symbol"],
            "price": round(quote["price"], 4) if quote["price"] > 1 else round(quote["price"], 8),
            "change_24h": round(quote.get("percent_change_24h", 0) or 0, 2)
        }
    except:
        return None