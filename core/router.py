# core/router.py
from config.state import SKILLS_STATE, STATE
from skills.macros import (
    iniciar_gravacao_sequencia, parar_gravacao_sequencia, 
    finalizar_salvamento, preparar_execucao, executar_com_loop
)
from skills.vision import analisar_tela
from skills.price import responder_preco
from core.opinion_engine import gerar_opiniao

def processar_comando(cmd, intent):
    comando_bruto = cmd.lower().strip()

    # --- 1. PRIORIDADE: ESTADOS DE ESPERA (Respostas diretas) ---
    if STATE.esperando_nome_sequencia:
        nome_final = comando_bruto.replace("luna", "").strip()
        return finalizar_salvamento(nome_final)

    if STATE.esperando_nome_execucao:
        nome_final = comando_bruto.replace("luna", "").strip()
        STATE.esperando_nome_execucao = False
        return preparar_execucao(nome_final)

    if STATE.esperando_loops:
        return executar_com_loop(comando_bruto)

    # --- 2. FILTRO DE ATIVAÇÃO "LUNA" ---
    if not comando_bruto.startswith("luna"):
        return None

    comando_limpo = comando_bruto.replace("luna", "", 1).strip()
    resposta = None

    # --- 3. ROTEAMENTO DE SKILLS ---

    # SEQUÊNCIAS (MACROS)
    if intent == "sequencia":
        if "gravar" in comando_limpo:
            resposta = iniciar_gravacao_sequencia()
        elif any(p in comando_limpo for p in ["parar", "pare"]):
            resposta = parar_gravacao_sequencia()
        elif "executar" in comando_limpo or "sequencia" in comando_limpo or "sequência" in comando_limpo:
            nome = comando_limpo.replace("executar", "").replace("sequencia", "").replace("sequência", "").strip()
            if not nome:
                STATE.esperando_nome_execucao = True
                return "Qual o nome da sequência que você deseja executar?"
            resposta = preparar_execucao(nome)

    # VISÃO
    elif intent == "visao" and SKILLS_STATE["vision"]:
        resposta = analisar_tela(comando_limpo)

    # PREÇO
    elif intent == "preco" and SKILLS_STATE["price"]:
        resposta = responder_preco(comando_limpo)
    
    # CONVERSA
    elif intent == "conversa":
        if not comando_limpo: return "Sim? Estou ouvindo."
        resposta = gerar_opiniao(comando_limpo)

    if resposta:
        STATE.adicionar_ao_historico(comando_limpo, resposta)
        return resposta
    
    return None