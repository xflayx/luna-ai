import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import streamlit as st
from config.state import SKILLS_STATE
from core.intent import detectar_intencao
from core.router import processar_comando
from skills.vision import listar_janelas, analisar_visao_streamlit
import mss

st.set_page_config(page_title="LUNA Assistant", layout="wide")
st.title("🤖 LUNA – Assistente IA Modular")

# ===============================
# SIDEBAR – SKILLS
# ===============================
st.sidebar.header("⚙️ Skills Ativas")

for skill in SKILLS_STATE:
    SKILLS_STATE[skill] = st.sidebar.checkbox(skill.upper(), value=SKILLS_STATE[skill])

# ===============================
# VISÃO AVANÇADA
# ===============================
st.sidebar.header("👁️ Visão Avançada")

modo_visao = st.sidebar.selectbox(
    "Fonte da Visão",
    ["Tela inteira", "Monitor", "Janela"]
)

monitor_index = None
janela_hwnd = None

if modo_visao == "Monitor":
    with mss.mss() as sct:
        monitor_index = st.sidebar.selectbox(
            "Selecionar Monitor",
            list(range(1, len(sct.monitors)))
        )

if modo_visao == "Janela":
    if st.sidebar.button("🔄 Atualizar Janelas"):
        st.session_state.janelas = listar_janelas()

    janelas = st.session_state.get("janelas", listar_janelas())
    escolha = st.sidebar.selectbox(
        "Selecionar Janela",
        janelas,
        format_func=lambda x: x["titulo"]
    )
    janela_hwnd = escolha["hwnd"]

# ===============================
# CHAT
# ===============================
if "chat" not in st.session_state:
    st.session_state.chat = []

st.subheader("💬 Chat com a Luna")

entrada = st.text_input("Digite um comando")

if st.button("Enviar") and entrada:
    intent = detectar_intencao(entrada.lower())

    if intent == "visao":
        if modo_visao == "Janela":
            resposta, img = analisar_visao_streamlit(
                entrada, "janela", janela_hwnd
            )
        elif modo_visao == "Monitor":
            resposta, img = analisar_visao_streamlit(
                entrada, "monitor", monitor_index
            )
        else:
            resposta, img = analisar_visao_streamlit(
                entrada, "tela"
            )

        if img:
            st.image(img, caption="Imagem analisada", width=st.get_option("server.maxUploadSize") or 800)


    else:
        resposta = processar_comando(entrada.lower(), intent)

    st.session_state.chat.append(("Você", entrada))
    st.session_state.chat.append(("Luna", resposta))

# ===============================
# HISTÓRICO
# ===============================
st.markdown("---")
for autor, msg in st.session_state.chat:
    st.markdown(f"**{autor}:** {msg}")
