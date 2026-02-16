# Auditoria Luna - Performance, Leveza e Segurança

## 1) Visão geral do projeto
- Tipo: app desktop/assistente de voz em Python com automação local, painel web em Flask-SocketIO, e pet desktop em Electron + backend FastAPI local.
- Entry points principais: `main.py:1`, `app/backend/server.py:1`, `app/electron/main.js:1`, `interface/radial_menu_eel.py:1`.
- Fluxo resumido: voz/comando em `main.py` -> roteamento em `core/router.py:112` -> skills em `skills/*.py`; estado/histórico em `config/state.py:181` e `core/memory.py:78`; painel em `core/realtime_panel_simple.py:188` e `core/realtime_panel_modern.py:188`.
- Dependências: `requirements.txt` (monolítico) + `app/backend/requirements.txt` (parcial). Há drift de versões (`requirements.txt:54`, `requirements.txt:55`, `app/backend/requirements.txt:1`, `app/backend/requirements.txt:2`).
- Segurança de segredos: `.env` local contém chaves reais (`.env:1`, `.env:2`, `.env:3`, `.env:4`, `.env:5`, `.env:6`, `.env:7`, `.env:34`, `.env:42`). `.env` não está versionado (bom), mas risco operacional é alto.
- Testes e tooling no ambiente: `pytest` executa sem testes; `ruff`, `bandit` e `pip-audit` não estão instalados.
- Arquivos citados no contexto IDE e ausentes no repo: `companion_flet.py`, `docs/flet_changes_summary.md`.

## 2) Top melhorias de performance (priorizadas)
1. `P0` Endurecer autenticação do backend/painel para evitar abuso remoto que vira DoS/uso indevido de CPU: `app/backend/server.py:73`, `app/backend/server.py:465`, `core/realtime_panel_simple.py:36`, `core/realtime_panel_modern.py:36`.
2. `P0` Limitar leitura de URL e bloquear SSRF por DNS-rebinding; hoje há `resp.text` sem limite: `app/backend/server.py:151`, `app/backend/server.py:156`, `app/backend/server.py:164`.
3. `P1` Trocar chamadas `requests.*` no backend pet por `SESSION` com pool/retry para reduzir latência/conexões: `app/backend/server.py:156`, `app/backend/server.py:192`, `app/backend/server.py:277`, `app/backend/server.py:359`.
4. `P1` Trocar streaming char-a-char por chunks no websocket para reduzir overhead de CPU/event loop: `app/backend/server.py:452`, `app/backend/server.py:453`.
5. `P1` Adicionar rate limit por conexão websocket para reduzir flood: `app/backend/server.py:475`.
6. `P1` Cache em memória + escrita atômica no storage curto/longo para cortar I/O repetido: `core/memory.py:22`, `core/memory.py:39`, `core/memory.py:78`, `core/memory.py:116`.
7. `P1` Escrita atômica/compacta do histórico de chat: `config/state.py:205`, `config/state.py:208`, `config/state.py:209`.
8. `P2` Aumentar intervalo do ticker do painel (1s é agressivo) e reduzir custo de `_build_state`: `core/realtime_panel_simple.py:313`, `core/realtime_panel_modern.py:313`.
9. `P2` Pré-indexar intents/gatilhos no router para evitar triplo loop a cada comando: `core/router.py:140`, `core/router.py:154`, `core/router.py:169`.
10. `P2` Split de dependências opcionais (Playwright/Eel/faster-whisper/Electron bridge) para reduzir instalação/startup de ambientes core.

## 3) Achados de segurança (por severidade)

### CRITICAL
1. Segredos reais no `.env` local (`.env:1` a `.env:7`, `.env:34`, `.env:42`).
- Risco: comprometimento de APIs/contas (GROQ, Gemini, Murf, SerpAPI, CoinMarketCap, Twitch, OBS).
- Exploração: exfiltração por malware local, backup indevido, screen sharing, commit acidental.
- Correção: rotacionar imediatamente todas as credenciais e mover para cofre/secret manager.

