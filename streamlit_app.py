import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB Supabase corrigé

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Debug", layout="wide")

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
# DEBUG: Vérification Supabase au démarrage
# -------------------------
@st.cache_resource
def check_supabase_connection():
    if hasattr(db, 'supabase') and db.supabase:
        try:
            response = db.supabase.table("users").select("*").limit(1).execute()
            return True, "Connexion Supabase OK"
        except Exception as e:
            return False, f"Erreur test Supabase: {e}"
    else:
        return False, "Client Supabase non initialisé"

supabase_ok, supabase_msg = check_supabase_connection()
if not supabase_ok:
    st.error(f"🔴 PROBLEME SUPABASE: {supabase_msg}")
else:
    st.success(f"🟢 {supabase_msg}")

# -------------------------
# Utils
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

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
st.sidebar.markdown("### 🐞 Debug Session State")

if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
    st.sidebar.info("🔄 user initialisé")

if "conversation" not in st.session_state:
    st.session_state.conversation = None
    st.sidebar.info("🔄 conversation initialisée")

if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
    st.sidebar.info("🔄 messages_memory initialisé")

if "conversation_loaded" not in st.session_state:
    st.session_state.conversation_loaded = False
    st.sidebar.info("🔄 conversation_loaded initialisé")

# -------------------------
# LLaMA client
# -------------------------
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
    st.sidebar.info("🔄 BLIP chargé")

if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
        st.sidebar.success("✅ LLaMA connecté")
    except Exception as e:
        st.session_state.llama_client = None
        st.sidebar.error(f"❌ LLaMA non connecté: {e}")

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
        time.sleep(0.01 if char == ' ' else 0.03)
    placeholder.markdown(full_text + " ✅")

# -------------------------
# Authentification simplifiée (guest par défaut)
# -------------------------
if st.session_state.user["id"] == "guest":
    st.sidebar.info("Mode invité : aucune sauvegarde des conversations")
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat - Mode Debug</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

# -------------------------
# Affichage messages
# -------------------------
if st.session_state.messages_memory:
    for i, m in enumerate(st.session_state.messages_memory):
        role = "user" if m.get("sender") == "user" else "assistant"
        with st.chat_message(role):
            if m.get("type") == "image" and m.get("image_data"):
                try:
                    st.image(base64_to_image(m["image_data"]), width=300)
                except Exception as img_e:
                    st.error(f"Erreur affichage image: {img_e}")
            if m.get("content"):
                st.markdown(m.get("content"))
else:
    st.info("💭 Aucun message dans cette conversation. Commencez à écrire!")

# -------------------------
# Formulaire message
# -------------------------
st.markdown("---")
st.subheader("📝 Nouveau Message")

with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_area("💭 Tapez votre message...", height=80)
    with col2:
        uploaded_file = st.file_uploader("📷 Image", type=["png","jpg","jpeg"])
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

if submit_button and (user_input.strip() or uploaded_file):
    image_base64 = None
    msg_type = "text"
    full_message = user_input.strip()

    if uploaded_file:
        image = Image.open(uploaded_file)
        image_base64 = image_to_base64(image)
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        full_message = f"[IMAGE] {caption}\n\nQuestion: {user_input.strip()}" if user_input.strip() else f"[IMAGE] {caption}"
        msg_type = "image"

    user_message = {
        "sender": "user",
        "content": full_message,
        "type": msg_type,
        "image_data": image_base64,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    st.session_state.messages_memory.append(user_message)

    with st.chat_message("user"):
        if msg_type == "image" and image_base64:
            st.image(base64_to_image(image_base64), width=300)
        st.markdown(full_message)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        resp = get_ai_response(f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}")
        stream_response(resp, placeholder)

    ai_message = {
        "sender": "assistant",
        "content": resp,
        "type": "text",
        "image_data": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    st.session_state.messages_memory.append(ai_message)

# -------------------------
# Debug final console
# -------------------------
print("\n=== DEBUG FINAL SESSION ===")
print(f"User ID: {st.session_state.user.get('id')}")
print(f"Conversation: {st.session_state.conversation.get('description') if st.session_state.conversation else None}")
print(f"Messages count: {len(st.session_state.messages_memory)}")
print(f"Conversation loaded: {st.session_state.conversation_loaded}")
print(f"Supabase OK: {supabase_ok}")
print("=" * 30)

