# Luna - Guia Tecnico Detalhado por Arquivo

## 1. Escopo deste documento

Este documento descreve a arquitetura da Luna e detalha o papel de cada arquivo principal do projeto.
O foco e:

- Codigo fonte Python da assistente.
- Integracoes (LLM, OBS, chat, painel, workflows).
- Frontend do pet (Electron).
- Arquivos de configuracao, dados e templates.

Observacao importante:
- O repositorio pode conter arquivos de runtime (capturas, audio gerado, backups locais) que nao fazem parte do nucleo de logica.

## 2. Visao geral da arquitetura

A Luna hoje opera em 4 camadas principais:

1. Entrada e orquestracao
- `main.py` inicializa ambiente, painel, chat ingest e loop de entrada de voz/PTT.
- `core/command_orchestrator.py` decide o caminho de execucao: workflow carregado primeiro, router como fallback.

2. Motor de skills e comandos
- `core/router.py` faz roteamento por intent/gatilhos e executa skill.
- `core/skill_registry.py` descobre, valida, carrega e recarrega skills.
- `core/skill_manifest.py` define contrato tipado de skill (inputs/outputs/config).

3. Fluxo, eventos e automacao
- `core/event_bus.py` publica/assina eventos com filtro.
- `core/event_queue.py` fila com metrica de drop/backpressure.
- `core/workflow_engine.py` executa fluxo linear e event-driven.
- `core/workflow_runtime.py` gerencia loading, start/stop, validacao e autostart por env.

4. Integracoes e interfaces
- Voz (`core/voice.py`, `core/push_to_talk.py`), chat (`core/chat_ingest.py`), OBS (`core/obs_client.py`), painel realtime (`core/realtime_panel_modern.py`).
- Skills em `skills/`.
- Pet desktop em `app/` (Electron + backend FastAPI).

## 3. Fluxo de inicializacao (boot)

Sequencia simplificada:

1. `main.py` chama `init_env()` e inicializa logging.
2. Painel realtime sobe via `core/realtime_panel.py` (proxy para `core/realtime_panel_modern.py`).
3. `core/workflow_runtime.autostart_workflow_from_env()` tenta iniciar workflow se configurado.
4. Chat ingest inicia (`core/chat_ingest.py`).
5. Se `LUNA_PTT_ENABLED=1`, entra em modo PTT; senao usa loop de `ouvir()` continuo.
6. Cada comando passa por `processar_comando_orquestrado()` (workflow first -> router fallback).

## 4. Mapa de arquivos - raiz do projeto

### `main.py`
- Papel: entrypoint principal da Luna.
- Responsabilidades:
- iniciar env/log/painel/chat ingest.
- ativar workflow autostart por env.
- capturar comando por voz/PTT/menu.
- chamar orquestrador de comando.

### `.env.example`
- Papel: referencia oficial de variaveis de ambiente.
- Inclui:
- painel, voz, OBS, chat, pet, workflow autostart.

### `.env` (local)
- Papel: configuracao real do ambiente local.
- Observacao: nao deve ser versionado com segredos.

### `README.md`
- Papel: onboarding, setup e uso rapido.

### `requirements.txt`
- Papel: dependencias Python da aplicacao principal.

### `.gitignore`
- Papel: excluir artefatos locais/temporarios/versionamento.

### `AGENTS.md`
- Papel: documento tecnico adicional de arquitetura/historico de design.

### `funcionalidades_luna.md`
- Papel: inventario funcional em linguagem de produto.

### `system_message.txt`
- Papel: prompt base em texto simples.

### `system_message.yaml`
- Papel: prompt estruturado (fallback/override por chave).

### `download.jpg`
- Papel: arquivo de apoio/imagem de teste local.

## 5. Configuracao (`config/`)

### `config/__init__.py`
- Papel: marca pacote Python.

### `config/env.py`
- Papel: bootstrap de ambiente.
- Funcoes:
- `_configure_console_utf8()`: reconfigura stdout/stderr para UTF-8.
- `init_env()`: carrega `.env` e aplica overrides de `assistant_config`.

### `config/assistant_config.py`
- Papel: carregar YAML central de configuracao de assistente.
- Funcoes:
- `load_assistant_config()`: le arquivo YAML.
- `apply_env_overrides()`: aplica valores no `os.environ` quando definidos.