2. Controle remoto potencialmente sem autenticação efetiva quando token está vazio no painel e backend local.
- Evidências: `core/realtime_panel_simple.py:36`, `core/realtime_panel_modern.py:36`, `app/backend/server.py:73`, `app/backend/server.py:465`, `.env.example:20`.
- Risco: qualquer página aberta no browser pode tentar atingir localhost e disparar comandos (`/control`, websocket), incluindo automação local.
- Correção: exigir token obrigatório por padrão, comparação constante, e limitar CORS/origens.

### HIGH
1. SSRF/DoS no resumo de URL do backend pet.
- Evidências: `app/backend/server.py:128`, `app/backend/server.py:136`, `app/backend/server.py:151`, `app/backend/server.py:164`.
- Risco: acesso indireto a destinos internos via hostname + leitura sem limite de tamanho.
- Correção: resolver DNS e bloquear IPs privados/loopback, desabilitar redirects e cap de bytes.

2. Ausência de rate limiting por conexão websocket.
- Evidência: loop principal sem limite em `app/backend/server.py:475`.
- Risco: flood de mensagens, consumo de CPU/rede e degradação global.
- Correção: janela por minuto + fechamento com `1013`.

3. Leitura arbitrária de arquivo em `tts_murf` quando comando chega por canal não confiável.
- Evidências: `skills/tts_murf.py:123`, `skills/tts_murf.py:125`, `skills/tts_murf.py:129`.
- Risco: exfiltração indireta de conteúdo local para API externa (Murf).
- Correção: restringir diretórios permitidos ou exigir opt-in explícito para leitura de arquivo.

### MED
1. I/O excessivo em memória/histórico (impacta perf e estabilidade sob carga).
- Evidências: `core/memory.py:22`, `core/memory.py:39`, `config/state.py:205`.
- Correção: cache em memória + escrita atômica compacta.

2. Painel emite estado a cada 1s e consulta memória curta em cada tick.
- Evidências: `core/realtime_panel_simple.py:95`, `core/realtime_panel_simple.py:313`, `core/realtime_panel_modern.py:95`, `core/realtime_panel_modern.py:313`.
- Correção: aumentar tick e reduzir custo do estado.

3. Drift de versões de dependências entre manifests.
- Evidências: `requirements.txt:54`, `requirements.txt:55`, `app/backend/requirements.txt:1`, `app/backend/requirements.txt:2`.
- Correção: unificar lock/versionamento.

### LOW
1. Imports não usados e inconsistências de organização em skills (`requests` importado mas `SESSION` usado): `skills/news.py:6`, `skills/price.py:6`, `skills/youtube_summary.py:10`.
2. Cobertura de testes ausente (`tests/` inexistente).

## 4) Patches (diffs)
Não apliquei no workspace porque o ambiente estava em modo read-only no momento da auditoria; seguem diffs prontos para aplicar.

