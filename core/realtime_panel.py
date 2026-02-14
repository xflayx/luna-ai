import os


def _panel_ui() -> str:
    return os.getenv("LUNA_PANEL_UI", "modern").strip().lower()


def _load_impl():
    ui = _panel_ui()
    if ui in {"simple", "basic", "legacy"}:
        from core import realtime_panel_simple as impl
        return impl
    from core import realtime_panel_modern as impl
    return impl


_IMPL = _load_impl()


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
