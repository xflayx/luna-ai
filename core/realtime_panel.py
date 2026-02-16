from core import realtime_panel_modern as _IMPL


def atualizar_estado(
    last_command: str | None = None,
    last_intent: str | None = None,
    last_response: str | None = None,
    status: str | None = None,
) -> None:
    return _IMPL.atualizar_estado(
        last_command=last_command,
        last_intent=last_intent,
        last_response=last_response,
        status=status,
    )


def iniciar_painel() -> None:
    return _IMPL.iniciar_painel()


__all__ = ["atualizar_estado", "iniciar_painel"]
