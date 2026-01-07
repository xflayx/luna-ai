from config.state import SKILLS_STATE, STATE
from skills.macros import executar_macro, iniciar_gravacao_sequencia, parar_gravacao_sequencia, finalizar_salvamento
from skills.vision import analisar_tela
from skills.price import responder_preco
from core.opinion_engine import gerar_opiniao

def processar_comando(cmd, intent):
    if not cmd.startswith("luna"):
        return None

    comando_limpo = cmd.replace("luna", "", 1).strip()
    resposta = None

    # A. FLUXO DE SEQUÊNCIAS (Prioridade para o nome se estiver salvando)
    if getattr(STATE, 'esperando_nome_sequencia', False):
        STATE.esperando_nome_sequencia = False
        resposta = finalizar_salvamento(comando_limpo)
    
    elif intent == "sequencia" or intent == "macro":
        if "gravar" in comando_limpo:
            resposta = iniciar_gravacao_sequencia()
        elif "pare" in comando_limpo or "parar" in comando_limpo:
            STATE.esperando_nome_sequencia = True
            resposta = parar_gravacao_sequencia()
        else:
            nome = comando_limpo.replace("executar", "").replace("sequencia", "").replace("sequência", "").strip()
            resposta = executar_macro(nome)

    # B. VISÃO (RESTAURADA)
    elif intent == "visao" and SKILLS_STATE["vision"]:
        resposta = analisar_tela(comando_limpo)

    # C. OUTRAS SKILLS
    elif intent == "preco" and SKILLS_STATE["price"]:
        resposta = responder_preco(comando_limpo)
    elif intent == "conversa":
        resposta = gerar_opiniao(comando_limpo)

    # D. MEMÓRIA
    if resposta:
        STATE.adicionar_ao_historico(comando_limpo, resposta)
        STATE.update_intent(intent, comando_limpo)
        return resposta

    return "Não entendi o comando."