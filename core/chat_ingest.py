import atexit
import os
import queue
import re
import socket
import threading
import time
from typing import Optional

import requests

from config.env import init_env
from core.http_client import SESSION
from core import memory
from core import voice
from skills import conversa

_COMMON_SHORT_WORDS = {
    "oi", "ola", "ok", "sim", "nao", "bom", "boa", "tudo", "top", "vale",
    "show", "blz", "beleza", "certo", "claro", "vai", "vem", "fala",
}

init_env()

_stop_event = threading.Event()
_threads: list[threading.Thread] = []
_reply_queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue(
    maxsize=int(os.getenv("LUNA_CHAT_REPLY_QUEUE_MAX", "20"))
)
_reply_lock = threading.Lock()
_last_reply_ts = 0.0
_last_user_ts: dict[str, float] = {}


def start_chat_ingest() -> None:
    """Inicia a integracao de chat (Twitch/YouTube) se habilitada via env."""
    if _is_enabled("LUNA_CHAT_REPLY_ENABLED"):
        t = threading.Thread(target=_reply_worker, daemon=True)
        _threads.append(t)
        t.start()

    if _is_enabled("LUNA_TWITCH_ENABLED"):
        t = threading.Thread(target=_twitch_loop, daemon=True)
        _threads.append(t)
        t.start()

    if _is_enabled("LUNA_YT_ENABLED") or _is_enabled("LUNA_YOUTUBE_ENABLED"):
        t = threading.Thread(target=_youtube_loop, daemon=True)
        _threads.append(t)
        t.start()


def stop_chat_ingest() -> None:
    _stop_event.set()


atexit.register(stop_chat_ingest)


def _is_enabled(env_key: str) -> bool:
    return os.getenv(env_key, "0").strip() == "1"


def _store_chat(platform: str, user: str, text: str) -> None:
    msg = (text or "").strip()
    if not msg:
        return
    user = (user or "").strip() or "anon"
    payload = f"[{platform}/{user}]: {msg}"
    memory.adicionar_memoria_curta(payload, origem=f"chat_{platform}")
    _enqueue_reply(platform, user, msg)


def _enqueue_reply(platform: str, user: str, text: str) -> None:
    if not _should_reply(platform, user, text):
        return
    cleaned = _clean_incoming_text(text)
    if not cleaned:
        return
    if _reply_queue.full():
        try:
            _reply_queue.get_nowait()
            _reply_queue.task_done()
        except Exception:
            pass
    _reply_queue.put((platform, user, cleaned))


def _reply_worker() -> None:
    while True:
        item = _reply_queue.get()
        try:
            if item is None:
                return
            platform, user, text = item
            resposta = _gerar_resposta(platform, user, text)
            if resposta:
                voice.falar(resposta)
        except Exception as e:
            print(f"ERRO CHAT REPLY: {e}")
        finally:
            _reply_queue.task_done()


