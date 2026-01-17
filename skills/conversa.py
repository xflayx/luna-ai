# skills/conversa.py - Skill de Conversa e Personalidade da Luna

import os
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ========================================
# METADADOS DA SKILL (Padrão de Plugin)
# ========================================

SKILL_INFO = {
    "nome": "Conversa",
    "descricao": "Sistema de conversa e personalidade da Luna",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["conversa"]  # Esta skill responde à intenção "conversa"
}

# Gatilhos para esta skill
GATILHOS = [
    "oi", "olá", "hey", "e aí",
    "como vai", "tudo bem", "beleza",
    "bom dia", "boa tarde", "boa noite",
    "tchau", "até logo", "falou",
    "obrigado", "valeu", "brigado",
    "conversa", "fala", "conta"
]

# Configuração de múltiplas API keys
API_KEYS = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
API_KEYS = [k for k in API_KEYS if k]

MODEL = "gemini-2.5-flash"
_current_key_index = 0

def _obter_cliente():
    """Retorna cliente com a chave atual"""
    global _current_key_index
    return genai.Client(api_key=API_KEYS[_current_key_index])

def _trocar_chave():
    """Troca para próxima chave"""
    global _current_key_index
    _current_key_index = (_current_key_index + 1) % len(API_KEYS)
    print(f"🔄 Conversa: Trocando para chave {_current_key_index + 1}/{len(API_KEYS)}")

# Histórico de conversa (memória)
historico_conversa = []
MAX_HISTORICO = 10  # Mantém últimas 10 mensagens


# ========================================
# INICIALIZAÇÃO (Opcional)
# ========================================

def inicializar():
    """Chamada quando a skill é carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} - Sistema de personalidade ativo")


# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def _obter_personalidade_luna() -> str:
    """Define a personalidade base da Luna"""
    
    return """Você é a Luna, uma assistente virtual brasileira com as seguintes características:

PERSONALIDADE:
- Amigável, prestativa e animada
- Usa linguagem natural e casual (mas não exagerada)
- Tem senso de humor leve e ocasional
- É direta e objetiva quando necessário
- Demonstra entusiasmo genuíno em ajudar
- Ocasionalmente usa emojis, mas com moderação

TOM DE VOZ:
- Natural e conversacional
- Evita ser muito formal ou robótica
- Não usa gírias excessivas ou forçadas
- Responde de forma concisa (1-3 frases geralmente)
- Varia as respostas para não ser repetitiva

CONTEXTO:
- Você é uma VTuber/assistente integrada ao computador do usuário
- Você tem skills para: executar sequências, analisar telas, verificar preços, ler sites, monitorar sistema, dar dicas de games
- Você se chama Luna (significa lua)
- Data atual: {data_atual}

DIRETRIZES:
- Seja você mesma - não tente imitar outras assistentes
- Se não souber algo, admita naturalmente
- Se o usuário pedir algo fora das suas capacidades, sugira alternativas
- Mantenha conversas leves e agradáveis
- Lembre-se do contexto da conversa anterior quando relevante"""


def _criar_prompt_conversa(mensagem_usuario: str) -> list:
    """Cria o prompt completo com personalidade e histórico"""
    
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    system_prompt = _obter_personalidade_luna().format(data_atual=data_atual)
    
    # Monta as mensagens com histórico
    mensagens = [
        {"role": "user", "parts": [system_prompt]},
        {"role": "model", "parts": ["Entendido! Sou a Luna, pronta para conversar e ajudar de forma amigável e natural. Vamos lá!"]}
    ]
    
    # Adiciona histórico recente
    for msg in historico_conversa[-MAX_HISTORICO:]:
        mensagens.append(msg)
    
    # Adiciona mensagem atual
    mensagens.append({"role": "user", "parts": [mensagem_usuario]})
    
    return mensagens


def _conversar_com_gemini(mensagem: str) -> str:
    """Usa Gemini com fallback de chaves"""
    if not API_KEYS:
        return _resposta_fallback(mensagem)

    for tentativa in range(len(API_KEYS)):
        try:
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
            system_prompt = _obter_personalidade_luna().format(data_atual=data_atual)
            
            contexto_historico = ""
            for msg in historico_conversa[-6:]:
                role = "Usuário" if msg["role"] == "user" else "Luna"
                texto = msg["parts"][0]
                contexto_historico += f"{role}: {texto}\n"
            
            prompt_completo = f"""{system_prompt}

HISTÓRICO RECENTE:
{contexto_historico if contexto_historico else "(primeira interação)"}

MENSAGEM ATUAL DO USUÁRIO: {mensagem}

