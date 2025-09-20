import os
import uuid
import re
from datetime import datetime
from dateutil import parser
import streamlit as st
from supabase import create_client

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================

def get_supabase_client():
    """Initialise et retourne le client Supabase"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_service_key:
            raise Exception("⚠️ Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes")

        if not supabase_url.startswith(("http://", "https://")):
            raise Exception(f"SUPABASE_URL invalide: {supabase_url}")

        client = create_client(supabase_url, supabase_service_key)

        # test rapide
        client.table("users").select("*").limit(1).execute()
        print("✅ Connexion Supabase réussie")
        return client

    except Exception as e:
        st.error(f"❌ Erreur connexion Supabase: {e}")
        return None


supabase = get_supabase_client()

# ===================================================
# UTILS
# ===================================================

def clean_message_content(content):
    if not content:
        return ""
    content = str(content).replace("\x00", "").strip()
    if len(content) > 10000:
        content = content[:9950] + "... [tronqué]"
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content

def safe_parse_datetime(date_str):
    try:
        return parser.isoparse(date_str) if date_str else datetime.now()
    except Exception:
        return datetime.now()

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    try:
        if not supabase:
            return None

        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if auth_response.user:
            return {
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "name": auth_response.user.user_metadata.get("name", email.split("@")[0])
            }

        return None
    except Exception as e:
        print(f"❌ verify_user: {e}")
        return None


# ===================================================
# CONVERSATIONS
# ===================================================

def create_conversation(user_id, description="Nouvelle discussion"):
    try:
        conv_data = {
            "conversation_id": str(uuid.uuid4()),
            "user_id": user_id,
            "description": clean_message_content(description),
            "created_at": datetime.now().isoformat()
        }
        response = supabase.table("conversations").insert(conv_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ create_conversation: {e}")
        return None

def get_conversations(user_id):
    try:
        response = (
            supabase.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"❌ get_conversations: {e}")
        return []

# ===================================================
# MESSAGES
# ===================================================

def add_message(conversation_id, sender, content):
    try:
        msg = {
            "message_id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "sender": sender,
            "content": clean_message_content(content),
            "created_at": datetime.now().isoformat(),
            "type": "text",
        }
        supabase.table("messages").insert(msg).execute()
        return True
    except Exception as e:
        print(f"❌ add_message: {e}")
        return False

def get_messages(conversation_id):
    try:
        response = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"❌ get_messages: {e}")
        return []

# ===================================================
# STREAMLIT UI
# ===================================================

def init_session():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

def show_login():
    st.subheader("Connexion")
    email = st.text_input("Email")
    pwd = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        user = verify_user(email, pwd)
        if user:
            st.session_state.user = user
            st.success(f"Bienvenue {user['name']}")
        else:
            st.error("Email ou mot de passe incorrect")

def show_conversations():
    user_id = st.session_state.user["id"]
    conversations = get_conversations(user_id)

    st.sidebar.subheader("Vos conversations")
    for conv in conversations:
        if st.sidebar.button(conv["description"], key=conv["conversation_id"]):
            st.session_state.conversation_id = conv["conversation_id"]

    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = create_conversation(user_id)
        if conv:
            st.session_state.conversation_id = conv["conversation_id"]

def show_chat():
    conv_id = st.session_state.conversation_id
    if not conv_id:
        st.info("Sélectionnez ou créez une conversation.")
        return

    messages = get_messages(conv_id)
    for msg in messages:
        st.write(f"**{msg['sender']}**: {msg['content']}")

    user_input = st.text_input("Votre message")
    if st.button("Envoyer"):
        if user_input.strip():
            add_message(conv_id, "user", user_input)
            st.experimental_rerun()

# ===================================================
# MAIN
# ===================================================

def main():
    st.title("💬 Chat App avec Supabase")
    init_session()

    if not st.session_state.user:
        show_login()
    else:
        show_conversations()
        show_chat()


if __name__ == "__main__":
    main()