```diff
diff --git a/app/backend/server.py b/app/backend/server.py
--- a/app/backend/server.py
+++ b/app/backend/server.py
@@
 import os
 import json
 import asyncio
 import ipaddress
 import time
 import base64
 import sys
+import socket
+import hmac
+import secrets
 from urllib.parse import urlparse
-import requests
 from fastapi import FastAPI, WebSocket, WebSocketDisconnect
 import uvicorn
@@
 try:
     from config.env import init_env
     init_env()
 except Exception:
     pass
+from core.http_client import SESSION
@@
 def _env_bool(name: str, default: bool) -> bool:
     raw = os.environ.get(name, str(int(default))).strip().lower()
     return raw in {"1", "true", "yes", "on"}
+
+
+def _env_float(name: str, default: float) -> float:
+    try:
+        return float(os.environ.get(name, str(default)))
+    except Exception:
+        return default
@@
-TOKEN = os.environ.get("BACKEND_TOKEN", "")
+TOKEN = os.environ.get("BACKEND_TOKEN", "").strip()
+if not TOKEN:
+    TOKEN = secrets.token_urlsafe(32)
+    _log("[PET SEC] BACKEND_TOKEN ausente; token efemero gerado.")
@@
-MAX_MSG = 16000
+MAX_MSG = _env_int("LUNA_WS_MAX_MSG_BYTES", 16000)
+MAX_WS_MESSAGES_PER_MIN = _env_int("LUNA_WS_MAX_MESSAGES_PER_MIN", 30)
+MAX_URL_FETCH_BYTES = _env_int("LUNA_URL_FETCH_MAX_BYTES", 256000)
+STREAM_CHUNK_CHARS = max(8, _env_int("LUNA_WS_STREAM_CHUNK_CHARS", 24))
+STREAM_CHUNK_DELAY_SEC = max(0.0, _env_float("LUNA_WS_STREAM_DELAY_SEC", 0.002))
@@
 def _is_private_host(host: str) -> bool:
@@
     except ValueError:
         return False
+
+
+def _resolve_host_ips(host: str) -> list[str]:
+    try:
+        infos = socket.getaddrinfo(host, None)
+    except Exception:
+        return []
+    ips: list[str] = []
+    for info in infos:
+        ip = info[4][0]
+        if ip and ip not in ips:
+            ips.append(ip)
+    return ips
+
+
+def _host_targets_private_network(host: str) -> bool:
+    if _is_private_host(host):
+        return True
+    return any(_is_private_host(ip) for ip in _resolve_host_ips(host))
@@
 def _validate_url(url: str) -> str | None:
@@
     host = parsed.hostname or ""
     if not host:
         return None
-    if _is_private_host(host):
+    if parsed.username or parsed.password:
+        return None
+    if _host_targets_private_network(host):
         return None
     return url
@@
 def _fetch_url_summary(url: str) -> str:
@@
-        resp = requests.get(
-            safe,
-            timeout=8,
-            headers={"User-Agent": "LunaDeskPet/1.0"},
-            stream=True,
-        )
-        if resp.status_code >= 400:
-            return f"Falha ao acessar ({resp.status_code})."
-        content = resp.text
-        return f"Resumo basico: pagina com {len(content)} caracteres."
+        with SESSION.get(
+            safe,
+            timeout=8,
+            headers={"User-Agent": "LunaDeskPet/1.0"},
+            stream=True,
+            allow_redirects=False,
+        ) as resp:
+            if resp.status_code >= 400:
+                return f"Falha ao acessar ({resp.status_code})."
+            content_type = (resp.headers.get("Content-Type") or "").lower()
+            if "text/" not in content_type and "json" not in content_type and "xml" not in content_type and "html" not in content_type:
+                return "Conteudo nao textual."
+            raw = bytearray()
+            for chunk in resp.iter_content(chunk_size=4096):
+                if not chunk:
+                    continue
+                remaining = MAX_URL_FETCH_BYTES - len(raw)
+                if remaining <= 0:
+                    break
+                raw.extend(chunk[:remaining])
+            try:
+                content = raw.decode(resp.encoding or "utf-8", errors="replace")
+            except LookupError:
+                content = raw.decode("utf-8", errors="replace")
+            sufixo = " (truncado)" if len(raw) >= MAX_URL_FETCH_BYTES else ""
+            return f"Resumo basico: pagina com {len(content)} caracteres{sufixo}."
@@
-        resp = requests.get(url, headers=headers, timeout=8)
+        resp = SESSION.get(url, headers=headers, timeout=8)
@@
-        resp = requests.post(url, json=payload, headers=headers, timeout=LUNA_COMMAND_TIMEOUT)
+        resp = SESSION.post(url, json=payload, headers=headers, timeout=LUNA_COMMAND_TIMEOUT)
@@
-        requests.post(url, json=payload, headers=headers, timeout=45)
+        SESSION.post(url, json=payload, headers=headers, timeout=45)
@@
-        resp = requests.post(url, headers=headers, json=payload, timeout=MURF_TIMEOUT)
+        resp = SESSION.post(url, headers=headers, json=payload, timeout=MURF_TIMEOUT)
@@
-        raw = requests.get(audio_url, timeout=45)
+        raw = SESSION.get(audio_url, timeout=45)
@@
-        with requests.post(
+        with SESSION.post(
             MURF_STREAM_URL,
             headers=headers,
             json=payload,
             stream=True,
             timeout=MURF_TIMEOUT,
         ) as resp:
@@
 async def _stream_text(ws: WebSocket, text: str):
-    for ch in text:
-        await ws.send_text(json.dumps({"type": "delta", "text": ch}))
-        await asyncio.sleep(0.004)
+    texto = text or ""
+    for i in range(0, len(texto), STREAM_CHUNK_CHARS):
+        chunk = texto[i:i + STREAM_CHUNK_CHARS]
+        await ws.send_text(json.dumps({"type": "delta", "text": chunk}))
+        if STREAM_CHUNK_DELAY_SEC:
+            await asyncio.sleep(STREAM_CHUNK_DELAY_SEC)
     await ws.send_text(json.dumps({"type": "done"}))
@@
         raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
         msg = json.loads(raw)
-        if msg.get("type") != "auth" or msg.get("token") != TOKEN:
+        token = str(msg.get("token") or "")
+        if msg.get("type") != "auth" or not hmac.compare_digest(token, TOKEN):
             await ws.close(code=1008)
             return
@@
     try:
+        window_start = time.monotonic()
+        msg_count = 0
         while True:
             raw = await ws.receive_text()
+            now = time.monotonic()
+            if now - window_start >= 60:
+                window_start = now
+                msg_count = 0
+            msg_count += 1
+            if msg_count > MAX_WS_MESSAGES_PER_MIN:
+                await ws.send_text(json.dumps({"type": "error", "message": "rate_limited"}))
+                await ws.close(code=1013)
+                return
             if len(raw) > MAX_MSG:
                 await ws.close(code=1009)
                 return
-            data = json.loads(raw)
+            try:
+                data = json.loads(raw)
+            except json.JSONDecodeError:
+                await ws.send_text(json.dumps({"type": "error", "message": "invalid_json"}))
+                continue
```