### `config/assistant_config.yaml`
- Papel: configuracao local consolidada em YAML.

### `config/assistant_config.example.yaml`
- Papel: template de configuracao YAML.

### `config/state.py`
- Papel: estado global thread-safe da Luna.
- Mantem:
- modo de ativacao (`assistente`/`vtuber`).
- flags de sequencia/macros.
- historico e ultima resposta.
- referencias de visao/captura.

## 6. Core (`core/`)

### `core/__init__.py`
- Papel: marca pacote.

### `core/command_orchestrator.py`
- Papel: orquestrador principal de comando (workflow-first).
- Logica:
- ignora workflow para comandos de controle (modo/reload).
- usa workflow linear carregado quando compativel.
- extrai resposta do output do workflow.
- fallback para `router.processar_comando`.

### `core/intent.py`
- Papel: classificador de intencao por regras.
- Detecta intents sem depender de LLM.

### `core/router.py`
- Papel: roteador de skills.
- Estrategia:
- candidatos por nome/intent/gatilho.
- executa skill com retry e emite eventos de ciclo (`skill.started`, `skill.completed`, `skill.error`).

### `core/skill_manifest.py`
- Papel: contrato tipado de skill.
- Estruturas:
- `SkillPort`, `SkillConfigField`, `SkillManifest`.
- Normaliza e mescla fontes de manifesto (arquivo + embedded + legado).

### `core/skill_registry.py`
- Papel: discovery/load/validacao de skills.
- Recursos:
- lazy load, reload, diagnostico, cobertura de manifests externos.
- validacao estrutural de contrato da skill.

### `core/event_bus.py`
- Papel: pub/sub de eventos com filtros.
- Estruturas:
- `Event`, `EventFilter`, `EventBus`.
- API principal:
- `subscribe`, `unsubscribe`, `emit`, `get_history`.

### `core/event_queue.py`
- Papel: fila de eventos com controle de drop e estado de processamento.
- Utilizada pelo `WorkflowEngine` para backpressure.

### `core/workflow_engine.py`
- Papel: motor de workflow.
- Modos:
- `execute_linear()`: rodar grafo em ordem topologica.
- `start_event_driven()`: assinar eventos e processar continuamente.
- Recursos:
- validacao de portas/contratos.
- deteccao de ciclo.
- nodes builtin (`manual-input`, `console-output`, `obs-scene-switch`, `obs-source-toggle`).

### `core/workflow_runtime.py`
- Papel: runtime e API operacional de workflows.
- Funcoes:
- listar/carregar/validar/start/stop/run_once.
- `run_loaded_workflow_once()`: executa workflow ja carregado.
- `autostart_workflow_from_env()`: sobe workflow automatico no boot.

### `core/chat_ingest.py`
- Papel: ingestao de chat Twitch/YouTube.
- Emite eventos:
- `chat.message.received`, `message.received`, `chat.message.superchat`, `chat.message.membership`, etc.
- Adiciona metadados: mod/member/subscriber e detalhes de evento da plataforma.

### `core/voice.py`
- Papel: STT + TTS.
- STT:
- escuta via `speech_recognition`, opcao Groq ASR.
- VAD com `webrtcvad`.
- TTS:
- Murf ou fallback pyttsx3.
- atualiza legenda no OBS via `obs_client.update_text`.

### `core/push_to_talk.py`
- Papel: modo PTT com varios metodos (keyboard/mouse/gamepad/web).
- Garante estado de gravacao e callback de audio pronto para `main.handle_command`.

### `core/obs_client.py`
- Papel: cliente OBS WebSocket.
- Acoes:
- `update_text()`: legenda.
- `switch_scene()`: troca de cena.
- `set_source_enabled()`: ativa/desativa fonte.

### `core/realtime_panel.py`
- Papel: facade/proxy de painel.
- Atualmente delega para `core/realtime_panel_modern.py`.

### `core/realtime_panel_modern.py`
- Papel: painel realtime (Flask + Socket.IO + HTML embutido).
- Contem:
- estado em tempo real.
- health endpoint.
- acoes de controle (`workflow_*`, comando manual, recarregar skills, etc).
- metricas de workflow/backpressure no frontend.

