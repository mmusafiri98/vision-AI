import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import io
import base64
import os
from supabase import create_client

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Fixed", layout="wide")

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
# Supabase
# -------------------------
@st.cache_resource
def init_supabase():
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            st.error("Supabase URL ou clé manquante")
            return None
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        st.error(f"Erreur Supabase: {e}")
        return None

supabase = init_supabase()

# -------------------------
# Fonctions DB simplifiées
# -------------------------
def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    if not supabase:
        st.error("Supabase non connecté")
        return False
    try:
        message_data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        if image_data:
            message_data["image_data"] = image_data
        response = supabase.table("messages").insert(message_data).execute()
        return bool(response.data and len(response.data) > 0)
    except Exception as e:
        st.error(f"add_message: {e}")
        return False

def get_messages(conversation_id):
    if not supabase:
        return []
    try:
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        return response.data if response.data else []
    except:
        return []

# -------------------------
# BLIP
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
# Conversion Image <-> Base64
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    return Image.open(io.BytesIO(base64.b64decode(img_str)))

# -------------------------
# IA
# -------------------------
@st.cache_resource
def load_llama():
    try:
        client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
        return client
    except:
        return None

llama_client = load_llama()

def get_ai_response(prompt):
    if not llama_client:
        return "Vision AI non disponible."
    try:
        resp = llama_client.predict(
            message=str(prompt),
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"Erreur modèle: {e}"

# -------------------------
# Session
# -------------------------
if "conversation" not in st.session_state:
    st.session_state.conversation = {"conversation_id": "demo"}
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# -------------------------
# Interface
# -------------------------
st.title("Vision AI Chat")

# Affichage messages
for msg in st.session_state.messages_memory:
    role = "user" if msg["sender"] == "user" else "assistant"
    with st.chat_message(role):
        if msg["type"] == "image" and msg.get("image_data"):
            st.image(base64_to_image(msg["image_data"]), width=300)
        st.markdown(msg["content"])

# Formulaire
with st.form("msg_form", clear_on_submit=True):
    user_input = st.text_area("Votre message:", height=100)
    uploaded_file = st.file_uploader("Image", type=["png","jpg","jpeg"])
    submit = st.form_submit_button("Envoyer")

if submit and (user_input.strip() or uploaded_file):
    conv_id = st.session_state.conversation["conversation_id"]
    
    message_content = user_input.strip()
    msg_type = "text"
    image_data = None

    if uploaded_file:
        image = Image.open(uploaded_file)
        image_data = image_to_base64(image)
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        message_content = f"[IMAGE] {caption}"
        if user_input.strip():
            message_content += f"\n\nQuestion: {user_input.strip()}"
        msg_type = "image"
    
    # Sauvegarde utilisateur
    if add_message(conv_id, "user", message_content, msg_type, image_data):
        st.session_state.messages_memory.append({
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # Affichage utilisateur
    with st.chat_message("user"):
        if msg_type == "image" and image_data:
            st.image(base64_to_image(image_data), width=300)
        st.markdown(message_content)
    
    # Générer réponse IA
    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_content}"
    ai_response = get_ai_response(prompt)
    
    # Sauvegarde IA
    if add_message(conv_id, "assistant", ai_response, "text"):
        st.session_state.messages_memory.append({
            "sender": "assistant",
            "content": ai_response,
            "type": "text",
            "image_data": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # Affichage IA
    with st.chat_message("assistant"):
        st.markdown(ai_response)
    
    st.rerun()

