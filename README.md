# LUNA - Assistente Virtual Inteligente

Luna e uma assistente virtual em Python com voz, visao e automacao. Ela usa LLMs
(Gemini/Groq) para conversar, resumir conteudos e responder com personalidade.

## Principais recursos
- Conversa com memoria curta
- Luna Vision: analise da tela via screenshot
- Reanalise da ultima captura (sem nova captura)
- Web Reader: resumo de pagina atual e posts do X/Twitter
- YouTube Summary: resumo via transcricao
- Noticias: busca e resumo via SerpAPI
- Precos: consulta de cripto via CoinMarketCap
- Sistema: status do PC (CPU/RAM)
- Sequencias: gravar e executar macros de teclado/mouse
- Atalhos radial e guia de jogos baseado na tela
- STT via Groq ASR com fallback para Google
- System prompt via YAML com fallback para system_message.txt
- Config central opcional via `config/assistant_config.yaml` (override do .env)
- Historico persistente em `memory/chat_history.json`
- Legendas no OBS via WebSocket v5
- Painel realtime (Flask + Socket.IO)
- Pet desktop (Electron + backend Python local via WebSocket)

## Skills (habilidades)
- conversa: chat principal com personalidade
- vision: analise visual da tela (Gemini Vision)
- web_reader: resumo de paginas e posts
- youtube_summary: resumo por transcricao
- news: noticias via SerpAPI
- price: preco de cripto via CoinMarketCap
- system_monitor: status do PC
- sequencia_manager: macros/loops
- atalhos_radial: menu radial/atalhos
- game_guide: guia rapido baseado na tela
- link_scraper: extracao de links em paginas

## Requisitos
- Python 3.10+
- Windows recomendado para voz e automacao

## Instalacao
```bash
pip install -r requirements.txt
playwright install chromium
```

### Pet desktop (opcional)
```bash
cd app
npm install
npm start
```

Notas do pet:
- O pet usa `app/backend/server.py` (FastAPI + WebSocket local em `127.0.0.1`).
- O pet nao depende de Flet (implementacao Flet foi removida).

Notas:
- No Windows, o pyaudio pode exigir instalacao extra:
  ```bash
  pip install pipwin
  pipwin install pyaudio
  ```

## Configuracao (.env ou YAML)
Voce pode usar o `.env` **ou** o `config/assistant_config.yaml`.
O YAML sobrescreve o `.env` apenas quando o valor estiver preenchido.

### Exemplo .env
Crie um arquivo `.env` com as chaves que voce usar:

