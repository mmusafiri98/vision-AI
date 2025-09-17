import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import db  # ton module db.py mis à jour

# === CONFIG ===
st.set_page_config(page_title="Vision AI Chat", layout="wide")

SYSTEM_PROMPT = """
You are Vision AI. Your role is to help users by describing uploaded images with precision,
answering their questions clearly and helpfully.
"""

# === BLIP MODEL ===
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

# === SESSION INIT ===
if "user" not in st.session_state:
    st.session_state.user = None
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

# === LLaMA CLIENT ===
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        st.session_state.llama_client = None

def get_ai_response(query):
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible"
    return st.session_state.llama_client.predict(message=query, max_tokens=8192, temperature=0.7, top_p=0.95, api_name="/chat")

def stream_response(text, placeholder):
    full_text = ""
    for char in text:
        full_text += char
        placeholder.write(full_text + "▋")
        time.sleep(0.03)
    placeholder.write(full_text)

# === AUTHENTIFICATION SIMPLIFIÉE ===
st.sidebar.title("🔐 Authentification")
if st.session_state.user is None:
    email = st.sidebar.text_input("📧 Email")
    password = st.sidebar.text_input("🔒 Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        user = db.verify_user(email, password)
        if user:
            st.session_state.user = user
            st.experimental_rerun()
        else:
            st.sidebar.error("❌ Identifiants invalides")
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user['email']}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = None
        st.session_state.conversation = None
        st.experimental_rerun()

# === CONVERSATION INIT ===
if st.session_state.user and st.session_state.conversation is None:
    user_id = st.session_state.user["id"]
    convs = db.get_conversations(user_id)
    if convs:
        st.session_state.conversation = convs[0]
    else:
        st.session_state.conversation = db.create_conversation(user_id, "Conversation automatique")

# === INTERFACE ===
st.title("🤖 Vision AI Chat")
if st.session_state.user:
    st.write(f"Connecté en tant que: {st.session_state.user['email']}")

# === IMAGE UPLOAD ===
with st.sidebar:
    uploaded_file = st.file_uploader("📷 Choisir une image", type=['png','jpg','jpeg'])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image)
        if st.button("Analyser l'image"):
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            image_message = f"[IMAGE] {caption}"
            conv_id = st.session_state.conversation["conversation_id"]
            db.add_message(conv_id, "user_api_request", image_message)
            enhanced_query = f"{SYSTEM_PROMPT}\n\nUtilisateur: {image_message}"
            with st.chat_message("assistant"):
                placeholder = st.empty()
                response = get_ai_response(enhanced_query)
                stream_response(response, placeholder)
                db.add_message(conv_id, "assistant_api_response", response)
            st.experimental_rerun()

# === CHAT MESSAGES ===
chat_container = st.container()
with chat_container:
    conv_id = st.session_state.conversation["conversation_id"]
    messages = db.get_messages(conv_id) if conv_id else st.session_state.messages_memory
    if not messages:
        st.chat_message("assistant").write("👋 Bonjour !")
    for msg in messages:
        role = "user" if msg["sender"] in ["user", "user_api_request"] else "assistant"
        st.chat_message(role).write(msg["content"])

# === INPUT UTILISATEUR ===
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    conv_id = st.session_state.conversation["conversation_id"]
    db.add_message(conv_id, "user", user_input)
    enhanced_query = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = get_ai_response(enhanced_query)
        stream_response(response, placeholder)
        db.add_message(conv_id, "assistant_api_response", response)
    st.experimental_rerun()

