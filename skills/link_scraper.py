# skills/link_scraper.py
import os
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from skills.web_reader import capturar_url_atual


SKILL_INFO = {
    "nome": "Link Scraper",
    "descricao": "Extrai todos os links de um site e salva em .txt",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["link_scraper"],
}

GATILHOS = [
    "extrair links",
    "listar links",
    "coletar links",
    "salvar links",
    "mapear links",
    "raspar links",
]


def inicializar():
    """Chamada quando a skill é carregada."""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    """Extrai links de uma URL e salva em arquivo .txt."""
    url = _extrair_url(comando)
    if not url:
        url = capturar_url_atual()
    if not url:
        return "Não encontrei nenhuma página aberta. Abra um site e tente novamente."

    try:
        links = _coletar_links(url, max_pages=30)
    except Exception as e:
        return f"Erro ao acessar o site: {e}"

    if not links:
        return "Não encontrei links nessa página."

    caminho = _salvar_links(links, url)
    return f"Salvei {len(links)} links em: {caminho}"


def _extrair_url(comando: str) -> str | None:
    match = re.search(r"https?://\S+", comando)
    if not match:
        return None
    return match.group(0).strip().rstrip(".,;)]")


def _coletar_links(url: str, max_pages: int = 30) -> list[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    origem = urlparse(url).netloc
    fila: list[str] = [url]
    visitados: set[str] = set()
    links: list[str] = []
    vistos_links: set[str] = set()

    while fila and len(visitados) < max_pages:
        atual = fila.pop(0)
        if atual in visitados:
            continue
        visitados.add(atual)

        resp = requests.get(atual, headers=headers, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            link = _normalizar_link(href, atual)
            if not link:
                continue
            if link not in vistos_links:
                vistos_links.add(link)
                links.append(link)

            parsed = urlparse(link)
            if parsed.netloc == origem and link not in visitados:
                fila.append(link)

    return links


def _normalizar_link(href: str, base_url: str) -> str | None:
    if not href or href.startswith("#"):
        return None
    if href.startswith(("mailto:", "javascript:", "tel:")):
        return None

    link = urljoin(base_url, href)
    parsed = urlparse(link)
    if parsed.scheme not in {"http", "https"}:
        return None
    return link


def _salvar_links(links: list[str], base_url: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    nome_base = _nome_arquivo_por_url(base_url)
    caminho = os.path.join(data_dir, f"{nome_base}.txt")

    with open(caminho, "w", encoding="utf-8") as f:
        for link in links:
            f.write(link + "\n")

    return caminho


def _nome_arquivo_por_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.split(":")[0]
    if host:
        partes = [p for p in host.split(".") if p]
        nome = partes[0] if partes else "links"
    else:
        nome = "links"
    nome = "".join(ch for ch in nome if ch.isalnum() or ch in ("-", "_")).strip()
    return nome or "links"
