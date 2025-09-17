import os
import uuid
from datetime import datetime
from dateutil import parser
from supabase import create_client

# ===================================================
# SUPABASE CLIENT
# ===================================================
def get_supabase_client():
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_service_key:
            raise Exception("Variables d'environnement Supabase manquantes")
        return create_client(supabase_url, supabase_service_key)
    except Exception as e:
        print(f"❌ Erreur connexion Supabase: {e}")
        return None

supabase = get_supabase_client()

# ===================================================
# USERS
# ===================================================
def verify_user(email, password):
    try:
        if not supabase:
            return None
        # Vérification dans Supabase auth
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0])
                }
            return None
        except:
            # Fallback : table users
            response = supabase.table("users").select("*").eq("email", email).execute()
            if response.data and len(response.data) > 0:
                user = response.data[0]
                if user.get("password") == password:
                    return {"id": user["id"], "email": user["email"], "name": user.get("name", email.split("@")[0])}
            return None
    except Exception as e:
        print(f"❌ verify_user: {e}")
        return None

def create_user(email, password, name=None):
    try:
        if not supabase:
            return False
        # Générer UUID pour user si nécessaire
        user_id = str(uuid.uuid4())
        data = {
            "id": user_id,
            "email": email,
            "password": password,
            "name": name or email.split("@")[0],
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("users").insert(data).execute()
        return len(response.data) > 0 if response.data else False
    except Exception as e:
        print(f"❌ create_user: {e}")
        return False

# ===================================================
# CONVERSATIONS
# ===================================================
def create_conversation(user_id, description):
    try:
        if not supabase:
            return None
        # Vérifier utilisateur
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        if not user_check.data:
            print(f"❌ Utilisateur {user_id} n'existe pas")
            return None
        conversation_id = str(uuid.uuid4())
        data = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "description": description,
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("conversations").insert(data).execute()
        if response.data and len(response.data) > 0:
            conv = response.data[0]
            return {
                "conversation_id": conv["conversation_id"],
                "description": conv["description"],
                "created_at": parser.isoparse(conv["created_at"]),
                "user_id": conv["user_id"]
            }
        return None
    except Exception as e:
        print(f"❌ create_conversation: {e}")
        return None

def get_conversations(user_id):
    try:
        if not supabase:
            return []
        response = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        conversations = []
        for conv in response.data:
            conversations.append({
                "conversation_id": conv["conversation_id"],
                "description": conv["description"],
                "created_at": parser.isoparse(conv["created_at"]),
                "user_id": conv["user_id"]
            })
        return conversations
    except Exception as e:
        print(f"❌ get_conversations: {e}")
        return []

# ===================================================
# MESSAGES
# ===================================================
def add_message(conversation_id, sender, content):
    try:
        if not supabase:
            return False
        # Vérifier conversation
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            print(f"❌ Conversation {conversation_id} n'existe pas")
            return False
        message_id = str(uuid.uuid4())
        data = {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("messages").insert(data).execute()
        return response.data and len(response.data) > 0
    except Exception as e:
        print(f"❌ add_message: {e}")
        return False

def get_messages(conversation_id):
    try:
        if not supabase:
            return []
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()
        messages = []
        for msg in response.data:
            messages.append({
                "sender": msg["sender"],
                "content": msg["content"],
                "created_at": parser.isoparse(msg["created_at"])
            })
        return messages
    except Exception as e:
        print(f"❌ get_messages: {e}")
        return []