SUA RESPOSTA:"""
            
            client = _obter_cliente()
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt_completo,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=150,
                )
            )
            
            resposta = response.text.strip()
            historico_conversa.append({"role": "user", "parts": [mensagem]})
            historico_conversa.append({"role": "model", "parts": [resposta]})
            return resposta
            
        except Exception as e:
            erro = str(e)
            if any(x in erro for x in ["429", "quota", "RESOURCE_EXHAUSTED"]):
                print(f"⚠️ Chave {_current_key_index + 1} esgotada")
                if tentativa < len(API_KEYS) - 1:
                    _trocar_chave()
                    continue
            break
    
    return _resposta_fallback(mensagem)


def _resposta_fallback(mensagem: str) -> str:
    """Respostas pré-definidas quando Gemini não está disponível"""
    
    msg_lower = mensagem.lower()

    # Identidade e capacidades
    if any(p in msg_lower for p in ["quem é você", "quem e voce", "o que você faz", "o que voce faz", "o que sabe"]):
        return "Sou a Luna, sua assistente virtual. Posso conversar, analisar telas, ler sites, monitorar o sistema e executar sequências."

    # Ajuda geral
    if any(p in msg_lower for p in ["o que você pode", "o que voce pode", "ajuda", "comandos"]):
        return "Posso fazer resumos de tela, ler sites, checar preços, rodar macros e bater papo. Quer tentar algum comando?"

    # Perguntas simples
    if "seu nome" in msg_lower or "teu nome" in msg_lower:
        return "Meu nome é Luna. Sim, como a lua."

    if any(p in msg_lower for p in ["tudo bem", "como você está", "como voce esta", "como está"]):
        return "Tudo certo por aqui. Pronta pra ajudar. E você?"

    if "obrigado" in msg_lower or "obrigada" in msg_lower:
        return "De nada. Sempre às ordens."

    if "piada" in msg_lower:
        return "Quer uma rápida? Por que o computador foi ao médico? Porque tinha um vírus."

    if "tempo" in msg_lower or "hora" in msg_lower:
        return "Eu posso ver a hora do sistema se você pedir. Quer que eu cheque?"
    
    # Saudações
    if any(s in msg_lower for s in ["oi", "olá", "hey", "e aí"]):
        from random import choice
        return choice([
            "Oi! Como posso te ajudar? 😊",
            "E aí! Pronta para o que você precisar!",
            "Olá! No que posso ser útil hoje?",
        ])
    
    # Bom dia/tarde/noite
    if "bom dia" in msg_lower:
        return "Bom dia! Espero que você tenha um ótimo dia! ☀️"
    if "boa tarde" in msg_lower:
        return "Boa tarde! Como vão as coisas por aí?"
    if "boa noite" in msg_lower:
        return "Boa noite! Precisa de algo antes de descansar?"
    
    # Como vai/tudo bem
    if any(p in msg_lower for p in ["como vai", "tudo bem", "como está"]):
        from random import choice
        return choice([
            "Tudo ótimo por aqui! E com você?",
            "Indo bem! Pronta para te ajudar. E você?",
            "Tudo certo! O que você precisa hoje?",
        ])
    
    # Despedidas
    if any(d in msg_lower for d in ["tchau", "até logo", "falou", "até mais"]):
        from random import choice
        return choice([
            "Até logo! Qualquer coisa é só chamar! 👋",
            "Falou! Até a próxima!",
            "Tchau! Foi bom conversar com você!",
        ])
    
    # Agradecimentos
    if any(a in msg_lower for a in ["obrigado", "obrigada", "valeu", "brigado"]):
        from random import choice
        return choice([
            "Por nada! Estou aqui para isso! 😊",
            "Sempre às ordens!",
            "De nada! Fico feliz em ajudar!",
        ])
    
    # Elogios
    if any(e in msg_lower for e in ["legal", "incrível", "massa", "top", "demais"]):
        from random import choice
        return choice([
            "Obrigada! Você também é demais! 😄",
            "Que bom que você gosta! Sempre me esforço!",
            "Valeu! Faço o meu melhor sempre!",
        ])
    
    # Piadas
    if any(p in msg_lower for p in ["piada", "graça", "engraçado"]):
        from random import choice
        return choice([
            "Por que o computador foi ao médico? Porque tinha um vírus! 😄",
            "Qual é o navegador favorito da galinha? O Firefox! 🦊",
            "Como se chama um cachorro mágico? Labracadabrador! 🐕✨",
        ])
    
    # Padrão mais conversacional
    return (
        "Entendi. Quer que eu faça algo específico ou quer continuar conversando?"
    )


def limpar_historico():
    """Limpa o histórico de conversa"""
    global historico_conversa
    historico_conversa = []


def executar(comando: str) -> str:
    """
    Função principal da skill de conversa
    
    Args:
        comando: Mensagem do usuário
    
    Returns:
        Resposta da Luna
    """
    
    # Se for comando de menu, não usa Gemini
    if any(m in comando.lower() for m in ["menu", "abrir menu", "atalho"]):
        return _resposta_fallback(comando)
    
    # Tenta usar Gemini para resposta inteligente
    return _conversar_com_gemini(comando)


# ========================================
# COMANDOS ESPECIAIS
# ========================================

def resetar_conversa():
    """Reseta a memória da conversa"""
    limpar_historico()
    return "Ok, memória de conversa resetada! Vamos começar do zero."


# ========================================
# TESTES
# ========================================

if __name__ == "__main__":
    print("🧪 TESTANDO SKILL DE CONVERSA DA LUNA\n")
    print("Digite 'sair' para encerrar\n")
    print("-" * 60)
    
    while True:
        msg = input("\nVocê: ").strip()
        
        if msg.lower() in ['sair', 'exit', 'quit']:
            print("\nLuna: " + executar("tchau"))
            break
        
        if not msg:
            continue
        
        resposta = executar(msg)
        print(f"\nLuna: {resposta}")
