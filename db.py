import os
from supabase import create_client
from datetime import datetime
from dateutil import parser
import uuid

# =======================
# INITIALISATION SUPABASE
# =======================
def get_supabase_client():
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_service_key:
            raise Exception("❌ Variables d'environnement Supabase manquantes")
        return create_client(supabase_url, supabase_service_key)
    except Exception as e:
        print(f"❌ Erreur connexion Supabase: {e}")
        return None

supabase = get_supabase_client()

# =======================
# UTILISATEURS
# =======================
def verify_user(email, password):
    if not supabase:
        return None
    try:
        resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if hasattr(resp, "user") and resp.user:
            return {
                "id": resp.user.id,
                "email": resp.user.email,
                "name": resp.user.user_metadata.get("name", email.split("@")[0])
            }
        # fallback table users
        data = supabase.table("users").select("*").eq("email", email).execute()
        if data.data and len(data.data) > 0:
            user = data.data[0]
            if user.get("password") == password:
                return {"id": user["id"], "email": user["email"], "name": user.get("name", email.split("@")[0])}
        return None
    except Exception as e:
        print(f"❌ verify_user error: {e}")
        return None

def create_user(email, password, name=None):
    if not supabase:
        return False
    try:
        resp = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or email.split("@")[0]}
        })
        return hasattr(resp, "user") and resp.user
    except Exception as e:
        print(f"❌ create_user auth error, fallback table insert: {e}")
        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": password,
            "name": name or email.split("@")[0],
            "created_at": datetime.now().isoformat()
        }
        resp = supabase.table("users").insert(user_data).execute()
        return bool(resp.data)

# =======================
# CONVERSATIONS
# =======================
def create_conversation(user_id, description):
    if not supabase:
        return None
    try:
        data = {"user_id": user_id, "description": description}
        resp = supabase.table("conversations").insert(data).execute()
        if resp.data and len(resp.data) > 0:
            conv = resp.data[0]
            conv.setdefault("conversation_id", str(uuid.uuid4()))
            return {
                "conversation_id": conv["conversation_id"],
                "description": conv["description"],
                "created_at": parser.isoparse(conv.get("created_at", datetime.now().isoformat())),
                "user_id": conv["user_id"]
            }
        return None
    except Exception as e:
        print(f"❌ create_conversation error: {e}")
        return None

def get_conversations(user_id):
    if not supabase:
        return []
    try:
        resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        conversations = []
        for c in resp.data:
            conversations.append({
                "conversation_id": c.get("conversation_id", str(uuid.uuid4())),
                "description": c["description"],
                "created_at": parser.isoparse(c.get("created_at", datetime.now().isoformat())),
                "user_id": c["user_id"]
            })
        return conversations
    except Exception as e:
        print(f"❌ get_conversations error: {e}")
        return []

# =======================
# MESSAGES
# =======================
def add_message(conversation_id, sender, content):
    if not supabase:
        return False
    try:
        data = {"conversation_id": conversation_id, "sender": sender, "content": content, "created_at": datetime.now().isoformat()}
        resp = supabase.table("messages").insert(data).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"❌ add_message error: {e}")
        return False

def get_messages(conversation_id):
    if not supabase:
        return []
    try:
        resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        messages = []
        for m in resp.data:
            messages.append({
                "sender": m["sender"],
                "content": m["content"],
                "created_at": parser.isoparse(m.get("created_at", datetime.now().isoformat()))
            })
        return messages
    except Exception as e:
        print(f"❌ get_messages error: {e}")
        return []
