import importlib
import logging
import os
from typing import Optional

from config.state import STATE
from core.intent import detectar_intencao

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Router")


class RouterLuna:
    def __init__(self):
        self.skills = {}
        self.skill_modulos = []
        self.skill_erros = {}
        self._descobrir_skills()
        logger.info(f"{len(self.skill_modulos)} skills registradas (lazy-load)")

    def _descobrir_skills(self):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        skills_dir = os.path.join(base_dir, "skills")
        if not os.path.isdir(skills_dir):
            logger.warning("Diretorio de skills nao encontrado")
            return
        ignorar = {"conversa1.py", "vision1.py"}
        for nome in os.listdir(skills_dir):
            if not nome.endswith(".py"):
                continue
            if nome.startswith("_") or nome == "__init__.py":
                continue
            if nome in ignorar:
                continue
            self.skill_modulos.append(nome[:-3])
        self.skill_modulos.sort()

    def _validar_skill(self, mod) -> bool:
        if not hasattr(mod, "GATILHOS"):
            logger.warning(f"{mod.__name__} sem GATILHOS")
            return False
        if not hasattr(mod, "executar"):
            logger.warning(f"{mod.__name__} sem executar()")
            return False
        if not hasattr(mod, "SKILL_INFO"):
            logger.warning(f"{mod.__name__} sem SKILL_INFO")
            return False
        return True

    def _carregar_skill(self, nome: str):
        if nome in self.skills:
            return self.skills[nome]
        try:
            mod = importlib.import_module(f"skills.{nome}")
            if self._validar_skill(mod):
                self.skills[nome] = mod
                if hasattr(mod, "inicializar"):
                    mod.inicializar()
                return mod
        except Exception as e:
            logger.error(f"Falha ao carregar {nome}: {e}")
            self.skill_erros[nome] = str(e)
        return None

    def recarregar_skill(self, nome: str):
        try:
            mod = importlib.import_module(f"skills.{nome}")
            mod = importlib.reload(mod)
            if self._validar_skill(mod):
                self.skills[nome] = mod
                if hasattr(mod, "inicializar"):
                    mod.inicializar()
                return mod
        except Exception as e:
            logger.error(f"Falha ao recarregar {nome}: {e}")
            self.skill_erros[nome] = str(e)
        return None

    def recarregar_todas(self):
        carregadas = 0
        for nome in self.skill_modulos:
            if self.recarregar_skill(nome):
                carregadas += 1
        return carregadas

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

        for nome in self.skill_modulos:
            if intent in nome:
                skill = self._carregar_skill(nome)
                if not skill:
                    continue
                try:
                    resp = skill.executar(cmd_limpo)
                    if resp:
                        STATE.adicionar_ao_historico(cmd_limpo, resp)
                    return resp
                except Exception as e:
                    return f"Erro: {e}"

        for nome in self.skill_modulos:
            skill = self._carregar_skill(nome)
            if not skill:
                continue
            info = getattr(skill, "SKILL_INFO", {})
            if intent in info.get("intents", []):
                try:
                    resp = skill.executar(cmd_limpo)
                    if resp:
                        STATE.adicionar_ao_historico(cmd_limpo, resp)
                    return resp
                except Exception as e:
                    return f"Erro: {e}"

        for nome in self.skill_modulos:
            skill = self._carregar_skill(nome)
            if not skill:
                continue
            if any(g in cmd_limpo for g in skill.GATILHOS):
                try:
                    resp = skill.executar(cmd_limpo)
                    if resp:
                        STATE.adicionar_ao_historico(cmd_limpo, resp)
                    return resp
                except Exception as e:
                    return f"Erro: {e}"

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
        info = getattr(skill, "SKILL_INFO", {})
        print(f"{info.get('nome', nome)}: {skill.GATILHOS[:3]}")
