import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB mis à jour avec add_message corrigé

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
    """Convertir une image PIL en base64 pour la stockage"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return img_str
    except:
        return None

def base64_to_image(img_str):
    """Convertir base64 en image PIL"""
    try:
        img_bytes = base64.b64decode(img_str)
        return Image.open(io.BytesIO(img_bytes))
    except:
        return None

def load_user_last_conversation(user_id):
    """Charger la dernière conversation de l'utilisateur"""
    try:
        if user_id != "guest":
            st.write(f"DEBUG load_user_last_conversation: user_id = {user_id}")
            convs = db.get_conversations(user_id)
            st.write(f"DEBUG load_user_last_conversation: conversations récupérées = {convs}")
            if convs and len(convs) > 0:
                st.write(f"DEBUG load_user_last_conversation: Retourne conversation = {convs[0]}")
                return convs[0]
            else:
                st.write("DEBUG load_user_last_conversation: Aucune conversation trouvée")
        else:
            st.write("DEBUG load_user_last_conversation: user_id est guest")
        return None
    except Exception as e:
        st.error(f"Erreur chargement conversation: {e}")
        st.write(f"DEBUG load_user_last_conversation: Exception = {str(e)}")
        return None

def safe_create_conversation(user_id, description):
    """Créer une conversation avec gestion d'erreur"""
    try:
        st.write(f"DEBUG safe_create_conversation: user_id={user_id}, description={description}")
        conv = db.create_conversation(user_id, description)
        st.write(f"DEBUG safe_create_conversation: résultat brut = {conv}")
        if conv is None:
            st.error("Erreur: create_conversation a retourné None")
            return None
        if isinstance(conv, dict):
            return conv
        st.write(f"DEBUG safe_create_conversation: type non-dict détecté: {type(conv)}")
        return None
    except Exception as e:
        st.error(f"Erreur création conversation: {e}")
        st.write(f"DEBUG safe_create_conversation: Exception = {str(e)}")
        return None

def save_active_conversation(user_id, conv_id):
    """Fonction placeholder - pas d'erreur si conv_id est None"""
    if user_id and conv_id:
        st.write(f"DEBUG save_active_conversation: user_id={user_id}, conv_id={conv_id}")
    pass

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
# Session init avec persistance
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
    text_str = str(text)
    thinking_messages = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_messages:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.3)
    for i, char in enumerate(text_str):
        full_text += char
        display_text = full_text + "**█**"
        placeholder.markdown(display_text)
        if char == ' ':
            time.sleep(0.01)
        elif char in '.,!?;:':
            time.sleep(0.1)
        else:
            time.sleep(0.03)
    placeholder.markdown(full_text)
    time.sleep(0.2)
    placeholder.markdown(full_text + " ✅")
    time.sleep(0.5)
    placeholder.markdown(full_text)

# -------------------------
# Auth avec restauration de session
# -------------------------
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Se connecter"):
                st.write(f"DEBUG: Tentative de connexion avec email: {email}")
                user_result = db.verify_user(email, password)
                st.write(f"DEBUG: Résultat verify_user: {user_result}")
                if user_result:
                    st.session_state.user = user_result
                    last_conv = load_user_last_conversation(user_result["id"])
                    st.session_state.conversation = last_conv
                    st.session_state.messages_memory = []
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
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# Auto-chargement de la dernière conversation avec debug
# -------------------------
if st.session_state.user["id"] != "guest" and not st.session_state.conversation_loaded:
    last_conv = load_user_last_conversation(st.session_state.user["id"])
    if last_conv:
        st.session_state.conversation = last_conv
        st.info(f"Dernière conversation chargée: {last_conv.get('description', 'Sans titre')}")
    st.session_state.conversation_loaded = True

