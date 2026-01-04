# core/mode_manager.py

from enum import Enum
from datetime import datetime


class LunaMode(Enum):
    VTUBER = "vtuber"
    AUTOMATION = "automation"
    GAMER = "gamer"
    TRADING = "trading"


class ModeManager:
    def __init__(self):
        self._current_mode = LunaMode.VTUBER
        self._last_changed = datetime.now()

        # Configuração central dos modos
        self._mode_config = {
            LunaMode.VTUBER: {
                "allowed_intents": [
                    "search",
                    "vision",
                    "chat"
                ],
                "can_execute_actions": False,
                "proactive": True,
                "requires_confirmation": False,
                "personality_weight": 1.0
            },

            LunaMode.AUTOMATION: {
                "allowed_intents": [
                    "system",
                    "macro",
                    "vision"
                ],
                "can_execute_actions": True,
                "proactive": False,
                "requires_confirmation": True,
                "personality_weight": 0.2
            },

            LunaMode.GAMER: {
                "allowed_intents": [
                    "vision",
                    "search",
                    "chat"
                ],
                "can_execute_actions": False,
                "proactive": True,
                "requires_confirmation": False,
                "personality_weight": 0.6
            },

            LunaMode.TRADING: {
                "allowed_intents": [
                    "price",
                    "search",
                    "analysis"
                ],
                "can_execute_actions": False,
                "proactive": False,
                "requires_confirmation": False,
                "personality_weight": 0.3
            }
        }

    # ==========================
    # MODE CONTROL
    # ==========================

    def set_mode(self, mode: str) -> bool:
        try:
            new_mode = LunaMode(mode)
        except ValueError:
            return False

        if new_mode != self._current_mode:
            self._current_mode = new_mode
            self._last_changed = datetime.now()

        return True

    def get_mode(self) -> str:
        return self._current_mode.value

    def get_mode_enum(self) -> LunaMode:
        return self._current_mode

    def mode_changed_at(self) -> datetime:
        return self._last_changed

    # ==========================
    # VALIDATION
    # ==========================

    def is_intent_allowed(self, intent: str) -> bool:
        config = self._mode_config.get(self._current_mode, {})
        return intent in config.get("allowed_intents", [])

    def can_execute_actions(self) -> bool:
        config = self._mode_config.get(self._current_mode, {})
        return config.get("can_execute_actions", False)

    def requires_confirmation(self) -> bool:
        config = self._mode_config.get(self._current_mode, {})
        return config.get("requires_confirmation", False)

    def is_proactive(self) -> bool:
        config = self._mode_config.get(self._current_mode, {})
        return config.get("proactive", False)

    # ==========================
    # PERSONALITY CONTROL
    # ==========================

    def personality_weight(self) -> float:
        """
        Retorna o peso da personalidade para o modo atual.
        1.0 = personalidade forte
        0.0 = totalmente neutra
        """
        config = self._mode_config.get(self._current_mode, {})
        return config.get("personality_weight", 0.5)

    # ==========================
    # CONTEXT HELPERS
    # ==========================

    def summary(self) -> dict:
        """
        Retorna um resumo do modo atual
        para logging, debug ou UI.
        """
        return {
            "mode": self.get_mode(),
            "changed_at": self._last_changed.isoformat(),
            "config": self._mode_config.get(self._current_mode, {})
        }
