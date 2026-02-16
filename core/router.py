import logging
import os
import time
from typing import Optional

from config.state import STATE
from core.event_bus import emit_event
from core.intent import detectar_intencao
from core.skill_registry import SkillRegistry

logger = logging.getLogger("Router")

_RETRY_ATTEMPTS = int(os.getenv("LUNA_RETRY_ATTEMPTS", "2"))
_RETRY_BACKOFF = float(os.getenv("LUNA_RETRY_BACKOFF", "0.4"))


def _with_retry(func, *args, **kwargs):
    last_exc = None
    for tentativa in range(1, _RETRY_ATTEMPTS + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Erro na execucao, tentativa %s/%s",
                tentativa,
                _RETRY_ATTEMPTS,
            )
            if tentativa < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF * tentativa)
    if last_exc:
        raise last_exc


class RouterLuna:
    def __init__(self):
        self.skills = {}
        self.skill_modulos = []
        self.skill_erros = {}
        self._skill_meta: dict[str, dict[str, tuple[str, ...]]] = {}
        self._registry = SkillRegistry()
        self._descobrir_skills()
        logger.info(f"{len(self.skill_modulos)} skills registradas (lazy-load)")

    def _descobrir_skills(self):
        self.skill_modulos = self._registry.discover()
        self._limpar_orfaos()

    def _limpar_orfaos(self):
        ativos = set(self.skill_modulos)
        for nome in list(self.skills.keys()):
            if nome not in ativos:
                self.skills.pop(nome, None)
        for nome in list(self._skill_meta.keys()):
            if nome not in ativos:
                self._skill_meta.pop(nome, None)
        for nome in list(self.skill_erros.keys()):
            if nome not in ativos:
                self.skill_erros.pop(nome, None)

    def _normalizar_lista_str(self, valores) -> tuple[str, ...]:
        itens: list[str] = []
        for valor in valores or []:
            texto = str(valor or "").strip().lower()
            if texto and texto not in itens:
                itens.append(texto)
        return tuple(itens)

    def _registrar_skill_meta(self, nome: str) -> None:
        manifest = self._registry.get_manifest(nome)
        if not manifest:
            return
        intents = self._normalizar_lista_str(manifest.intents)
        gatilhos = self._normalizar_lista_str(manifest.gatilhos)
        self._skill_meta[nome] = {
            "intents": intents,
            "gatilhos": gatilhos,
        }

    def _carregar_skill(self, nome: str):
        if nome in self.skills:
            return self.skills[nome]
        entry = self._registry.load(nome)
        if not entry or not entry.module:
            if entry and entry.last_error:
                self.skill_erros[nome] = entry.last_error
            return None
        self.skills[nome] = entry.module
        self._registrar_skill_meta(nome)
        return entry.module

    def recarregar_skill(self, nome: str):
        entry = self._registry.reload(nome)
        if not entry or not entry.module:
            if entry and entry.last_error:
                self.skill_erros[nome] = entry.last_error
            return None
        self.skills[nome] = entry.module
        self._registrar_skill_meta(nome)
        return entry.module

    def recarregar_todas(self):
        self._descobrir_skills()
        carregadas = self._registry.reload_all()
        # Sincroniza cache local para manter comportamento atual.
        for nome in list(self.skills.keys()):
            if nome not in self.skill_modulos:
                self.skills.pop(nome, None)
        for nome in self.skill_modulos:
            entry = self._registry.get_entry(nome)
            if not entry or not entry.module:
                continue
            self.skills[nome] = entry.module
            self._registrar_skill_meta(nome)
        return carregadas

    def _executar_skill(self, nome: str, cmd_limpo: str, intent: Optional[str]) -> Optional[str]:
        skill = self._carregar_skill(nome)
        if not skill:
            return None
        try:
            emit_event(
                "skill.started",
                {"skill": nome, "intent": intent or "", "command": cmd_limpo},
                source="router",
            )
            logger.info("Skill ativada", extra={"skill": nome, "intent": intent})
            resp = _with_retry(skill.executar, cmd_limpo)
            if resp:
                STATE.adicionar_ao_historico(cmd_limpo, resp)
                emit_event(
                    "skill.completed",
                    {"skill": nome, "intent": intent or "", "response": resp},
                    source="router",
                )
                return resp
            emit_event(
                "skill.completed",
                {"skill": nome, "intent": intent or "", "response": ""},
                source="router",
            )
            return None
        except Exception as e:
            emit_event(
                "skill.error",
                {"skill": nome, "intent": intent or "", "error": str(e)},
                source="router",
            )
            return f"Erro: {e}"

    def _candidatos_por_intent_nome(self, intent: Optional[str]) -> list[str]:
        if not intent:
            return []
        return [nome for nome in self.skill_modulos if intent in nome]

    def _candidatos_por_intent_meta(self, intent: Optional[str]) -> list[str]:
        return self._registry.candidates_by_intent(intent)

    def _candidatos_por_gatilho_meta(self, cmd_limpo: str) -> list[str]:
        return self._registry.candidates_by_trigger(cmd_limpo)

    def processar_comando(self, cmd: str, intent: Optional[str] = None) -> Optional[str]:
        cmd_lower = cmd.lower().strip()
        cmd_limpo = cmd_lower.replace("luna", "").strip()

        if "modo vtuber" in cmd_limpo or "ativar vtuber" in cmd_limpo:
            STATE.set_modo_ativacao("vtuber")
            return "Modo VTuber ativado. Agora respondo sem precisar dizer 'Luna'."

        if "modo assistente" in cmd_limpo or "ativar assistente" in cmd_limpo:
            STATE.set_modo_ativacao("assistente")
            return "Modo Assistente ativado. Diga 'Luna' para falar comigo."

        if "recarregar" in cmd_limpo and ("skill" in cmd_limpo or "skills" in cmd_limpo):
            total = self.recarregar_todas()
            return f"Recarreguei {total} skills."

        if STATE.esperando_nome_sequencia or STATE.esperando_loops or STATE.gravando_sequencia:
            for nome in self.skill_modulos:
                if "sequencia" in nome or "macros" in nome:
                    skill = self._carregar_skill(nome)
                    if skill:
                        return skill.executar(cmd_limpo)
            return "Erro: sequencia nao carregada"

        if STATE.get_modo_ativacao() == "assistente" and not cmd_lower.startswith("luna"):
            return None

        if not cmd_limpo:
            return "Sim?"

        if not intent:
            intent = detectar_intencao(cmd_limpo)

        tentados: set[str] = set()

        fases = (
            self._candidatos_por_intent_nome(intent),
            self._candidatos_por_intent_meta(intent),
            self._candidatos_por_gatilho_meta(cmd_limpo),
        )
        for candidatos in fases:
            for nome in candidatos:
                if nome in tentados:
                    continue
                tentados.add(nome)
                resp = self._executar_skill(nome, cmd_limpo, intent)
                if resp is not None:
                    return resp

        for nome in self.skill_modulos:
            if nome in tentados:
                continue
            skill = self._carregar_skill(nome)
            tentados.add(nome)
            if not skill:
                continue
            meta = self._skill_meta.get(nome, {})
            intents = meta.get("intents", ())
            gatilhos = meta.get("gatilhos", ())
            if (intent and intent in intents) or any(g in cmd_limpo for g in gatilhos):
                resp = self._executar_skill(nome, cmd_limpo, intent)
                if resp is not None:
                    return resp

        return "Nao entendi esse comando."


_router = None


def processar_comando(cmd: str, intent: Optional[str] = None) -> Optional[str]:
    global _router
    if not _router:
        _router = RouterLuna()
    return _router.processar_comando(cmd, intent)


if __name__ == "__main__":
    r = RouterLuna()
    for nome in r.skill_modulos:
        skill = r._carregar_skill(nome)
        if not skill:
            continue
        manifest = r._registry.get_manifest(nome)
        if not manifest:
            print(f"{nome}: (sem manifesto)")
            continue
        print(f"{manifest.nome}: {list(manifest.gatilhos)[:3]}")