```diff
diff --git a/core/realtime_panel_simple.py b/core/realtime_panel_simple.py
--- a/core/realtime_panel_simple.py
+++ b/core/realtime_panel_simple.py
@@
 import os
+import hmac
 import threading
 import time
 import logging
@@
 def _panel_token() -> str:
     return os.getenv("LUNA_PANEL_TOKEN", "").strip()
+
+
+def _panel_require_token() -> bool:
+    return os.getenv("LUNA_PANEL_REQUIRE_TOKEN", "1") == "1"
+
+
+def _panel_cors_origins() -> list[str]:
+    raw = os.getenv("LUNA_PANEL_CORS_ORIGINS", "http://127.0.0.1,http://localhost")
+    origins = [o.strip() for o in raw.split(",") if o.strip()]
+    return origins or ["http://127.0.0.1", "http://localhost"]
+
+
+def _panel_tick_sec() -> float:
+    try:
+        return max(0.5, float(os.getenv("LUNA_PANEL_TICK_SEC", "1.5")))
+    except ValueError:
+        return 1.5
+
+
+def _panel_max_payload_bytes() -> int:
+    try:
+        return max(1024, int(os.getenv("LUNA_PANEL_MAX_PAYLOAD_BYTES", "16384")))
+    except ValueError:
+        return 16384
@@
 def _token_ok(request) -> bool:
     required = _panel_token()
     if not required:
-        return True
+        return not _panel_require_token()
@@
-    return token == required
+    return hmac.compare_digest(token, required)
@@
-    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
+    socketio = SocketIO(app, cors_allowed_origins=_panel_cors_origins(), async_mode="threading")
@@
     @app.post("/control")
     def control_api():
+        max_payload = _panel_max_payload_bytes()
+        if request.content_length and request.content_length > max_payload:
+            return {"ok": False, "msg": "payload muito grande"}, 413
         if not _token_ok(request):
             return {"ok": False, "msg": "token invalido"}, 401
@@
     def on_connect():
         token = request.args.get("token", "")
         required = _panel_token()
-        if required and token != required:
+        if (_panel_require_token() and not required) or (required and not hmac.compare_digest(token, required)):
             return False
         emit("state_update", _last_state or _build_state())
@@
-            time.sleep(1)
+            time.sleep(_panel_tick_sec())
```

