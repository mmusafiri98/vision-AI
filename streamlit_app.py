import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import db  # module pour Supabase, messager, utilisateurs

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
Your role is to help users by describing uploaded images with precision,
answering their questions clearly and helpfully.
Always answer naturally as Vision AI.
"""

# -------------------------
# BLIP model loader
# -------------------------
@st.cache_resource
def load_blip():
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return processor, model
    except Exception as e:
        st.error(f"Erreur chargement BLIP: {e}")
        return None, None

def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Description indisponible (erreur BLIP)"
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"Erreur génération description: {e}"

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state or not isinstance(st.session_state.user, dict):
    st.session_state.user = {"id": "guest", "email": "invité"}
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
        st.warning("Impossible de connecter le modèle LLaMA (gradio client).")

# -------------------------
# LLaMA AI
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
        return f"❌ Erreur appel modèle: {e}"

def stream_response(text, placeholder):
    full = ""
    for ch in str(text):
        full += ch
        placeholder.write(full + "▋")
        time.sleep(0.01)
    placeholder.write(full)

# -------------------------
# Sidebar Auth
# -------------------------
st.sidebar.title("🔐 Authentification")
if db and st.session_state.user.get("id") != "guest":
    logged_in = True
else:
    logged_in = False

login_action = None
if not logged_in:
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email", key="login_email")
        password = st.text_input("🔒 Mot de passe", type="password", key="login_password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Se connecter"):
                login_action = "login"
        with col2:
            if st.button("👤 Mode invité"):
                login_action = "guest"

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

# Traitement login ou mode invité après boutons
if login_action:
    if login_action == "login":
        user_result = db.verify_user(email, password)
        if user_result:
            st.session_state.user = user_result
            st.session_state.conversation = None
            st.session_state.messages_memory = []
            st.experimental_rerun()
        else:
            st.error("Email ou mot de passe invalide")
    elif login_action == "guest":
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")

# -------------------------
# Conversations sidebar
# -------------------------
if db and st.session_state.user.get("id") != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            st.experimental_rerun()
    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            options = ["Choisir une conversation..."] + [
                f"{c['description']} - {c['created_at']}" for c in convs
            ]
            sel = st.sidebar.selectbox("📋 Vos conversations:", options)
            if sel != "Choisir une conversation...":
                idx = options.index(sel) - 1
                st.session_state.conversation = convs[idx]
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# Image upload
# -------------------------
with st.sidebar:
    st.markdown("---")
    st.title("📷 Analyser une image")
    uploaded_file = st.file_uploader("Choisissez une image", type=["png","jpg","jpeg"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Image à analyser", use_column_width=True)
        if st.button("🔍 Analyser l'image"):
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            message_text = f"[IMAGE] {caption}"

            conv_id = None
            if db and st.session_state.conversation:
                conv_id = st.session_state.conversation.get("conversation_id")
                db.add_message(conv_id, "user_api_request", message_text, "image")
            else:
                st.session_state.messages_memory.append({"sender":"user_api_request","content":message_text,"created_at":None})

            prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_text}"
            with st.chat_message("assistant"):
                ph = st.empty()
                resp = get_ai_response(prompt)
                stream_response(resp, ph)

            if db and conv_id:
                db.add_message(conv_id, "assistant", resp, "text")
            else:
                st.session_state.messages_memory.append({"sender":"assistant","content":resp,"created_at":None})

# -------------------------
# Chat display
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

display_msgs = []
if db and st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    db_msgs = db.get_messages(conv_id) or []
    for m in db_msgs:
        display_msgs.append({"sender": m.get("sender"), "content": m.get("content"), "created_at": m.get("created_at")})
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
        file_name=f"conversation_{st.session_state.conversation.get('conversation_id','invite')}.csv",
        mime="text/csv"
    )

# -------------------------
# User input
# -------------------------
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    st.chat_message("user").write(user_input)
    conv_id = None
    if db and st.session_state.conversation:
        conv_id = st.session_state.conversation.get("conversation_id")
        db.add_message(conv_id, "user", user_input, "text")
    else:
        st.session_state.messages_memory.append({"sender":"user","content":user_input,"created_at":None})

    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        ph = st.empty()
        resp = get_ai_response(prompt)
        stream_response(resp, ph)

    if db and conv_id:
        db.add_message(conv_id, "assistant", resp, "text")
    else:
        st.session_state.messages_memory.append({"sender":"assistant","content":resp,"created_at":None})


