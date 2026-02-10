from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable


@dataclass(frozen=True)
class PromptSection:
    text: str
    priority: int = 0
    label: str | None = None


def build_prompt(
    base: str,
    sections: Iterable[PromptSection],
    joiner: str = "\n\n",
    max_chars: int | None = None,
) -> str:
    parts: list[str] = []
    base_text = (base or "").strip()
    if base_text:
        parts.append(base_text)

    ordered = sorted(sections, key=lambda s: s.priority, reverse=True)
    for section in ordered:
        texto = (section.text or "").strip()
        if not texto:
            continue
        parts.append(texto)

    texto_final = joiner.join(parts)
    if max_chars and max_chars > 0 and len(texto_final) > max_chars:
        texto_final = texto_final[:max_chars].rstrip()
    return texto_final


def build_vision_analysis_prompt(contexto: str, cmd: str, foco: str | None) -> str:
    base = (
        "Voce e a Luna, VTuber e assistente IA.\n"
        f"Contexto: {contexto}\n"
        f"Comando: '{cmd}'\n\n"
        "Analise a imagem e responda:\n"
        "- Descreva a cena com detalhes objetivos\n"
        "- Interprete o contexto (o que parece estar acontecendo)\n"
        "Use 1 a 2 frases sempre completas, sem listas."
    )
    if foco:
        base += f"\n- Foque em {foco} e detalhes relacionados."
    return base


def build_vision_opinion_prompt(cmd: str, analise: str, foco: str | None) -> str:
    base = (
        "Voce e a Luna, VTuber reagindo ao jogo.\n"
        f"Pedido do usuario: '{cmd}'\n\n"
        "ANALISE:\n"
        f"{analise}\n\n"
        "Regras:\n"
        "- Reaja com opiniao natural e divertida (estilo streamer)\n"
        "- Responda em 1 frase completa, no maximo 25 palavras\n"
        "- Sem listas, sem asteriscos ou hashtags\n"
        "- Texto pronto para TTS"
    )
    if foco:
        base += f"\n- Foque em {foco} e detalhes relacionados"
    return base


def build_vision_opinion_reforco() -> str:
    return "INSTRUCAO CRITICA: detalhe mais e evite respostas curtas."


def build_web_reader_prompt(contexto: str, is_twitter: bool) -> str:
    if is_twitter:
        return (
            f"Luna, VTuber. Contexto: {contexto}\n\n"
            "Leia o post do X/Twitter. Responda em NO MAXIMO 3 frases curtas:\n"
            "- Quem postou e o que disse\n"
            "- Se tiver imagem, descreva brevemente\n"
            "- Se aparecer tela de login: \"O Elon trancou.\"\n\n"
            "Sem listas, sem *, sem #. Resposta COMPLETA em 3 frases."
        )
    return (
        f"Luna, assistente. Contexto: {contexto}\n\n"
        "Resuma esta pagina em NO MAXIMO 4 frases curtas:\n"
        "- Tema principal\n"
        "- 2-3 pontos importantes\n"
        "- Ignore menus e anuncios\n\n"
        "Sem listas, sem *, sem #. Resposta COMPLETA em 4 frases."
    )


def build_game_guide_prompt(contexto: str, busca: str) -> str:
    return (
        "Voce e a Luna, assistente gamer e VTuber.\n"
        f"Contexto: {contexto}\n"
        f"O usuario quer um guia para: '{busca}'\n\n"
        "INSTRUCOES:\n"
        "1. Analise a pagina de busca do Google\n"
        "2. Extraia as informacoes principais dos resultados visiveis\n"
        "3. Resuma o passo a passo de forma clara e direta\n"
        "4. Se houver varios metodos, cite o mais rapido\n"
        "5. Use tom sarcastico e confiante\n"
        "6. Responda em portugues brasileiro\n"
        "7. Responda em 3-5 frases uteis\n"
        "8. SEM usar *, -, # ou listas\n\n"
        "Responda como se estivesse explicando ao vivo."
    )


def build_youtube_summary_prompt(texto: str, cmd: str, url: str, contexto: str) -> str:
    return (
        "Voce e a Luna, assistente IA brasileira.\n"
        f"Contexto: {contexto}\n"
        f"Link: {url}\n"
        f"Pedido: {cmd}\n\n"
        "Tarefa: Resuma o conteudo do video usando a transcricao abaixo.\n"
        "Regras:\n"
        "1) 4 a 8 frases, texto corrido, sem listas\n"
        "2) Destaque o tema principal e pontos mais importantes\n"
        "3) Evite repetir a transcricao literalmente\n"
        "4) Nao se apresente e nao cumprimente\n"
        "5) Responda apenas com o resumo\n\n"
        "TRANSCRICAO:\n"
        f"{texto}\n"
    )


def build_youtube_summary_simple_prompt(texto: str, cmd: str, url: str) -> str:
    return (
        f"Contexto: {cmd}\n"
        f"Link: {url}\n\n"
        "Faca um resumo da transcricao. Responda apenas com o resumo:\n"
        f"{texto}\n"
    )


def build_youtube_summary_reforco() -> str:
    return (
        "\nINSTRUCAO EXTRA: Entregue um resumo completo com 6 a 10 frases. "
        "Nao se apresente. Nao cumprimente.\n"
    )


def build_youtube_summary_merge_prompt(contexto: str, url: str, resumos: list[str]) -> str:
    return (
        "Voce e a Luna, assistente IA brasileira.\n"
        f"Contexto: {contexto}\n"
        f"Link: {url}\n\n"
        "Tarefa: Unifique os resumos parciais abaixo em um unico resumo final.\n"
        "Regras:\n"
        "1) 6 a 10 frases, texto corrido, sem listas\n"
        "2) Sem apresentacao ou cumprimento\n"
        "3) Seja objetiva e completa\n\n"
        "RESUMOS PARCIAIS:\n"
        f"{os.linesep.join(resumos)}\n"
    )


def build_system_monitor_prompt(cpu: float, ram: float, contexto: str) -> str:
    return (
        f"A Luna esta analisando o PC do usuario. CPU: {cpu}%, RAM: {ram}%.\n"
        "De uma resposta curta e sarcastica sobre esses numeros."
    )
