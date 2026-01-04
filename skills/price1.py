import os
import re
import requests
import unicodedata

# =============================
# CONFIG
# =============================
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1"

HEADERS = {
    "X-CMC_PRO_API_KEY": CMC_API_KEY,
    "Accepts": "application/json"
}

# =============================
# DICIONÁRIO CANÔNICO (BASE)
# =============================
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

PALAVRAS_LIXO = [
    "preco", "preço", "valor", "cotacao", "cotação",
    "token", "moeda", "cripto", "criptomoeda",
    "qual", "quanto", "hoje", "atual", "do", "da", "de"
]

# =============================
# UTILIDADES
# =============================
def normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    for lixo in PALAVRAS_LIXO:
        texto = texto.replace(lixo, " ")

    texto = re.sub(r"[^a-zA-Z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def extrair_nome_cripto(frase: str) -> str | None:
    texto = normalizar_texto(frase)
    palavras = texto.split()

    # remove wake word
    palavras = [p for p in palavras if p != "luna"]

    if not palavras:
        return None

    # tenta resolver pelo dicionário
    for p in palavras:
        if p in CRYPTO_MAP:
            return CRYPTO_MAP[p]

    # fallback: usa o texto restante
    return " ".join(palavras) if palavras else None


# =============================
# BUSCA NO COINMARKETCAP
# =============================
def buscar_preco(nome_ou_simbolo: str) -> dict | None:
    # 1️⃣ tenta como símbolo
    r = requests.get(
        f"{CMC_BASE_URL}/cryptocurrency/quotes/latest",
        headers=HEADERS,
        params={"symbol": nome_ou_simbolo.upper()}
    )

    data = r.json()

    if data.get("status", {}).get("error_code") == 0:
        if not data.get("data"):
            return None

        crypto = next(iter(data["data"].values()))
        return formatar_resposta(crypto)

    # 2️⃣ tenta resolver pelo nome
    r = requests.get(
        f"{CMC_BASE_URL}/cryptocurrency/map",
        headers=HEADERS,
        params={"listing_status": "active"}
    )

    data = r.json()
    if "data" not in data:
        return None

    candidatos = [
        c for c in data["data"]
        if nome_ou_simbolo.lower() in c["name"].lower()
        or nome_ou_simbolo.lower() == c["symbol"].lower()
    ]

    if not candidatos:
        return None

    # escolhe o mais relevante (menor rank)
    escolhido = sorted(candidatos, key=lambda x: x.get("rank", 9999))[0]

    r = requests.get(
        f"{CMC_BASE_URL}/cryptocurrency/quotes/latest",
        headers=HEADERS,
        params={"id": escolhido["id"]}
    )

    data = r.json()
    if data.get("status", {}).get("error_code") != 0:
        return None

    if not data.get("data"):
        return None

    crypto = next(iter(data["data"].values()))
    return formatar_resposta(crypto)


def formatar_resposta(crypto: dict) -> dict:
    quote = crypto["quote"]["USD"]

    return {
        "name": crypto["name"],
        "symbol": crypto["symbol"],
        "price": round(quote["price"], 4),
        "change_24h": round(quote["percent_change_24h"], 2)
    }


# =============================
# INTERFACE FINAL (ROUTER)
# =============================
def responder_preco(frase: str) -> str:
    cripto = extrair_nome_cripto(frase)

    if not cripto:
        return "Não consegui identificar nenhuma criptomoeda no que você disse."

    resultado = buscar_preco(cripto)

    if not resultado:
        return f"Não consegui identificar a criptomoeda **{cripto}** com segurança."

    tendencia = "subindo 📈" if resultado["change_24h"] > 0 else "caindo 📉"

    return (
        f"{resultado['name']} ({resultado['symbol']}) está em "
        f"**{resultado['price']:.2f} dólares** agora.\n"
        f"Variação nas últimas 24h: **{resultado['change_24h']}%** ({tendencia}).\n"
        "Quer que eu te diga o que está puxando isso ou só acompanhar por enquanto?"
    )


# =============================
# ALIAS (compatibilidade)
# =============================
def executar_price(frase: str) -> str:
    return responder_preco(frase)
