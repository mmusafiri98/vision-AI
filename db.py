import os
import uuid
import re
from datetime import datetime
from dateutil import parser
import streamlit as st
from supabase import create_client
from streamlit_extras.switch_page_button import switch_page

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================

def get_supabase_client():
    """Initialise et retourne le client Supabase avec gestion d'erreur améliorée"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url:
            raise Exception("Variable SUPABASE_URL manquante")
        if not supabase_service_key:
            raise Exception("Variable SUPABASE_SERVICE_KEY manquante")

        if not supabase_url.startswith(('http://', 'https://')):
            raise Exception(f"SUPABASE_URL invalide: {supabase_url}")

        client = create_client(supabase_url, supabase_service_key)

        # Test rapide
        try:
            client.table("users").select("*").limit(1).execute()
            print("✅ Connexion Supabase réussie")
        except Exception as test_e:
            print(f"⚠️ Connexion Supabase mais test échoué: {test_e}")

        return client
    except Exception as e:
        st.error(f"❌ Erreur connexion Supabase: {e}")
        return None

# Initialiser le client global
supabase = get_supabase_client()

# ===================================================
# FONCTIONS UTILITAIRES
# ===================================================

def clean_message_content(content):
    if not content:
        return ""
    content = str(content).replace("\x00", "")
    content = content.replace("\\", "\\\\").replace("'", "''").replace('"', '""')
    if len(content) > 10000:
        content = content[:9950] + "... [contenu tronqué]"
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()

def safe_parse_datetime(date_str):
    try:
        if not date_str or date_str == "NULL":
            return datetime.now()
        return parser.isoparse(date_str)
    except Exception:
        return datetime.now()

def validate_uuid(uuid_string):
    try:
        uuid.UUID(str(uuid_string))
        return True
    except (ValueError, TypeError):
        return False

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    try:
        if not supabase:
            return None
        if not email or not password:
            return None

        # Auth Supabase
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if auth_response.user:
                user_data = {
                    "id": auth_response.user.id,
                    "email": auth_response.user.email,
                    "name": auth_response.user.user_metadata.get("name", email.split("@")[0])
                }

                # ✅ Redirection spéciale pour l’admin
                if (
                    user_data["email"] == "jessice34@gmail.com"
                    and user_data["id"] == "999fffa6-b296-4bb3-9f1e-bed764094517"
                ):
                    st.success("Connexion réussie ! Redirection vers la page admin...")
                    switch_page("streamlit_admin")

                return user_data
        except Exception as auth_e:
            print(f"⚠️ verify_user: Auth échoué {auth_e}")

        # Vérification simple via table (fallback)
        try:
            table_response = supabase.table("users").select("*").eq("email", email).execute()
            if table_response.data and len(table_response.data) > 0:
                user = table_response.data[0]
                if user.get("password") == password:
                    return {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name", email.split("@")[0])
                    }
        except Exception as table_e:
            print(f"❌ verify_user: Erreur table: {table_e}")

        return None
    except Exception as e:
        print(f"❌ verify_user: Exception {e}")
        return None

def create_user(email, password, name=None):
    try:
        if not supabase:
            return False
        if not email or not password:
            return False

        try:
            auth_response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name or email.split("@")[0]}
            })
            if auth_response.user:
                return True
        except Exception as auth_e:
            print(f"⚠️ create_user: Auth échoué {auth_e}")

        try:
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,
                "name": name or email.split("@")[0],
                "created_at": datetime.now().isoformat()
            }
            supabase.table("users").insert(user_data).execute()
            return True
        except Exception as table_e:
            print(f"❌ create_user: Erreur table: {table_e}")
        return False
    except Exception as e:
        print(f"❌ create_user: Exception {e}")
        return False

# ===================================================
# CONVERSATIONS
# ===================================================

def create_conversation(user_id, description):
    try:
        if not supabase or not user_id or not description:
            return None
        clean_description = clean_message_content(description)
        conversation_data = {
            "user_id": user_id,
            "description": clean_description,
            "created_at": datetime.now().isoformat()
        }
        response = supabase.table("conversations").insert(conversation_data).execute()
        if response.data:
            conv = response.data[0]
            return {
                "conversation_id": conv.get("conversation_id") or conv.get("id"),
                "description": conv.get("description", ""),
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
        return None
    except Exception as e:
        print(f"❌ create_conversation: {e}")
        return None

def get_conversations(user_id):
    try:
        if not supabase or not user_id:
            return []
        response = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        if not response.data:
            return []
        return [
            {
                "conversation_id": conv.get("conversation_id") or conv.get("id"),
                "description": conv.get("description", "Sans titre"),
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
            for conv in response.data if conv.get("conversation_id") or conv.get("id")
        ]
    except Exception as e:
        print(f"❌ get_conversations: {e}")
        return []

def delete_conversation(conversation_id):
    try:
        if not supabase or not conversation_id:
            return False
        supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
        conv_delete = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        return bool(conv_delete.data)
    except Exception as e:
        print(f"❌ delete_conversation: {e}")
        return False

# ===================================================
# MESSAGES
# ===================================================

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    try:
        if not supabase or not conversation_id or not content.strip():
            return False
        message_data = {
            "conversation_id": conversation_id,
            "sender": sender.strip() if sender else "unknown",
            "content": clean_message_content(content),
            "type": msg_type,
            "created_at": datetime.now().isoformat()
        }
        if image_data:
            message_data["image_data"] = image_data
        response = supabase.table("messages").insert(message_data).execute()
        return bool(response.data)
    except Exception as e:
        print(f"❌ add_message: {e}")
        return False

def get_messages(conversation_id):
    try:
        if not supabase or not conversation_id:
            return []
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        if not response.data:
            return []
        return [
            {
                "message_id": msg.get("message_id") or msg.get("id"),
                "sender": msg.get("sender", "unknown"),
                "content": msg.get("content", ""),
                "created_at": msg.get("created_at"),
                "type": msg.get("type", "text"),
                "image_data": msg.get("image_data")
            }
            for msg in response.data
        ]
    except Exception as e:
        print(f"❌ get_messages: {e}")
        return []

def add_messages_batch(conversation_id, messages_list):
    try:
        if not supabase or not conversation_id or not messages_list:
            return False
        cleaned_messages = []
        for msg in messages_list:
            content = clean_message_content(msg.get("content", ""))
            if content:
                data = {
                    "conversation_id": conversation_id,
                    "sender": msg.get("sender", "unknown").strip(),
                    "content": content,
                    "type": msg.get("type", "text"),
                    "created_at": msg.get("created_at") or datetime.now().isoformat()
                }
                if msg.get("image_data"):
                    data["image_data"] = msg.get("image_data")
                cleaned_messages.append(data)
        if not cleaned_messages:
            return False
        response = supabase.table("messages").insert(cleaned_messages).execute()
        return bool(response.data)
    except Exception as e:
        print(f"❌ add_messages_batch: {e}")
        return False

def delete_message(message_id):
    try:
        if not supabase or not message_id:
            return False
        response = supabase.table("messages").delete().eq("message_id", message_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"❌ delete_message: {e}")
        return False

# ===================================================
# STATS
# ===================================================

def get_database_stats():
    try:
        if not supabase:
            return
        users = supabase.table("users").select("*", count="exact").execute()
        convs = supabase.table("conversations").select("*", count="exact").execute()
        msgs = supabase.table("messages").select("*", count="exact").execute()
        st.write("📊 Statistiques")
        st.write(f"👥 Utilisateurs : {users.count if hasattr(users,'count') else len(users.data or [])}")
        st.write(f"💬 Conversations : {convs.count if hasattr(convs,'count') else len(convs.data or [])}")
        st.write(f"📨 Messages : {msgs.count if hasattr(msgs,'count') else len(msgs.data or [])}")
    except Exception as e:
        print(f"❌ get_database_stats: {e}")

# ===================================================
# INTERFACE LOGIN STREAMLIT
# ===================================================

st.set_page_config(page_title="Login", page_icon="🔑", layout="centered")

st.title("🔑 Connexion")

email = st.text_input("Email")
password = st.text_input("Mot de passe", type="password")

if st.button("Se connecter"):
    user = verify_user(email, password)
    if not user:
        st.error("❌ Identifiants incorrects")

