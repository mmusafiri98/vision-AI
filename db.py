import os
from supabase import create_client
from datetime import datetime
import uuid

# ======================
# SUPABASE CONFIG
# ======================
def get_supabase_client():
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Variables d'environnement Supabase manquantes")
        return create_client(url, key)
    except Exception as e:
        print(f"❌ Erreur Supabase: {e}")
        return None

supabase = get_supabase_client()

# ======================
# USERS
# ======================
def verify_user(email, password):
    if not supabase: return None
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            return {"id": response.user.id, "email": response.user.email, "name": response.user.user_metadata.get("name", email.split("@")[0])}
        return None
    except:
        # fallback simple pour test
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data and res.data[0]["password"] == password:
            return {"id": res.data[0]["id"], "email": res.data[0]["email"], "name": res.data[0].get("name", email.split("@")[0])}
        return None

def create_user(email, password, name=None):
    if not supabase: return False
    try:
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or email.split("@")[0]}
        })
        if response.user: return True
    except:
        # fallback insertion directe
        data = {"id": str(uuid.uuid4()), "email": email, "password": password, "name": name or email.split("@")[0], "created_at": datetime.utcnow().isoformat()}
        res = supabase.table("users").insert(data).execute()
        return bool(res.data)
    return False

# ======================
# CONVERSATIONS
# ======================
def create_conversation(user_id, description):
    if not supabase: return None
    # créer un conversation_id
    conv_id = str(uuid.uuid4())
    data = {"conversation_id": conv_id, "user_id": user_id, "description": description, "created_at": datetime.utcnow().isoformat()}
    res = supabase.table("conversations").insert(data).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None

def get_conversations(user_id):
    if not supabase: return []
    res = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data or []

# ======================
# MESSAGES
# ======================
def add_message(conversation_id, sender, content):
    if not supabase: return False
    data = {"conversation_id": conversation_id, "sender": sender, "content": content, "created_at": datetime.utcnow().isoformat()}
    res = supabase.table("messages").insert(data).execute()
    return bool(res.data)

def get_messages(conversation_id):
    if not supabase: return []
    res = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    return res.data or []