def _twitch_loop() -> None:
    nick = os.getenv("LUNA_TWITCH_NICK", "").strip()
    oauth = os.getenv("LUNA_TWITCH_OAUTH", "").strip()
    channel = os.getenv("LUNA_TWITCH_CHANNEL", "").strip().lstrip("#")

    if not nick or not oauth or not channel:
        print("Twitch chat: variaveis ausentes (LUNA_TWITCH_NICK/OAUTH/CHANNEL).")
        return

    if not oauth.lower().startswith("oauth:"):
        oauth = f"oauth:{oauth}"

    nick_norm = nick.lower()
    while not _stop_event.is_set():
        try:
            sock = socket.socket()
            sock.connect(("irc.chat.twitch.tv", 6667))
            sock.send(f"PASS {oauth}\r\n".encode("utf-8"))
            sock.send(f"NICK {nick}\r\n".encode("utf-8"))
            sock.send(f"JOIN #{channel}\r\n".encode("utf-8"))
            sock.settimeout(1.0)

            buffer = ""
            while not _stop_event.is_set():
                try:
                    data = sock.recv(2048).decode("utf-8", errors="ignore")
                except socket.timeout:
                    continue
                if not data:
                    break
                buffer += data
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if line.startswith("PING"):
                        sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                        continue
                    user, msg = _parse_twitch_privmsg(line)
                    if user and msg:
                        if user.lower() == nick_norm:
                            continue
                        _store_chat("twitch", user, msg)
        except Exception as e:
            print(f"Twitch chat erro: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass
        time.sleep(3)


def _parse_twitch_privmsg(line: str) -> tuple[Optional[str], Optional[str]]:
    if "PRIVMSG" not in line:
        return None, None
    try:
        prefix, trailing = line.split(" PRIVMSG ", 1)
        user = prefix.split("!", 1)[0].lstrip(":")
        if " :" not in trailing:
            return user, None
        _, msg = trailing.split(" :", 1)
        return user, msg
    except Exception:
        return None, None


def _youtube_loop() -> None:
    api_key = os.getenv("LUNA_YT_API_KEY", "").strip()
    live_chat_id = os.getenv("LUNA_YT_LIVE_CHAT_ID", "").strip()
    poll_default = _env_int("LUNA_YT_POLL_MS", 5000)

    if not api_key or not live_chat_id:
        print("YouTube chat: variaveis ausentes (LUNA_YT_API_KEY/LUNA_YT_LIVE_CHAT_ID).")
        return

    page_token = None
    base_url = "https://www.googleapis.com/youtube/v3/liveChat/messages"

    while not _stop_event.is_set():
        params = {
            "liveChatId": live_chat_id,
            "part": "snippet,authorDetails",
            "key": api_key,
            "maxResults": 200,
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = SESSION.get(base_url, params=params, timeout=15)
            if resp.status_code != 200:
                print(f"YouTube chat erro HTTP {resp.status_code}")
                _sleep(poll_default)
                continue
            data = resp.json()
            items = data.get("items", []) or []
            for item in items:
                author = (item.get("authorDetails") or {}).get("displayName", "anon")
                snippet = item.get("snippet") or {}
                text = snippet.get("displayMessage", "")
                _store_chat("youtube", author, text)
            page_token = data.get("nextPageToken") or page_token
            poll_ms = int(data.get("pollingIntervalMillis") or poll_default)
            _sleep(poll_ms)
        except Exception as e:
            print(f"YouTube chat erro: {e}")
            _sleep(poll_default)


def _sleep(ms: int) -> None:
    secs = max(1, int(ms)) / 1000.0
    _stop_event.wait(secs)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _should_reply(platform: str, user: str, text: str) -> bool:
    if not _is_enabled("LUNA_CHAT_REPLY_ENABLED"):
        return False
    platforms = os.getenv("LUNA_CHAT_REPLY_PLATFORMS", "twitch,youtube")
    allowed = {p.strip().lower() for p in platforms.split(",") if p.strip()}
    if allowed and platform.lower() not in allowed:
        return False
    if _is_ignored_user(user):
        return False

    mode = os.getenv("LUNA_CHAT_REPLY_MODE", "mention").strip().lower()
    if mode == "all":
        allowed_msg = True
    elif mode == "prefix":
        allowed_msg = _has_prefix(text)
    else:
        allowed_msg = _has_mention(text)
    if not allowed_msg:
        return False

    min_interval = _env_int("LUNA_CHAT_REPLY_MIN_INTERVAL", 8)
    per_user_cd = _env_int("LUNA_CHAT_REPLY_USER_COOLDOWN", 30)
    now = time.time()
    user_key = user.lower().strip()
    with _reply_lock:
        global _last_reply_ts
        last_user = _last_user_ts.get(user_key, 0.0)
        if now - _last_reply_ts < min_interval:
            return False
        if now - last_user < per_user_cd:
            return False
        _last_reply_ts = now
        _last_user_ts[user_key] = now
    return True


def _is_ignored_user(user: str) -> bool:
    ignore = os.getenv("LUNA_CHAT_REPLY_IGNORE_USERS", "").strip()
    if not ignore:
        return False
    nomes = {u.strip().lower() for u in ignore.split(",") if u.strip()}
    return user.lower().strip() in nomes


def _has_prefix(text: str) -> bool:
    prefix = os.getenv("LUNA_CHAT_REPLY_PREFIX", "!luna").strip()
    if not prefix:
        return False
    return text.strip().lower().startswith(prefix.lower())


def _has_mention(text: str) -> bool:
    name = os.getenv("LUNA_CHAT_REPLY_NAME", "luna").strip()
    if not name:
        return False
    pattern = rf"(^|\\W)@?{re.escape(name)}(\\W|$)"
    return re.search(pattern, text.lower()) is not None


def _clean_incoming_text(text: str) -> str:
    max_chars = _env_int("LUNA_CHAT_REPLY_MAX_CHARS", 200)
    cleaned = (text or "").strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip()
    prefix = os.getenv("LUNA_CHAT_REPLY_PREFIX", "!luna").strip()
    if prefix and cleaned.lower().startswith(prefix.lower()):
        cleaned = cleaned[len(prefix):].strip()
    name = os.getenv("LUNA_CHAT_REPLY_NAME", "luna").strip()
    if name:
        cleaned = re.sub(rf"@?{re.escape(name)}[:,]?\s*", "", cleaned, flags=re.I).strip()
    return cleaned


def _gerar_resposta(platform: str, user: str, text: str) -> str:
    if not text:
        return ""
    instr = (
        f"Mensagem do chat ({platform}) de {user}: {text}\n"
        f"Responda em portugues, chame {user} pelo nome e use 1 frase completa e curta.\n"
        "Nao use abreviacoes e nao corte palavras. Finalize com ponto."
    )
    try:
        resposta = conversa.executar(instr)
        if _resposta_incompleta(resposta):
            retry = (
                f"{instr}\n"
                "Reescreva a frase completa sem cortar palavras."
            )
            resposta_retry = conversa.executar(retry)
            return resposta_retry or resposta
        return resposta
    except Exception:
        return ""


def _resposta_incompleta(texto: str) -> bool:
    if not texto:
        return True
    clean = texto.strip()
    if not clean:
        return True
    if clean[-1] not in ".!?":
        return True
    last = re.sub(r"[.!?]+$", "", clean).split()[-1].lower()
    if not last:
        return True
    if last in _COMMON_SHORT_WORDS:
        return False
    # Heuristica simples: palavra curta terminando em consoante
    if len(last) <= 4 and last[-1] not in "aeiouáéíóúãõâêô":
        return True
    return False
