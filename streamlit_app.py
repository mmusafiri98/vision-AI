# streamlit_app.py
import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import base64
from io import BytesIO
import time
import cohere

# --- CONFIG ---
st.set_page_config(
    page_title="Vision AI Chat",
    page_icon="🎯",
    layout="wide"
)

# --- CSS ---
st.markdown("""
<style>
    body, .stApp {
        font-family: 'Inter', sans-serif;
        background: #f9fafb;
    }
    .main-header {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        color: #2d3748;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #718096;
        margin-bottom: 2rem;
    }
    .chat-container {
        max-width: 900px;
        margin: auto;
        padding: 20px;
    }
    .message-user, .message-ai {
        display: flex;
        margin: 15px 0;
    }
    .message-user { justify-content: flex-end; }
    .message-ai { justify-content: flex-start; }
    .bubble {
        border-radius: 16px;
        padding: 12px 16px;
        max-width: 70%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-size: 0.95rem;
    }
    .user-bubble {
        background: #4299e1;
        color: white;
    }
    .ai-bubble {
        background: white;
        border: 1px solid #e2e8f0;
        color: #2d3748;
    }
    .uploaded-image {
        max-width: 300px;
        border-radius: 12px;
        margin-top: 5px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .form-container {
        background: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-top: 20px;
    }
    .stButton button {
        background: #4299e1;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 8px 20px;
        font-weight: 600;
    }
    .stButton button:hover {
        background: #3182ce;
    }
    /* Masquer le footer et menu */
    .stApp > footer {visibility: hidden;}
    .stApp > header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- CHARGEMENT BLIP ---
@st.cache_resource
def load_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

# --- UTILS ---
def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50)
    return processor.decode(out[0], skip_special_tokens=True)

# --- INIT ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "processor" not in st.session_state or "model" not in st.session_state:
    with st.spinner("Chargement du modèle BLIP..."):
        st.session_state.processor, st.session_state.model = load_model()
if "co" not in st.session_state:
    st.session_state.co = cohere.Client(api_key="Uw540GN865rNyiOs3VMnWhRaYQ97KAfudAHAnXzJ")

# --- UI HEADER ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<h1 class="main-header">🎯 Vision AI Chat</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Décrivez vos images & discutez avec l’IA</p>', unsafe_allow_html=True)

# --- AFFICHAGE CHAT ---
for message in st.session_state.chat_history:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="message-user">
            <div class="bubble user-bubble">{message['content']}</div>
        </div>
        """, unsafe_allow_html=True)
        if "image" in message:
            st.image(message["image"], caption="Image uploadée", use_container_width=False)
    else:
        st.markdown(f"""
        <div class="message-ai">
            <div class="bubble ai-bubble"><b>🤖 Vision AI:</b> {message['content']}</div>
        </div>
        """, unsafe_allow_html=True)

# --- FORMULAIRE ---
with st.form("chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📤 Uploadez une image", type=["jpg", "jpeg", "png"])
    user_message = st.text_input("💬 Votre message")
    submit = st.form_submit_button("🚀 Envoyer")

# --- TRAITEMENT ---
if submit:
    if uploaded_file is not None:
        image = Image.open(uploaded_file).convert("RGB")
        img_b64 = image_to_base64(image)

        # Ajout du message utilisateur
        st.session_state.chat_history.append({
            "role": "user",
            "content": "Image envoyée 📸",
            "image": image
        })

        # Générer description BLIP
        with st.spinner("🔍 Analyse de l'image..."):
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)

        # Ajouter description dans le chat
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Description initiale : {caption}"
        })

        # Demander à Cohere d’expliquer mieux
        chat_context = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history])
        response = st.session_state.co.chat(
            model="command-r-plus",
            messages=[
                {"role": "system", "content": "Tu es un assistant qui aide à expliquer les images analysées et à discuter avec l’utilisateur."},
                {"role": "user", "content": f"L'image a été décrite comme : {caption}. Explique en détail et engage une discussion."}
            ]
        )

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response.text
        })

    elif user_message.strip():
        # Ajout message utilisateur
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message
        })

        # Générer réponse Cohere avec contexte
        messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]
        response = st.session_state.co.chat(model="command-r-plus", messages=messages)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response.text
        })

    st.rerun()

# --- RESET ---
if st.session_state.chat_history:
    if st.button("🗑️ Vider la discussion"):
        st.session_state.chat_history = []
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

