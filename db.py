import os
from supabase import create_client
from datetime import datetime
import uuid
import base64

# -------------------------
# Connexion Supabase
# -------------------------
def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise Exception("Variables d'environnement Supabase manquantes")
    return create_client(url, key)

supabase = get_supabase_client()

# -------------------------
# Utilitaires
# -------------------------
def now_iso():
    return datetime.utcnow().isoformat()

def clean_text(text):
    if not text:
        return ""
    text = str(text).replace("\x00", "")
    if len(text) > 10000:
        text = text[:9950] + "... [tronqué]"
    return text

# -------------------------
# USERS
# -------------------------
def verify_user(email, password):
    try:
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data and res.data[0]["password"] == password:
            user = res.data[0]
            return {"id": user["id"], "email": user["email"], "name": user.get("name")}
        return None
    except:
        return None

def create_user(email, password, name=None):
    try:
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "email": email,
            "password": password,
            "name": name or email.split("@")[0],
            "created_at": now_iso()
        }
        res = supabase.table("users").insert(user_data).execute()
        return bool(res.data)
    except:
        return False

# -------------------------
# CONVERSATIONS
# -------------------------
def create_conversation(user_id, description="Nouvelle discussion"):
    try:
        conv_id = str(uuid.uuid4())
        data = {
            "conversation_id": conv_id,
            "user_id": user_id,
            "description": description,
            "created_at": now_iso()
        }
        res = supabase.table("conversations").insert(data).execute()
        if res.data:
            return data
        return None
    except Exception as e:
        print("Erreur create_conversation:", e)
        return None

def get_conversations(user_id):
    try:
        res = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return res.data or []
    except:
        return []

# -------------------------
# MESSAGES
# -------------------------
def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    try:
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": clean_text(content),
            "type": msg_type,
            "image_data": image_data,
            "created_at": now_iso()
        }
        res = supabase.table("messages").insert(data).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur add_message:", e)
        return False

def get_messages(conversation_id):
    try:
        res = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        return res.data or []
    except:
        return []

# -------------------------
# DELETE
# -------------------------
def delete_conversation(conversation_id):
    try:
        supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
        res = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        return bool(res.data)
    except:
        return False

def delete_message(message_id):
    try:
        res = supabase.table("messages").delete().eq("message_id", message_id).execute()
        return bool(res.data)
    except:
        return False
