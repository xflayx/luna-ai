import os
import re
import requests
import unicodedata
from core.opinion_engine import gerar_opiniao

# =============================
# CONFIG
# =============================
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1"

HEADERS = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY,
    "Accepts": "application/json"
}

CRYPTO_MAP = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "ether": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "sui": "SUI",
    "suy": "SUI",
    "sue": "SUI",
}

# =============================
# UTILIDADES
# =============================
def extrair_nome_cripto(frase: str) -> str | None:
    frase = frase.lower().replace("luna", "").strip()
    texto = unicodedata.normalize("NFD", frase)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    
    remover = [
        "preco", "preço", "valor", "cotacao", "cotação",
        "token", "moeda", "cripto", "criptomoeda",
        "qual", "quanto", "hoje", "atual", "do", "da", "de",
        "está", "esta", "agora", "me", "diga"
    ]
    
    palavras = texto.split()
    candidatos = [p for p in palavras if p not in remover]
    
    if not candidatos:
        return None
        
    for p in candidatos:
        if p in CRYPTO_MAP:
            return CRYPTO_MAP[p]
            
    return candidatos[-1]

# =============================
# BUSCA NO COINMARKETCAP
# =============================
def buscar_preco(nome_ou_simbolo: str) -> dict | None:
    url_quotes = f"{CMC_BASE_URL}/cryptocurrency/quotes/latest"
    
    # 1️⃣ Tenta busca direta por Símbolo
    try:
        r = requests.get(url_quotes, headers=HEADERS, params={"symbol": nome_ou_simbolo.upper()}, timeout=10)
        data = r.json()
        if data.get("status", {}).get("error_code") == 0 and data.get("data"):
            crypto = next(iter(data["data"].values()))
            return formatar_resposta(crypto)
    except:
        pass

    # 2️⃣ Busca no Mapa Global
    try:
        r_map = requests.get(f"{CMC_BASE_URL}/cryptocurrency/map", headers=HEADERS, timeout=10)
        if r_map.status_code == 200:
            map_data = r_map.json().get("data", [])
            candidatos = [
                c for c in map_data 
                if nome_ou_simbolo.lower() == c["name"].lower() or nome_ou_simbolo.lower() == c["symbol"].lower()
            ]
            
            if not candidatos:
                candidatos = [c for c in map_data if nome_ou_simbolo.lower() in c["name"].lower()]

            if candidatos:
                escolhido = sorted(candidatos, key=lambda x: x.get("rank", 99999))[0]
                r_final = requests.get(url_quotes, headers=HEADERS, params={"id": escolhido["id"]}, timeout=10)
                final_data = r_final.json()
                
                if final_data.get("status", {}).get("error_code") == 0 and final_data.get("data"):
                    crypto = next(iter(final_data["data"].values()))
                    return formatar_resposta(crypto)
    except:
        pass

    return None

def formatar_resposta(crypto: dict) -> dict | None:
    try:
        # Verifica se existem dados de cotação para evitar o TypeError
        if "quote" not in crypto or "USD" not in crypto["quote"]:
            return None
            
        quote = crypto["quote"]["USD"]
        
        # Se o preço for None, retorna None para o router tratar
        if quote.get("price") is None:
            return None

        return {
            "name": crypto["name"],
            "symbol": crypto["symbol"],
            "price": round(quote["price"], 4),
            "change_24h": round(quote.get("percent_change_24h", 0) or 0, 2)
        }
    except Exception as e:
        print(f"Erro na formatação: {e}")
        return None

# =============================
# INTERFACE FINAL
# =============================
def responder_preco(frase: str) -> str:
    cripto = extrair_nome_cripto(frase)
    if not cripto:
        return "Não consegui identificar nenhuma criptomoeda."

    resultado = buscar_preco(cripto)

    if not resultado:
        return f"Não encontrei dados de preço para {cripto}."

    tendencia = "subindo 📈" if resultado["change_24h"] > 0 else "caindo 📉"
    
    # Texto base com os dados
    texto_base = (
        f"O {resultado['name']} está custando {resultado['price']} dólares, "
        f"com uma variação de {resultado['change_24h']}% nas últimas 24 horas, ou seja, está {tendencia}."
    )

    # --- NOVIDADE: Chama a opinião da Luna ---
    # Passamos o texto_base para a Luna analisar o contexto do preço
    opiniao_luna = gerar_opiniao(texto_base)

    return f"{texto_base} {opiniao_luna}"