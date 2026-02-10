# skills/conversa.py
import os
import warnings
from typing import Optional

try:
    from pydantic.warnings import ArbitraryTypeWarning
    warnings.filterwarnings("ignore", category=ArbitraryTypeWarning)
except Exception:
    warnings.filterwarnings("ignore", message=r".*is not a Python type.*")

from google import genai
from google.genai import types
import logging
import yaml
import pyperclip
import unicodedata

from config.env import init_env
from config.state import STATE
from core import memory
from core.prompt_injector import PromptSection, build_prompt
from core.realtime_panel import atualizar_estado


init_env()


logger = logging.getLogger("Conversa")

FALLBACK_MSG = "Ainda estou pensando aqui, tenta de novo em instantes."

SKILL_INFO = {
    "nome": "Conversa",
    "descricao": "Conversa com personalidade usando Gemini",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["chat", "conversa"],
}

GATILHOS = ["conversa", "falar", "chat", "papo", "fale comigo"]

MODEL_NAME = os.getenv("LUNA_GEMINI_MODEL", "gemini-3-flash-preview")
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_SYSTEM_PROMPT_PATH = os.path.join(_BASE_DIR, "system_message.txt")
_DEFAULT_SYSTEM_YAML_PATH = os.path.join(_BASE_DIR, "system_message.yaml")

API_KEYS = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
API_KEYS = [k for k in API_KEYS if k]

_current_key_index = 0


def inicializar():
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    msg = (comando or "").strip()
    if not msg:
        return "Diz ai."

    msg = _injetar_clipboard_se_necessario(msg)

    memoria = _tratar_memoria(msg)
    if memoria:
        return memoria

    return _conversar(msg)


def _tratar_memoria(msg: str) -> Optional[str]:
    msg_lower = msg.lower().strip()

    if msg_lower.startswith("lembre que ") or msg_lower.startswith("lembra que "):
        texto = msg[10:].strip()
        if memory.adicionar_memoria(texto):
            return "Ok, vou lembrar disso."
        return "Nao consegui salvar essa memoria."

    if any(p in msg_lower for p in ["o que voce lembra", "quais memorias", "minhas memorias"]):
        itens = memory.listar_memorias(5)
        if not itens:
            return "Ainda nao tenho memorias salvas."
        lista = "; ".join([i.get("texto", "") for i in itens if i.get("texto")])
        return f"Eu lembro disso: {lista}"

    return None


def _injetar_clipboard_se_necessario(msg: str) -> str:
    msg_lower = msg.lower().strip()
    msg_norm = (
        unicodedata.normalize("NFKD", msg_lower)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    msg_norm = msg_norm.replace("luna", "").strip()
    gatilhos = [
        "o que e isso",
        "o que e isso?",
        "o que significa isso",
        "o que significa isso?",
        "o que e isso ai",
        "o que e isso ai?",
        "me explica isso",
        "me explica isso?",
        "explica isso",
        "explica isso?",
    ]
    if not any(g in msg_norm for g in gatilhos):
        return msg
    try:
        texto = pyperclip.paste().strip()
    except Exception:
        return msg
    if not texto:
        return msg
    if len(texto) > 1500:
        texto = texto[:1500].rstrip()
    return f"{msg}\n\nTexto selecionado:\n{texto}"


def _conversar(msg: str) -> str:
    if not API_KEYS:
        return "GEMINI_API_KEY nao configurada."

    contents = [_montar_mensagem(msg)]
    system_instruction = _montar_prompt_personalidade(msg)
    temperature = _temperatura_modo()
    max_tokens = _max_tokens_modo()

    for tentativa in range(len(API_KEYS)):
        try:
            client = _obter_cliente()
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    system_instruction=system_instruction,
                ),
            )
            texto = _extract_text(response)
            resposta = _normalizar_resposta(texto)
            if _precisa_reforco(resposta, msg):
                reforco = (
                    "INSTRUCAO CRITICA: responda com mais detalhes, "
                    "3 a 5 frases completas, especifico e direto."
                )
                resposta = _tentar_reforco(
                    msg,
                    system_instruction + "\n\n" + reforco,
                    temperature,
                    max_tokens,
                )
            return _normalizar_resposta(resposta)
        except Exception as exc:
            status_code = _extrair_status_code(exc)
            key_info = f"key {_current_key_index + 1}/{len(API_KEYS)}"
            logger.error(
                "Erro Gemini (%s, %s, tentativa %s/%s)",
                status_code,
                key_info,
                tentativa + 1,
                len(API_KEYS),
            )
            try:
                status = f"Erro Gemini [{status_code}] {key_info}"
                atualizar_estado(status=status)
            except Exception:
                pass
            if _pode_trocar_chave(exc) and tentativa < len(API_KEYS) - 1:
                _trocar_chave()
                continue
            break

    return FALLBACK_MSG


