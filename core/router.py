from config.state import SKILLS_STATE, STATE
from skills.macros import executar_macro
from skills.vision import analisar_tela
from skills.price import responder_preco
from skills.news import buscar_noticias


def processar_comando(cmd, intent):
    if intent == "macro" and SKILLS_STATE["macros"]:
        nome = cmd.replace("luna", "").replace("executar", "").strip()
        return executar_macro(nome)

    if intent == "visao" and SKILLS_STATE["vision"]:
        resultado = analisar_tela(cmd)

        # 🔥 ESSENCIAL: salvar estado
        STATE.update_vision(resultado)
        STATE.update_intent(intent, cmd)

        # 🔥 ESSENCIAL: retornar SOMENTE STRING
        return resultado.get(
            "summary",
            "Não consegui entender o que está na tela."
        )

    if intent == "preco" and SKILLS_STATE["price"]:
        return responder_preco(cmd)

    if intent == "noticia" and SKILLS_STATE["news"]:
        return buscar_noticias(cmd)

    return "Essa função está desativada ou não reconhecida."
