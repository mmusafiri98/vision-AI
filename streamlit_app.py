import streamlit as st
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from gradio_client import Client
import time
import db
import io
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = "You are Vision AI. Answer clearly and describe uploaded images with precision."

# -------------------------
# BLIP model loader
# -------------------------
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

if "processor" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# -------------------------
# LLaMA Client
# -------------------------
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        st.session_state.llama_client = None

def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible."
    try:
        return str(st.session_state.llama_client.predict(message=query, max_tokens=8192, temperature=0.7, top_p=0.95, api_name="/chat"))
    except Exception as e:
        return f"❌ Erreur: {e}"

def stream_response(text, placeholder):
    full = ""
    for ch in str(text):
        full += ch
        placeholder.write(full + "▋")
        time.sleep(0.01)
    placeholder.write(full)

# -------------------------
# Auth
# -------------------------
st.sidebar.title("🔐 Auth")
if st.session_state.user["id"] == "guest":
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        user_result = db.verify_user(email, password)
        if user_result:
            st.session_state.user = user_result
            st.experimental_rerun()
        else:
            st.sidebar.error("Email ou mot de passe invalide")

# -------------------------
# Sidebar: Nouvelle conversation
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Conversations")
    if st.sidebar.button("Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"])
        st.session_state.conversation = conv
        st.experimental_rerun()

    convs = db.get_conversations(st.session_state.user["id"])
    if convs:
        sel = st.sidebar.selectbox("Vos conversations:", [c["conversation_id"] for c in convs])
        st.session_state.conversation = next((c for c in convs if c["conversation_id"] == sel), None)

# -------------------------
# Main UI: chat
# -------------------------
st.title("🤖 Vision AI Chat")
if st.session_state.user:
    st.write(f"Connecté en tant que: {st.session_state.user.get('email')}")

display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation["conversation_id"]
    db_msgs = db.get_messages(conv_id)
    for m in db_msgs:
        display_msgs.append({"sender": m["sender"], "content": m["content"], "created_at": m["created_at"]})
else:
    display_msgs = st.session_state.messages_memory

for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    st.chat_message(role).write(m["content"])

# -------------------------
# User input
# -------------------------
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    st.chat_message("user").write(user_input)
    conv_id = st.session_state.conversation["conversation_id"] if st.session_state.conversation else None
    if conv_id:
        db.add_message(conv_id, "user", user_input)
    else:
        st.session_state.messages_memory.append({"sender":"user","content":user_input,"created_at":datetime.now().isoformat()})

    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        ph = st.empty()
        resp = get_ai_response(prompt)
        stream_response(resp, ph)
        if conv_id:
            db.add_message(conv_id, "assistant", resp)
        else:
            st.session_state.messages_memory.append({"sender":"assistant","content":resp,"created_at":datetime.now().isoformat()})

# -------------------------
# Export CSV
# -------------------------
if display_msgs and st.session_state.conversation:
    df = pd.DataFrame(display_msgs)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button("💾 Télécharger la conversation (CSV)", csv_buffer.getvalue(), file_name=f"conversation_{conv_id}.csv")

