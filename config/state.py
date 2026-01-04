# config/state.py

from datetime import datetime

# ===============================
# CONTROLE DE SKILLS (JÁ EXISTENTE)
# ===============================
SKILLS_STATE = {
    "macros": True,
    "vision": True,
    "price": True,
    "news": True
}

# ===============================
# ESTADO GLOBAL DA LUNA
# ===============================
class LunaState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.last_intent = None
        self.last_command = None

        self.last_vision = None
        self.last_updated = None

    # ===============================
    # ATUALIZAÇÕES
    # ===============================
    def update_intent(self, intent: str, command: str):
        self.last_intent = intent
        self.last_command = command
        self.last_updated = datetime.now().isoformat()

    def update_vision(self, vision_result: dict):
        """
        Espera receber o output estruturado da vision:
        {
          summary, tags, confidence, timestamp
        }
        """
        if not vision_result:
            return

        self.last_vision = {
            "summary": vision_result.get("summary"),
            "tags": vision_result.get("tags", []),
            "confidence": vision_result.get("confidence", 0.0),
            "timestamp": vision_result.get("timestamp")
        }

        self.last_updated = datetime.now().isoformat()

    # ===============================
    # HELPERS
    # ===============================
    def has_recent_vision(self) -> bool:
        return self.last_vision is not None

    def get_last_vision_summary(self) -> str | None:
        if not self.last_vision:
            return None
        return self.last_vision.get("summary")

    def get_last_vision_tags(self) -> list:
        if not self.last_vision:
            return []
        return self.last_vision.get("tags", [])

    def debug(self) -> dict:
        return {
            "last_intent": self.last_intent,
            "last_command": self.last_command,
            "last_vision": self.last_vision,
            "last_updated": self.last_updated
        }


# ===============================
# INSTÂNCIA GLOBAL (SINGLETON SIMPLES)
# ===============================
STATE = LunaState()
