# config/state.py
from datetime import datetime
from core import memory


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
        self.ultima_visao = None
        self.ultima_visao_ts = None

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
        memory.adicionar_memoria_curta(f"U: {comando}\nL: {resposta}", origem="dialogo")

    def obter_contexto_curto(self):
        if not self.historico:
            return "Primeira interacao"
        ultimas = self.historico[-2:]
        return "\n".join(
            [f"U: {i['comando']}\nL: {i['resposta'][:50]}..." for i in ultimas]
        )

    def obter_ultima_resposta(self, max_chars: int = 800):
        if not self.historico:
            return None
        resposta = self.historico[-1].get("resposta", "")
        if len(resposta) <= max_chars:
            return resposta
        return resposta[:max_chars] + "..."

    def set_ultima_visao(self, texto: str):
        self.ultima_visao = (texto or "").strip()
        self.ultima_visao_ts = datetime.now().isoformat()

    def get_ultima_visao(self) -> str | None:
        if not self.ultima_visao:
            return None
        return self.ultima_visao

    def set_modo_ativacao(self, modo: str) -> bool:
        if modo not in ["assistente", "vtuber"]:
            return False
        self.modo_ativacao = modo
        return True

    def get_modo_ativacao(self) -> str:
        return self.modo_ativacao


STATE = StateManager()
