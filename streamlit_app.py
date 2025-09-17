import os
import uuid
import time
import io
import pandas as pd
import streamlit as st
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from gradio_client import Client
import db  # module db.py que tu as déjà

# -------------------------
# CONFIGURATION PAGE
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")

SYSTEM_PROMPT = """You are Vision AI.
Your role is to help users by describing uploaded images with precision,
answering their questions clearly and helpfully.
Always answer naturally as Vision AI."""

# -------------------------
# SESSION INIT
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# -------------------------
# BLIP MODEL
# -------------------------
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model = model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

# -------------------------
# LLaMA / Gradio client
# -------------------------
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter le modèle LLaMA (Gradio client).")

def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible."
    try:
        resp = st.session_state.llama_client.predict(
            message=query,
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"❌ Erreur appel modèle: {e}"

def stream_response(text, placeholder):
    full = ""
    for ch in str(text):
        full += ch
        placeholder.write(full + "▋")
        time.sleep(0.01)
    placeholder.write(full)

# -------------------------
# SIDEBAR AUTH
# -------------------------
st.sidebar.title("🔐 Authentification")
user = st.session_state.user
logged_in = user.get("id") != "guest"

if not logged_in:
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email", key="login_email")
        password = st.text_input("🔒 Mot de passe", type="password", key="login_password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Se connecter"):
                if email and password:
                    user_result = db.verify_user(email, password)
                    if user_result:
                        st.session_state.user = user_result
                        st.session_state.conversation = None
                        st.session_state.messages_memory = []
                        st.experimental_rerun()
                    else:
                        st.error("Email ou mot de passe invalide")
                else:
                    st.error("Merci de remplir tous les champs")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.experimental_rerun()
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        if st.button("✨ Créer mon compte"):
            if email_reg and name_reg and pass_reg:
                ok = db.create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Compte créé, connecte-toi.")
                else:
                    st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

# -------------------------
# Sidebar: Conversations
# -------------------------
st.sidebar.title("💬 Mes Conversations")
if st.sidebar.button("➕ Nouvelle conversation"):
    conv = db.create_conversation(st.session_state.user["id"])
    st.session_state.conversation = conv
    st.experimental_rerun()

try:
    convs = db.get_conversations(st.session_state.user.get("id"))
    options = ["Choisir une conversation..."] + [f"{c['description']} - {c['created_at'][:16]}" for c in convs]
    sel = st.sidebar.selectbox("📋 Vos conversations:", options)
    if sel != "Choisir une conversation...":
        idx = options.index(sel) - 1
        st.session_state.conversation = convs[idx]
except Exception as e:
    st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# Sidebar: Image Upload
# -------------------------
st.sidebar.markdown("---")
st.sidebar.title("📷 Analyser une image")
uploaded_file = st.sidebar.file_uploader("Choisissez une image", type=["png","jpg","jpeg"])
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.sidebar.image(image, caption="Image à analyser", use_column_width=True)
    if st.sidebar.button("🔍 Analyser l'image"):
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        message_text = f"[IMAGE] {caption}"
        conv_id = st.session_state.conversation.get("conversation_id")
        db.add_message(conv_id, "user_api_request", message_text, message_type="image")
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_text}"
        with st.chat_message("assistant"):
            ph = st.empty()
            resp = get_ai_response(prompt)
            stream_response(resp, ph)
        db.add_message(conv_id, "assistant", resp)

# -------------------------
# Main Chat
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

display_msgs = []
conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
if conv_id:
    display_msgs = db.get_messages(conv_id)
else:
    display_msgs = st.session_state.messages_memory.copy()

if not display_msgs:
    st.chat_message("assistant").write("👋 Bonjour ! Je suis Vision AI. Comment puis-je vous aider ?")
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    st.chat_message(role).write(m["content"])

# -------------------------
# Export CSV
# -------------------------
if display_msgs:
    st.markdown("---")
    st.subheader("📂 Exporter la conversation")
    df = pd.DataFrame(display_msgs)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="💾 Télécharger la conversation (CSV)",
        data=csv_buffer.getvalue(),
        file_name=f"conversation_{conv_id}.csv" if conv_id else "conversation_invite.csv",
        mime="text/csv"
    )

# -------------------------
# User Input
# -------------------------
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    st.chat_message("user").write(user_input)
    if conv_id:
        db.add_message(conv_id, "user", user_input)
    else:
        st.session_state.messages_memory.append({"sender":"user","content":user_input,"created_at":None})
    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        ph = st.empty()
        resp = get_ai_response(prompt)
        stream_response(resp, ph)
    if conv_id:
        db.add_message(conv_id, "assistant", resp)
    else:
        st.session_state.messages_memory.append({"sender":"assistant","content":resp,"created_at":None})


