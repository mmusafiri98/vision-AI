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
    .error-message {
        background: #fed7d7;
        border: 1px solid #fc8181;
        border-radius: 8px;
        padding: 10px;
        color: #c53030;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- CHARGEMENT BLIP ---
@st.cache_resource
def load_model():
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return processor, model
    except Exception as e:
        st.error(f"Erreur lors du chargement du modèle BLIP: {e}")
        return None, None

# --- UTILS ---
def image_to_base64(image):
    try:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        st.error(f"Erreur lors de la conversion de l'image: {e}")
        return None

def generate_caption(image, processor, model):
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        
        caption = processor.decode(out[0], skip_special_tokens=True)
        return caption
    except Exception as e:
        return f"Erreur lors de la génération de la description: {e}"

# --- COHERE SETUP ---
def init_cohere():
    """Initialise Cohere avec la clé API depuis les secrets"""
    try:
        # Récupérer la clé API depuis les secrets Streamlit
        if "COHERE_API_KEY" in st.secrets:
            api_key = st.secrets["COHERE_API_KEY"]
        else:
            # Fallback si pas dans les secrets (pour le développement local)
            api_key = st.text_input("Clé API Cohere:", type="password", help="Entrez votre clé API Cohere")
            if not api_key:
                st.warning("⚠️ Veuillez entrer votre clé API Cohere pour utiliser le chat.")
                return None
        
        return cohere.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Erreur lors de l'initialisation de Cohere: {e}")
        return None

def get_cohere_response(messages, co_client):
    """Génère une réponse Cohere avec gestion d'erreurs"""
    try:
        # Convertir les messages au format Cohere
        cohere_messages = []
        for msg in messages[-10:]:  # Garder seulement les 10 derniers messages pour éviter les limites
            if msg["role"] in ["user", "assistant"]:
                cohere_messages.append({
                    "role": "USER" if msg["role"] == "user" else "CHATBOT",
                    "message": msg["content"]
                })
        
        # Appel à l'API Cohere
        response = co_client.chat(
            model="command-r-plus",
            message=cohere_messages[-1]["message"] if cohere_messages else "Bonjour",
            chat_history=cohere_messages[:-1] if len(cohere_messages) > 1 else []
        )
        
        return response.text
    
    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            return "⚠️ Limite de taux atteinte. Veuillez patienter quelques minutes."
        elif "invalid api key" in error_msg.lower():
            return "❌ Clé API Cohere invalide. Veuillez vérifier votre clé."
        else:
            return f"❌ Erreur Cohere: {error_msg}"

# --- INIT SESSION STATE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "processor" not in st.session_state or "model" not in st.session_state:
    with st.spinner("🤖 Chargement du modèle BLIP..."):
        processor, model = load_model()
        if processor is not None and model is not None:
            st.session_state.processor = processor
            st.session_state.model = model
        else:
            st.error("❌ Impossible de charger le modèle BLIP")
            st.stop()

if "co" not in st.session_state:
    co_client = init_cohere()
    if co_client:
        st.session_state.co = co_client
    else:
        st.session_state.co = None

# --- UI HEADER ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<h1 class="main-header">🎯 Vision AI Chat</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Décrivez vos images &amp; discutez avec l\'IA</p>', unsafe_allow_html=True)

# Afficher le statut des services
col1, col2 = st.columns(2)
with col1:
    if "processor" in st.session_state and "model" in st.session_state:
        st.success("✅ BLIP chargé")
    else:
        st.error("❌ BLIP non disponible")

with col2:
    if st.session_state.get("co") is not None:
        st.success("✅ Cohere connecté")
    else:
        st.warning("⚠️ Cohere non disponible")

# --- AFFICHAGE CHAT ---
if not st.session_state.chat_history:
    st.markdown("""
    <div style="text-align: center; color: #a0aec0; margin: 50px 0;">
        <p>👋 Bonjour ! Uploadez une image ou écrivez un message pour commencer.</p>
    </div>
    """, unsafe_allow_html=True)

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
        uploaded_file = st.file_uploader("📤 Uploadez une image", type=["jpg", "jpeg", "png"])
    
    with col2:
        st.write("")  # Espacement
        st.write("")
        submit = st.form_submit_button("🚀 Envoyer", use_container_width=True)
    
    user_message = st.text_input("💬 Votre message (optionnel)")

# --- TRAITEMENT ---
if submit:
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file).convert("RGB")
            
            # Ajout du message utilisateur
            message_content = f"Image envoyée 📸"
            if user_message.strip():
                message_content += f" - {user_message.strip()}"
            
            st.session_state.chat_history.append({
                "role": "user",
                "content": message_content,
                "image": image
            })

            # Générer description BLIP
            with st.spinner("🔍 Analyse de l'image..."):
                caption = generate_caption(image, st.session_state.processor, st.session_state.model)

            # Utiliser Cohere pour une réponse enrichie
            if st.session_state.co is not None:
                with st.spinner("💭 Génération de la réponse..."):
                    prompt = f"Une image a été analysée avec cette description: '{caption}'"
                    if user_message.strip():
                        prompt += f" L'utilisateur demande: '{user_message.strip()}'"
                    prompt += " Explique cette image de manière détaillée et engageante."
                    
                    # Ajouter le prompt temporairement pour Cohere
                    temp_messages = st.session_state.chat_history.copy()
                    temp_messages.append({"role": "user", "content": prompt})
                    
                    cohere_response = get_cohere_response(temp_messages, st.session_state.co)
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": cohere_response
                    })
            else:
                # Fallback sur BLIP seul
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Description de l'image: {caption}"
                })
            
        except Exception as e:
            st.error(f"Erreur lors du traitement: {e}")

    elif user_message.strip():
        # Message texte seulement
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message.strip()
        })

        if st.session_state.co is not None:
            with st.spinner("💭 Génération de la réponse..."):
                cohere_response = get_cohere_response(st.session_state.chat_history, st.session_state.co)
                
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": cohere_response
                })
        else:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "❌ Cohere n'est pas disponible. Seule l'analyse d'images fonctionne."
            })
    else:
        st.warning("⚠️ Veuillez uploader une image ou écrire un message.")

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

# --- HELP SECTION ---
with st.expander("ℹ️ Comment utiliser Vision AI Chat"):
    st.markdown("""
    ### 🖼️ **Analyse d'images**
    1. Uploadez une image (JPG, JPEG, PNG)
    2. Ajoutez un message optionnel
    3. Cliquez sur "🚀 Envoyer"
    
    ### 💬 **Chat**
    - Écrivez vos questions dans le champ message
    - L'IA utilise le contexte des images précédentes
    
    ### 🔧 **Configuration**
    - **BLIP**: Analyse automatique des images
    - **Cohere**: Chat conversationnel avancé
    
    ### 🔐 **Sécurité**
    - Ajoutez votre clé API Cohere dans les secrets Streamlit
    - Format: `COHERE_API_KEY = "votre_cle_ici"`
    """)
