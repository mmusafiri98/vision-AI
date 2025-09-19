import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # tuo modulo DB

# -------------------------
# Config
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
# Utility functions
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

def load_conversation_messages(conv_id):
    """Carica tutti i messaggi di una conversazione dal DB"""
    return db.get_messages(conv_id) or []

# -------------------------
# BLIP loader
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
# AI functions
# -------------------------
def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponibile."
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
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "**█**")
        time.sleep(0.01 if char == ' ' else 0.03)
    placeholder.markdown(full_text + " ✅")

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter LLaMA.")

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
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Email ou mot de passe invalide")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
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
        st.rerun()

# -------------------------
# Sidebar Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.rerun()
    try:
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
                    st.rerun()
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)
if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description', 'Conversation sans titre')
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title}</p>", unsafe_allow_html=True)

# -------------------------
# Carica messaggi dal DB
# -------------------------
display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    display_msgs = load_conversation_messages(conv_id)

# -------------------------
# Visualizza messaggi
# -------------------------
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        if m.get("type") == "image" and m.get("image_data"):
            img = base64_to_image(m["image_data"])
            if img:
                st.image(img, width=300)
            st.write(m["content"])
        else:
            st.markdown(m["content"])

# -------------------------
# Nuovo messaggio
# -------------------------
message_container = st.container()

with st.form(key="chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"])
    user_input = st.text_area(
        "💭 Tapez votre message...", 
        placeholder="Posez votre question ou décrivez ce que vous voulez que j'analyse dans l'image...",
        height=80
    )
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

if submit_button and (user_input or uploaded_file):
    conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
    full_message = ""
    image_base64 = None

    # Gestione immagine
    if uploaded_file:
        image = Image.open(uploaded_file)
        image_base64 = image_to_base64(image)
        image_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        full_message = f"[IMAGE] {image_caption}"
        if user_input.strip():
            full_message += f"\n\nQuestion: {user_input}"
    else:
        full_message = user_input

    # Salva messaggio utente nel DB
    if conv_id:
        db.add_message(conv_id, "user", full_message, "image" if image_base64 else "text", image_data=image_base64)
        display_msgs.append({
            "sender": "user",
            "content": full_message,
            "type": "image" if image_base64 else "text",
            "image_data": image_base64
        })

    # Mostra messaggio utente subito
    with message_container:
        with st.chat_message("user"):
            if image_base64:
                st.image(base64_to_image(image_base64), width=300)
            st.markdown(full_message)

    # Risposta AI
    if full_message:
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
        with message_container:
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response_placeholder.write("Vision AI réfléchit... 🤔")
                resp = get_ai_response(prompt)
                stream_response(resp, response_placeholder)
        if conv_id:
            db.add_message(conv_id, "assistant", resp, "text")
            display_msgs.append({
                "sender": "assistant",
                "content": resp,
                "type": "text",
                "image_data": None
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

