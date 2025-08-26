# streamlit_app.py
import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import base64
from io import BytesIO
import time

# --- Configuration de la page ---
st.set_page_config(
    page_title="Vision AI Chat", 
    page_icon="🎯",
    layout="wide"
)

# --- CSS pour l'interface similaire à Claude ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2d3748;
        font-size: 2.5rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        font-family: 'Inter', sans-serif;
    }
    
    .subtitle {
        text-align: center;
        color: #718096;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }
    
    .message-user {
        display: flex;
        justify-content: flex-end;
        margin: 15px 0;
    }
    
    .message-ai {
        display: flex;
        justify-content: flex-start;
        margin: 15px 0;
    }
    
    .message-content-user {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 12px 16px;
        max-width: 70%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .message-content-ai {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 12px 16px;
        max-width: 70%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .upload-area {
        border: 2px dashed #cbd5e0;
        border-radius: 12px;
        padding: 40px 20px;
        text-align: center;
        background: #f7fafc;
        margin: 20px 0;
    }
    
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 20px;
        border-top: 1px solid #e2e8f0;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    }
    
    .send-button {
        background: #4299e1;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        cursor: pointer;
        font-weight: 600;
    }
    
    .send-button:hover {
        background: #3182ce;
    }
    
    .uploaded-image {
        max-width: 300px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    .stButton button {
        background: #4299e1;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 8px 24px;
        font-weight: 600;
    }
    
    .stButton button:hover {
        background: #3182ce;
    }
    
    /* Masquer le footer Streamlit */
    .stApp > footer {visibility: hidden;}
    
    /* Masquer le menu hamburger */
    .stApp > header {visibility: hidden;}
    
    /* Style pour les messages du chat */
    .chat-message {
        margin: 20px 0;
        padding: 0;
    }
</style>
""", unsafe_allow_html=True)

# --- Chargement du modèle BLIP ---
@st.cache_resource
def load_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

# --- Fonction pour convertir image en base64 ---
def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

# --- Fonction pour générer la description ---
def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

# --- Initialisation des variables de session ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'processor' not in st.session_state or 'model' not in st.session_state:
    with st.spinner('Chargement du modèle Vision AI...'):
        st.session_state.processor, st.session_state.model = load_model()

# --- Interface principale ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# En-tête
st.markdown('<h1 class="main-header">🎯 Vision AI</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Décrivez vos images avec l\'intelligence artificielle</p>', unsafe_allow_html=True)

# Zone d'affichage du chat
chat_container = st.container()

with chat_container:
    if st.session_state.chat_history:
        for message in st.session_state.chat_history:
            if message['type'] == 'user':
                st.markdown(f"""
                <div class="message-user">
                    <div class="message-content-user">
                        <img src="{message['image']}" class="uploaded-image" alt="Image uploadée">
                        <p style="margin: 5px 0 0 0; font-size: 0.9em; color: #666;">Image uploadée</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="message-ai">
                    <div class="message-content-ai">
                        <p style="margin: 0; color: #2d3748;"><strong>🤖 Vision AI:</strong></p>
                        <p style="margin: 8px 0 0 0; color: #4a5568;">{message['content']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; color: #a0aec0; margin: 50px 0;">
            <p>👋 Bonjour ! Uploadez une image pour commencer.</p>
            <p>Je vais analyser votre image et vous fournir une description détaillée.</p>
        </div>
        """, unsafe_allow_html=True)

# Zone de saisie en bas
st.markdown("---")
st.markdown("### 📤 Uploadez votre image")

col1, col2 = st.columns([3, 1])

with col1:
    uploaded_file = st.file_uploader(
        "Choisissez une image", 
        type=["jpg", "jpeg", "png"],
        help="Formats supportés: JPG, JPEG, PNG"
    )

with col2:
    send_button = st.button("🚀 Analyser", type="primary", use_container_width=True)

# Traitement de l'upload et envoi
if uploaded_file is not None and send_button:
    try:
        # Chargement de l'image
        image = Image.open(uploaded_file).convert("RGB")
        image_b64 = image_to_base64(image)
        
        # Ajout du message utilisateur
        st.session_state.chat_history.append({
            'type': 'user',
            'image': image_b64,
            'content': 'Image uploadée'
        })
        
        # Affichage du message de traitement
        with st.spinner('🔍 Analyse de l\'image en cours...'):
            time.sleep(1)  # Simulation du temps de traitement
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        
        # Ajout de la réponse de l'IA
        st.session_state.chat_history.append({
            'type': 'ai',
            'content': caption
        })
        
        # Actualisation de la page pour afficher les nouveaux messages
        st.rerun()
        
    except Exception as e:
        st.error(f"Erreur lors du traitement de l'image: {str(e)}")

# Bouton pour vider le chat
if st.session_state.chat_history:
    st.markdown("---")
    if st.button("🗑️ Vider le chat"):
        st.session_state.chat_history = []
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# Instructions d'utilisation
with st.expander("ℹ️ Comment utiliser Vision AI"):
    st.markdown("""
    1. **Uploadez une image** : Cliquez sur "Browse files" et sélectionnez votre image
    2. **Cliquez sur "Analyser"** : Le modèle BLIP analysera votre image
    3. **Recevez la description** : L'IA vous fournira une description détaillée
    4. **Continuez la conversation** : Uploadez d'autres images pour continuer
    
    **Formats supportés** : JPG, JPEG, PNG
    **Modèle utilisé** : Salesforce BLIP (Bootstrapping Language-Image Pre-training)
    """)
