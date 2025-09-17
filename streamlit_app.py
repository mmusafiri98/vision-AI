import os
import time
import streamlit as st
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from gradio_client import Client
import db  # ton fichier db.py avec toutes les fonctions

# =======================
# CONFIG STREAMLIT
# =======================
st.set_page_config(page_title="Vision AI Chat", layout="wide")

SYSTEM_PROMPT = """
You are Vision AI.
Your role is to help users by describing uploaded images with precision,
answering their questions clearly and helpfully.
Always answer naturally as Vision AI.
"""

# =======================
# CHARGEMENT DU MODELE BLIP
# =======================
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Description indisponible"
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model = model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

# =======================
# INITIALISATION SESSION
# =======================
if "user" not in st.session_state:
    st.session_state.user = None
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# =======================
# CLIENT LLaMA (Gradio)
# =======================
if "llama_client" not in st.session_state:
    try:
        with st.spinner("🔄 Connexion à Vision AI..."):
            st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
        st.success("✅ Vision AI connecté !")
    except Exception as e:
        st.error(f"Erreur connexion Vision AI: {e}")
        st.session_state.llama_client = None

def get_ai_response(query):
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible"
    with st.spinner("🤖 Vision AI réfléchit..."):
        response = st.session_state.llama_client.predict(
            message=query,
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
    return str(response)

def stream_response(text, placeholder):
    full_text = ""
    for char in text:
        full_text += char
        placeholder.write(full_text + "▋")
        time.sleep(0.03)
    placeholder.write(full_text)

# =======================
# AUTHENTIFICATION
# =======================
st.sidebar.title("🔐 Authentification")

user = st.session_state.user
is_logged_in = user is not None and isinstance(user, dict) and "id" in user

if not is_logged_in:
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
                        st.success(f"✅ Bienvenue {user_result['email']} !")
                        st.experimental_rerun()
                    else:
                        st.error("❌ Email ou mot de passe invalide")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"email": "invité", "id": "guest"}
                st.success("✅ Mode invité activé")
                st.experimental_rerun()
    
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        if st.button("✨ Créer mon compte"):
            if email_reg and name_reg and pass_reg:
                created = db.create_user(email_reg, pass_reg, name_reg)
                if created:
                    st.success("✅ Compte créé ! Vous pouvez vous connecter.")
                else:
                    st.error("❌ Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user['email']}")
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = None
        st.session_state.conversation = None
        st.experimental_rerun()

# =======================
# GESTION CONVERSATIONS
# =======================
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            st.success("✅ Nouvelle conversation créée !")
            st.experimental_rerun()
    conversations = db.get_conversations(st.session_state.user["id"])
    if conversations:
        options = ["Choisir une conversation..."] + [
            f"{c['description']} - {c['created_at'].strftime('%d/%m %H:%M')}" for c in conversations
        ]
        selected = st.sidebar.selectbox("📋 Vos conversations:", options)
        if selected != "Choisir une conversation...":
            idx = options.index(selected) - 1
            st.session_state.conversation = conversations[idx]

# =======================
# INTERFACE PRINCIPALE
# =======================
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
if is_logged_in:
    st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user['email']}</b></p>", unsafe_allow_html=True)

# =======================
# UPLOAD IMAGE
# =======================
with st.sidebar:
    st.markdown("---")
    st.title("📷 Analyser une image")
    uploaded_file = st.file_uploader("Choisissez une image", type=['png', 'jpg', 'jpeg'])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Image à analyser", use_column_width=True)
        if st.button("🔍 Analyser cette image"):
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            image_message = f"[IMAGE] Analyse: {caption}"
            if st.session_state.conversation:
                db.add_message(st.session_state.conversation["conversation_id"], "user", image_message)
            else:
                st.session_state.messages_memory.append({"role": "user", "content": image_message})
            enhanced_query = f"{SYSTEM_PROMPT}\n\nUtilisateur: {image_message}"
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response = get_ai_response(enhanced_query)
                stream_response(response, response_placeholder)
            if st.session_state.conversation:
                db.add_message(st.session_state.conversation["conversation_id"], "assistant", response)
            else:
                st.session_state.messages_memory.append({"role": "assistant", "content": response})
            st.experimental_rerun()

# =======================
# AFFICHAGE MESSAGES
# =======================
chat_container = st.container()
with chat_container:
    messages = []
    if st.session_state.conversation:
        messages = db.get_messages(st.session_state.conversation["conversation_id"])
    else:
        messages = st.session_state.messages_memory
    if not messages:
        st.chat_message("assistant").write("👋 Bonjour ! Je suis Vision AI. Comment puis-je vous aider ?")
    for msg in messages:
        role = "user" if msg["sender"] in ["user", "user_api_request"] else "assistant"
        st.chat_message(role).write(msg["content"])

# =======================
# INPUT UTILISATEUR
# =======================
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    st.chat_message("user").write(user_input)
    if st.session_state.conversation:
        db.add_message(st.session_state.conversation["conversation_id"], "user", user_input)
    else:
        st.session_state.messages_memory.append({"role": "user", "content": user_input})
    enhanced_query = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response = get_ai_response(enhanced_query)
        stream_response(response, response_placeholder)
    if st.session_state.conversation:
        db.add_message(st.session_state.conversation["conversation_id"], "assistant", response)
    else:
        st.session_state.messages_memory.append({"role": "assistant", "content": response})
    st.experimental_rerun()

# =======================
# FOOTER
# =======================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 0.8em;'>"
    f"Vision AI Chat | Créé par Pepe Musafiri"
    "</div>",
    unsafe_allow_html=True
)

