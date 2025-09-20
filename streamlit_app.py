import streamlit as st
from PIL import Image
import io
import base64
import uuid
from datetime import datetime
import db  # ton module db.py qui utilise Supabase

# ==============================
# UTILITAIRES
# ==============================
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

# ==============================
# SESSION INIT
# ==============================
if "user" not in st.session_state:
    st.session_state.user = None
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# ==============================
# AUTHENTIFICATION
# ==============================
st.sidebar.title("🔐 Authentification")
if st.session_state.user is None:
    email = st.sidebar.text_input("📧 Email")
    if st.sidebar.button("Se connecter") and email.strip():
        # Récupérer l'utilisateur dans la DB
        user = db.get_user_by_email(email)
        if not user:
            user = db.create_user(email)
        if user and "user_id" in user:
            st.session_state.user = user
            st.success(f"✅ Connecté en tant que {user.get('email')}")
            st.experimental_rerun()
        else:
            st.error("❌ Impossible de créer ou récupérer l'utilisateur")
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email', 'Inconnu')}")
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = None
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

# ==============================
# SIDEBAR CONVERSATIONS
# ==============================
if st.session_state.user:
    st.sidebar.title("💬 Mes Conversations")
    user_id = st.session_state.user.get("user_id")
    if user_id:
        conversations = db.get_conversations(user_id)
    else:
        conversations = []

    # Bouton pour créer une nouvelle conversation
    if st.sidebar.button("➕ Nouvelle conversation") and user_id:
        new_conv = db.create_conversation(user_id)
        if new_conv:
            st.session_state.conversation = new_conv
            st.session_state.messages_memory = []
            st.experimental_rerun()

    # Sélecteur de conversation existante
    if conversations:
        conv_mapping = {f"{c['description']} ({c['created_at'][:16]})": c for c in conversations}
        selected_desc = st.sidebar.selectbox("Sélectionner une conversation:", list(conv_mapping.keys()))
        selected_conv = conv_mapping[selected_desc]

        # Charger la conversation si changement
        if (st.session_state.conversation is None) or (st.session_state.conversation["conversation_id"] != selected_conv["conversation_id"]):
            st.session_state.conversation = selected_conv
            st.session_state.messages_memory = db.get_messages(selected_conv["conversation_id"])

# ==============================
# CHAT PRINCIPAL
# ==============================
st.title("💬 Chat App")
if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation['description']}")

    # Affichage des messages existants
    for msg in st.session_state.messages_memory:
        role = "user" if msg["sender"] == "user" else "assistant"
        if msg["type"] == "image" and msg.get("image_data"):
            st.image(base64_to_image(msg["image_data"]), width=300)
        st.markdown(f"**{role}:** {msg['content']}")

    # Nouveau message
    new_msg = st.text_input("Votre message")
    uploaded_file = st.file_uploader("📷 Image", type=["png","jpg","jpeg"], key="upload_msg")
    if st.button("Envoyer") and (new_msg.strip() or uploaded_file):
        image_data = None
        if uploaded_file:
            img = Image.open(uploaded_file)
            image_data = image_to_base64(img)
            if not new_msg.strip():
                new_msg = "[IMAGE]"

        db.add_message(
            st.session_state.conversation["conversation_id"],
            "user",
            new_msg,
            "image" if image_data else "text",
            image_data=image_data
        )
        st.session_state.messages_memory.append({
            "sender": "user",
            "content": new_msg,
            "type": "image" if image_data else "text",
            "image_data": image_data
        })
        st.experimental_rerun()
else:
    st.info("Sélectionnez ou créez une conversation pour commencer à discuter.")