```
GEMINI_API_KEY=...
# opcionais para rotacao
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...

# resumo de YouTube e STT Groq
GROQ_API_KEY=...
LUNA_GROQ_MODEL=llama-3.1-8b-instant
LUNA_GROQ_STT_MODEL=whisper-large-v3
LUNA_STT_ENGINE=groq

# noticias
SERPAPI_API_KEY=...

# precos cripto
COINMARKETCAP_API_KEY=...

# TTS externo (opcional)
MURF_API_KEY=...
LUNA_TTS_ENGINE=murf
LUNA_MURF_VOICE=pt-BR-isadora
MURF_FORMAT=WAV
MURF_STYLE=Conversational
MURF_LOCALE=pt-BR
MURF_RATE=15
MURF_PITCH=10
MURF_MODEL=FALCON
MURF_SAMPLE_RATE=24000
MURF_CHANNEL_TYPE=MONO
MURF_BASE_URL=https://api.murf.ai
MURF_STREAM_URL=https://global.api.murf.ai/v1/speech/stream
LUNA_FFPLAY_PATH=...

# Pet TTS (somente pet, sem afetar a Luna principal)
LUNA_PET_TTS_ENABLED=1
LUNA_PET_TTS_PROVIDER=murf
LUNA_PET_FALAR=0
LUNA_PET_TTS_FORMAT=WAV
LUNA_PET_MURF_VOICE=pt-BR-isadora
LUNA_PET_MURF_STYLE=Conversational
LUNA_PET_MURF_LOCALE=pt-BR
LUNA_PET_MURF_MODEL=FALCON
LUNA_PET_MURF_RATE=15
LUNA_PET_MURF_PITCH=10
LUNA_PET_MURF_SAMPLE_RATE=24000
LUNA_PET_MURF_CHANNEL_TYPE=MONO
LUNA_PET_TTS_TIMEOUT=120

# memoria curta
LUNA_MEM_LENGTH=2
LUNA_SYSTEM_PROMPT_PATH=system_message.txt
LUNA_SYSTEM_YAML_PATH=system_message.yaml
LUNA_PROMPT_ORDER=inject_then_trim
LUNA_CHAT_HISTORY_PATH=memory/chat_history.json
LUNA_CHAT_HISTORY_MAX=20

# painel realtime
LUNA_PANEL_ENABLED=1
LUNA_PANEL_HOST=127.0.0.1
LUNA_PANEL_PORT=5055
LUNA_PANEL_TOKEN=

# OBS WebSocket (legendas) - v5
LUNA_OBS_ENABLED=1
LUNA_OBS_HOST=127.0.0.1
LUNA_OBS_PORT=4455
LUNA_OBS_PASSWORD=...
LUNA_OBS_TEXT_SOURCE=Legenda_Luna
LUNA_OBS_WRAP_CHARS=42
LUNA_OBS_CLEAR_SEC=6
LUNA_OBS_CLEAR_HIDE=1
LUNA_OBS_SCENE=MinhaCena

# Integracao chat (Twitch/YouTube)
LUNA_TWITCH_ENABLED=0
LUNA_TWITCH_NICK=seu_bot
LUNA_TWITCH_OAUTH=oauth:seu_token
LUNA_TWITCH_CHANNEL=seu_canal

LUNA_YT_ENABLED=0
LUNA_YT_API_KEY=...
LUNA_YT_LIVE_CHAT_ID=...
LUNA_YT_POLL_MS=5000

# Resposta por voz para chat
LUNA_CHAT_REPLY_ENABLED=0
LUNA_CHAT_REPLY_MODE=mention  # mention | prefix | all
LUNA_CHAT_REPLY_PREFIX=!luna
LUNA_CHAT_REPLY_NAME=luna
LUNA_CHAT_REPLY_MIN_INTERVAL=8
LUNA_CHAT_REPLY_USER_COOLDOWN=30
LUNA_CHAT_REPLY_MAX_CHARS=200
LUNA_CHAT_REPLY_PLATFORMS=twitch,youtube
LUNA_CHAT_REPLY_QUEUE_MAX=20
LUNA_CHAT_REPLY_IGNORE_USERS=
```

## Uso rapido
Exemplos de comandos por voz:
- "Luna, analise minha tela"
- "Luna, leia esse site" (usa a URL atual do navegador)
- "Luna, faca um resumo desse post" (X/Twitter)
- "Luna, resumo do youtube https://..."
- "Luna, preco do bitcoin"
- "Luna, noticias de tecnologia"
- "Luna, gravar sequencia" / "Luna, executar sequencia NOME"

## Estrutura do projeto
- `core`: roteamento, intencoes, voz e painel realtime
- `skills`: habilidades (vision, web_reader, youtube_summary, etc)
- `llm`: integracoes com LLM
- `config`: estado e configuracoes
- `config/assistant_config.yaml`: config central opcional (override do .env)
- `data`: macros/seqs gravadas
- `interface`: menu radial (eel)
- `system_message.yaml`: prompt principal (fallback para `system_message.txt`)
- `memory/chat_history.json`: historico persistente da conversa

## Testes
```bash
pytest tests/ -v
```

## Observacoes
- O Web Reader depende do navegador aberto e pode falhar em sites com login.
- Para X/Twitter, logue no navegador antes do resumo.
