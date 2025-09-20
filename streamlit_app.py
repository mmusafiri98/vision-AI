import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB Supabase

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
# Utility functions
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

def load_last_conversation(user_id):
    if user_id != "guest":
        convs = db.get_conversations(user_id)
        if convs:
            return convs[0]
    return None

def save_active_conversation(user_id, conv_id):
    """Placeholder si besoin de stocker active conv"""
    pass

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
# Initialisation session
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
    except:
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
    full_text = ""
    thinking_msgs = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_msgs:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.2)
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "**█**")
        time.sleep(0.01 if char==' ' else 0.03)
    placeholder.markdown(full_text + " ✅")

# -------------------------
# Authentification
# -------------------------
st.sidebar.title("🔐 Authentification")

def login_ui():
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
                    st.session_state.conversation_loaded = False
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

if st.session_state.user["id"] == "guest":
    login_ui()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# Chargement dernière conversation et messages
# -------------------------
if st.session_state.user["id"] != "guest" and not st.session_state.conversation_loaded:
    last_conv = load_last_conversation(st.session_state.user["id"])
    if last_conv:
        st.session_state.conversation = last_conv
        conv_id = last_conv.get("id") or last_conv.get("conversation_id")
        st.session_state.messages_memory = db.get_messages(conv_id) or []
    st.session_state.conversation_loaded = True

# -------------------------
# Sidebar conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.rerun()
    convs = db.get_conversations(st.session_state.user["id"]) or []
    if convs:
        options = ["Choisir une conversation..."] + [f"{c['description']} - {c['created_at']}" for c in convs]
        sel = st.sidebar.selectbox("Vos conversations:", options)
        if sel != "Choisir une conversation...":
            idx = options.index(sel)-1
            selected_conv = convs[idx]
            if st.session_state.conversation != selected_conv:
                st.session_state.conversation = selected_conv
                conv_id = selected_conv.get("id") or selected_conv.get("conversation_id")
                st.session_state.messages_memory = db.get_messages(conv_id) or []
                st.rerun()

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)
if st.session_state.conversation:
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {st.session_state.conversation.get('description','Conversation sans titre')}</p>", unsafe_allow_html=True)

# -------------------------
# Affichage messages
# -------------------------
message_container = st.container()
for m in st.session_state.messages_memory:
    role = "user" if m["sender"]=="user" else "assistant"
    with message_container:
        with st.chat_message(role):
            if m.get("type")=="image" and m.get("image_data"):
                st.image(base64_to_image(m["image_data"]), width=300)
            st.markdown(m["content"])

# -------------------------
# Formulaire message
# -------------------------
with st.form(key="chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"])
    user_input = st.text_area("💭 Tapez votre message...", height=80)
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

if submit_button and (user_input.strip() or uploaded_file):
    conv_id = st.session_state.conversation.get("id") if st.session_state.conversation else None
    full_message = user_input.strip()
    image_base64 = None
    msg_type = "text"

    if uploaded_file:
        image = Image.open(uploaded_file)
        image_base64 = image_to_base64(image)
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        full_message = f"[IMAGE] {caption}"
        if user_input.strip():
            full_message += f"\n\nQuestion: {user_input}"
        msg_type = "image"

    if conv_id:
        db.add_message(conv_id, "user", full_message, msg_type, image_data=image_base64)

    st.session_state.messages_memory.append({
        "sender":"user","content":full_message,"type":msg_type,"image_data":image_base64
    })

    with message_container:
        with st.chat_message("user"):
            if msg_type=="image" and image_base64:
                st.image(base64_to_image(image_base64), width=300)
            st.markdown(full_message if msg_type=="text" else "")

    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
    with message_container:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.write("Vision AI réfléchit... 🤔")
            resp = get_ai_response(prompt)
            stream_response(resp, placeholder)

    if conv_id:
        db.add_message(conv_id, "assistant", resp, "text")

    st.session_state.messages_memory.append({
        "sender":"assistant","content":resp,"type":"text"
    })
    st.rerun()