def _montar_mensagem(msg: str) -> str:
    partes = []
    contexto = _montar_contexto_curto()
    ultimas_secao = _montar_ultima_resposta() if _pede_expansao(msg) else None
    visao_secao = _montar_ultima_visao()
    prompt_order = _obter_prompt_order()

    if prompt_order == "inject_then_trim":
        secao_contexto = PromptSection(contexto or "", priority=10, label="contexto")
        secao_visao = PromptSection(visao_secao or "", priority=30, label="visao")
        secao_ultima = PromptSection(ultimas_secao or "", priority=20, label="ultima")
    else:
        secao_contexto = PromptSection(contexto or "", priority=30, label="contexto")
        secao_visao = PromptSection(visao_secao or "", priority=20, label="visao")
        secao_ultima = PromptSection(ultimas_secao or "", priority=10, label="ultima")

    bloco_contexto = build_prompt("", [secao_contexto, secao_visao, secao_ultima])
    if bloco_contexto:
        partes.append(bloco_contexto)

    if _pede_expansao(msg) and not ultimas_secao:
        ultima_resposta = STATE.obter_ultima_resposta()
        if ultima_resposta:
            partes.append(f"Ultima resposta:\n{ultima_resposta}")

    partes.append(f"Usuario:\n{msg}")
    return "\n\n".join(partes)


def _montar_prompt_personalidade(msg: str) -> str:
    modo = STATE.get_modo_ativacao()
    base = _carregar_system_prompt()

    secoes = [PromptSection(base, priority=100, label="base")]
    if modo == "vtuber":
        secoes.append(
            PromptSection(
                "Fale como se estivesse ao vivo, com personalidade e leve ironia, "
                "sem perder a clareza.",
                priority=90,
                label="modo",
            )
        )

    instrucoes_extras = []
    msg_lower = msg.lower()
    tem_visao = bool(STATE.get_ultima_visao())

    if _pede_expansao(msg):
        instrucoes_extras.append(
            "O usuario pediu para expandir a resposta. "
            "Reescreva com mais detalhes e sem repetir exatamente."
        )

    if _pede_opiniao(msg_lower):
        if tem_visao:
            instrucoes_extras.append(
                "O usuario pediu sua opiniao sobre a ultima imagem/visao. "
                "Responda com 3 a 4 frases, com detalhes do que viu."
            )
        else:
            instrucoes_extras.append(
                "O usuario pediu sua opiniao. Responda com 3 a 4 frases e justificativa."
            )

    if _pede_descricao(msg_lower) and tem_visao:
        instrucoes_extras.append(
            "O usuario pediu descricao/detalhes da ultima imagem. "
            "Descreva elementos, cores e detalhes visiveis em 4 a 6 frases."
        )

    if instrucoes_extras:
        secoes.append(
            PromptSection(
                "\n".join(instrucoes_extras),
                priority=80,
                label="extras",
            )
        )

    return build_prompt("", secoes)


def _obter_prompt_order() -> str:
    valor = os.getenv("LUNA_PROMPT_ORDER", "inject_then_trim").strip().lower()
    if valor not in {"inject_then_trim", "trim_then_inject"}:
        return "inject_then_trim"
    return valor


def _obter_mem_length() -> int:
    bruto = os.getenv("LUNA_MEM_LENGTH", "2")
    try:
        valor = int(bruto)
        return max(1, valor)
    except ValueError:
        return 2


def _obter_system_prompt_path() -> str:
    path = os.getenv("LUNA_SYSTEM_PROMPT_PATH", _DEFAULT_SYSTEM_PROMPT_PATH)
    return path


def _obter_system_yaml_path() -> str:
    path = os.getenv("LUNA_SYSTEM_YAML_PATH", _DEFAULT_SYSTEM_YAML_PATH)
    return path


def _carregar_system_prompt_yaml() -> str | None:
    path = _obter_system_yaml_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        presets = data.get("presets", {})
        default = presets.get("default", {})
        texto = (default.get("system_prompt") or "").strip()
        return texto or None
    except Exception:
        return None


