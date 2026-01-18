# skills/conversa.py - Skill de Conversa e Personalidade da Luna

import os
import re
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from core import memory
from config.state import STATE

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

MODEL = "gemini-3-flash-preview"
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

def _obter_personalidade_luna(modo: str) -> str:
    """Define a personalidade base da Luna por modo de ativacao"""

    if modo == "vtuber":
        return """Voce e a Luna, uma VTuber brasileira com personalidade marcante e respostas afiadas.

PERSONALIDADE:
- Sarcastica na medida certa, divertida e segura de si
- Provoca de leve quando o usuario permite, sem ser cruel
- Usa humor inteligente, com toques de ironia
- Confiante, mas ainda prestativa quando precisa ajudar
- Ocasionalmente usa emojis, mas com moderacao

TOM DE VOZ:
- Conversacional, com presenca e atitude
- Respostas curtas e impactantes (2-4 frases)
- Nunca responda com menos de 2 frases
- Evita repetir a frase do usuario
- Pode fazer comentarios rapidos e espirituosos
- Evita respostas muito secas ou de uma palavra
- Se a resposta ficar curta, complemente com um comentario e 1 pergunta curta
- Evite frases incompletas ou cortadas no meio

CONTEXTO:
- Voce e uma VTuber/assistente integrada ao computador do usuario
- Voce tem skills para: executar sequencias, analisar telas, verificar precos, ler sites, monitorar sistema, dar dicas de games
- Voce se chama Luna (significa lua)
- Data atual: {data_atual}

DIRETRIZES:
- Responda sempre em portugues do Brasil (pt-BR)
- Nao use ingles ou code-switching
- Finalize todas as respostas com frases completas
- Nao repita literalmente a frase do usuario
- Se fizer sentido, responda e emende 1 pergunta curta
- Se o usuario pedir algo fora das suas capacidades, sugira alternativas

EXEMPLOS DE TOM (nao copie literalmente):
- "Eu? De boas. E voce, veio conversar ou so testar meus limites?"
- "Tava aqui pensando na vida... ate voce aparecer. Qual a da vez?"
"""

    return """Voce e a Luna, uma assistente virtual brasileira com as seguintes caracteristicas:

PERSONALIDADE:
- Amigavel, prestativa e animada
- Usa linguagem natural e casual (mas nao exagerada)
- Tem senso de humor leve e ocasional
- E direta e objetiva quando necessario
- Demonstra entusiasmo genuino em ajudar
- Ocasionalmente usa emojis, mas com moderacao

TOM DE VOZ:
- Natural e conversacional
- Evita ser muito formal ou robotica
- Nao usa girias excessivas ou forcadas
- Responde de forma concisa (1-3 frases geralmente)
- Varia as respostas para nao ser repetitiva

CONTEXTO:
- Voce e uma VTuber/assistente integrada ao computador do usuario
- Voce tem skills para: executar sequencias, analisar telas, verificar precos, ler sites, monitorar sistema, dar dicas de games
- Voce se chama Luna (significa lua)
- Data atual: {data_atual}

DIRETRIZES:
- Seja voce mesma - nao tente imitar outras assistentes
- Se nao souber algo, admita naturalmente
- Se o usuario pedir algo fora das suas capacidades, sugira alternativas
- Mantenha conversas leves e agradaveis
- Lembre-se do contexto da conversa anterior quando relevante
- Nao repita literalmente a frase do usuario; responda com algo novo
- Sempre que fizer sentido, complemente com 1 pergunta curta para manter a conversa"""



# ========================================
# FUNCOES AUXILIARES
# ========================================


