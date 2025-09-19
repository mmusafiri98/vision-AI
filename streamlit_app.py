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
# Utilitaires image
# -------------------------
def image_to_base64(image: Image.Image) -> str:
    try:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return img_str
    except Exception:
        return None

def base64_to_image(img_str: str) -> Image.Image:
    try:
        img_bytes = base64.b64decode(img_str)
        return Image.open(io.BytesIO(img_bytes))
    except Exception:
        return None

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
if "conversation_loaded" not in st.session_state:
    st.session_state.conversation_loaded = False
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter LLaMA.")

# -------------------------
# Fonctions DB + AI
# -------------------------
def load_user_last_conversation(user_id):
    if user_id == "guest" or not user_id:
        return None
    try:
        convs = db.get_conversations(user_id)
        if convs:
            return convs[0]  # la plus récente
    except Exception as e:
        st.error(f"Erreur chargement conversation: {e}")
    return None

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
    text_str = str(text)
    thinking_messages = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_messages:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.3)
    for char in text_str:
        full_text += char
        display_text = full_text + "**█**"
        placeholder.markdown(display_text)
        time.sleep(0.01 if char==' ' else 0.03)
    placeholder.markdown(full_text + " ✅")
    time.sleep(0.2)
    placeholder.markdown(full_text)

# -------------------------
# Authentification
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
                    st.session_state.conversation = load_user_last_conversation(user_result["id"])
                    st.session_state.messages_memory = []
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
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# Auto-chargement conversation
# -------------------------
if st.session_state.user["id"] != "guest" and not st.session_state.conversation_loaded:
    st.session_state.conversation = load_user_last_conversation(st.session_state.user["id"])
    st.session_state.conversation_loaded = True

# -------------------------
# Conversations côté sidebar
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.rerun()
    convs = db.get_conversations(st.session_state.user["id"])
    if convs:
        current_conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
        options = ["Choisir une conversation..."] + [f"{c['description']} - {c['created_at']}" + (" (Actuelle)" if c['conversation_id']==current_conv_id else "") for c in convs]
        sel = st.sidebar.selectbox("Vos conversations:", options)
        if sel != "Choisir une conversation..." and not sel.endswith(" (Actuelle)"):
            idx = options.index(sel)-1
            selected_conv = convs[idx]
            st.session_state.conversation = selected_conv
            st.session_state.messages_memory = []
            st.rerun()

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)
if st.session_state.conversation:
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {st.session_state.conversation.get('description', 'Sans titre')}</p>", unsafe_allow_html=True)

# -------------------------
# Affichage messages
# -------------------------
display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    db_msgs = db.get_messages(conv_id)
    if db_msgs:
        for m in db_msgs:
            display_msgs.append({
                "sender": m["sender"],
                "content": m["content"],
                "created_at": m["created_at"],
                "type": m.get("message_type","text"),
                "image_data": m.get("image_data")
            })
else:
    display_msgs = st.session_state.messages_memory.copy()

for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        if m.get("type") == "image":
            if m.get("image_data"):
                img = base64_to_image(m["image_data"])
                if img: st.image(img, caption="Image analysée", width=300)
            st.write(m["content"])
        else:
            st.markdown(m["content"])

# -------------------------
# Formulaire envoi messages
# -------------------------
message_container = st.container()
with st.form("chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"])
    user_input = st.text_area("💭 Tapez votre message...", height=80)
    submit_button = st.form_submit_button("📤 Envoyer")

if submit_button and (user_input or uploaded_file):
    conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
    if not conv_id and st.session_state.user["id"] != "guest":
        # Création automatique si nécessaire
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        conv_id = conv.get("conversation_id")
    
    full_message = ""
    image_base64 = None
    image_caption = ""

    if uploaded_file:
        image = Image.open(uploaded_file)
        image_base64 = image_to_base64(image)
        with message_container:
            with st.chat_message("user"):
                st.image(image, caption="Image uploadée", width=300)
        image_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        full_message = f"[IMAGE] {image_caption}"
        if user_input.strip():
            full_message += f"\n\nQuestion/Demande: {user_input}"
            with message_container:
                with st.chat_message("user"):
                    st.write(f"**Question:** {user_input}")
        if conv_id:
            db.add_message(conv_id, "user", full_message, "image", image_data=image_base64)
        else:
            st.session_state.messages_memory.append({
                "sender":"user","content":full_message,"created_at":None,"type":"image","image_data":image_base64
            })
    elif user_input.strip():
        full_message = user_input
        with message_container:
            with st.chat_message("user"):
                st.markdown(user_input)
        if conv_id:
            db.add_message(conv_id, "user", full_message, "text")
        else:
            st.session_state.messages_memory.append({
                "sender":"user","content":full_message,"created_at":None,"type":"text"
            })
    
    # Réponse AI
    if full_message:
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
        with message_container:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                resp = get_ai_response(prompt)
                stream_response(resp, placeholder)
        if conv_id:
            db.add_message(conv_id, "assistant", resp, "text")
        else:
            st.session_state.messages_memory.append({
                "sender":"assistant","content":resp,"created_at":None,"type":"text"
            })
        st.rerun()
