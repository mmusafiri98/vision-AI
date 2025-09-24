# app.py
import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client, handle_file
import time
import io
import base64
import os
import uuid
import traceback
from supabase import create_client

# -------------------------
# Config Streamlit
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Full", layout="wide")
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
# Dossiers locaux
# -------------------------
TMP_DIR = "tmp_files"
EDITED_IMAGES_DIR = "edited_images"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(EDITED_IMAGES_DIR, exist_ok=True)

# -------------------------
# Supabase init
# -------------------------
@st.cache_resource
def init_supabase():
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            st.error("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquante.")
            return None
        client = create_client(supabase_url, supabase_key)
        try:
            _ = client.table("users").select("*").limit(1).execute()
        except Exception:
            pass
        return client
    except Exception as e:
        st.error(f"Erreur init_supabase: {e}")
        return None

supabase = init_supabase()

# -------------------------
# Fonctions utilitaires DB
# -------------------------
def verify_user(email, password):
    if not supabase:
        return None
    try:
        # Auth avec Supabase
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if getattr(resp, "user", None):
                return {
                    "id": resp.user.id,
                    "email": resp.user.email,
                    "name": resp.user.user_metadata.get("name", email.split("@")[0])
                }
        except Exception:
            pass
        # Fallback table users
        resp = supabase.table("users").select("*").eq("email", email).execute()
        if resp.data and len(resp.data) > 0:
            user = resp.data[0]
            if user.get("password") == password:
                return {"id": user["id"], "email": user["email"], "name": user.get("name", email.split("@")[0])}
        return None
    except Exception as e:
        st.error(f"verify_user: {e}")
        return None

def create_user(email, password, name):
    if not supabase:
        return False
    try:
        try:
            resp = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name}
            })
            return getattr(resp, "user", None) is not None
        except Exception:
            pass
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
        st.error(f"create_user: {e}")
        return False

def get_conversations(user_id):
    if not supabase or not user_id:
        return []
    try:
        resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        if not resp.data:
            return []
        convs = []
        for conv in resp.data:
            conv_id = conv.get("conversation_id") or conv.get("id")
            convs.append({"conversation_id": conv_id, "description": conv.get("description", "Conversation"), "created_at": conv.get("created_at"), "user_id": conv.get("user_id")})
        return convs
    except Exception as e:
        st.error(f"get_conversations: {e}")
        return []

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
            conv = resp.data[0]
            return {"conversation_id": conv.get("conversation_id") or conv.get("id"), "description": conv.get("description"), "created_at": conv.get("created_at"), "user_id": conv.get("user_id")}
        return None
    except Exception as e:
        st.error(f"create_conversation: {e}")
        return None

def get_messages(conversation_id):
    if not supabase or not conversation_id:
        return []
    try:
        resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        if not resp.data:
            return []
        msgs = []
        for m in resp.data:
            msgs.append({"message_id": m.get("message_id") or m.get("id"), "conversation_id": m.get("conversation_id"), "sender": m.get("sender", "unknown"), "content": m.get("content", ""), "type": m.get("type", "text"), "image_data": m.get("image_data"), "created_at": m.get("created_at")})
        return msgs
    except Exception as e:
        st.error(f"get_messages: {e}")
        st.code(traceback.format_exc())
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    if not supabase:
        st.error("add_message: Supabase non connecté")
        return False
    if not conversation_id or not content:
        st.error("add_message: paramètres manquants")
        return False
    try:
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            st.error(f"add_message: conversation {conversation_id} introuvable")
            return False
        message_data = {"message_id": str(uuid.uuid4()), "conversation_id": conversation_id, "sender": sender, "content": content, "type": msg_type, "image_data": image_data, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        resp = supabase.table("messages").insert(message_data).execute()
        if hasattr(resp, "error") and resp.error:
            st.error(f"add_message supabase error: {resp.error}")
            return False
        if not resp.data or len(resp.data) == 0:
            st.error("add_message: insertion renvoyée sans données")
            return False
        return True
    except Exception as e:
        st.error(f"add_message exception: {e}")
        st.code(traceback.format_exc())
        return False

# -------------------------
# Utilitaires image <-> base64
# -------------------------
def image_to_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(img_str)))

# -------------------------
# BLIP caption loader
# -------------------------
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

def generate_caption(image: Image.Image, processor, model) -> str:
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
        model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

# -------------------------
# LLaMA client
# -------------------------
@st.cache_resource
def load_llama_client():
    try:
        return Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        return None

