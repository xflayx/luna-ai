from datetime import datetime

# Define quais skills estão ativas
SKILLS_STATE = {
    "macros": True,
    "vision": True,
    "price": True,
    "news": True
}

class LunaState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.last_intent = None
        self.last_command = None
        self.historico = [] 
        self.max_historico = 5
        self.esperando_nome_sequencia = False # Para a gravação

    def adicionar_ao_historico(self, usuario, luna):
        self.historico.append({"usuario": usuario, "luna": luna})
        if len(self.historico) > self.max_historico:
            self.historico.pop(0)

    def obter_contexto_curto(self):
        if not self.historico:
            return ""
        contexto = "\nContexto anterior:\n"
        for h in self.historico:
            contexto += f"Usuário: {h['usuario']} | Luna: {h['luna']}\n"
        return contexto

    def update_intent(self, intent: str, command: str):
        self.last_intent = intent
        self.last_command = command
        self.last_updated = datetime.now().isoformat()

STATE = LunaState()