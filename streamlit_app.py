import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
You were created by Pepe Musafiri, an AI Engineer.
Your role is to help users with any task, from image analysis
to answering questions clearly.
Always answer naturally as Vision AI.

When you receive an image description starting with [IMAGE], you should:
1. Acknowledge the image
2. Provide detailed analysis
3. Answer any user questions
4. Be descriptive and helpful"""

# -------------------------
# Utility functions
# -------------------------
def image_to_base64(image):
    try:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    except:
        return None

def base64_to_image(img_str):
    try:
        img_bytes = base64.b64decode(img_str)
        return Image.open(io.BytesIO(img_bytes))
    except:
        return None

def load_conversation_with_messages(user_id):
    """Charge la dernière conversation et tous les messages depuis DB"""
    conv = None
    if user_id != "guest":
        try:
            convs = db.get_conversations(user_id)
            if convs:
                conv = convs[0]  # La plus récente
                conv_id = conv.get("conversation_id")
                msgs = db.get_messages(conv_id)
                st.session_state.messages_memory = [
                    {
                        "sender": m["sender"],
                        "content": m["content"],
                        "created_at": m.get("created_at"),
                        "type": m.get("type","text"),
                        "image_data": m.get("image_data", None)
                    } for m in msgs
                ]
            else:
                st.session_state.messages_memory = []
        except Exception as e:
            st.error(f"Erreur chargement conversation/messages: {e}")
            st.session_state.messages_memory = []
    else:
        st.session_state.messages_memory = []
    return conv

# -------------------------
# BLIP loader
# -------------------------
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Description indisponible"
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"Erreur génération: {e}"

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "conversation_loaded" not in st.session_state:
    st.session_state.conversation_loaded = False
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter LLaMA.")

# -------------------------
# AI functions
# -------------------------
def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible."
    try:
        resp = st.session_state.llama_client.predict(
            message=query,
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"❌ Erreur modèle: {e}"

def stream_response(text, placeholder):
    full_text = ""
    thinking_messages = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_messages:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.3)
    for char in text:
        full_text += char
        display_text = full_text + "**█**"
        placeholder.markdown(display_text)
        time.sleep(0.03 if char not in " .,!?;:" else 0.1)
    placeholder.markdown(full_text + " ✅")
    time.sleep(0.5)
    placeholder.markdown(full_text)

# -------------------------
# Auth
# -------------------------
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Se connecter"):
                user_result = db.verify_user(email, password)
                if user_result:
                    st.session_state.user = user_result
                    # Charger la dernière conversation + messages
                    last_conv = load_conversation_with_messages(user_result["id"])
                    st.session_state.conversation = last_conv
                    st.session_state.conversation_loaded = True
                    st.success("Connexion réussie ! Conversation restaurée.")
                    st.rerun()
                else:
                    st.error("Email ou mot de passe invalide")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.session_state.conversation = None
                st.session_state.messages_memory = []
                st.session_state.conversation_loaded = False
                st.rerun()
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        if st.button("✨ Créer mon compte"):
            if email_reg and name_reg and pass_reg:
                ok = db.create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Compte créé, connecte-toi.")
                else:
                    st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# Auto-chargement des conversations/messages
# -------------------------
if (st.session_state.user["id"] != "guest" and 
    not st.session_state.conversation_loaded):
    last_conv = load_conversation_with_messages(st.session_state.user["id"])
    st.session_state.conversation = last_conv
    st.session_state.conversation_loaded = True

# -------------------------
# Sidebar conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.rerun()
    convs = db.get_conversations(st.session_state.user["id"])
    if convs:
        current_conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
        options = ["Choisir une conversation..."]
        for c in convs:
            title = f"{c['description']} - {c['created_at']}"
            if c.get('conversation_id') == current_conv_id:
                title += " (Actuelle)"
            options.append(title)
        sel = st.sidebar.selectbox("Vos conversations:", options)
        if sel != "Choisir une conversation..." and not sel.endswith(" (Actuelle)"):
            idx = options.index(sel) - 1
            selected_conv = convs[idx]
            if st.session_state.conversation != selected_conv:
                st.session_state.conversation = selected_conv
                # Charger les messages de la conversation sélectionnée
                conv_id = selected_conv.get("conversation_id")
                msgs = db.get_messages(conv_id)
                st.session_state.messages_memory = [
                    {
                        "sender": m["sender"],
                        "content": m["content"],
                        "created_at": m.get("created_at"),
                        "type": m.get("type","text"),
                        "image_data": m.get("image_data", None)
                    } for m in msgs
                ]
                st.rerun()
    else:
        st.sidebar.info("Aucune conversation. Créez-en une.")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Créé par <b>Pepe Musafiri</b></p>", unsafe_allow_html=True)
if st.session_state.user:
    st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)
if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description', 'Conversation sans titre')
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title}</p>", unsafe_allow_html=True)

# -------------------------
# Affichage messages
# -------------------------
display_msgs = st.session_state.messages_memory.copy()
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        if m.get("type") == "image":
            if m.get("image_data"):
                img = base64_to_image(m["image_data"])
                if img:
                    st.image(img, caption="Image analysée", width=300)
                else:
                    st.write("📷 Image (non disponible)")
            if "[IMAGE]" in m["content"]:
                description = m["content"].replace("[IMAGE] ", "").split("\n\nQuestion/Demande")[0]
                st.write(f"*Description automatique: {description}*")
                if "Question/Demande de l'utilisateur:" in m["content"]:
                    user_question = m["content"].split("Question/Demande de l'utilisateur: ")[1]
                    st.write(f"**Question:** {user_question}")
        else:
            st.markdown(m["content"])

# -------------------------
# Nouveau message
# -------------------------
message_container = st.container()
with st.form(key="chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"])
    user_input = st.text_area("💭 Tapez votre message...", height=80)
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

if submit_button and (user_input or uploaded_file):
    if st.session_state.user["id"] != "guest" and not st.session_state.conversation:
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.session_state.messages_memory = []

    full_message = ""
    image_base64 = None
    image_caption = ""

    if uploaded_file:
        try:
            image = Image.open(uploaded_file)
            image_base64 = image_to_base64(image)
            with message_container:
                with st.chat_message("user"):
                    st.image(image, caption="Image uploadée pour analyse", width=300)
            image_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            full_message = f"[IMAGE] {image_caption}"
            if user_input.strip():
                full_message += f"\n\nQuestion/Demande de l'utilisateur: {user_input}"
                with message_container:
                    with st.chat_message("user"):
                        st.write(f"**Question:** {user_input}")
            # Sauvegarde immédiate DB
            conv_id = st.session_state.conversation.get("conversation_id")
            db.add_message(conv_id, "user", full_message, "image", image_data=image_base64)
            st.session_state.messages_memory.append({
                "sender": "user",
                "content": full_message,
                "created_at": None,
                "type": "image",
                "image_data": image_base64
            })
        except Exception as e:
            st.error(f"Erreur image: {e}")
            full_message = user_input if user_input else ""
    elif user_input.strip():
        full_message = user_input
        with message_container:
            with st.chat_message("user"):
                st.markdown(user_input)
        conv_id = st.session_state.conversation.get("conversation_id")
        db.add_message(conv_id, "user", user_input, "text")
        st.session_state.messages_memory.append({
            "sender": "user",
            "content": user_input,
            "created_at": None,
            "type": "text"
        })

    if full_message:
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
        with message_container:
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response_placeholder.write("Vision AI réfléchit... 🤔")
                resp = get_ai_response(prompt)
                stream_response(resp, response_placeholder)
        conv_id = st.session_state.conversation.get("conversation_id")
        db.add_message(conv_id, "assistant", resp, "text")
        st.session_state.messages_memory.append({
            "sender": "assistant",
            "content": resp,
            "created_at": None,
            "type": "text"
        })
        st.rerun()

# -------------------------
# Export CSV
# -------------------------
if display_msgs:
    st.markdown("---")
    with st.expander("📂 Exporter la conversation"):
        export_msgs = []
        for m in display_msgs:
            export_msgs.append({
                "sender": m["sender"],
                "content": m["content"],
                "created_at": m["created_at"],
                "type": m.get("type","text"),
                "has_image": "Oui" if m.get("image_data") else "Non"
            })
        df = pd.DataFrame(export_msgs)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        conv_id_for_file = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else "invite"
        st.download_button(
            "💾 Télécharger la conversation (CSV)",
            csv_buffer.getvalue(),
            file_name=f"conversation_{conv_id_for_file}.csv",
            mime="text/csv",
            use_container_width=True
        )