# -------------------------
# Qwen Image Edit client
# -------------------------
@st.cache_resource
def load_qwen_client():
    try:
        return Client("Qwen/Qwen-Image-Edit")
    except Exception:
        return None

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité", "name": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "processor" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    st.session_state.llama_client = load_llama_client()
if "qwen_client" not in st.session_state:
    st.session_state.qwen_client = load_qwen_client()
# -------------------------
# Fonctions IA / UX
# -------------------------
def get_ai_response(prompt):
    client = st.session_state.get("llama_client")
    if not client:
        return "Vision AI (texte) non disponible."
    try:
        resp = client.predict(
            message=str(prompt),
            max_tokens=2048,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"Erreur modèle texte: {e}"

def stream_response(text, placeholder):
    displayed = ""
    for ch in str(text):
        displayed += ch
        placeholder.markdown(displayed + "▋")
        time.sleep(0.01)
    placeholder.markdown(displayed)

# -------------------------
# Edition d'image Qwen-Image-Edit
# -------------------------
def edit_image_with_qwen(image: Image.Image, edit_instruction: str):
    client = st.session_state.get("qwen_client")
    if not client:
        st.error("Client Qwen non disponible.")
        return None, "Client Qwen non disponible."
    try:
        temp_path = os.path.join(TMP_DIR, f"input_{uuid.uuid4().hex}.png")
        image.save(temp_path)
        result = client.predict(
            image=handle_file(temp_path),
            prompt=edit_instruction,
            seed=0,
            randomize_seed=True,
            true_guidance_scale=4,
            num_inference_steps=50,
            rewrite_prompt=True,
            api_name="/infer"
        )
        if isinstance(result, (list, tuple)) and len(result) >= 1:
            edited_tmp_path = result[0]
            edited_img = Image.open(edited_tmp_path).convert("RGBA")
            final_path = os.path.join(EDITED_IMAGES_DIR, f"edited_{uuid.uuid4().hex}.png")
            edited_img.save(final_path)
            return edited_img, final_path
        else:
            return None, f"Résultat inattendu: {result}"
    except Exception as e:
        st.error(f"edit_image_with_qwen exception: {e}")
        st.code(traceback.format_exc())
        return None, str(e)

# -------------------------
# Sidebar Auth & Debug
# -------------------------
st.sidebar.title("⚙️ Paramètres & Auth")
st.sidebar.write(f"Supabase: {'OK' if supabase else 'KO'}")
st.sidebar.write(f"Qwen client: {'OK' if st.session_state.qwen_client else 'KO'}")
st.sidebar.write(f"LLaMA client: {'OK' if st.session_state.llama_client else 'KO'}")

if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if email and password:
                user = verify_user(email, password)
                if user:
                    st.session_state.user = user
                    st.success("Connexion réussie")
                    st.experimental_rerun()
                else:
                    st.error("Identifiants invalides")
    with tab2:
        email_reg = st.text_input("Email (inscription)", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe (inscription)", type="password", key="reg_pass")
        if st.button("Créer un compte"):
            if email_reg and name_reg and pass_reg:
                ok = create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Compte créé. Connectez-vous.")
                else:
                    st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')} ({st.session_state.user.get('name')})")
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité", "name": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

# -------------------------
# Gestion conversations sidebar
# -------------------------
st.sidebar.markdown("---")
st.sidebar.title("Conversations")
if st.sidebar.button("Nouvelle conversation"):
    conv = create_conversation(st.session_state.user["id"], "Nouvelle conversation")
    if conv:
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.success("Conversation créée")
        st.experimental_rerun()

convs = get_conversations(st.session_state.user["id"]) if st.session_state.user["id"] != "guest" else []
if convs:
    opts = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
    current_idx = 0
    if st.session_state.conversation:
        for i, c in enumerate(convs):
            if c["conversation_id"] == st.session_state.conversation.get("conversation_id"):
                current_idx = i
                break
    sel = st.sidebar.selectbox("Vos conversations", range(len(opts)), format_func=lambda i: opts[i], index=current_idx)
    sel_conv = convs[sel]
    if not st.session_state.conversation or st.session_state.conversation.get("conversation_id") != sel_conv.get("conversation_id"):
        st.session_state.conversation = sel_conv
        st.session_state.messages_memory = get_messages(sel_conv.get("conversation_id"))
        st.experimental_rerun()

# -------------------------
# Interface principale
# -------------------------
st.title("🎯 Vision AI Chat — Analyse & Édition d'Images")

if st.session_state.conversation:
    st.subheader(f"Conversation : {st.session_state.conversation.get('description')}")
else:
    st.info("Sélectionnez ou créez une conversation dans la barre latérale.")

# Affichage messages
if st.session_state.messages_memory:
    for msg in st.session_state.messages_memory:
        role = "user" if msg.get("sender") == "user" else "assistant"
        with st.chat_message(role):
            if msg.get("type") == "image" and msg.get("image_data"):
                try:
                    st.image(base64_to_image(msg["image_data"]), width=300)
                except Exception:
                    st.write(msg.get("content", "Image (non affichable)"))
            else:
                st.markdown(msg.get("content", ""))

# Formulaire message + upload
with st.form("msg_form", clear_on_submit=True):
    user_input = st.text_area("Votre message (ou instruction pour modifier l'image)", height=120)
    uploaded_file = st.file_uploader("Uploader une image (optionnel)", type=["png", "jpg", "jpeg"])
    submit = st.form_submit_button("Envoyer")

if submit and (user_input.strip() or uploaded_file):
    if not st.session_state.conversation:
        conv = create_conversation(st.session_state.user["id"], "Discussion automatique")
        if not conv:
            st.error("Impossible de créer une conversation")
            st.stop()
        st.session_state.conversation = conv

    conv_id = st.session_state.conversation.get("conversation_id")
    msg_type = "text"
    image_b64 = None
    message_content = user_input.strip()

    if uploaded_file:
        img = Image.open(uploaded_file).convert("RGBA")
        try:
            caption = generate_caption(img.convert("RGB"), st.session_state.processor, st.session_state.model)
        except Exception as e:
            caption = "Impossible de générer une description."
            st.error(f"Erreur BLIP: {e}")
        message_content = f"[IMAGE] {caption}"
        if user_input.strip():
            message_content += f"\n\nQuestion: {user_input.strip()}"
        msg_type = "image"
        image_b64 = image_to_base64(img.convert("RGB"))

        saved = add_message(conv_id, "user", message_content, msg_type, image_b64)
        if not saved:
            st.error("Impossible de sauvegarder le message image en DB.")
        else:
            st.session_state.messages_memory.append({"message_id": str(uuid.uuid4()), "sender": "user", "content": message_content, "type": msg_type, "image_data": image_b64, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})

        lower = user_input.lower()
        if any(k in lower for k in ["modifie", "modifier", "edit", "changer", "retouche", "retoucher"]):
            with st.spinner("Édition de l'image via Qwen..."):
                edited_img, info = edit_image_with_qwen(img.convert("RGB"), user_input.strip())
                if edited_img:
                    edited_b64 = image_to_base64(edited_img.convert("RGB"))
                    add_message(conv_id, "assistant", f"Image éditée selon la demande: {user_input.strip()}", "image", edited_b64)
                    st.success("Image éditée avec succès.")
                    st.image(edited_img, caption="Image éditée", use_column_width=True)
                    st.session_state.messages_memory.append({"message_id": str(uuid.uuid4()), "sender": "assistant", "content": f"Image éditée selon la demande: {user_input.strip()}", "type": "image", "image_data": edited_b64, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})
                else:
                    st.error(f"Échec édition : {info}")
            st.experimental_rerun()
        else:
            prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_content}"
            with st.chat_message("assistant"):
                ph = st.empty()
                ai_resp = get_ai_response(prompt)
                stream_response(ai_resp, ph)
            add_message(conv_id, "assistant", ai_resp, "text")
            st.session_state.messages_memory.append({"message_id": str(uuid.uuid4()), "sender": "assistant", "content": ai_resp, "type": "text", "image_data": None, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            st.experimental_rerun()
    else:
        if message_content:
            saved = add_message(conv_id, "user", message_content, "text", None)
            if not saved:
                st.error("Impossible de sauvegarder le message texte.")
            else:
                st.session_state.messages_memory.append({"message_id": str(uuid.uuid4()), "sender": "user", "content": message_content, "type": "text", "image_data": None, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})

            prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_content}"
            with st.chat_message("assistant"):
                ph = st.empty()
                ai_resp = get_ai_response(prompt)
                stream_response(ai_resp, ph)
            add_message(conv_id, "assistant", ai_resp, "text", None)
            st.session_state.messages_memory.append({"message_id": str(uuid.uuid4()), "sender": "assistant", "content": ai_resp, "type": "text", "image_data": None, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            st.experimental_rerun()