```diff
diff --git a/core/realtime_panel_modern.py b/core/realtime_panel_modern.py
--- a/core/realtime_panel_modern.py
+++ b/core/realtime_panel_modern.py
@@
 import os
+import hmac
 import threading
 import time
 import logging
@@
 def _panel_token() -> str:
     return os.getenv("LUNA_PANEL_TOKEN", "").strip()
+
+
+def _panel_require_token() -> bool:
+    return os.getenv("LUNA_PANEL_REQUIRE_TOKEN", "1") == "1"
+
+
+def _panel_cors_origins() -> list[str]:
+    raw = os.getenv("LUNA_PANEL_CORS_ORIGINS", "http://127.0.0.1,http://localhost")
+    origins = [o.strip() for o in raw.split(",") if o.strip()]
+    return origins or ["http://127.0.0.1", "http://localhost"]
+
+
+def _panel_tick_sec() -> float:
+    try:
+        return max(0.5, float(os.getenv("LUNA_PANEL_TICK_SEC", "1.5")))
+    except ValueError:
+        return 1.5
+
+
+def _panel_max_payload_bytes() -> int:
+    try:
+        return max(1024, int(os.getenv("LUNA_PANEL_MAX_PAYLOAD_BYTES", "16384")))
+    except ValueError:
+        return 16384
@@
 def _token_ok(request) -> bool:
     required = _panel_token()
     if not required:
-        return True
+        return not _panel_require_token()
@@
-    return token == required
+    return hmac.compare_digest(token, required)
@@
-    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
+    socketio = SocketIO(app, cors_allowed_origins=_panel_cors_origins(), async_mode="threading")
@@
     @app.post("/control")
     def control_api():
+        max_payload = _panel_max_payload_bytes()
+        if request.content_length and request.content_length > max_payload:
+            return {"ok": False, "msg": "payload muito grande"}, 413
         if not _token_ok(request):
             return {"ok": False, "msg": "token invalido"}, 401
@@
     def on_connect():
         token = request.args.get("token", "")
         required = _panel_token()
-        if required and token != required:
+        if (_panel_require_token() and not required) or (required and not hmac.compare_digest(token, required)):
             return False
         emit("state_update", _last_state or _build_state())
@@
-            time.sleep(1)
+            time.sleep(_panel_tick_sec())
```

