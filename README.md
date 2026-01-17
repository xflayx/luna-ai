# 🤖 LUNA - Assistente Virtual Inteligente

A **Luna** é uma assistente virtual personalizada desenvolvida em Python, integrada com o modelo **Gemini 1.5 Flash**. Ela combina automação de tarefas, visão computacional e uma personalidade sarcástica e inteligente.

## 🚀 Funcionalidades Principais

### 👁️ Luna Vision (Análise de Tela)
A Luna consegue "enxergar" o que você está fazendo e responder a perguntas específicas sobre a sua tela.
* **Resumos:** "Luna, analise minha tela e faça um breve resumo do texto."
* **Identificação:** "Luna, veja a imagem e me diga qual é esse personagem."
* **Sugestões:** "Luna, analise a tela e recomende um anime baseado no que estou vendo."

## 🤖 Sequências (Macros)
Módulo de automação de periféricos controlado por voz.

| Comando | Descrição |
| :--- | :--- |
| **"Luna gravar sequência"** | Inicia a gravação de movimentos do mouse e teclas pressionadas. |
| **"Luna parar sequência"** | Interrompe a gravação e solicita um nome para salvar o arquivo. |
| **"Luna executar sequência [nome]"** | Carrega a sequência desejada. |
| **Loop** | Após o comando de execução, a Luna perguntará quantas vezes a sequência deve ser repetida. |."

### 🧠 Opinion Engine & Contexto
A Luna possui memória de curto prazo e um motor de personalidade que permite conversas fluidas sem perder o fio da meada. Ela detecta intenções de forma flexível, aceitando variações naturais da fala.

## 🛠️ Tecnologias Utilizadas
* **Python 3.10+**
* **Google Generative AI (Gemini API)**
* **PyAutoGUI** (Para automação de sequências)
* **Pillow** (Para captura e processamento de imagens)
* **SpeechRecognition & Pyttsx3** (Interface de voz)

## 📁 Estrutura do Projeto
* `/core`: Motores de intenção, roteamento e voz.
* `/skills`: Habilidades específicas como Visão, Preço e Sequências.
* `/data`: Local onde as sequências salvas são armazenadas em formato JSON.
* `/config`: Arquivos de configuração de personalidade e estado do sistema.

## ⚙️ Configuração
1. Clone o repositório.
2. Instale as dependências: `pip install -r requirements.txt`.
3. Configure sua `API_KEY` do Gemini no arquivo de configuração.
4. Execute o projeto: `python main.py`.

## 🎤 Comandos de Ativação
Todos os comandos devem ser precedidos pelo nome **Luna**.
* *Exemplo:* "Luna, qual o preço do Bitcoin?" ou "Luna, analise minha tela." [cite: 2025-12-30]