### `core/http_client.py`
- Papel: sessao HTTP compartilhada com retry/timeouts.
- Evita repeticao de configuracao de `requests`.

### `core/logging_setup.py`
- Papel: logging estruturado/legivel.
- Formatters:
- `JsonFormatter` e `CleanFormatter`.

### `core/memory.py`
- Papel: armazenamento de memoria curta e longa.
- Funcoes para adicionar, listar, buscar e limpar memorias.

### `core/prompt_injector.py`
- Papel: composicao de prompts por contexto/skill.
- Entrega funcoes especificas para vision, web reader, youtube summary, system monitor e temperamento.

### `core/realtime_panel_simple.py` (removido no estado atual)
- Papel anterior: painel simplificado.
- Status: removido da implementacao ativa.

## 7. Skills (`skills/`)

### `skills/__init__.py`
- Papel: marca pacote.

### `skills/conversa.py`
- Papel: conversa principal com LLM.
- Usa contexto de memoria, prompt base e reforco quando detecta resposta fraca/incompleta.

### `skills/vision.py`
- Papel: captura e analise visual.
- Usa `llm/vision_llm.py` e atualiza estado de ultima visao.

### `skills/web_reader.py`
- Papel: leitura de pagina atual e resumo assistido.
- Usa Playwright + captura + analise.

### `skills/youtube_summary.py`
- Papel: resumo de video YouTube.
- Usa transcricao (API/yt-dlp), chunking e sintese.

### `skills/news.py`
- Papel: busca e resumo de noticias (SerpAPI), com filtros de periodo e refinamento de query.

### `skills/price.py`
- Papel: consulta de preco de criptomoedas (CoinMarketCap).

### `skills/system_monitor.py`
- Papel: status de CPU/RAM com resposta em estilo Luna.

### `skills/sequencia_manager.py`
- Papel: gravacao e execucao de macros.
- Estados de fluxo (nome, loops, gravando) integrados ao `STATE`.

### `skills/atalhos_radial.py`
- Papel: comandos para abrir/usar menu radial.

### `skills/game_guide.py`
- Papel: captura contexto de jogo e gera guia rapido via LLM.

### `skills/link_scraper.py`
- Papel: extracao e normalizacao de links de paginas.

### `skills/tts_murf.py`
- Papel: utilitario de TTS dedicado (geracao de audio/arquivos).

### `skills/teste.py` (removido no estado atual)
- Papel anterior: skill de teste.
- Status: removido.

## 8. Manifestos de skill (`skills/manifests/`)

Estes arquivos definem contrato externo tipado de cada skill.
Cada manifesto normalmente descreve:
- metadados (id, name, version, category).
- intents/gatilhos.
- portas de `inputs` e `outputs`.
- campos de `config`.

Arquivos:
- `skills/manifests/atalhos_radial.json`
- `skills/manifests/conversa.json`
- `skills/manifests/game_guide.json`
- `skills/manifests/link_scraper.json`
- `skills/manifests/news.json`
- `skills/manifests/price.json`
- `skills/manifests/sequencia_manager.json`
- `skills/manifests/system_monitor.json`
- `skills/manifests/tts_murf.json`
- `skills/manifests/vision.json`
- `skills/manifests/web_reader.json`
- `skills/manifests/youtube_summary.json`

## 9. Workflows (`workflows/templates/`)

Templates de fluxo prontos para validacao/teste e operacao:

- `workflows/templates/manual_system_monitor.json`
- fluxo linear de input manual -> skill system monitor -> console.

- `workflows/templates/chat_superchat_console.json`
- event-driven para superchat, output em console.

- `workflows/templates/chat_superchat_obs_scene.json`
- event-driven para superchat com troca de cena OBS.

- `workflows/templates/chat_membership_console.json`
- event-driven para membership, output em console.

- `workflows/templates/chat_membership_obs_source.json`
- event-driven para membership com toggle de fonte OBS.

- `workflows/templates/chat_system_monitor.json`
- template de monitoramento por evento para diagnostico.

## 10. LLM (`llm/`)

### `llm/__init__.py`
- Papel: marca pacote.

