import streamlit as st
from PIL import Image
import io
import base64
import db

# ==============================
# UTILITAIRES IMAGE
# ==============================
def image_to_base64(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

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
# AUTHENTIFICATION SIMPLIFIÉE
# ==============================
st.sidebar.title("🔐 Authentification")
if not st.session_state.user:
    email = st.sidebar.text_input("📧 Email")
    if st.sidebar.button("Se connecter") and email.strip():
        user = db.get_user_by_email(email)
        if not user:
            user = db.create_user(email)
        st.session_state.user = user
        st.success(f"Connecté en tant que {user['email']}")
        st.experimental_rerun()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user['email']}")
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
    user_id = st.session_state.user['user_id']
    conversations = db.get_conversations(user_id)

    if st.sidebar.button("➕ Nouvelle conversation"):
        new_conv = db.create_conversation(user_id)
        if new_conv:
            st.session_state.conversation = new_conv
            st.session_state.messages_memory = []
            st.experimental_rerun()

    if conversations:
        conv_mapping = {f"{c['description']} ({c['created_at'][:16]})": c for c in conversations}
        selected_desc = st.sidebar.selectbox("Sélectionner une conversation:", list(conv_mapping.keys()))
        selected_conv = conv_mapping[selected_desc]

        if (st.session_state.conversation is None) or (st.session_state.conversation["conversation_id"] != selected_conv["conversation_id"]):
            st.session_state.conversation = selected_conv
            st.session_state.messages_memory = db.get_messages(selected_conv["conversation_id"])

# ==============================
# CHAT
# ==============================
st.title("💬 Chat App")
if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation['description']}")

    # Affichage messages
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
