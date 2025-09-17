import streamlit as st
from PIL import Image
import pandas as pd
import io
from datetime import datetime
import uuid

# ======================
# Import DB
# ======================
try:
    import db
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False
    db = None

# ======================
# Config
# ======================
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
Your role is to help users by describing uploaded images with precision,
answering their questions clearly and helpfully.
Always answer naturally as Vision AI.
"""

# ======================
# Session State Init
# ======================
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "invité", "role": "user"}

if "conversation" not in st.session_state:
    st.session_state.conversation = None

if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# ======================
# Authentication Sidebar
# ======================
st.sidebar.title("🔐 Authentification")

user = st.session_state.user
logged_in = user.get("id") != "guest"

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
                        # Définir le rôle admin si nécessaire
                        if email.endswith("@admin.com"):
                            user_result["role"] = "admin"
                        else:
                            user_result["role"] = "user"
                        st.session_state.user = user_result
                        st.experimental_rerun()
                    else:
                        st.error("Email ou mot de passe invalide")
                else:
                    st.error("Remplis email & mot de passe")
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
    st.sidebar.success(f"✅ Connecté: {user.get('email')} ({user.get('role')})")
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "invité", "role": "user"}
        st.session_state.conversation = None
        st.experimental_rerun()

# ======================
# Tabs Menu
# ======================
tabs = ["Chat"]
if user.get("role") == "admin":
    tabs.append("Admin")
selected_tab = st.tabs(tabs)

# ======================
# Chat Tab
# ======================
with selected_tab[0]:
    st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)

    # Conversation management
    if DB_AVAILABLE and user.get("id") != "guest":
        if st.button("➕ Nouvelle conversation"):
            conv_id = db.create_conversation(user.get("id"))
            st.session_state.conversation = {"conversation_id": conv_id, "description": "Nouvelle discussion"}
            st.experimental_rerun()

        conversations = db.get_conversations(user.get("id"))
        options = ["Choisir une conversation..."] + [
            f"{c['description']} - {c['created_at']}" for c in conversations
        ]
        sel = st.selectbox("📋 Vos conversations:", options)
        if sel != "Choisir une conversation...":
            idx = options.index(sel) - 1
            st.session_state.conversation = conversations[idx]

    # Display messages
    display_msgs = []
    if st.session_state.conversation:
        conv_id = st.session_state.conversation["conversation_id"]
        db_msgs = db.get_messages(conv_id) or []
        display_msgs = db_msgs
    else:
        display_msgs = st.session_state.messages_memory

    if not display_msgs:
        st.chat_message("assistant").write("👋 Bonjour ! Je suis Vision AI. Comment puis-je vous aider ?")
    for m in display_msgs:
        role = "user" if m["sender"] in ["user", "user_api_request"] else "assistant"
        st.chat_message(role).write(m["content"])

    # User input
    user_input = st.chat_input("💭 Tapez votre message...")
    if user_input:
        st.chat_message("user").write(user_input)
        conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
        if DB_AVAILABLE and conv_id:
            db.add_message(conv_id, "user", user_input)
        else:
            st.session_state.messages_memory.append({"sender":"user","content":user_input,"created_at":None})

        # Simulated AI response
        ai_response = f"Réponse AI pour: {user_input}"
        st.chat_message("assistant").write(ai_response)
        if DB_AVAILABLE and conv_id:
            db.add_message(conv_id, "assistant", ai_response)
        else:
            st.session_state.messages_memory.append({"sender":"assistant","content":ai_response,"created_at":None})

    # CSV Export + Supabase Storage
    if display_msgs:
        df = pd.DataFrame(display_msgs)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_filename = f"conversation_{conv_id if conv_id else 'invite'}_{user['id']}.csv"

        st.download_button(
            "💾 Télécharger la conversation (CSV)",
            data=csv_buffer.getvalue(),
            file_name=csv_filename,
            mime="text/csv"
        )

        # Upload to Supabase Storage
        if DB_AVAILABLE:
            try:
                bucket_name = "user_csvs"
                db.supabase.storage.from_(bucket_name).upload(
                    path=csv_filename,
                    file=csv_buffer.getvalue(),
                    content_type="text/csv",
                    upsert=True
                )
            except Exception as e:
                st.warning(f"⚠ Impossible de sauvegarder le CSV sur Storage: {e}")

# ======================
# Admin Tab
# ======================
if user.get("role") == "admin":
    with selected_tab[1]:
        st.markdown("<h1 style='text-align:center; color:#FF6347;'>🛠 Admin Dashboard</h1>", unsafe_allow_html=True)

        if DB_AVAILABLE:
            users = db.supabase.table("users").select("*").execute().data
            st.subheader("📋 Utilisateurs enregistrés")
            st.dataframe(users)

            st.subheader("📂 Fichiers CSV utilisateurs")
            try:
                bucket_name = "user_csvs"
                files = db.supabase.storage.from_(bucket_name).list()
                for f in files:
                    file_name = f['name']
                    st.write(f"• {file_name}")
                    download_url = db.supabase.storage.from_(bucket_name).get_public_url(file_name).get('publicUrl')
                    st.markdown(f"[Télécharger]({download_url})", unsafe_allow_html=True)
            except Exception as e:
                st.warning(f"⚠ Impossible de récupérer les fichiers CSV: {e}")