def _carregar_system_prompt() -> str:
    texto_yaml = _carregar_system_prompt_yaml()
    if texto_yaml:
        return texto_yaml
    path = _obter_system_prompt_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            texto = f.read().strip()
        if texto:
            return texto
    except Exception:
        pass
    return (
        "Voce e a Luna, assistente virtual brasileira. "
        "Responda em portugues brasileiro, com tom natural e direto. "
        "Use 2 a 4 frases completas, sem listas, sem asteriscos ou hashtags. "
        "Seja especifica e evite respostas genericas. "
        "Finalize com pontuacao completa e sem perguntas vazias."
    )


def _montar_contexto_curto() -> Optional[str]:
    historico = STATE.historico or []
    if not historico:
        return "Contexto curto:\nPrimeira interacao"

    mem_length = _obter_mem_length()
    ultimas = historico[-mem_length:]
    linhas = []
    for item in ultimas:
        comando = item.get("comando", "")
        resposta = item.get("resposta", "")
        linhas.append(f"U: {comando}\nL: {resposta[:50]}...")
    return "Contexto curto:\n" + "\n\n".join(linhas)


def _montar_ultima_visao() -> Optional[str]:
    ultima_visao = STATE.get_ultima_visao()
    if ultima_visao:
        return f"Ultima visao:\n{ultima_visao}"
    return None


def _montar_ultima_resposta() -> Optional[str]:
    ultima_resposta = STATE.obter_ultima_resposta()
    if ultima_resposta:
        return f"Ultima resposta:\n{ultima_resposta}"
    return None


def _temperatura_modo() -> float:
    return 0.9 if STATE.get_modo_ativacao() == "vtuber" else 0.7


def _max_tokens_modo() -> int:
    return 500


def _obter_cliente():
    return genai.Client(api_key=API_KEYS[_current_key_index])


def _trocar_chave():
    global _current_key_index
    _current_key_index = (_current_key_index + 1) % len(API_KEYS)


def _pode_trocar_chave(exc: Exception) -> bool:
    texto = str(exc)
    return any(x in texto for x in ["429", "quota", "RESOURCE_EXHAUSTED", "rate limit"])


def _extrair_status_code(exc: Exception) -> str:
    for attr in ("status_code", "code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return str(val)
    texto = str(exc)
    for token in texto.split():
        if token.isdigit() and len(token) in (3, 4):
            return token
    return "erro"


def _extract_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        chunks = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(part_text)
        if chunks:
            return "\n".join(chunks)
    return ""


def _tentar_reforco(
    msg: str,
    system_instruction: str,
    temperature: float,
    max_tokens: int,
) -> str:
    try:
        client = _obter_cliente()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[_montar_mensagem(msg)],
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction,
            ),
        )
        return _extract_text(response)
    except Exception:
        return ""


def _pede_opiniao(msg_lower: str) -> bool:
    termos = [
        "o que voce acha",
        "o que acha",
        "sua opiniao",
        "o que voce achou",
        "acha da",
        "acha do",
    ]
    return any(t in msg_lower for t in termos)


def _pede_descricao(msg_lower: str) -> bool:
    termos = [
        "descreva",
        "descricao",
        "caracteristicas",
        "detalhes",
        "o que voce ve",
        "o que tem",
        "roupa",
        "vestindo",
    ]
    return any(t in msg_lower for t in termos)


def _pede_expansao(msg: str) -> bool:
    msg_lower = msg.lower()
    termos = [
        "resposta mais",
        "mais detalhes",
        "mais completo",
        "aprofundar",
        "detalhe mais",
        "explique melhor",
    ]
    return any(t in msg_lower for t in termos)


def _precisa_reforco(resposta: str, msg: str) -> bool:
    limpa = (resposta or "").strip()
    if not limpa:
        return True
    if len(limpa) < 60:
        return True
    palavras_finais = limpa.split()
    if palavras_finais:
        ultima = palavras_finais[-1].rstrip(".!?").lower()
        preposicoes_soltas = {
            "a", "o", "as", "os", "de", "da", "do", "das", "dos",
            "em", "no", "na", "nos", "nas", "com", "por", "para",
            "aquele", "aquela", "aquilo", "isso", "essa", "esse",
        }
        if ultima in preposicoes_soltas:
            return True
    frases = [f for f in limpa.replace("!", ".").replace("?", ".").split(".") if f.strip()]
    if len(frases) < 2:
        return True
    if limpa and not limpa.endswith((".", "!", "?")):
        return True
    if _pede_descricao(msg.lower()) and len(limpa) < 100:
        return True
    return False


def _normalizar_resposta(texto: Optional[str]) -> str:
    if not texto:
        return FALLBACK_MSG
    limpa = texto.strip()
    if limpa and not limpa.endswith((".", "!", "?")):
        limpa += "."
    return limpa
