import streamlit as st
from PIL import Image
import time
import pandas as pd
import io
import uuid
from datetime import datetime

# Import DB module
try:
    import db
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False
    db = None

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
Help users by describing images precisely, answer clearly and helpfully."""

# -------------------------
# SESSION STATE INIT
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "invité", "role": "user"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# -------------------------
# SIDEBAR: AUTHENTICATION
# -------------------------
st.sidebar.title("🔐 Authentification")

if DB_AVAILABLE:
    user = st.session_state.user
    logged_in = user and user.get("id") != "guest"

    if not logged_in:
        tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
        with tab1:
            email = st.text_input("📧 Email", key="login_email")
            password = st.text_input("🔒 Mot de passe", type="password", key="login_password")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚪 Se connecter"):
                    if email and password:
                        user_result = db.verify_user(email, password)
                        if user_result:
                            st.session_state.user = user_result
                            st.experimental_rerun()
                        else:
                            st.error("Email ou mot de passe invalide")
            with col2:
                if st.button("👤 Mode invité"):
                    st.session_state.user = {"id": "guest", "email": "invité", "role": "user"}
                    st.experimental_rerun()
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
        if st.sidebar.button("🚪 Se déconnecter"):
            st.session_state.user = {"id": "guest", "email": "invité", "role": "user"}
            st.session_state.conversation = None
            st.experimental_rerun()
else:
    st.sidebar.info("Mode hors-ligne: DB indisponible.")

# -------------------------
# SIDEBAR: CONVERSATIONS
# -------------------------
if DB_AVAILABLE and st.session_state.user.get("role") != "admin":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            st.experimental_rerun()
        else:
            st.sidebar.error("Impossible de créer la conversation.")

    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            options = ["Choisir une conversation..."] + [
                f"{c['description']} - {c['created_at']}" for c in convs
            ]
            sel = st.sidebar.selectbox("📋 Vos conversations:", options)
            if sel != "Choisir une conversation...":
                idx = options.index(sel) - 1
                st.session_state.conversation = convs[idx]
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# MAIN UI
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

# Display messages
display_msgs = []
if DB_AVAILABLE and st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    try:
        db_msgs = db.get_messages(conv_id) or []
        for m in db_msgs:
            display_msgs.append({
                "sender": m.get("sender","assistant"),
                "content": m.get("content",""),
                "created_at": m.get("created_at")
            })
    except Exception:
        display_msgs = st.session_state.messages_memory.copy()
else:
    for m in st.session_state.messages_memory:
        display_msgs.append({
            "sender": m.get("sender"),
            "content": m.get("content"),
            "created_at": m.get("created_at")
        })

if not display_msgs:
    st.chat_message("assistant").write("👋 Bonjour ! Je suis Vision AI. Comment puis-je vous aider ?")
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    st.chat_message(role).write(m["content"])

# -------------------------
# Export CSV
# -------------------------
if display_msgs:
    st.markdown("---")
    st.subheader("📂 Exporter la conversation")
    df = pd.DataFrame(display_msgs)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="💾 Télécharger la conversation (CSV)",
        data=csv_buffer.getvalue(),
        file_name=f"conversation_{st.session_state.conversation.get('conversation_id','invite')}.csv",
        mime="text/csv"
    )

# -------------------------
# Input user
# -------------------------
user_input = st.chat_input("💭 Tapez votre message...")
if user_input:
    st.chat_message("user").write(user_input)

    conv_id = None
    if DB_AVAILABLE and st.session_state.conversation:
        conv_id = st.session_state.conversation.get("conversation_id")
        ok = db.add_message(conv_id, "user", user_input)
        if not ok:
            st.warning("Impossible d'ajouter le message user en DB.")
    else:
        st.session_state.messages_memory.append({"sender":"user","content":user_input,"created_at":None})

    # Simulated AI response (à remplacer par ton modèle BLIP/LLaMA)
    ai_response = f"🤖 Vision AI: J'ai reçu votre message: {user_input}"
    with st.chat_message("assistant"):
        ph = st.empty()
        full = ""
        for ch in ai_response:
            full += ch
            ph.write(full + "▋")
            time.sleep(0.01)
        ph.write(full)

    if DB_AVAILABLE and conv_id:
        ok = db.add_message(conv_id, "assistant", ai_response)
        if not ok:
            st.warning("Impossible d'ajouter la réponse assistant en DB.")
    else:
        st.session_state.messages_memory.append({"sender":"assistant","content":ai_response,"created_at":None})

