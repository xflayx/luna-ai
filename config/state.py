# config/state.py
import json
import os
import threading
import time
import random
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
        self._lock = threading.RLock()
        # Sequencias
        self._gravando_sequencia = False
        self._esperando_nome_sequencia = False
        self._esperando_loops = False
        self._sequencia_pendente = None

        # Conversa
        self._em_conversa_ativa = False
        self._historico = self._carregar_historico()
        self._ultima_skill_usada = None
        self._ultima_visao = None
        self._ultima_visao_ts = None
        self._ultima_captura_path = None
        self._ultima_captura_ts = None
        self._ultima_captura_hash = None

        # Ativacao
        self._modo_ativacao = "assistente"

        # Temperamento
        self._temperamento = None
        self._temperamento_ts = 0.0
        self._temperamentos = self._carregar_temperamentos()
        self._temperamento_intervalo = None
        self._temperamento_intervalo_min, self._temperamento_intervalo_max = (
            self._carregar_temperamento_intervalo_range()
        )

    # -------------------------
    # Propriedades thread-safe
    # -------------------------
    @property
    def gravando_sequencia(self):
        with self._lock:
            return self._gravando_sequencia

    @gravando_sequencia.setter
    def gravando_sequencia(self, value):
        with self._lock:
            self._gravando_sequencia = bool(value)

    @property
    def esperando_nome_sequencia(self):
        with self._lock:
            return self._esperando_nome_sequencia

    @esperando_nome_sequencia.setter
    def esperando_nome_sequencia(self, value):
        with self._lock:
            self._esperando_nome_sequencia = bool(value)

    @property
    def esperando_loops(self):
        with self._lock:
            return self._esperando_loops

    @esperando_loops.setter
    def esperando_loops(self, value):
        with self._lock:
            self._esperando_loops = bool(value)

    @property
    def sequencia_pendente(self):
        with self._lock:
            return self._sequencia_pendente

    @sequencia_pendente.setter
    def sequencia_pendente(self, value):
        with self._lock:
            self._sequencia_pendente = value

    @property
    def em_conversa_ativa(self):
        with self._lock:
            return self._em_conversa_ativa

    @em_conversa_ativa.setter
    def em_conversa_ativa(self, value):
        with self._lock:
            self._em_conversa_ativa = bool(value)

    @property
    def historico(self):
        with self._lock:
            return list(self._historico)

    @property
    def ultima_skill_usada(self):
        with self._lock:
            return self._ultima_skill_usada

    @ultima_skill_usada.setter
    def ultima_skill_usada(self, value):
        with self._lock:
            self._ultima_skill_usada = value

    @property
    def ultima_visao(self):
        with self._lock:
            return self._ultima_visao

    @property
    def ultima_visao_ts(self):
        with self._lock:
            return self._ultima_visao_ts

    @property
    def ultima_captura_path(self):
        with self._lock:
            return self._ultima_captura_path

    @property
    def ultima_captura_ts(self):
        with self._lock:
            return self._ultima_captura_ts

    @property
    def ultima_captura_hash(self):
        with self._lock:
            return self._ultima_captura_hash

    @property
    def modo_ativacao(self):
        with self._lock:
            return self._modo_ativacao

    def get_temperamento(self) -> str:
        with self._lock:
            agora = time.time()
            if (
                self._temperamento is None
                or (
                    self._temperamento_intervalo is not None
                    and (agora - self._temperamento_ts) >= self._temperamento_intervalo
                )
            ):
                self._temperamento = self._escolher_temperamento(self._temperamento)
                self._temperamento_ts = agora
                self._temperamento_intervalo = random.uniform(
                    self._temperamento_intervalo_min,
                    self._temperamento_intervalo_max,
                )
                try:
                    minutos = self._temperamento_intervalo / 60.0
                    print(f"[TEMPERAMENTO] agora: {self._temperamento} (prox {minutos:.1f} min)")
                except Exception:
                    pass
            return self._temperamento or "neutra"

    def limpar_estados_sequencia(self):
        with self._lock:
            self._gravando_sequencia = False
            self._esperando_nome_sequencia = False
            self._esperando_loops = False
            self._sequencia_pendente = None

    def adicionar_ao_historico(self, comando, resposta):
        with self._lock:
            self._historico.append({
                "timestamp": datetime.now().isoformat(),
                "comando": comando,
                "resposta": resposta,
            })
            if len(self._historico) > _HISTORY_MAX:
                self._historico = self._historico[-_HISTORY_MAX:]
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
                json.dump(self._historico, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def obter_contexto_curto(self):
        with self._lock:
            if not self._historico:
                return "Primeira interacao"
            ultimas = self._historico[-2:]
            return "\n".join(
                [f"U: {i['comando']}\nL: {i['resposta'][:50]}..." for i in ultimas]
            )

    def obter_ultima_resposta(self, max_chars: int = 800):
        with self._lock:
            if not self._historico:
                return None
            resposta = self._historico[-1].get("resposta", "")
            if len(resposta) <= max_chars:
                return resposta
            return resposta[:max_chars] + "..."

    def set_ultima_visao(self, texto: str):
        with self._lock:
            self._ultima_visao = (texto or "").strip()
            self._ultima_visao_ts = datetime.now().isoformat()

    def get_ultima_visao(self) -> str | None:
        with self._lock:
            if not self._ultima_visao:
                return None
            return self._ultima_visao

    def set_ultima_captura(self, path: str, file_hash: str | None = None):
        with self._lock:
            self._ultima_captura_path = path
            self._ultima_captura_hash = file_hash
            self._ultima_captura_ts = datetime.now().isoformat()

    def get_ultima_captura(self) -> str | None:
        with self._lock:
            if not self._ultima_captura_path:
                return None
            return self._ultima_captura_path

    def set_modo_ativacao(self, modo: str) -> bool:
        if modo not in ["assistente", "vtuber"]:
            return False
        with self._lock:
            self._modo_ativacao = modo
        return True

    def get_modo_ativacao(self) -> str:
        with self._lock:
            return self._modo_ativacao

    def _carregar_temperamentos(self) -> list[str]:
        bruto = os.getenv("LUNA_TEMPERAMENTOS", "feliz,cansada,triste,rabujenta")
        itens = [t.strip().lower() for t in bruto.split(",") if t.strip()]
        return itens or ["feliz", "cansada", "triste", "rabujenta"]

    def _carregar_temperamento_intervalo_range(self) -> tuple[float, float]:
        bruto_min = os.getenv("LUNA_TEMPERAMENTO_MIN_MINUTOS", "").strip()
        bruto_max = os.getenv("LUNA_TEMPERAMENTO_MAX_MINUTOS", "").strip()
        if bruto_min and bruto_max:
            try:
                min_v = float(bruto_min)
                max_v = float(bruto_max)
            except ValueError:
                min_v = 15.0
                max_v = 25.0
        else:
            bruto = os.getenv("LUNA_TEMPERAMENTO_MINUTOS", "15")
            try:
                min_v = float(bruto)
            except ValueError:
                min_v = 15.0
            max_v = min_v
        if min_v < 1.0:
            min_v = 1.0
        if max_v < min_v:
            max_v = min_v
        return min_v * 60.0, max_v * 60.0

    def _escolher_temperamento(self, atual: str | None) -> str:
        if not self._temperamentos:
            return "neutra"
        if atual and len(self._temperamentos) > 1:
            opcoes = [t for t in self._temperamentos if t != atual]
        else:
            opcoes = list(self._temperamentos)
        return random.choice(opcoes)


STATE = StateManager()
