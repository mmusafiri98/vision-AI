import streamlit as st
from PIL import Image
import base64
import io
import uuid
import db  # ton module DB

# ===========================
# UTILITAIRES
# ===========================
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

# ===========================
# INITIALISATION SESSION
# ===========================
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# ===========================
# AUTHENTIFICATION
# ===========================
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    
    # ---------- Connexion ----------
    with tab1:
        email = st.text_input("📧 Email", key="login_email")
        password = st.text_input("🔒 Mot de passe", type="password", key="login_password")
        if st.button("🚪 Se connecter", key="login_button"):
            if not email or not password:
                st.error("⚠️ Veuillez remplir email et mot de passe")
            else:
                user_result = db.verify_user(email, password)
                if user_result:
                    st.session_state.user = user_result
                    st.success(f"✅ Connecté en tant que {user_result.get('name')}")
                    # Charger première conversation
                    convs = db.get_conversations(user_result["id"]) or []
                    if convs:
                        st.session_state.conversation = convs[0]
                        st.session_state.messages_memory = db.get_messages(convs[0]["conversation_id"]) or []
                    st.experimental_rerun()
                else:
                    st.error("❌ Email ou mot de passe invalide")
    
    # ---------- Inscription ----------
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        if st.button("✨ Créer mon compte", key="reg_button"):
            if email_reg and name_reg and pass_reg:
                ok = db.create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Compte créé, connecte-toi.")
                else:
                    st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("🚪 Se déconnecter", key="logout_button"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

# ===========================
# CONVERSATIONS
# ===========================
st.sidebar.title("💬 Mes Conversations")

# Nouvelle conversation
if st.sidebar.button("➕ Nouvelle conversation", key="new_conv"):
    conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
    if conv:
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.experimental_rerun()

# Liste des conversations
convs = db.get_conversations(st.session_state.user["id"]) or []
conv_mapping = {f"{c['description']} - {c['created_at'][:16]}": c for c in convs}
selected_display = st.sidebar.selectbox(
    "📋 Choisir une conversation:", list(conv_mapping.keys()),
    index=0 if not st.session_state.conversation else list(conv_mapping.values()).index(st.session_state.conversation),
    key="conv_selector"
)
selected_conv = conv_mapping[selected_display]
if st.session_state.conversation != selected_conv:
    st.session_state.conversation = selected_conv
    st.session_state.messages_memory = db.get_messages(selected_conv["conversation_id"]) or []

# ===========================
# HEADER
# ===========================
st.markdown(f"<h1 style='text-align:center;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
if st.session_state.conversation:
    st.markdown(f"<h3 style='text-align:center;'>{st.session_state.conversation.get('description')}</h3>", unsafe_allow_html=True)

# ===========================
# AFFICHAGE DES MESSAGES
# ===========================
st.markdown("---")
for m in st.session_state.messages_memory:
    role = "user" if m["sender"] == "user" else "assistant"
    with st.chat_message(role):
        if m.get("type") == "image" and m.get("image_data"):
            st.image(base64_to_image(m["image_data"]), width=300)
        st.markdown(m.get("content", ""))

# ===========================
# NOUVEAU MESSAGE
# ===========================
st.markdown("---")
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("💭 Tapez votre message...", key="chat_input", height=100)
    uploaded_file = st.file_uploader("📷 Image", type=["png","jpg","jpeg"], key="chat_file")
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

if submit_button and (user_input.strip() or uploaded_file):
    conv_id = st.session_state.conversation["conversation_id"]
    full_message = user_input.strip()
    image_base64 = None
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        image_base64 = image_to_base64(image)
        full_message = "[IMAGE] Image uploadée"

    # Sauvegarde DB
    db.add_message(conv_id, "user", full_message, "image" if image_base64 else "text", image_data=image_base64)
    
    # Ajout à la mémoire
    st.session_state.messages_memory.append({
        "sender": "user",
        "content": full_message,
        "type": "image" if image_base64 else "text",
        "image_data": image_base64
    })
    st.experimental_rerun()

