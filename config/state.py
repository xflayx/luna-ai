# config/state.py
from datetime import datetime

class StateManager:
    def __init__(self):
        # Sequências
        self.gravando_sequencia = False
        self.esperando_nome_sequencia = False
        self.esperando_loops = False
        self.sequencia_pendente = None
        
        # Conversa
        self.em_conversa_ativa = False
        self.historico = []
        self.ultima_skill_usada = None
    
    def limpar_estados_sequencia(self):
        self.gravando_sequencia = False
        self.esperando_nome_sequencia = False
        self.esperando_loops = False
        self.sequencia_pendente = None
    
    def adicionar_ao_historico(self, comando, resposta):
        self.historico.append({
            "timestamp": datetime.now().isoformat(),
            "comando": comando,
            "resposta": resposta
        })
        if len(self.historico) > 20:
            self.historico = self.historico[-20:]
    
    def obter_contexto_curto(self):
        if not self.historico:
            return "Primeira interação"
        ultimas = self.historico[-2:]
        return "\n".join([f"U: {i['comando']}\nL: {i['resposta'][:50]}..." for i in ultimas])

STATE = StateManager()