```diff
diff --git a/core/memory.py b/core/memory.py
--- a/core/memory.py
+++ b/core/memory.py
@@
+import copy
 import json
 import os
 import re
+import tempfile
+import threading
 from datetime import datetime
@@
 LEGACY_MEMORY_PATH = os.path.join(BASE_DIR, "data", "memoria.json")
+_STORE_LOCK = threading.RLock()
+_STORE_CACHE: dict[str, tuple[float, dict]] = {}
@@
 def _empty_store():
     return {"items": [], "meta": {"created_at": "", "updated_at": "", "version": 1}}
+
+
+def _clone_store(store: dict) -> dict:
+    return copy.deepcopy(store)
@@
 def _load_store(path):
     if not os.path.isfile(path):
         return _empty_store()
-    try:
-        with open(path, "r", encoding="utf-8") as f:
-            data = json.load(f)
-        if isinstance(data, dict) and isinstance(data.get("items"), list):
-            return data
-        if isinstance(data, list):
-            store = _empty_store()
-            store["items"] = data
-            return store
-    except Exception:
-        pass
-    return _empty_store()
+    with _STORE_LOCK:
+        try:
+            mtime = os.path.getmtime(path)
+        except OSError:
+            return _empty_store()
+
+        cached = _STORE_CACHE.get(path)
+        if cached and cached[0] == mtime:
+            return _clone_store(cached[1])
+
+        try:
+            with open(path, "r", encoding="utf-8") as f:
+                data = json.load(f)
+            if isinstance(data, dict) and isinstance(data.get("items"), list):
+                store = data
+            elif isinstance(data, list):
+                store = _empty_store()
+                store["items"] = data
+            else:
+                store = _empty_store()
+        except Exception:
+            store = _empty_store()
+
+        _STORE_CACHE[path] = (mtime, _clone_store(store))
+        return store
@@
 def _save_store(path, store):
-    os.makedirs(MEMORY_DIR, exist_ok=True)
-    now = _now_iso()
-    meta = store.get("meta") or {}
-    if not meta.get("created_at"):
-        meta["created_at"] = now
-    meta["updated_at"] = now
-    meta["version"] = meta.get("version", 1)
-    store["meta"] = meta
-    with open(path, "w", encoding="utf-8") as f:
-        json.dump(store, f, ensure_ascii=True, indent=2)
+    with _STORE_LOCK:
+        os.makedirs(MEMORY_DIR, exist_ok=True)
+        now = _now_iso()
+        meta = store.get("meta") or {}
+        if not meta.get("created_at"):
+            meta["created_at"] = now
+        meta["updated_at"] = now
+        meta["version"] = meta.get("version", 1)
+        store["meta"] = meta
+
+        fd, tmp_path = tempfile.mkstemp(prefix="luna_mem_", suffix=".tmp", dir=MEMORY_DIR)
+        try:
+            with os.fdopen(fd, "w", encoding="utf-8") as f:
+                json.dump(store, f, ensure_ascii=True, separators=(",", ":"))
+            os.replace(tmp_path, path)
+        finally:
+            try:
+                if os.path.exists(tmp_path):
+                    os.remove(tmp_path)
+            except Exception:
+                pass
+
+        try:
+            mtime = os.path.getmtime(path)
+        except OSError:
+            mtime = -1.0
+        _STORE_CACHE[path] = (mtime, _clone_store(store))
@@
 def _ensure_long_memory_initialized():
-    if os.path.isfile(LONG_MEMORY_PATH):
-        return
-    legacy_items = _load_legacy_items()
-    if not legacy_items:
-        return
-    store = _empty_store()
-    store["items"] = legacy_items
-    _save_store(LONG_MEMORY_PATH, store)
+    with _STORE_LOCK:
+        if os.path.isfile(LONG_MEMORY_PATH):
+            return
+        legacy_items = _load_legacy_items()
+        if not legacy_items:
+            return
+        store = _empty_store()
+        store["items"] = legacy_items
+        _save_store(LONG_MEMORY_PATH, store)
@@
 def _add_item(path, texto, origem="usuario", max_items=None):
     texto_limpo = (texto or "").strip()
     if not texto_limpo:
         return False
-    store = _load_store(path)
-    store.setdefault("items", []).append(
-        {
-            "timestamp": _now_iso(),
-            "origem": origem,
-            "texto": texto_limpo,
-        }
-    )
-    if max_items is not None and len(store["items"]) > max_items:
-        store["items"] = store["items"][-max_items:]
-    _save_store(path, store)
+    with _STORE_LOCK:
+        store = _load_store(path)
+        store.setdefault("items", []).append(
+            {
+                "timestamp": _now_iso(),
+                "origem": origem,
+                "texto": texto_limpo,
+            }
+        )
+        if max_items is not None and len(store["items"]) > max_items:
+            store["items"] = store["items"][-max_items:]
+        _save_store(path, store)
     return True
```

