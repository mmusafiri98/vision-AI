import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import db

st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = "You are Vision AI. Répondez aux utilisateurs de manière claire et naturelle."

# ======================
# BLIP MODEL
# ======================
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model.to("cuda")
    out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

if "processor" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# ======================
# LLaMA API
# ======================
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        st.session_state.llama_client = None

def get_ai_response(query):
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible."
    resp = st.session_state.llama_client.predict(message=query, max_tokens=8192, temperature=0.7, top_p=0.95, api_name="/chat")
    return str(resp)

def stream_response(text, placeholder):
    full_text = ""
    for c in text:
        full_text += c
        placeholder.write(full_text + "▋")
        time.sleep(0.03)
    placeholder.write(full_text)

# ======================
# AUTHENTIFICATION
# ======================
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "invité"}

# ======================
# INTERFACE PRINCIPALE
# ======================
st.title("🤖 Vision AI Chat")

with st.sidebar:
    uploaded_file = st.file_uploader("📷 Choisissez une image", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, use_column_width=True)
        if st.button("🔍 Analyser l'image"):
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            user_input = f"[IMAGE] {caption}"
            # Créer conversation si nécessaire
            if "conversation" not in st.session_state or not st.session_state.conversation:
                conv = db.create_conversation(st.session_state.user["id"], "Conversation automatique")
                st.session_state.conversation = conv
            conv_id = st.session_state.conversation["conversation_id"]
            db.add_message(conv_id, "user_api_request", user_input)
            enhanced_query = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
            with st.chat_message("assistant"):
                placeholder = st.empty()
                response = get_ai_response(enhanced_query)
                stream_response(response, placeholder)
            db.add_message(conv_id, "assistant", response)
            st.rerun()

# ======================
# Affichage chat
# ======================
if "conversation" in st.session_state and st.session_state.conversation:
    conv_id = st.session_state.conversation["conversation_id"]
    messages = db.get_messages(conv_id)
else:
    messages = st.session_state.messages_memory

if not messages:
    st.chat_message("assistant").write("👋 Bonjour ! Je suis Vision AI.")

for msg in messages:
    role = "user" if msg.get("sender") in ["user","user_api_request"] else "assistant"
    st.chat_message(role).write(msg.get("content"))

# ======================
# Input utilisateur
# ======================
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    st.chat_message("user").write(user_input)
    # Créer conversation si nécessaire
    if "conversation" not in st.session_state or not st.session_state.conversation:
        conv = db.create_conversation(st.session_state.user["id"], "Conversation automatique")
        st.session_state.conversation = conv
    conv_id = st.session_state.conversation["conversation_id"]
    db.add_message(conv_id, "user_api_request", user_input)
    enhanced_query = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_input}"
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = get_ai_response(enhanced_query)
        stream_response(response, placeholder)
    db.add_message(conv_id, "assistant", response)
    st.rerun()


