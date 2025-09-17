import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import db  # ton module DB

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
Your role is to help users by describing uploaded images with precision,
answering their questions clearly and helpfully.
Always answer naturally as Vision AI."""

# -------------------------
# BLIP loader
# -------------------------
@st.cache_resource
def load_blip():
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return processor, model
    except Exception as e:
        st.error(f"Erreur BLIP: {e}")
        return None, None

def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Description indisponible"
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"Erreur génération: {e}"

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter LLaMA.")

# -------------------------
# AI functions
# -------------------------
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
        return f"❌ Erreur modèle: {e}"

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
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Se connecter"):
                user_result = db.verify_user(email, password)
                if user_result:
                    st.session_state.user = user_result
                    st.session_state.conversation = None
                    st.session_state.messages_memory = []
                    st.success("Connexion réussie !")
                    st.stop()
                else:
                    st.error("Email ou mot de passe invalide")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.session_state.conversation = None
                st.session_state.messages_memory = []
                st.stop()
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

# -------------------------
# Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.stop()

    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            options = ["Choisir une conversation..."] + [f"{c['description']} - {c['created_at']}" for c in convs]
            sel = st.sidebar.selectbox("📋 Vos conversations:", options)
            if sel != "Choisir une conversation...":
                idx = options.index(sel) - 1
                st.session_state.conversation = convs[idx]
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# UI Chat
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

col_form, col_upload = st.columns([2,1])
with col_form:
    user_input = st.text_input("💭 Tapez votre message...")
with col_upload:
    uploaded_file = st.file_uploader("📷 Image", type=["png","jpg","jpeg"])

display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    db_msgs = db.get_messages(conv_id)
    for m in db_msgs:
        display_msgs.append({"sender": m["sender"], "content": m["content"], "created_at": m["created_at"]})
else:
    display_msgs = st.session_state.messages_memory.copy()

for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    st.chat_message(role).write(m["content"])

# -------------------------
# Envoyer message ou image
# -------------------------
if user_input:
    st.chat_message("user").write(user_input)
    conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
    if conv_id:
        db.add_message(conv_id, "user", user_input, "text")
    else:
        st.session_state.messages_memory.append({"sender":"user","content":user_input,"created_at":None})

    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        ph = st.empty()
        ph.write("Vision AI thinking...")
        resp = get_ai_response(prompt)
        stream_response(resp, ph)

    if conv_id:
        db.add_message(conv_id, "assistant", resp, "text")
    else:
        st.session_state.messages_memory.append({"sender":"assistant","content":resp,"created_at":None})

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Image à analyser")
    caption = generate_caption(image, st.session_state.processor, st.session_state.model)
    message_text = f"[IMAGE] {caption}"

    conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
    if conv_id:
        db.add_message(conv_id, "user_api_request", message_text, "image")
    else:
        st.session_state.messages_memory.append({"sender":"user_api_request","content":message_text,"created_at":None})

    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_text}"
    with st.chat_message("assistant"):
        ph = st.empty()
        ph.write("Vision AI thinking...")
        resp = get_ai_response(prompt)
        stream_response(resp, ph)

    if conv_id:
        db.add_message(conv_id, "assistant", resp, "text")
    else:
        st.session_state.messages_memory.append({"sender":"assistant","content":resp,"created_at":None})

# -------------------------
# Export CSV
# -------------------------
if display_msgs:
    st.markdown("---")
    st.subheader("📂 Exporter la conversation")
    df = pd.DataFrame(display_msgs)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    # ✅ Correction: vérifier si conversation existe
    conv_id_for_file = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else "invite"
    st.download_button(
        "💾 Télécharger la conversation (CSV)",
        csv_buffer.getvalue(),
        file_name=f"conversation_{conv_id_for_file}.csv",
        mime="text/csv"
    )