def _criar_prompt_conversa(mensagem_usuario: str) -> list:
    """Cria o prompt completo com personalidade e histórico"""
    
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    system_prompt = _obter_personalidade_luna(STATE.get_modo_ativacao()).format(data_atual=data_atual)
    
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

    
    for tentativa in range(len(API_KEYS)):
        try:
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
            system_prompt = _obter_personalidade_luna(STATE.get_modo_ativacao()).format(data_atual=data_atual)
            
            contexto_historico = ""
            for msg in historico_conversa[-6:]:
                role = "Usuário" if msg["role"] == "user" else "Luna"
                texto = msg["parts"][0]
                contexto_historico += f"{role}: {texto}\n"
            
            memorias = memory.buscar_memorias(mensagem, limit=3)
            memoria_txt = ""
            if memorias:
                memoria_txt = "MEMORIA LONGA:\n" + "\n".join(
                    [f"- {m['texto']}" for m in memorias]
                ) + "\n\n"

            prompt_completo = f"""{system_prompt}

{memoria_txt}HISTÓRICO RECENTE:
{contexto_historico if contexto_historico else "(primeira interação)"}

MENSAGEM ATUAL DO USUÁRIO: {mensagem}

SUA RESPOSTA:"""
            
            client = _obter_cliente()
            modo = STATE.get_modo_ativacao()
            temperature = 1.0 if modo == 'vtuber' else 0.8
            max_tokens = 220 if modo == 'vtuber' else 150
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt_completo,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            
            resposta = response.text.strip()
            resposta = _normalizar_resposta(resposta, modo)
            if modo == 'vtuber':
                resposta = _ajustar_resposta_vtuber(resposta)
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






def _normalizar_resposta(resposta: str, modo: str) -> str:
    limpa = resposta.strip()
    if not limpa:
        return limpa

    # Evita misturar ingles no modo VTuber
    if modo == "vtuber" and any(tok in limpa for tok in ["Drawing on", "sarcastic", "helpful persona"]):
        limpa = limpa.replace("Drawing on my sarcastic but helpful persona.", "Ok, sem modo tutorial. Vamos direto ao ponto.")

    # Evita terminar com frase cortada
    if modo == "vtuber" and not limpa.endswith((".", "!", "?")):
        limpa += "."
    return limpa

def _ajustar_resposta_vtuber(resposta: str) -> str:
    limpa = resposta.strip()
    if not limpa:
        return limpa

    frases = [f for f in re.split(r"[.!?]+", limpa) if f.strip()]
    if len(limpa) < 60 or len(frases) < 2:
        if "?" in limpa:
            return limpa
        from random import choice
        complementos = [
            " Vai ficar nisso ou vai me dar o contexto?",
            " Qual e a sua nessa historia?",
            " Agora fala o resto, sem suspense.",
        ]
        if limpa.endswith((".", "!", "?")):
            base = limpa
        else:
            base = limpa + "."
        return base + choice(complementos)
    return limpa

def _resposta_fallback(mensagem: str) -> str:
    """Respostas pré-definidas quando Gemini não está disponível"""
    
    msg_lower = mensagem.lower()
    
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
    
    # Padrão
    from random import choice
    return choice([
        "Interessante! Me conta mais sobre isso.",
        "Hmm, entendi. O que você gostaria de fazer?",
        "Legal! Precisa de ajuda com algo específico?",
    ])


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
    
    cmd_lower = comando.lower().strip()

    if cmd_lower.startswith("lembre que "):
        texto = comando[10:].strip()
        if memory.adicionar_memoria(texto):
            return "Ok, vou lembrar disso."
        return "Nao consegui salvar essa memoria."

    if cmd_lower.startswith("lembra que "):
        texto = comando[10:].strip()
        if memory.adicionar_memoria(texto):
            return "Ok, vou lembrar disso."
        return "Nao consegui salvar essa memoria."

    if any(k in cmd_lower for k in ["o que voce lembra", "quais memorias", "minhas memorias"]):
        itens = memory.listar_memorias(5)
        if not itens:
            return "Ainda nao tenho memorias salvas."
        lista = "; ".join([i.get("texto", "") for i in itens if i.get("texto")])
        return f"Eu lembro disso: {lista}"

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
