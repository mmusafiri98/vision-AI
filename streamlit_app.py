import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import io
import base64
import os
import uuid
from supabase import create_client
from gtts import gTTS

# -------------------------
# Configuration Streamlit
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Typing Effect", layout="wide")

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
# Fonctions Utilisateur
# -------------------------
def create_user(email, password, name):
    if not supabase:
        return False
    try:
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name}
            })
            return response.user is not None
        except:
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,
                "name": name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            resp = supabase.table("users").insert(user_data).execute()
            return bool(resp.data and len(resp.data) > 0)
    except Exception as e:
        st.error(f"Erreur create_user: {e}")
        return False

def verify_user(email, password):
    if not supabase:
        return None
    try:
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if resp.user:
                return {
                    "id": resp.user.id,
                    "email": resp.user.email,
                    "name": resp.user.user_metadata.get("name", email.split("@")[0])
                }
        except:
            resp = supabase.table("users").select("*").eq("email", email).execute()
            if resp.data and len(resp.data) > 0:
                user = resp.data[0]
                if user.get("password") == password:
                    return {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name", email.split("@")[0])
                    }
        return None
    except Exception as e:
        st.error(f"Erreur verify_user: {e}")
        return None

# -------------------------
# Conversations & Messages
# -------------------------
def create_conversation(user_id, description="Nouvelle conversation"):
    if not supabase or not user_id:
        return None
    try:
        data = {
            "conversation_id": str(uuid.uuid4()),
            "user_id": user_id,
            "description": description,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        resp = supabase.table("conversations").insert(data).execute()
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None
    except Exception as e:
        st.error(f"Erreur create_conversation: {e}")
        return None

def get_conversations(user_id):
    if not supabase or not user_id:
        return []
    try:
        resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return resp.data if resp.data else []
    except:
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    if not supabase:
        return False
    try:
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        if image_data:
            data["image_data"] = image_data
        resp = supabase.table("messages").insert(data).execute()
        return bool(resp.data and len(resp.data) > 0)
    except Exception as e:
        st.error(f"add_message: {e}")
        return False

def get_messages(conversation_id):
    if not supabase:
        return []
    try:
        resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        return resp.data if resp.data else []
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
# Image <-> Base64
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    return Image.open(io.BytesIO(base64.b64decode(img_str)))

# -------------------------
# LLaMA Client
# -------------------------
@st.cache_resource
def load_llama():
    try:
        return Client("muryshev/LLaMA-3.1-70b-it-NeMo")
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
# Effet dactylographique + TTS (gTTS segmenté)
# -------------------------
def text_to_speech(text, lang="fr"):
    try:
        tts = gTTS(text=text, lang=lang)
        filename = f"/tmp/{uuid.uuid4()}.mp3"
        tts.save(filename)
        return filename
    except Exception as e:
        st.error(f"Erreur TTS: {e}")
        return None

def stream_response_with_voice(text, placeholder):
    displayed = ""
    for sentence in text.split(". "):  # découpe par phrase
        for char in sentence:
            displayed += char
            placeholder.markdown(displayed + "▋")
            time.sleep(0.02)
        displayed += ". "
        placeholder.markdown(displayed)

        # Générer la voix pour chaque phrase finie
        audio_file = text_to_speech(sentence, lang="fr")
        if audio_file:
            st.audio(audio_file, format="audio/mp3")

# -------------------------
# Session State
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "processor" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

# -------------------------
# Sidebar Auth & Debug
# -------------------------
st.sidebar.title("Authentification / Debug")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            user = verify_user(email, password)
            if user:
                st.session_state.user = user
                st.success("Connexion réussie!")
                st.rerun()
            else:
                st.error("Identifiants invalides")
    with tab2:
        email_reg = st.text_input("Email", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe", type="password", key="reg_pass")
        if st.button("Créer compte"):
            if create_user(email_reg, pass_reg, name_reg):
                st.success("Compte créé!")
            else:
                st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Gestion Conversations
# -------------------------
st.sidebar.title("Conversations")
if st.sidebar.button("Nouvelle conversation"):
    conv = create_conversation(st.session_state.user["id"])
    if conv:
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.success("Nouvelle conversation créée!")
        st.rerun()

convs = get_conversations(st.session_state.user["id"])
if convs:
    options = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
    current_idx = 0
    if st.session_state.conversation:
        for i, c in enumerate(convs):
            if c["conversation_id"] == st.session_state.conversation.get("conversation_id"):
                current_idx = i
                break
    selected_idx = st.sidebar.selectbox("Vos conversations:", range(len(options)), format_func=lambda i: options[i], index=current_idx)
    st.session_state.conversation = convs[selected_idx]
    st.session_state.messages_memory = get_messages(st.session_state.conversation["conversation_id"])

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat")

# Affichage messages
for msg in st.session_state.messages_memory:
    role = "user" if msg["sender"] == "user" else "assistant"
    with st.chat_message(role):
        if msg["type"] == "image" and msg.get("image_data"):
            st.image(base64_to_image(msg["image_data"]), width=300)
        st.markdown(msg["content"])

# Formulaire nouveau message
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

    # Sauvegarde message utilisateur
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

    # Placeholder "Thinking"
    with st.chat_message("assistant"):
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown("🤖 Vision AI is thinking...")
        time.sleep(1.5)

        # Générer réponse IA
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_content}"
        ai_response = get_ai_response(prompt)

        # Supprimer placeholder
        thinking_placeholder.empty()
        response_placeholder = st.empty()
        stream_response_with_voice(ai_response, response_placeholder)

        # Sauvegarder réponse IA
        if add_message(conv_id, "assistant", ai_response, "text"):
            st.session_state.messages_memory.append({
                "sender": "assistant",
                "content": ai_response,
                "type": "text",
                "image_data": None,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })

    st.rerun()


