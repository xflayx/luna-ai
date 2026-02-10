# Funcionalidades da Luna e Comandos de Ativacao

Este arquivo resume as funcionalidades principais da Luna e como ativa-las por voz ou por interface.

## Ativacao Geral
- Modo assistente: dizer "Luna, ..." (exige o prefixo).
- Modo vtuber: "modo vtuber" ou "ativar vtuber" (responde sem prefixo).
- Modo assistente (voltar): "modo assistente" ou "ativar assistente".
- Recarregar skills: "recarregar skills" ou "recarregar skill".
- Abrir menu radial por voz: "abrir menu", "menu", "atalhos" ou "radial".
- Abrir menu radial por atalho: Alt+Q ou botao lateral do mouse (requer AutoHotkey configurado).

## Voz (STT e TTS)
- Entrada de voz: sempre ativa no loop principal.
- Saida de voz: respostas da Luna sao faladas automaticamente.

## Conversa (Gemini)
- Conversa normal: "Luna, <mensagem>".
- Memoria curta: usada automaticamente nas respostas.
- Memoria persistente:
- "lembre que <texto>"
- "o que voce lembra"
- "quais memorias"

## Visao (Tela e Gemini Vision)
- Analise geral de tela:
- "Luna, analise a tela"
- "Luna, o que aparece na tela?"
- "Luna, descreva a tela"
- "Luna, analise essa imagem"
- Reanalise da ultima captura:
- "reanalisar"
- "analise novamente"
- "ultima captura" ou "ultima imagem"

## Visao Focada (Detalhes Especificos)
- Exemplos de foco suportado: roupa, rosto, cabelo, olhos, maos, objeto, texto, placa, comida, bebida, acessorios.
- Comandos de exemplo:
- "Luna, foque na roupa"
- "Luna, o que ela esta segurando?"
- "Luna, descreva o rosto"
- "Luna, leia o texto da placa"

## Visao Automatica
- Ativar:
- "ativar visao automatica"
- "visao automatica"
- "modo automatico"
- Desativar:
- "parar visao automatica"
- "desativar visao automatica"
- "parar modo automatico"

## Leitura e Resumo de Sites (Web Reader)
- "Luna, leia este site"
- "Luna, resuma a pagina"
- "Luna, resumo do link"
- "Luna, resuma este tweet"

## Resumo de Video do YouTube
- "Luna, resumir video"
- "Luna, resumo do video"
- URL do YouTube no comando.

## Extracao de Links (Link Scraper)
- "extrair links"
- "listar links"
- "coletar links"
- "mapear links"
- "salvar links"
- "raspar links"

## Preco de Criptomoedas
- "preco do bitcoin"
- "cotacao do dolar"
- "valor do eth"
- "quanto esta o solana"

## Monitoramento do Sistema
- "status do pc"
- "cpu"
- "memoria"
- "ram"
- "temperatura"

## Guias e Tutoriais de Jogos
- "guia de <jogo>"
- "tutorial de <jogo>"
- "dicas de <jogo>"
- "como passar <fase>"
- "como conseguir <item>"

## Sequencias e Macros
- Iniciar gravacao: "gravar sequencia" ou "iniciar gravacao".
- Parar gravacao: "parar gravacao" ou "encerrar".
- Salvar: responder com o nome da sequencia quando solicitado.
- Executar: "executar sequencia <nome>" ou "rodar sequencia <nome>".
- Repeticoes: responder com numero ou "uma vez", "duas vezes", "tres vezes".

## TTS Murf (Narracao)
- "tts: <texto>"
- "narrar: <texto>"
- "murf: <texto>"
- "tts arquivo: <caminho>"
- Opcoes: "voz=<id>" e "fmt=mp3" ou "fmt=wav".
- "ler roteiro" ou "leia o roteiro".

## Noticias (SerpAPI)
- "noticias sobre <tema>"
- "news <tema>"
- "jornal <tema>"
- "o que esta acontecendo sobre <tema>"

## Chat Ingest (Twitch e YouTube)
- Funcionalidade automatica quando ativada via .env.
- Twitch: LUNA_TWITCH_ENABLED=1.
- Respostas automaticas: LUNA_CHAT_REPLY_ENABLED=1.

## Painel Realtime
- Controle de modo, comando remoto e recarga de skills via painel.
- Acesso local pelo painel configurado (ver README e .env).
