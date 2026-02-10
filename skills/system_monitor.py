# skills/system_monitor.py
import psutil

from config.state import STATE
from core.prompt_injector import build_system_monitor_prompt


SKILL_INFO = {
    "nome": "System Monitor",
    "descricao": "Monitora CPU, RAM e desempenho do sistema",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["system_monitor"],
}

GATILHOS = ["computador", "pc", "memória", "processador", "status"]


def inicializar():
    """Chamada quando a skill é carregada."""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")


def executar(comando: str) -> str:
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    contexto = STATE.obter_contexto_curto()
    _ = build_system_monitor_prompt(cpu, ram, contexto)

    if cpu > 80:
        return (
            f"Sua CPU está em {cpu}%. Se você fritar um ovo no processador agora, "
            "ele fica pronto em 2 minutos. Fecha esse jogo, vai."
        )
    return (
        f"CPU em {cpu}% e RAM em {ram}%. O PC está sobrevivendo, "
        "ao contrário das suas interações sociais."
    )
