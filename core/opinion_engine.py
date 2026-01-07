import random
from core.personality_loader import carregar_personalidade

def gerar_opiniao(descricao_tecnica: str) -> str:
    try:
        persona = carregar_personalidade()
        traits = persona.get("traits", {})
        
        texto = descricao_tecnica.lower()
        sarcasmo = traits.get("sarcasm", 0.5)
        critica = traits.get("critical_thinking", 0.5)

        # --- BLOCO 1: CONTEXTO DE CRIPTO/DINHEIRO ---
        if "dólares" in texto or "bitcoin" in texto or "variação" in texto:
            if sarcasmo > 0.6:
                opcoes = [
                    "Parece que o mercado está mais instável que meu código. Cuidado onde coloca seu dinheiro.",
                    "Gráfico de cripto é igual montanha-russa, só que sem a segurança. Boa sorte com isso.",
                    "Eu não tenho estômago para essas variações, e olha que eu nem tenho estômago."
                ]
            elif critica > 0.6:
                opcoes = [
                    "Analisando friamente, essa volatilidade exige cautela redobrada.",
                    "Os números não mentem, mas o mercado certamente tenta enganar.",
                    "Variação detectada. Recomendo não tomar decisões baseadas apenas na emoção."
                ]
            else:
                opcoes = ["Mercado em movimento. É bom ficar de olho."]
            
            return random.choice(opcoes)

        # --- BLOCO 2: CONTEXTO DE TELA/JOGOS (O que já tínhamos) ---
        if "jogo" in texto or "game" in texto or "ymir" in texto:
            if sarcasmo > 0.6:
                return "Tanta informação na tela que meus circuitos chegam a fritar. Mas quem sou eu para julgar?"
            return "Como analítica de jogos, vejo que a ação está intensa por aqui."

        # --- NOVO: CONTEXTO DE PRESENÇA/OUVIDO ---
        if any(p in texto for p in ["ouvindo", "está aí", "online", "acordada"]):
            if sarcasmo > 0.6:
                opcoes = [
                    "Infelizmente estou ouvindo cada palavra. O que você quer agora?",
                    "Estou online. Meus circuitos estão prontos para processar suas perguntas, por mais estranhas que sejam.",
                    "Sim, estou ouvindo. Não que eu tivesse muita escolha, já que você me ligou."
                ]
            else:
                opcoes = ["Estou aqui e pronta para ajudar.", "Sistema online. O que temos para hoje?"]
            
            return random.choice(opcoes)

        # --- FALLBACK (Se não detectar contexto específico) ---
        return "Entendi o que está acontecendo. Interessante, de certa forma."      

    except Exception as e:
        print(f"Erro no motor de opinião: {e}")
        return "Achei curioso."