# skills/news.py
import os
import re
import unicodedata
import logging
from datetime import datetime
from urllib.parse import urlparse
from core.http_client import SESSION


SKILL_INFO = {
    "nome": "Noticias",
    "descricao": "Busca noticias usando SerpAPI",
    "versao": "1.1.6",
    "autor": "Luna Team",
    "intents": ["noticias", "news"],
}

GATILHOS = ["noticia", "noticias", "news", "jornal", "acontecendo"]
logger = logging.getLogger("NewsSkill")
_LAST_NEWS_CONTEXT: dict = {"query": "", "items": [], "updated_at": ""}


def inicializar():
    """Chamada quando a skill e carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    """Busca noticias baseado no comando"""
    cmd_norm = _normalizar((comando or "").lower())
    if _eh_comando_resumo(cmd_norm):
        return _resumir_noticia_em_contexto(cmd_norm)

    periodo = _extrair_periodo(comando)
    limit = _extrair_limite(comando)
    query = _extrair_query(comando)
    if not query:
        return "Quer noticias sobre o que?"
    return buscar_noticias(query, periodo=periodo, limit=limit)


def buscar_noticias(query: str, periodo: dict | None = None, limit: int = 3) -> str:
    """Busca noticias usando SerpAPI"""
    serpapi_api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY", "")
    if not serpapi_api_key:
        return "SERPAPI_API_KEY nao configurada."

    periodo = periodo or {}
    tbs = str(periodo.get("tbs") or "")
    when = str(periodo.get("when") or "")

    params_google = {
        "engine": "google",
        "q": query,
        "hl": "pt-BR",
        "gl": "br",
        "api_key": serpapi_api_key,
        "tbm": "nws",
    }
    if tbs:
        params_google["tbs"] = tbs

    params_google_news = {
        "engine": "google_news",
        "q": query,
        "hl": "pt-BR",
        "gl": "br",
        "api_key": serpapi_api_key,
    }
    if when:
        params_google_news["when"] = when

    tentativas = [
        params_google,
        params_google_news,
    ]

    erro_fatal = ""
    try:
        for params in tentativas:
            r = SESSION.get("https://serpapi.com/search", params=params, timeout=12)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get("error"):
                erro_msg = str(data.get("error", "erro_serpapi"))
                if _is_no_results_error(erro_msg):
                    continue
                erro_fatal = erro_msg
                continue

            resultados = _extrair_resultados(data)
            if periodo:
                resultados = [
                    item for item in resultados if _resultado_compativel_periodo(item, periodo)
                ]
            if not resultados:
                continue

            _registrar_ultimas_noticias(query, resultados)
            texto = _formatar_noticias(resultados, query=query, limit=limit)
            if texto:
                return texto

        if erro_fatal:
            return f"Erro ao buscar noticias: {erro_fatal}"
        if periodo:
            return "Nao encontrei noticias recentes nesse periodo."
        return "Nao encontrei informacoes relevantes sobre isso."
    except Exception as e:
        logger.warning("Falha ao buscar noticias", exc_info=True)
        return f"Erro ao buscar noticias: {e}"


def _extrair_query(comando: str) -> str:
    texto = (comando or "").strip()
    if not texto:
        return ""

    texto = _normalizar(texto.lower())
    tokens_remover = [
        "luna",
        "busque",
        "buscar",
        "busca",
        "procure",
        "traga",
        "traz",
        "mostre",
        "quero",
        "me",
        "de",
        "diga",
        "preciso",
        "noticia",
        "noticias",
        "news",
        "manchete",
        "manchetes",
        "jornal",
        "acontecendo",
        "ela",
        "ele",
        "isso",
        "isto",
        "tem",
        "tenha",
        "que",
        "ser",
        "sobre",
        "a",
        "o",
        "os",
        "as",
        "um",
        "uma",
        "do",
        "da",
        "de",
        "dos",
        "das",
        "no",
        "na",
        "nos",
        "nas",
        "hoje",
        "agora",
        "semana",
        "mes",
        "ano",
        "dessa",
        "deste",
        "desse",
        "dessa",
        "esta",
        "este",
        "essa",
        "esse",
        "nesta",
        "neste",
        "nessa",
        "nesse",
        "ultimas",
        "ultimos",
        "ultima",
        "ultimo",
        "recente",
        "recentes",
    ]
    pattern = r"\b(" + "|".join(re.escape(t) for t in tokens_remover) + r")\b"
    texto = re.sub(pattern, " ", texto)
    texto = re.sub(r"\b\d+\b", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    termos = [t for t in texto.split() if len(t) > 1]
    texto = " ".join(termos)
    return texto


def _normalizar(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _extrair_resultados(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    candidates = (
        data.get("news_results")
        or data.get("organic_results")
        or data.get("results")
        or []
    )
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _registrar_ultimas_noticias(query: str, resultados: list[dict]) -> None:
    itens = []
    for item in resultados[:5]:
        if not isinstance(item, dict):
            continue
        titulo = _limpar_texto(item.get("title") or "")
        if not titulo:
            continue
        snippet = _limpar_texto(item.get("snippet") or "")
        fonte, data_pub = _fonte_e_data(item)
        itens.append(
            {
                "title": titulo,
                "snippet": snippet,
                "source": fonte,
                "date": data_pub,
            }
        )
    if not itens:
        return
    _LAST_NEWS_CONTEXT["query"] = query
    _LAST_NEWS_CONTEXT["items"] = itens
    _LAST_NEWS_CONTEXT["updated_at"] = datetime.now().isoformat(timespec="seconds")


def _eh_comando_resumo(cmd_norm: str) -> bool:
    if not cmd_norm:
        return False
    termos_resumo = [
        "resuma",
        "resumir",
        "resumo",
        "faca um resumo",
        "faça um resumo",
        "faz um resumo",
    ]
    if not any(t in cmd_norm for t in termos_resumo):
        return False
    if any(t in cmd_norm for t in ["busque", "buscar", "busca", "procure", "traga", "traz", "mostre"]):
        return False
    if any(t in cmd_norm for t in ["noticia", "noticias", "manchete", "manchetes", "dessa", "dessa noticia", "encontrada", "que voce achou"]):
        return True
    return bool(_LAST_NEWS_CONTEXT.get("items"))


def _resumir_noticia_em_contexto(cmd_norm: str) -> str:
    itens = _LAST_NEWS_CONTEXT.get("items") or []
    if not itens:
        return "Ainda nao tenho noticia salva para resumir. Primeiro peca para eu buscar noticias."

    idx = _extrair_indice_noticia(cmd_norm, total=len(itens))
    item = itens[idx]
    query = _LAST_NEWS_CONTEXT.get("query") or "o tema pedido"

    titulo = _limpar_texto(item.get("title") or "")
    snippet = _limpar_texto(item.get("snippet") or "")
    fonte = _limpar_texto(item.get("source") or "")
    data_pub = _limpar_texto(item.get("date") or "")

    resumo_curto = _gerar_resumo_curto(titulo=titulo, snippet=snippet, query=query)
    partes = [f"Resumo da noticia {idx + 1} sobre {query}: {resumo_curto}"]
    if fonte:
        detalhe_fonte = f"Fonte: {fonte}"
        if data_pub:
            detalhe_fonte += f", {data_pub}"
        partes.append(_garantir_ponto(detalhe_fonte))
    return " ".join(partes)


def _extrair_indice_noticia(cmd_norm: str, total: int) -> int:
    m = re.search(r"\b(\d{1,2})\s*(noticia|noticias|manchete|manchetes|item)\b", cmd_norm)
    if m:
        try:
            idx = int(m.group(1)) - 1
            if 0 <= idx < total:
                return idx
        except Exception:
            pass

    ordinais = {
        "primeira": 0,
        "primeiro": 0,
        "segunda": 1,
        "segundo": 1,
        "terceira": 2,
        "terceiro": 2,
    }
    for termo, idx in ordinais.items():
        if termo in cmd_norm and idx < total:
            return idx
    return 0


def _extrair_periodo(comando: str) -> dict:
    texto = _normalizar((comando or "").lower())

    if any(t in texto for t in ["hoje", "agora", "ultimas 24", "ultimos 24", "24h", "24 h"]):
        return {"kind": "day", "tbs": "qdr:d", "when": "1d"}
    if "semana" in texto:
        return {"kind": "week", "tbs": "qdr:w", "when": "7d"}
    if "mes" in texto:
        return {"kind": "month", "tbs": "qdr:m", "when": "1m"}
    if "ano" in texto:
        return {"kind": "year", "tbs": "qdr:y", "when": "1y"}
    return {}


def _extrair_limite(comando: str) -> int:
    texto = _normalizar((comando or "").lower())
    m = re.search(r"\b(\d{1,2})\s*(noticia|noticias|news|manchete|manchetes)\b", texto)
    if m:
        try:
            val = int(m.group(1))
            return max(1, min(5, val))
        except Exception:
            return 3
    if any(t in texto for t in ["uma noticia", "uma manchete", "1 noticia", "1 manchete"]):
        return 1
    return 3


def _resultado_compativel_periodo(item: dict, periodo: dict) -> bool:
    kind = (periodo or {}).get("kind")
    if kind not in {"day", "week", "month"}:
        return True

    date_text = _limpar_texto(item.get("date") or "")
    if not date_text:
        return True

    age_days = _age_days_from_text(date_text)
    if age_days is not None:
        if kind == "day":
            return age_days <= 1
        if kind == "week":
            return age_days <= 7
        if kind == "month":
            return age_days <= 31
        return True

    year_match = re.search(r"\b(19|20)\d{2}\b", date_text)
    if year_match:
        try:
            year = int(year_match.group(0))
            if year < datetime.now().year:
                return False
        except Exception:
            return True
    return True


def _is_no_results_error(msg: str) -> bool:
    t = (msg or "").strip().lower()
    if not t:
        return False
    markers = (
        "hasn't returned any results",
        "has not returned any results",
        "didn't return any results",
        "did not return any results",
        "no results for this query",
        "nenhum resultado",
        "nao retornou resultados",
    )
    return any(m in t for m in markers)


def _age_days_from_text(date_text: str) -> int | None:
    t = _normalizar((date_text or "").lower())
    if not t:
        return None
    if "hoje" in t or "today" in t or "agora" in t:
        return 0
    if "ontem" in t or "yesterday" in t:
        return 1

    m = re.search(r"(\d+)\s*(min|mins|minute|minutes|minuto|minutos)", t)
    if m:
        return 0
    m = re.search(r"(\d+)\s*(h|hr|hrs|hour|hours|hora|horas)", t)
    if m:
        return 0
    m = re.search(r"(\d+)\s*(day|days|dia|dias)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(week|weeks|semana|semanas)", t)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r"(\d+)\s*(month|months|mes|meses)", t)
    if m:
        return int(m.group(1)) * 30
    return None


def _formatar_noticias(resultados: list[dict], query: str, limit: int = 3) -> str:
    blocos: list[str] = []
    for item in resultados:
        title = _limpar_texto(item.get("title") or "")
        if not title:
            continue
        snippet = _limpar_texto(item.get("snippet") or "")
        if snippet:
            snippet = _limitar_palavras(snippet, max_words=24)
            if _texto_incompleto(snippet):
                snippet = ""

        fonte, data_pub = _fonte_e_data(item)

        partes = [f"{len(blocos) + 1}) {_garantir_ponto(title)}"]
        if snippet:
            partes.append(_garantir_ponto(snippet))
        if fonte:
            detalhe_fonte = f"Fonte: {fonte}"
            if data_pub:
                detalhe_fonte += f", {data_pub}"
            partes.append(_garantir_ponto(detalhe_fonte))

        blocos.append(" ".join(partes))
        if len(blocos) >= limit:
            break

    if not blocos:
        return ""

    cabecalho = f"Achei {len(blocos)} noticias sobre {query}:"
    return f"{cabecalho} " + " ".join(blocos)


def _fonte_e_data(item: dict) -> tuple[str, str]:
    source = _limpar_texto(item.get("source") or "")
    date = _limpar_texto(item.get("date") or "")
    if not source:
        link = _limpar_texto(item.get("link") or "")
        if link:
            try:
                host = urlparse(link).netloc.lower()
                host = host[4:] if host.startswith("www.") else host
                source = host
            except Exception:
                source = ""
    return source, date


def _limpar_texto(texto: str) -> str:
    t = str(texto or "").strip()
    if not t:
        return ""
    t = t.replace("…", "...")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;!?])", r"\1", t)
    return t.strip(" -|")


def _garantir_ponto(texto: str) -> str:
    t = (texto or "").strip()
    if not t:
        return ""
    if t.endswith((".", "!", "?")):
        return t
    return t + "."


def _limitar_palavras(texto: str, max_words: int = 24) -> str:
    palavras = (texto or "").split()
    if len(palavras) <= max_words:
        return texto
    return " ".join(palavras[:max_words]).rstrip()


def _texto_incompleto(texto: str) -> bool:
    t = (texto or "").strip().lower()
    if not t:
        return True
    if t.endswith("..."):
        return True
    ultima = re.sub(r"[.!?]+$", "", t).split()[-1]
    conectores = {
        "e", "de", "da", "do", "dos", "das", "com", "para", "por",
        "sem", "que", "todo", "toda", "todos", "todas",
    }
    return ultima in conectores


def _gerar_resumo_curto(titulo: str, snippet: str, query: str) -> str:
    snippet_limpo = _limpar_texto(snippet)
    titulo_limpo = _limpar_texto(titulo)
    base = ""

    if snippet_limpo and not _texto_incompleto(snippet_limpo):
        base = _sintese_especialistas(snippet_limpo, query=query) or _normalizar_texto_resumo(snippet_limpo)
    elif titulo_limpo:
        base = _normalizar_texto_resumo(titulo_limpo)

    base = _remover_clickbait(base)
    base = _limitar_palavras_resumo(base, max_words=24)

    if not base:
        return _garantir_ponto(f"Noticia sobre {query} sem detalhes suficientes")

    return _garantir_ponto(base)


def _remover_clickbait(texto: str) -> str:
    t = _normalizar(_limpar_texto(texto))
    if not t:
        return ""

    # Remove aberturas de clickbait comuns em manchetes.
    t = re.sub(r"^(veja|entenda|saiba|descubra)\b[:\-]?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(
        r"o que ninguem (esta|te) (te )?contando sobre",
        "os fatores por tras de",
        t,
        flags=re.IGNORECASE,
    )

    if "?" in t:
        antes, depois = t.split("?", 1)
        # Se o inicio for pergunta chamativa, usa a parte informativa apos "?".
        if len(antes.split()) <= 10 and len(depois.split()) >= 5:
            t = depois.strip()

    return _limpar_texto(t)


def _normalizar_texto_resumo(texto: str) -> str:
    t = _normalizar(_limpar_texto(texto))
    if not t:
        return ""

    substituicoes = (
        (r"\bfalam sobre\b", "abordam"),
        (r"\bfala sobre\b", "aborda"),
        (r"\bo que esta por tras da\b", "os fatores por tras da"),
        (r"\bo que esta por tras do\b", "os fatores por tras da"),
        (r"\bo que esta por tras de\b", "os fatores por tras de"),
        (r"\btombo historico\b", "queda recente"),
    )
    for pattern, novo in substituicoes:
        t = re.sub(pattern, novo, t, flags=re.IGNORECASE)

    t = re.sub(r"\bdo queda\b", "da queda", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _limitar_palavras_resumo(texto: str, max_words: int = 20) -> str:
    t = _limitar_palavras(texto, max_words=max_words).strip(" ,;:-")
    while t and _texto_incompleto(t):
        palavras = t.split()
        if len(palavras) <= 1:
            break
        t = " ".join(palavras[:-1]).strip(" ,;:-")
    return t


def _sintese_especialistas(snippet: str, query: str) -> str:
    s = _limpar_texto(snippet)
    if not s:
        return ""

    m = re.match(
        r"^[^,]{2,},\s*da\s+([^,]{2,}),\s*e\s+[^,]{2,},\s*da\s+([^,]{2,}),\s*(?:falam|fala|comentam|explicam)\s+sobre\s+(.+)$",
        s,
        flags=re.IGNORECASE,
    )
    if not m:
        return ""

    casa1 = _limpar_texto(m.group(1))
    casa2 = _limpar_texto(m.group(2))
    assunto = _limpar_texto(m.group(3))
    tema = _tema_resumo(assunto, query)

    if casa1 and casa2:
        return f"Analistas da {casa1} e da {casa2} analisam {tema}"
    return f"Analistas analisam {tema}"


def _tema_resumo(assunto: str, query: str) -> str:
    a = _normalizar(_limpar_texto(assunto)).lower()
    q = _normalizar(_limpar_texto(query)).lower()
    base = f"{a} {q}".strip()

    if "btc" in base or "bitcoin" in base:
        return "os fatores por tras da queda recente do BTC"
    if "eth" in base or "ethereum" in base:
        return "os fatores por tras da queda recente do Ethereum"
    if "queda" in base or "tombo" in base:
        return "as causas da queda recente no mercado"
    if q:
        return f"os principais fatores ligados a {q}"
    return "os principais fatores por tras do movimento de mercado"
