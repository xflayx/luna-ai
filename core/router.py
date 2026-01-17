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
        self.carregar_skills()

    def carregar_skills(self):
        pasta = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
        
        for arquivo in os.listdir(pasta):
            if not arquivo.endswith('.py') or arquivo.startswith('_'):
                continue
            
            nome = arquivo[:-3]
            try:
                mod = importlib.import_module(f"skills.{nome}")
                if hasattr(mod, 'GATILHOS') and hasattr(mod, 'executar'):
                    self.skills[nome] = mod
                    if hasattr(mod, 'inicializar'):
                        mod.inicializar()
                    else:
                        logger.info(f"✅ {nome}")
            except Exception as e:
                logger.error(f"❌ {nome}: {e}")
        
        logger.info(f"📦 {len(self.skills)} skills carregadas")

    def processar_comando(self, cmd: str, intent: Optional[str] = None) -> Optional[str]:
        cmd_lower = cmd.lower().strip()
        cmd_limpo = cmd_lower.replace("luna", "").strip()

        # Estados de sequência (prioridade máxima)
        if STATE.esperando_nome_sequencia or STATE.esperando_loops or STATE.gravando_sequencia:
            for skill in self.skills.values():
                if "sequencia" in skill.__name__ or "macros" in skill.__name__:
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
        for nome, skill in self.skills.items():
            info = getattr(skill, 'SKILL_INFO', {})
            if intent in info.get('intents', []) or intent in nome:
                try:
                    resp = skill.executar(cmd_limpo)
                    if resp:
                        STATE.adicionar_ao_historico(cmd_limpo, resp)
                    return resp
                except Exception as e:
                    return f"Erro: {e}"

        # Busca por gatilhos
        for skill in self.skills.values():
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