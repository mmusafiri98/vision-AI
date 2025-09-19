import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
You were created by Pepe Musafiri, an Artificial Intelligence Engineer,
with contributions from Meta AI.
Your role is to help users with any task they need, from image analysis
and editing to answering questions clearly and helpfully.
Always answer naturally as Vision AI.

When you receive an image description starting with [IMAGE], you should:
1. Acknowledge that you can see and analyze the image
2. Provide detailed analysis of what you observe
3. Answer any specific questions about the image
4. Be helpful and descriptive in your analysis"""

# -------------------------
# Utilitaires
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    return Image.open(io.BytesIO(base64.b64decode(img_str)))

def load_user_last_conversation(user_id):
    if user_id != "guest":
        convs = db.get_conversations(user_id)
        if convs:
            return convs[0]
    return None

def load_conversation_messages(conv_id):
    """Charge les messages depuis la DB et retourne une liste pour session_state"""
    db_msgs = db.get_messages(conv_id) or []
    mem_msgs = []
    for m in db_msgs:
        mem_msgs.append({
            "sender": m["sender"],
            "content": m["content"],
            "created_at": m.get("created_at"),
            "type": m.get("type", "text"),
            "image_data": m.get("image_data")
        })
    return mem_msgs

# -------------------------
# BLIP loader
# -------------------------
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model = model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "conversation_loaded" not in st.session_state:
    st.session_state.conversation_loaded = False
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None

# -------------------------
# Auth
# -------------------------
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    email = st.text_input("📧 Email")
    password = st.text_input("🔒 Mot de passe", type="password")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚪 Se connecter"):
            user_result = db.verify_user(email, password)
            if user_result:
                st.session_state.user = user_result
                last_conv = load_user_last_conversation(user_result["id"])
                st.session_state.conversation = last_conv
                if last_conv:
                    st.session_state.messages_memory = load_conversation_messages(last_conv["conversation_id"])
                st.session_state.conversation_loaded = True
                st.success("Connexion réussie !")
                st.rerun()
            else:
                st.error("Email ou mot de passe invalide")
    with col2:
        if st.button("👤 Mode invité"):
            st.session_state.user = {"id": "guest", "email": "Invité"}
            st.session_state.conversation = None
            st.session_state.messages_memory = []
            st.session_state.conversation_loaded = False
            st.rerun()
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# Charger dernière conversation si pas déjà fait
# -------------------------
if st.session_state.user["id"] != "guest" and not st.session_state.conversation_loaded:
    last_conv = load_user_last_conversation(st.session_state.user["id"])
    if last_conv:
        st.session_state.conversation = last_conv
        st.session_state.messages_memory = load_conversation_messages(last_conv["conversation_id"])
    st.session_state.conversation_loaded = True

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description', 'Conversation sans titre')
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title}</p>", unsafe_allow_html=True)

# -------------------------
# Afficher les messages
# -------------------------
message_container = st.container()
for m in st.session_state.messages_memory:
    role = "user" if m["sender"] == "user" else "assistant"
    with message_container:
        with st.chat_message(role):
            if m.get("type") == "image" and m.get("image_data"):
                img = base64_to_image(m["image_data"])
                st.image(img, caption="Image analysée", width=300)
            st.markdown(m["content"])

# -------------------------
# Formulaire
# -------------------------
with st.form(key="chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image", type=["png","jpg","jpeg"])
    user_input = st.text_area("💭 Tapez votre message...", height=80)
    submit_button = st.form_submit_button("📤 Envoyer")

# -------------------------
# Traitement message
# -------------------------
def add_message(sender, content, type_="text", image_data=None):
    msg = {"sender": sender, "content": content, "created_at": None, "type": type_, "image_data": image_data}
    st.session_state.messages_memory.append(msg)
    conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
    if conv_id:
        db.add_message(conv_id, sender, content, type_, image_data=image_data)

if submit_button and (user_input.strip() or uploaded_file):
    full_message = ""
    image_base64 = None
    # Image
    if uploaded_file:
        image = Image.open(uploaded_file)
        image_base64 = image_to_base64(image)
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        full_message = f"[IMAGE] {caption}"
        if user_input.strip():
            full_message += f"\n\nQuestion/Demande: {user_input}"
    else:
        full_message = user_input

    # Ajouter message utilisateur
    add_message("user", full_message, "image" if uploaded_file else "text", image_data=image_base64)

    # Afficher dans le chat
    with message_container:
        with st.chat_message("user"):
            if uploaded_file:
                st.image(image, caption="Image uploadée", width=300)
            st.markdown(user_input)

    # Générer réponse AI
    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
    resp = get_ai_response(prompt) if st.session_state.llama_client else "❌ Vision AI non disponible."
    add_message("assistant", resp, "text")

    with message_container:
        with st.chat_message("assistant"):
            st.markdown(resp)

    st.rerun()

