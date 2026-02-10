# config/state.py
import json
import os
from datetime import datetime

from config.env import init_env
from core import memory

init_env()

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_HISTORY_PATH = os.path.join(_BASE_DIR, "memory", "chat_history.json")
_HISTORY_PATH = os.getenv("LUNA_CHAT_HISTORY_PATH", _DEFAULT_HISTORY_PATH)
if not os.path.isabs(_HISTORY_PATH):
    _HISTORY_PATH = os.path.join(_BASE_DIR, _HISTORY_PATH)
_HISTORY_MAX = int(os.getenv("LUNA_CHAT_HISTORY_MAX", "20"))


class StateManager:
    def __init__(self):
        # Sequencias
        self.gravando_sequencia = False
        self.esperando_nome_sequencia = False
        self.esperando_loops = False
        self.sequencia_pendente = None

        # Conversa
        self.em_conversa_ativa = False
        self.historico = self._carregar_historico()
        self.ultima_skill_usada = None
        self.ultima_visao = None
        self.ultima_visao_ts = None
        self.ultima_captura_path = None
        self.ultima_captura_ts = None
        self.ultima_captura_hash = None

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
        if len(self.historico) > _HISTORY_MAX:
            self.historico = self.historico[-_HISTORY_MAX:]
        self._salvar_historico()
        memory.adicionar_memoria_curta(f"U: {comando}\nL: {resposta}", origem="dialogo")

    def _carregar_historico(self):
        if not os.path.isfile(_HISTORY_PATH):
            return []
        try:
            with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _salvar_historico(self):
        try:
            os.makedirs(os.path.dirname(_HISTORY_PATH), exist_ok=True)
            with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.historico, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

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

    def set_ultima_captura(self, path: str, file_hash: str | None = None):
        self.ultima_captura_path = path
        self.ultima_captura_hash = file_hash
        self.ultima_captura_ts = datetime.now().isoformat()

    def get_ultima_captura(self) -> str | None:
        if not self.ultima_captura_path:
            return None
        return self.ultima_captura_path

    def set_modo_ativacao(self, modo: str) -> bool:
        if modo not in ["assistente", "vtuber"]:
            return False
        self.modo_ativacao = modo
        return True

    def get_modo_ativacao(self) -> str:
        return self.modo_ativacao


STATE = StateManager()
