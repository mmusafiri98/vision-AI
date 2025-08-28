# streamlit_app.py
import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from io import BytesIO
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

# --- INIT GRADIO CLIENT Qwen-Image ---
if "qwen_image_client" not in st.session_state:
    st.session_state.qwen_image_client = Client("Qwen/Qwen-Image")

# --- UI HEADER ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<h1 class="main-header">🎯 Vision AI Chat</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Générez des images & discutez avec l\'IA</p>', unsafe_allow_html=True)

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
        if "generated_image" in message:
            st.image(message["generated_image"], caption="Image générée par l'IA", width=400)

# --- FORMULAIRE ---
with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader("📤 Uploadez une image (optionnel)", type=["jpg", "jpeg", "png"])
        prompt_text = st.text_input("💬 Décrivez ce que vous voulez générer")
    with col2:
        submit = st.form_submit_button("🚀 Envoyer", use_container_width=True)

# --- TRAITEMENT ---
if submit:
    user_msg = ""
    caption_text = ""
    if uploaded_file is not None:
        image = Image.open(uploaded_file).convert("RGB")
        caption_text = generate_caption(image, st.session_state.processor, st.session_state.model)
        user_msg += f"Image uploadée 📸 - Description BLIP: {caption_text}. "

    if prompt_text.strip():
        user_msg += f"Prompt utilisateur: {prompt_text.strip()}"

    # Ajouter message utilisateur
    st.session_state.chat_history.append({"role": "user", "content": user_msg, "image": uploaded_file if uploaded_file else None})

    # Génération image via Qwen-Image
    if prompt_text.strip() or caption_text:
        combined_prompt = user_msg
        result = st.session_state.qwen_image_client.predict(
            prompt=combined_prompt,
            seed=0,
            randomize_seed=True,
            aspect_ratio="16:9",
            guidance_scale=4,
            num_inference_steps=50,
            prompt_enhance=True,
            api_name="/infer"
        )
        # Le résultat est un chemin vers l'image générée ou un b64 ?
        generated_image = Image.open(result) if isinstance(result, str) else result
        st.session_state.chat_history.append({"role": "assistant", "content=": "Voici l'image générée par l'IA", "generated_image": generated_image})

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



