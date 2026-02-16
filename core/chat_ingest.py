import atexit
import os
import queue
import re
import socket
import threading
import time
import logging
from typing import Optional, Any

import requests

from config.env import init_env
from core.event_bus import emit_event
from core.http_client import SESSION
from core import memory
from core import voice
from skills import conversa

_COMMON_SHORT_WORDS = {
    "oi", "ola", "ok", "sim", "nao", "bom", "boa", "tudo", "top", "vale",
    "show", "blz", "beleza", "certo", "claro", "vai", "vem", "fala",
}

_YT_EVENT_KIND_MAP = {
    "textMessageEvent": "message",
    "superChatEvent": "superchat",
    "superStickerEvent": "supersticker",
    "newSponsorEvent": "membership",
    "memberMilestoneChatEvent": "membership_milestone",
    "membershipGiftPurchaseEvent": "membership_gift_purchase",
    "membershipGiftRedemptionEvent": "membership_gift_redemption",
}
logger = logging.getLogger("ChatIngest")

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


def _store_chat(
    platform: str,
    user: str,
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
    message_kind: str = "message",
) -> None:
    msg = (text or "").strip()
    user = (user or "").strip() or "anon"
    kind = (message_kind or "message").strip().lower() or "message"
    meta = dict(metadata or {})
    payload = f"[{platform}/{user}]: {msg}" if msg else f"[{platform}/{user}]"

    if msg:
        memory.adicionar_memoria_curta(payload, origem=f"chat_{platform}")

    event_payload = {
        "platform": platform,
        "user": user,
        "text": msg,
        "payload": payload,
        "kind": kind,
        "metadata": meta,
    }
    _emit_chat_events(platform, kind, event_payload)

    if msg and kind == "message":
        _enqueue_reply(platform, user, msg)


def _emit_chat_events(platform: str, kind: str, payload: dict[str, Any]) -> None:
    source = f"chat_ingest:{platform}"
    emit_event("chat.message", payload, source=source)
    emit_event("chat.message.received", payload, source=source)
    emit_event(f"chat.{platform}.message.received", payload, source=source)
    emit_event("message.received", payload, source=source)

    if kind and kind != "message":
        emit_event(f"chat.message.{kind}", payload, source=source)
        emit_event(f"chat.{platform}.{kind}", payload, source=source)
        emit_event(f"message.{kind}", payload, source=source)

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if metadata.get("is_mod"):
        emit_event("chat.message.mod", payload, source=source)
    if metadata.get("is_member"):
        emit_event("chat.message.member", payload, source=source)
    if metadata.get("is_subscriber"):
        emit_event("chat.message.subscriber", payload, source=source)


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
        sock = None
        try:
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
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
                except OSError as e:
                    if _is_twitch_reset_error(e):
                        break
                    raise
                if not data:
                    break
                buffer += data
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if line.startswith("PING"):
                        sock.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                        continue
                    user, msg, meta = _parse_twitch_privmsg(line)
                    kind = str(meta.get("kind", "message")).strip().lower() or "message"
                    if user and (msg or kind != "message"):
                        if user.lower() == nick_norm:
                            continue
                        _store_chat(
                            "twitch",
                            user,
                            msg or "",
                            metadata=meta,
                            message_kind=kind,
                        )
        except Exception as e:
            if _is_twitch_reset_error(e):
                logger.info("Twitch chat: conexao resetada pelo host, reconectando...")
            else:
                print(f"Twitch chat erro: {e}")
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
        time.sleep(3)


def _is_twitch_reset_error(exc: Exception) -> bool:
    if isinstance(exc, ConnectionResetError):
        return True
    if isinstance(exc, OSError):
        if getattr(exc, "winerror", None) == 10054:
            return True
    texto = str(exc).lower()
    return (
        "10054" in texto
        or "connection reset" in texto
        or "forcado o cancelamento" in texto
        or "cancelamento de uma conexao existente" in texto
    )


