# config/state.py
from datetime import datetime


class StateManager:
    def __init__(self):
        # Sequencias
        self.gravando_sequencia = False
        self.esperando_nome_sequencia = False
        self.esperando_loops = False
        self.sequencia_pendente = None

        # Conversa
        self.em_conversa_ativa = False
        self.historico = []
        self.ultima_skill_usada = None

        # Ativacao
        self.modo_ativacao = "assistente"

    def limpar_estados_sequencia(self):
        self.gravando_sequencia = False
        self.esperando_nome_sequencia = False
        self.esperando_loops = False
        self.sequencia_pendente = None

    def adicionar_ao_historico(self, comando, resposta):
        self.historico.append({
            "timestamp": datetime.now().isoformat(),
            "comando": comando,
            "resposta": resposta,
        })
        if len(self.historico) > 20:
            self.historico = self.historico[-20:]

    def obter_contexto_curto(self):
        if not self.historico:
            return "Primeira interacao"
        ultimas = self.historico[-2:]
        return "\n".join(
            [f"U: {i['comando']}\nL: {i['resposta'][:50]}..." for i in ultimas]
        )

    def set_modo_ativacao(self, modo: str) -> bool:
        if modo not in ["assistente", "vtuber"]:
            return False
        self.modo_ativacao = modo
        return True

    def get_modo_ativacao(self) -> str:
        return self.modo_ativacao


STATE = StateManager()
