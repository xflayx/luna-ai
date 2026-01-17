# core/router.py
import os, sys, importlib, logging
from typing import Optional, Dict
from config.state import STATE
from core.intent import detectar_intencao

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Router")

class RouterLuna:
    def __init__(self):
        self.skills = {}
        self.skill_modulos = []
        self.skill_erros = {}
        self.carregar_skills()

    def carregar_skills(self):
        pasta = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
        
        for arquivo in os.listdir(pasta):
            if not arquivo.endswith('.py') or arquivo.startswith('_'):
                continue
            
            nome = arquivo[:-3]
            self.skill_modulos.append(nome)
        
        logger.info(f"📦 {len(self.skill_modulos)} skills registradas (lazy-load)")

    def _validar_skill(self, mod) -> bool:
        """Valida se o módulo segue o contrato de skill."""
        if not hasattr(mod, "GATILHOS"):
            logger.warning(f"⚠️ {mod.__name__} sem GATILHOS")
            return False
        if not hasattr(mod, "executar"):
            logger.warning(f"⚠️ {mod.__name__} sem executar()")
            return False
        if not hasattr(mod, "SKILL_INFO"):
            logger.warning(f"⚠️ {mod.__name__} sem SKILL_INFO")
            return False
        return True

    def _carregar_skill(self, nome: str):
        if nome in self.skills:
            return self.skills[nome]
        try:
            mod = importlib.import_module(f"skills.{nome}")
            if self._validar_skill(mod):
                self.skills[nome] = mod
                if hasattr(mod, 'inicializar'):
                    mod.inicializar()
                else:
                    logger.info(f"✅ {nome}")
                return mod
        except Exception as e:
            logger.error(f"❌ {nome}: {e}")
            self.skill_erros[nome] = str(e)
        return None

    def recarregar_skill(self, nome: str):
        """Recarrega uma skill específica (hot-reload)."""
        try:
            mod = importlib.import_module(f"skills.{nome}")
            mod = importlib.reload(mod)
            if self._validar_skill(mod):
                self.skills[nome] = mod
                if hasattr(mod, 'inicializar'):
                    mod.inicializar()
                else:
                    logger.info(f"✅ {nome} (recarregada)")
                return mod
        except Exception as e:
            logger.error(f"❌ Falha ao recarregar {nome}: {e}")
            self.skill_erros[nome] = str(e)
        return None

    def recarregar_todas(self):
        """Recarrega todas as skills conhecidas."""
        carregadas = 0
        for nome in self.skill_modulos:
            if self.recarregar_skill(nome):
                carregadas += 1
        return carregadas

    def processar_comando(self, cmd: str, intent: Optional[str] = None) -> Optional[str]:
        cmd_lower = cmd.lower().strip()
        cmd_limpo = cmd_lower.replace("luna", "").strip()

        # Estados de sequência (prioridade máxima)
        if STATE.esperando_nome_sequencia or STATE.esperando_loops or STATE.gravando_sequencia:
            for nome in self.skill_modulos:
                if "sequencia" in nome or "macros" in nome:
                    skill = self._carregar_skill(nome)
                    if skill:
                        return skill.executar(cmd_limpo)
            return "Erro: sequência não carregada"

        # Filtro "Luna"
        if not cmd_lower.startswith("luna"):
            return None
        
        if not cmd_limpo:
            return "Sim?"

        # Detecta intenção
        if not intent:
            intent = detectar_intencao(cmd_limpo)

        # Busca por intenção
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
            info = getattr(skill, 'SKILL_INFO', {})
            if intent in info.get('intents', []):
                try:
                    resp = skill.executar(cmd_limpo)
                    if resp:
                        STATE.adicionar_ao_historico(cmd_limpo, resp)
                    return resp
                except Exception as e:
                    return f"Erro: {e}"

        # Busca por gatilhos
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

        return "Não entendi esse comando."

_router = None

def processar_comando(cmd: str, intent: Optional[str] = None) -> Optional[str]:
    global _router
    if not _router:
        _router = RouterLuna()
    return _router.processar_comando(cmd, intent)

if __name__ == "__main__":
    r = RouterLuna()
    for nome, skill in r.skills.items():
        info = getattr(skill, 'SKILL_INFO', {})
        print(f"{info.get('nome', nome)}: {skill.GATILHOS[:3]}")
