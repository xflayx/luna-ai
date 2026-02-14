import json
import logging
import os
import sys
import time


_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)

        extras = {
            k: v for k, v in record.__dict__.items() if k not in _RESERVED
        }
        if extras:
            data.update(extras)

        return json.dumps(data, ensure_ascii=False)


class CleanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        name = (record.name or "LUNA").upper()
        return f"[{name}][{ts}] {record.getMessage()}"


def init_logging() -> None:
    debug = os.getenv("LUNA_DEBUG", "0") == "1"
    level_name = os.getenv("LUNA_LOG_LEVEL", "")
    if level_name:
        level = getattr(logging, level_name.upper(), logging.INFO)
    else:
        level = logging.DEBUG if debug else logging.INFO
    fmt = os.getenv("LUNA_LOG_FORMAT", "text").strip().lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        if debug:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                )
            )
        else:
            handler.setFormatter(CleanFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("comtypes").setLevel(logging.ERROR)
    logging.getLogger("comtypes.client._code_cache").setLevel(logging.ERROR)
    logging.getLogger("werkzeug").setLevel(logging.ERROR if debug else logging.CRITICAL)