```diff
diff --git a/config/state.py b/config/state.py
--- a/config/state.py
+++ b/config/state.py
@@
 import json
 import os
 import threading
 import time
 import random
+import tempfile
 from datetime import datetime
@@
     def _carregar_historico(self):
         if not os.path.isfile(_HISTORY_PATH):
             return []
         try:
             with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
                 data = json.load(f)
             if isinstance(data, list):
-                return data
+                return data[-_HISTORY_MAX:]
         except Exception:
             pass
         return []
@@
     def _salvar_historico(self):
         try:
             os.makedirs(os.path.dirname(_HISTORY_PATH), exist_ok=True)
-            with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
-                json.dump(self._historico, f, ensure_ascii=True, indent=2)
+            dir_path = os.path.dirname(_HISTORY_PATH)
+            fd, tmp_path = tempfile.mkstemp(
+                prefix="chat_history_",
+                suffix=".tmp",
+                dir=dir_path,
+            )
+            try:
+                with os.fdopen(fd, "w", encoding="utf-8") as f:
+                    json.dump(self._historico, f, ensure_ascii=True, separators=(",", ":"))
+                os.replace(tmp_path, _HISTORY_PATH)
+            finally:
+                try:
+                    if os.path.exists(tmp_path):
+                        os.remove(tmp_path)
+                except Exception:
+                    pass
         except Exception:
             pass
```

```diff
diff --git a/.env.example b/.env.example
--- a/.env.example
+++ b/.env.example
@@
 LUNA_PANEL_ENABLED=1
 LUNA_PANEL_HOST=127.0.0.1
 LUNA_PANEL_PORT=5055
 LUNA_PANEL_TOKEN=
+LUNA_PANEL_REQUIRE_TOKEN=1
+LUNA_PANEL_CORS_ORIGINS=http://127.0.0.1,http://localhost
```

## 5) Comandos para validar
1. Instalar ferramentas ausentes:
```powershell
python -m pip install -U pip
python -m pip install ruff black bandit pip-audit pytest
```

2. Validação estática:
```powershell
ruff check .
black --check .
bandit -r . -x .git,.context,backup,outputs,node_modules
pip-audit -r requirements.txt
pip-audit -r app/backend/requirements.txt
```

3. Sanidade de sintaxe:
```powershell
python -m compileall app/backend/server.py core/realtime_panel_simple.py core/realtime_panel_modern.py core/memory.py config/state.py
```

4. Testes (hoje inexistentes):
```powershell
pytest -q
```

5. Testes mínimos recomendados (criar):
- `test_backend_ws_rejects_invalid_token`
- `test_validate_url_blocks_private_and_limits_fetch`
- `test_panel_requires_token_when_flag_enabled`
- `test_memory_cache_add_and_count_consistency`
- `test_history_save_is_atomic_and_truncates_loaded_history`

## 6) Checklist final antes do merge
1. Rotacionar imediatamente todas as credenciais expostas em `.env` (`GROQ`, `SERPAPI`, `COINMARKETCAP`, `GEMINI`, `MURF`, `TWITCH`, `OBS`).
2. Definir `LUNA_PANEL_TOKEN` forte e manter `LUNA_PANEL_REQUIRE_TOKEN=1`.
3. Aplicar os diffs P0/P1 acima.
4. Rodar `ruff`, `bandit`, `pip-audit` e corrigir findings bloqueantes.
5. Adicionar os 3-5 testes mínimos críticos.
6. Unificar versões entre `requirements.txt` e `app/backend/requirements.txt`.
7. Validar fluxo manual: voz local, painel, pet Electron, e comandos websocket.
8. Confirmar que `.env` segue fora do controle de versão e sem logs contendo segredos.
