from __future__ import annotations

import fnmatch
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


Callback = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True)
class EventFilter:
    event: str
    condition: str = ""

    def matches(self, event: Event) -> bool:
        if self.event and not fnmatch.fnmatch(event.type, self.event):
            return False
        if not self.condition:
            return True
        return _safe_eval_condition(self.condition, event)


@dataclass
class _Subscription:
    pattern: str
    callback: Callback
    subscriber_id: str = ""
    filters: tuple[EventFilter, ...] = ()


class EventBus:
    def __init__(self, max_history: int = 100):
        self._lock = threading.RLock()
        self._subscriptions: dict[str, _Subscription] = {}
        self._history: list[Event] = []
        self._max_history = max(1, int(max_history))

    def subscribe(
        self,
        pattern: str,
        callback: Callback,
        *,
        filters: list[EventFilter] | tuple[EventFilter, ...] | None = None,
        subscriber_id: str = "",
    ) -> str:
        sub_id = uuid.uuid4().hex
        subscription = _Subscription(
            pattern=pattern or "*",
            callback=callback,
            subscriber_id=subscriber_id,
            filters=tuple(filters or ()),
        )
        with self._lock:
            self._subscriptions[sub_id] = subscription
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        with self._lock:
            self._subscriptions.pop(sub_id, None)

    def clear(self, subscriber_id: str = "") -> None:
        with self._lock:
            if not subscriber_id:
                self._subscriptions.clear()
                return
            for sub_id, sub in list(self._subscriptions.items()):
                if sub.subscriber_id == subscriber_id:
                    self._subscriptions.pop(sub_id, None)

    def emit(self, event: Event) -> int:
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]
            subscriptions = list(self._subscriptions.items())

        notified = 0
        for _, sub in subscriptions:
            if not fnmatch.fnmatch(event.type, sub.pattern):
                continue
            if sub.filters and not all(f.matches(event) for f in sub.filters):
                continue
            try:
                sub.callback(event)
                notified += 1
            except Exception:
                continue
        return notified

    def get_history(self, event_type: str = "", limit: int = 10) -> list[Event]:
        limit = max(1, int(limit))
        with self._lock:
            history = list(self._history)
        if event_type:
            history = [ev for ev in history if ev.type == event_type]
        return history[-limit:]


def _safe_eval_condition(expr: str, event: Event) -> bool:
    """
    Avalia condicoes simples sem expor builtins.

    Exemplo suportado:
    - "event.text != ''"
    - "event.amount > 100"
    """
    expr = (expr or "").strip()
    if not expr:
        return True
    payload = event.payload if isinstance(event.payload, dict) else {}
    safe_context = {
        "event": payload,
        "source": event.source,
        "event_type": event.type,
    }
    try:
        result = eval(expr, {"__builtins__": {}}, safe_context)  # noqa: S307
        return bool(result)
    except Exception:
        return False


event_bus = EventBus()


def emit_event(
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    source: str = "",
) -> Event:
    event = Event(
        type=event_type,
        payload=payload or {},
        source=source,
    )
    event_bus.emit(event)
    return event
