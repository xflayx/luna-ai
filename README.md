# LUNA - Assistente Virtual Inteligente

Luna e uma assistente virtual em Python com voz, visao e automacao. Ela usa modelos LLM (Gemini) para conversar, resumir conteudos e responder com personalidade.

## O que ela faz
- Conversa com memoria curta e respostas naturais
- Luna Vision: analise da tela por screenshot
- Reanalise da ultima captura sem nova captura de tela
- Web Reader: resumo de pagina atual e posts do X/Twitter
- YouTube Summary: resumo via transcricao
- Noticias: busca e resumo via SerpAPI
- Precos: consulta de cripto via CoinMarketCap
- Sistema: status do PC (CPU/RAM)
- Sequencias: gravar e executar macros de teclado/mouse
- Atalhos radial e guia de jogos baseado na tela
- STT via Groq ASR com fallback para Google
- System prompt via YAML com fallback para system_message.txt

## Requisitos
- Python 3.10+
- Windows recomendado para voz e automacao

## Instalacao
```bash
pip install -r requirements.txt
playwright install chromium
```

Notas:
- No Windows, o pyaudio pode exigir instalacao extra:
  ```bash
  pip install pipwin
  pipwin install pyaudio
  ```

## Configuracao (.env)
Crie um arquivo `.env` com as chaves que voce usar:

```
GEMINI_API_KEY=...
# opcionais para rotacao
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...

# resumo de YouTube
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
- `core`: roteamento, intencoes e voz
- `skills`: habilidades (vision, web_reader, youtube_summary, etc)
- `llm`: integracoes com LLM
- `config`: estado e configuracoes
- `data`: macros/seqs gravadas
- `ui`: dashboard
- `system_message.yaml`: prompt principal (fallback para `system_message.txt`)

## Testes
```bash
pytest tests/ -v
```

## Observacoes
- O Web Reader depende do navegador aberto e pode falhar em sites com login.
- Para X/Twitter, logue no navegador antes do resumo.
