# LUNA - Assistente Virtual com Voz, Workflow e Automacao

Luna e uma assistente virtual em Python com:

- voz (STT + TTS),
- skills modulares,
- motor de workflow (linear e event-driven),
- event bus para automacoes,
- painel realtime,
- integracao opcional com OBS e pet desktop (Electron + FastAPI).

---

## 1. Destaques da arquitetura atual

### Workflow-first com fallback
- Comandos passam por `core/command_orchestrator.py`.
- Se houver workflow carregado compativel, ele roda primeiro.
- Se nao houver resposta, cai no router tradicional.

### Skill manifests tipados
- Cada skill possui manifesto em `skills/manifests/*.json`.
- Contratos de `inputs`, `outputs` e `config` sao validados por `core/skill_registry.py`.

### Event bus + chat events ricos
- `core/event_bus.py` suporta pub/sub com filtros.
- `core/chat_ingest.py` publica eventos como:
- `chat.message.received`
- `chat.message.superchat`
- `chat.message.membership`
- `message.received`

### OBS alem de legenda
- `core/obs_client.py` suporta:
- update de texto (legenda),
- troca de cena,
- toggle de fonte.

### Metricas de fila/backpressure
- `core/workflow_engine.py` expoe:
- `queue_size`, `queue_dropped`, `queue_processing`,
- `events_processed`, `events_failed`.
- Painel mostra essas metricas em tempo real.

---

## 2. Requisitos

- Python 3.10+
- Windows recomendado (voz/automacao/PTT)
- Node.js (somente para pet desktop em `app/`)

---

## 3. Instalacao

```bash
pip install -r requirements.txt
playwright install chromium
```

Opcional (pet desktop):

```bash
cd app
npm install
npm start
```

---

## 4. Configuracao rapida (.env)

Copie `.env.example` para `.env` e ajuste as chaves necessarias.

Minimo comum:

```env
GEMINI_API_KEY=
GROQ_API_KEY=

LUNA_PANEL_ENABLED=1
LUNA_PANEL_HOST=127.0.0.1
LUNA_PANEL_PORT=5055
```

---

## 5. Workflow Engine (com autostart)

### 5.1 Variaveis principais

```env
LUNA_WORKFLOW_DIR=
LUNA_WORKFLOW_AUTOSTART=0
LUNA_WORKFLOW_AUTO_ID=
LUNA_WORKFLOW_AUTO_PATH=
LUNA_WORKFLOW_AUTO_LISTEN_PATTERNS=chat.*
LUNA_WORKFLOW_AUTO_START_NODE_ID=
```

### 5.2 Exemplo de autostart event-driven

```env
LUNA_WORKFLOW_AUTOSTART=1
LUNA_WORKFLOW_AUTO_PATH=templates/chat_superchat_console.json
LUNA_WORKFLOW_AUTO_LISTEN_PATTERNS=chat.*
```

Com isso, ao iniciar a Luna:
- workflow sobe automaticamente,
- eventos de chat ja comecam a ser processados.

### 5.3 Templates prontos

Em `workflows/templates/`:

- `manual_system_monitor.json`
- `chat_superchat_console.json`
- `chat_superchat_obs_scene.json`
- `chat_membership_console.json`
- `chat_membership_obs_source.json`
- `chat_system_monitor.json`

---

## 6. Modos de ativacao e PTT

- `assistente`: exige prefixo "luna" no comando.
- `vtuber`: aceita comando direto.
- Com `LUNA_PTT_ENABLED=1`, o PTT controla quando gravar, e o modo continua influenciando validacao de comando.

---

## 7. Comandos de exemplo

- `Luna, analise minha tela`
- `Luna, leia esse site`
- `Luna, resumo do youtube https://...`
- `Luna, preco do bitcoin`
- `Luna, noticias de tecnologia`
- `Luna, modo vtuber`
- `Luna, modo assistente`
- `Luna, gravar sequencia`
- `Luna, executar sequencia NOME`

---

## 8. Estrutura principal

```text
Luna/
  main.py
  config/
  core/
  skills/
    manifests/
  workflows/
    templates/
  llm/
  interface/
  app/
    backend/
    electron/
  memory/
  data/
  docs/
```

---

## 9. Arquivos centrais para desenvolvimento

- `main.py`: bootstrap e loop principal.
- `core/command_orchestrator.py`: workflow-first + fallback router.
- `core/workflow_engine.py`: motor de fluxo/eventos.
- `core/workflow_runtime.py`: runtime/load/start/stop/autostart.
- `core/router.py`: roteamento por intent/gatilho.
- `core/skill_registry.py`: discovery/load/validacao de skills.
- `core/chat_ingest.py`: ingestao de Twitch/YouTube e emissao de eventos.
- `core/realtime_panel_modern.py`: painel, controles e health.

---

## 10. Documentacao detalhada por arquivo

Para um mapeamento tecnico completo de cada arquivo:

- `docs/luna_guia_detalhado_arquivos.md`

---

## 11. Observacoes operacionais

- Para usar OBS, habilite `LUNA_OBS_ENABLED=1` e configure host/port/password/source.
- Para chat ingest, configure variaveis de Twitch/YouTube no `.env`.
- Sem APIs configuradas, skills que dependem de LLM/search podem falhar de forma esperada.
- O painel realtime pode requerer token (`LUNA_PANEL_TOKEN`) dependendo da configuracao.

