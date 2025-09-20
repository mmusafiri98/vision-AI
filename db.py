import os
import uuid
from datetime import datetime
import streamlit as st
from supabase import create_client

# ==============================
# CONFIGURATION SUPABASE
# ==============================
def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        st.error("⚠️ Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes")
        return None
    return create_client(url, key)

supabase = get_supabase_client()

# ==============================
# UTILS
# ==============================
def clean_content(text):
    if not text:
        return ""
    return str(text).replace("\x00", "").strip()

# ==============================
# CONVERSATIONS
# ==============================
def create_conversation(user_id, description="Nouvelle conversation"):
    data = {
        "conversation_id": str(uuid.uuid4()),
        "user_id": user_id,
        "description": clean_content(description),
        "created_at": datetime.now().isoformat()
    }
    resp = supabase.table("conversations").insert(data).execute()
    return resp.data[0] if resp.data else None

def get_conversations(user_id):
    resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return resp.data or []

# ==============================
# MESSAGES
# ==============================
def add_message(conversation_id, sender, content, msg_type="text"):
    msg = {
        "conversation_id": conversation_id,
        "sender": sender,
        "content": clean_content(content),
        "type": msg_type,
        "created_at": datetime.now().isoformat()
    }
    supabase.table("messages").insert(msg).execute()

def get_messages(conversation_id):
    resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()
    return resp.data or []

# ==============================
# SESSION INIT
# ==============================
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}

if "conversation" not in st.session_state:
    st.session_state.conversation = None

if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

# ==============================
# AUTHENTIFICATION SIMPLIFIÉE
# ==============================
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    email = st.sidebar.text_input("📧 Email")
    if st.sidebar.button("Se connecter"):
        # Ici tu devrais utiliser supabase.auth.sign_in_with_password
        # Pour l'exemple, on simule la connexion
        st.session_state.user = {"id": "user_1", "email": email}
        st.success(f"Connecté en tant que {email}")
        st.experimental_rerun()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user['email']}")
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

# ==============================
# CONVERSATIONS SIDEBAR
# ==============================
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    conversations = get_conversations(st.session_state.user["id"])
    
    # Création nouvelle conversation
    if st.sidebar.button("➕ Nouvelle conversation"):
        new_conv = create_conversation(st.session_state.user["id"])
        if new_conv:
            st.session_state.conversation = new_conv
            st.session_state.messages_memory = []
            st.experimental_rerun()

    # Sélecteur de conversation
    if conversations:
        conv_mapping = {f"{c['description']} ({c['created_at'][:16]})": c for c in conversations}
        selected_desc = st.sidebar.selectbox("Sélectionner une conversation:", list(conv_mapping.keys()))
        selected_conv = conv_mapping[selected_desc]

        # Si conversation change ou pas encore chargée
        if (st.session_state.conversation is None) or (st.session_state.conversation["conversation_id"] != selected_conv["conversation_id"]):
            st.session_state.conversation = selected_conv
            st.session_state.messages_memory = get_messages(selected_conv["conversation_id"])

# ==============================
# CHAT
# ==============================
st.title("💬 Chat App")
if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation['description']}")

    # Affichage messages
    for msg in st.session_state.messages_memory:
        role = "user" if msg["sender"] == "user" else "assistant"
        st.markdown(f"**{role}:** {msg['content']}")

    # Nouveau message
    new_msg = st.text_input("Votre message")
    if st.button("Envoyer") and new_msg.strip():
        add_message(st.session_state.conversation["conversation_id"], "user", new_msg)
        st.session_state.messages_memory.append({
            "sender": "user",
            "content": new_msg
        })
        st.experimental_rerun()
else:
    st.info("Sélectionnez ou créez une conversation pour commencer à discuter.")