# -------------------------
# Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = safe_create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            st.session_state.messages_memory = []
            conv_id_for_save = conv.get("conversation_id")
            save_active_conversation(st.session_state.user["id"], conv_id_for_save)
            st.rerun()
        else:
            st.error("Impossible de créer une nouvelle conversation")
    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            current_conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
            options = ["Choisir une conversation..."]
            for c in convs:
                title = f"{c['description']} - {c['created_at']}"
                if c.get('conversation_id') == current_conv_id:
                    title += " (Actuelle)"
                options.append(title)
            sel = st.sidebar.selectbox("Vos conversations:", options)
            if sel != "Choisir une conversation..." and not sel.endswith(" (Actuelle)"):
                idx = options.index(sel) - 1
                selected_conv = convs[idx]
                if st.session_state.conversation != selected_conv:
                    st.session_state.conversation = selected_conv
                    st.session_state.messages_memory = []
                    st.rerun()
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Créé par <b>Pepe Musafiri</b></p>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)
if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description', 'Conversation sans titre')
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title}</p>", unsafe_allow_html=True)

# -------------------------
# Affichage des messages existants
# -------------------------
display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    try:
        db_msgs = db.get_messages(conv_id)
        if db_msgs:
            for m in db_msgs:
                display_msgs.append({
                    "sender": m["sender"], 
                    "content": m["content"], 
                    "created_at": m["created_at"], 
                    "type": m.get("type", "text"),
                    "image_data": m.get("image_data", None)
                })
    except Exception as e:
        st.error(f"Erreur chargement messages: {e}")
else:
    display_msgs = st.session_state.messages_memory.copy()

# Afficher l'historique
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        if m.get("type") == "image":
            if m.get("image_data"):
                img = base64_to_image(m["image_data"])
                if img:
                    st.image(img, caption="Image analysée", width=300)
                else:
                    st.write("📷 Image (non disponible)")
            else:
                st.write("📷 Image uploadée")
            if "[IMAGE]" in m["content"]:
                description = m["content"].replace("[IMAGE] ", "").split("\n\nQuestion/Demande")[0]
                st.write(f"*Description automatique: {description}*")
                if "Question/Demande de l'utilisateur:" in m["content"]:
                    user_question = m["content"].split("Question/Demande de l'utilisateur: ")[1]
                    st.write(f"**Question:** {user_question}")
        else:
            st.markdown(m["content"])

# -------------------------
# Conteneur pour les nouveaux messages
# -------------------------
message_container = st.container()

# -------------------------
# Formulaire de saisie
# -------------------------
with st.form(key="chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"], key="image_upload")
    user_input = st.text_area("💭 Tapez votre message...", key="user_message", placeholder="Posez votre question ou décrivez ce que vous voulez que j'analyse dans l'image...", height=80)
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

# -------------------------
# Traitement message
# -------------------------
if submit_button and (user_input or uploaded_file):
    if st.session_state.user["id"] != "guest" and not st.session_state.conversation:
        conv = safe_create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            conv_id = conv.get("conversation_id")
        else:
            st.error("Impossible de créer une conversation")
            st.stop()
    else:
        conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None

    img_base64 = None
    if uploaded_file:
        try:
            img = Image.open(uploaded_file).convert("RGB")
            img_base64 = image_to_base64(img)
            caption = generate_caption(img, st.session_state.processor, st.session_state.model)
            user_input = f"[IMAGE] {caption}\n\nQuestion/Demande de l'utilisateur: {user_input}" if user_input else f"[IMAGE] {caption}"
        except Exception as e:
            st.error(f"Erreur traitement image: {e}")

    # Ajouter le message dans la DB
    ok = db.add_message(conv_id, "user", user_input, "image" if uploaded_file else "text", img_base64)
    if ok:
        st.session_state.messages_memory.append({"sender": "user", "content": user_input, "type": "image" if uploaded_file else "text", "image_data": img_base64, "created_at": time.time()})
    else:
        st.warning("Impossible d'ajouter le message à la conversation")

    # Obtenir la réponse AI
    placeholder = message_container.empty()
    response_text = get_ai_response(user_input)
    stream_response(response_text, placeholder)

    # Ajouter réponse AI à la DB
    if st.session_state.conversation:
        db.add_message(conv_id, "assistant", response_text, "text")
        st.session_state.messages_memory.append({"sender": "assistant", "content": response_text, "type": "text", "created_at": time.time()})