def _parse_twitch_privmsg(line: str) -> tuple[Optional[str], Optional[str], dict[str, Any]]:
    if "PRIVMSG" not in line:
        return None, None, {}
    try:
        tags: dict[str, str] = {}
        raw_line = line
        if raw_line.startswith("@"):
            first_space = raw_line.find(" ")
            if first_space > 1:
                tags_raw = raw_line[1:first_space]
                raw_line = raw_line[first_space + 1 :]
                for part in tags_raw.split(";"):
                    if not part:
                        continue
                    if "=" in part:
                        key, value = part.split("=", 1)
                    else:
                        key, value = part, ""
                    tags[key] = value

        prefix, trailing = raw_line.split(" PRIVMSG ", 1)
        user = prefix.split("!", 1)[0].lstrip(":")
        display_user = (tags.get("display-name") or user or "").strip() or "anon"
        if " :" not in trailing:
            return display_user, None, {}
        _, msg = trailing.split(" :", 1)
        badges_raw = tags.get("badges", "")
        badges = [b for b in badges_raw.split(",") if b]
        badge_names = {b.split("/", 1)[0] for b in badges}
        bits = _safe_int(tags.get("bits", "0"))
        is_mod = tags.get("mod", "0") == "1" or "moderator" in badge_names
        is_subscriber = tags.get("subscriber", "0") == "1" or "subscriber" in badge_names
        is_member = is_subscriber
        metadata: dict[str, Any] = {
            "platform_event_type": "privmsg",
            "message_id": (tags.get("id") or "").strip(),
            "user_id": (tags.get("user-id") or "").strip(),
            "room_id": (tags.get("room-id") or "").strip(),
            "badges": badges,
            "is_mod": is_mod,
            "is_subscriber": is_subscriber,
            "is_member": is_member,
            "is_vip": "vip" in badge_names,
            "bits": bits,
            "raw_tags": tags,
            "kind": "bits" if bits > 0 else "message",
        }
        return display_user, msg, metadata
    except Exception:
        return None, None, {}


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
                author_details = item.get("authorDetails") or {}
                author = author_details.get("displayName", "anon")
                snippet = item.get("snippet") or {}
                yt_type = str(snippet.get("type") or "textMessageEvent").strip()
                kind = _YT_EVENT_KIND_MAP.get(yt_type, "message")
                text = str(snippet.get("displayMessage") or "").strip()
                if not text:
                    text = _youtube_fallback_text(snippet, kind)
                if kind == "message" and not text:
                    continue

                metadata: dict[str, Any] = {
                    "platform_event_type": yt_type,
                    "message_id": str(item.get("id") or "").strip(),
                    "published_at": str(snippet.get("publishedAt") or "").strip(),
                    "author_channel_id": str(author_details.get("channelId") or "").strip(),
                    "is_mod": bool(author_details.get("isChatModerator")),
                    "is_member": bool(author_details.get("isChatSponsor")),
                    "is_owner": bool(author_details.get("isChatOwner")),
                    "is_verified": bool(author_details.get("isVerified")),
                    "kind": kind,
                }

                details_fields = (
                    "textMessageDetails",
                    "superChatDetails",
                    "superStickerDetails",
                    "newSponsorDetails",
                    "memberMilestoneChatDetails",
                    "membershipGiftPurchaseDetails",
                    "membershipGiftRedemptionDetails",
                )
                for field in details_fields:
                    details = snippet.get(field)
                    if isinstance(details, dict):
                        metadata[field] = details

                _store_chat(
                    "youtube",
                    author,
                    text,
                    metadata=metadata,
                    message_kind=kind,
                )
            page_token = data.get("nextPageToken") or page_token
            poll_ms = int(data.get("pollingIntervalMillis") or poll_default)
            _sleep(poll_ms)
        except Exception as e:
            print(f"YouTube chat erro: {e}")
            _sleep(poll_default)


def _youtube_fallback_text(snippet: dict[str, Any], kind: str) -> str:
    if kind == "superchat":
        details = snippet.get("superChatDetails") or {}
        amount = str(details.get("amountDisplayString") or "").strip()
        return f"[SUPER CHAT] {amount}".strip()
    if kind == "supersticker":
        details = snippet.get("superStickerDetails") or {}
        amount = str(details.get("amountDisplayString") or "").strip()
        return f"[SUPER STICKER] {amount}".strip()
    if kind in {"membership", "membership_milestone"}:
        details = snippet.get("newSponsorDetails") or snippet.get("memberMilestoneChatDetails") or {}
        level = str(details.get("memberLevelName") or "").strip()
        return f"[MEMBERSHIP] {level}".strip()
    if kind == "membership_gift_purchase":
        details = snippet.get("membershipGiftPurchaseDetails") or {}
        count = _safe_int(details.get("giftMembershipsCount"), 0)
        return f"[MEMBERSHIP GIFT] x{count}" if count > 0 else "[MEMBERSHIP GIFT]"
    if kind == "membership_gift_redemption":
        return "[MEMBERSHIP GIFT REDEMPTION]"
    return ""


def _sleep(ms: int) -> None:
    secs = max(1, int(ms)) / 1000.0
    _stop_event.wait(secs)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
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
            final = resposta_retry or resposta
            if final:
                emit_event(
                    "chat.reply_generated",
                    {"platform": platform, "user": user, "text": text, "reply": final},
                    source="chat_ingest",
                )
            return final
        if resposta:
            emit_event(
                "chat.reply_generated",
                {"platform": platform, "user": user, "text": text, "reply": resposta},
                source="chat_ingest",
            )
        return resposta
    except Exception:
        emit_event(
            "chat.reply_error",
            {"platform": platform, "user": user, "text": text},
            source="chat_ingest",
        )
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
