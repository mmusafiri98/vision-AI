# streamlit_app.py
import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client

# --- CONFIG ---
st.set_page_config(
    page_title="Vision AI Chat",
    page_icon="🎯",
    layout="wide"
)

# --- CSS ---
st.markdown("""
<style>
    body, .stApp { font-family: 'Inter', sans-serif; background: #f9fafb; }
    .main-header { text-align: center; font-size: 2.5rem; font-weight: 700; color: #2d3748; margin-bottom: 0.5rem; }
    .subtitle { text-align: center; font-size: 1.1rem; color: #718096; margin-bottom: 2rem; }
    .chat-container { max-width: 900px; margin: auto; padding: 20px; }
    .message-user, .message-ai { display: flex; margin: 15px 0; }
    .message-user { justify-content: flex-end; }
    .message-ai { justify-content: flex-start; }
    .bubble { border-radius: 16px; padding: 12px 16px; max-width: 70%; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 0.95rem; }
    .user-bubble { background: #4299e1; color: white; }
    .ai-bubble { background: white; border: 1px solid #e2e8f0; color: #2d3748; }
    .uploaded-image { max-width: 300px; border-radius: 12px; margin-top: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .form-container { background: white; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-top: 20px; }
    .stButton button { background: #4299e1; color: white; border-radius: 8px; border: none; padding: 8px 20px; font-weight: 600; }
    .stButton button:hover { background: #3182ce; }
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

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model = model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

# --- INIT SESSION STATE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "processor" not in st.session_state or "model" not in st.session_state:
    with st.spinner("🤖 Chargement du modèle BLIP..."):
        processor, model = load_model()
        st.session_state.processor = processor
        st.session_state.model = model

# --- INIT GRADIO CLIENT Qwen2-72B ---
if "qwen_client" not in st.session_state:
    st.session_state.qwen_client = Client("Qwen/Qwen2-72B-Instruct")

# --- UI HEADER ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<h1 class="main-header">🎯 Vision AI Chat</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Décrivez vos images ou discutez librement avec l\'IA</p>', unsafe_allow_html=True)

# --- AFFICHAGE CHAT ---
for message in st.session_state.chat_history:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="message-user">
            <div class="bubble user-bubble">{message['content']}</div>
        </div>
        """, unsafe_allow_html=True)
        if "image" in message:
            st.image(message["image"], caption="Image uploadée", width=300)
    else:
        st.markdown(f"""
        <div class="message-ai">
            <div class="bubble ai-bubble"><b>🤖 Vision AI:</b> {message['content']}</div>
        </div>
        """, unsafe_allow_html=True)

# --- FORMULAIRE ---
with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader("📤 Uploadez une image (optionnel)", type=["jpg", "jpeg", "png"])
    with col2:
        submit = st.form_submit_button("🚀 Envoyer", use_container_width=True)
    user_message = st.text_input("💬 Votre message (optionnel)")

# --- TRAITEMENT ---
if submit:
    # Cas 1 : Image fournie
    if uploaded_file is not None:
        image = Image.open(uploaded_file).convert("RGB")
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        user_text = f"Description de l'image: '{caption}'"
        if user_message.strip():
            user_text += f" L'utilisateur demande: '{user_message.strip()}'"
        qwen_response = st.session_state.qwen_client.predict(
            query=user_text,
            history=[],
            system="You are a helpful assistant.",
            api_name="/model_chat"
        )
        st.session_state.chat_history.append({"role": "user", "content": f"Image envoyée 📸 {user_message.strip()}", "image": uploaded_file})
        st.session_state.chat_history.append({"role": "assistant", "content": qwen_response})

    # Cas 2 : Aucun upload, seulement texte
    elif user_message.strip():
        qwen_response = st.session_state.qwen_client.predict(
            query=user_message.strip(),
            history=[],
            system="You are a helpful assistant.",
            api_name="/model_chat"
        )
        st.session_state.chat_history.append({"role": "user", "content": user_message.strip()})
        st.session_state.chat_history.append({"role": "assistant", "content": qwen_response})

    st.rerun()

# --- RESET ---
if st.session_state.chat_history:
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🗑️ Vider la discussion", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