### `llm/vision_llm.py`
- Papel: client wrapper Gemini Vision.
- Recursos:
- rotacao de API keys.
- retries por chave.
- extração de texto e log de metadados de resposta.

## 11. Interface radial (`interface/`)

### `interface/radial_menu_eel.py`
- Papel: processo de UI radial via Eel.
- Comunica comando para Luna via clipboard com prefixo `@menu:`.

### `interface/web/radial_menu.html`
- Papel: UI do menu radial.

### `interface/web/icons/sequencias.svg`
- Papel: icone usado na UI radial.

## 12. Pet desktop (`app/`)

### `app/package.json`
- Papel: metadados e script de start do Electron.

### `app/package-lock.json`
- Papel: lock de dependencias Node.

### `app/backend/server.py`
- Papel: backend local do pet (FastAPI + WebSocket).
- Funcoes:
- ponte de comandos para painel da Luna.
- busca de estado e retorno final.
- geracao de audio base64 para o frontend.

### `app/backend/requirements.txt`
- Papel: dependencias especificas do backend do pet.

### `app/electron/main.js`
- Papel: processo principal Electron.
- Inicia backend Python local, cria janela e envia config WS para renderer.

### `app/electron/preload.js`
- Papel: ponte segura IPC (context bridge) para renderer.

### `app/electron/renderer/index.html`
- Papel: layout principal do pet.

### `app/electron/renderer/renderer.js`
- Papel: logica de UI/estado, WebSocket e animacoes de estado.

### `app/electron/renderer/styles.css`
- Papel: estilo visual do pet.

### `app/electron/renderer/assets/*.mp4`
- Papel: estados visuais do avatar (`idle`, `thinking`, `speaking`, `error`).

## 13. Documentacao (`docs/`)

### `docs/audio_output_fallback.md`
- Papel: guia de fallback de audio/TTS.

### `docs/auditoria_luna_performance_seguranca.md`
- Papel: auditoria tecnica (riscos, melhorias de perf/seguranca).

## 14. Dados e memoria (`data/`, `memory/`)

### `data/macros.json`
- Papel: persistencia das macros/sequencias gravadas.

### `data/links.txt`
- Papel: saida de extracao de links.

### `data/capturas/ultima_captura.png`
- Papel: ultima captura para fluxo de visao.

### `data/suuuiplash.txt`
- Papel: arquivo de dados local (uso auxiliar/manual).

### `memory/chat_history.json`
- Papel: historico persistente de conversa.

### `memory/short_term.json`
- Papel: memoria curta.

### `memory/long_term.json`
- Papel: memoria longa.

## 15. Arquivos locais de backup/runtime detectados

Estes arquivos existem no ambiente local e nao representam modulo de codigo central:

- `backup/*.bak`: snapshots manuais/automaticos de edicao.
- `outputs/tts/**`: audios e metadados gerados por TTS.
- `luna/pyvenv.cfg`, `luna/etc/jupyter/**`: artefatos do ambiente virtual local.

## 16. Variaveis chave de workflow (estado atual)

- `LUNA_WORKFLOW_DIR`: pasta base de workflows.
- `LUNA_WORKFLOW_AUTOSTART=1`: habilita start automatico no boot.
- `LUNA_WORKFLOW_AUTO_ID`: id do workflow para autostart.
- `LUNA_WORKFLOW_AUTO_PATH`: caminho relativo/absoluto do workflow para autostart.
- `LUNA_WORKFLOW_AUTO_LISTEN_PATTERNS`: padroes de evento (csv), ex: `chat.*,message.*`.
- `LUNA_WORKFLOW_AUTO_START_NODE_ID`: opcional, inicia em subgrafo.

## 17. Como navegar o codigo de forma eficiente

Ordem recomendada para leitura:

1. `main.py`
2. `core/command_orchestrator.py`
3. `core/workflow_runtime.py` + `core/workflow_engine.py`
4. `core/router.py` + `core/skill_registry.py` + `core/skill_manifest.py`
5. `core/chat_ingest.py` + `core/event_bus.py`
6. Skills em `skills/` (com manifestos correspondentes em `skills/manifests/`)
7. `core/realtime_panel_modern.py`
8. `app/backend/server.py` e `app/electron/*` (se usar pet desktop)

