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

# -------------------------
# Configuration Streamlit
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")

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
# BLIP (Image Captioning)
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
# Qwen Image Edit
# -------------------------
EDITED_IMAGES_DIR = "edited_images"
os.makedirs(EDITED_IMAGES_DIR, exist_ok=True)

def edit_image_with_qwen(image_path, edit_instruction, client):
    try:
        result = client.predict(
            image=image_path,  # ✅ correction
            prompt=edit_instruction,
            seed=0,
            randomize_seed=True,
            true_guidance_scale=4,
            num_inference_steps=50,
            rewrite_prompt=True,
            api_name="/infer"
        )
        if isinstance(result, tuple) and len(result) >= 1:
            temp_image_path = result[0]
            edited_image_path = os.path.join(EDITED_IMAGES_DIR, f"edited_{uuid.uuid4().hex}.png")
            img = Image.open(temp_image_path)
            img.save(edited_image_path)
            return edited_image_path, f"✅ Image éditée selon : '{edit_instruction}'"
        else:
            return None, f"❌ Résultat inattendu : {result}"
    except Exception as e:
        return None, f"Erreur édition : {e}"

# -------------------------
# Interface Streamlit
# -------------------------
def main():
    st.title("🧠 Vision AI - Analyse et Édition d’Images")

    # Auth utilisateur
    if "user" not in st.session_state:
        choice = st.sidebar.radio("Connexion / Inscription", ["Connexion", "Inscription"])
        if choice == "Inscription":
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            name = st.text_input("Nom")
            if st.button("Créer un compte"):
                if create_user(email, password, name):
                    st.success("Compte créé, connectez-vous.")
                else:
                    st.error("Erreur lors de l’inscription")
        else:
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            if st.button("Connexion"):
                user = verify_user(email, password)
                if user:
                    st.session_state.user = user
                    st.success(f"Bienvenue {user['name']}")
                else:
                    st.error("Identifiants incorrects")
        return

    st.sidebar.success(f"Connecté en tant que {st.session_state.user['name']}")

    # Gestion des conversations
    convs = get_conversations(st.session_state.user["id"])
    conv_choice = st.sidebar.selectbox("Conversations", ["Nouvelle"] + [c["description"] for c in convs])
    if conv_choice == "Nouvelle":
        if st.button("Créer conversation"):
            conv = create_conversation(st.session_state.user["id"], "Nouvelle conversation")
            if conv:
                st.session_state.conversation = conv
    else:
        conv = [c for c in convs if c["description"] == conv_choice][0]
        st.session_state.conversation = conv

    if "conversation" not in st.session_state:
        st.info("Créez une nouvelle conversation.")
        return

    conv_id = st.session_state.conversation["conversation_id"]
    messages = get_messages(conv_id)

    for m in messages:
        if m["type"] == "image":
            st.image(base64_to_image(m["image_data"]), caption=f"{m['sender']}: {m['content']}")
        else:
            st.write(f"**{m['sender']}**: {m['content']}")

    # Upload d'image
    uploaded = st.file_uploader("Uploader une image", type=["png", "jpg", "jpeg"])
    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Image téléchargée")
        processor, model = load_blip()
        caption = generate_caption(image, processor, model)
        st.write("📷 Description générée :", caption)
        add_message(conv_id, "user", f"[IMAGE] {caption}", "image", image_to_base64(image))

    # Chat texte
    user_input = st.text_input("Votre message :")
    if st.button("Envoyer"):
        if user_input.strip():
            add_message(conv_id, "user", user_input)
            response = get_ai_response(SYSTEM_PROMPT + "\n\n" + user_input)
            add_message(conv_id, "assistant", response)

if __name__ == "__main__":
    main()

