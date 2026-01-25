from __future__ import annotations

from dataclasses import dataclass
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
