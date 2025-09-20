# db.py
import os
import uuid
from datetime import datetime
from supabase import create_client

# ==============================
# CONFIG SUPABASE
# ==============================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# UTILS
# ==============================
def clean_text(text):
    if not text:
        return ""
    return str(text).replace("\x00", "").strip()

def generate_uuid():
    return str(uuid.uuid4())

# ==============================
# USERS
# ==============================
def create_user(email):
    user_id = generate_uuid()  # UUID valide
    data = {
        "user_id": user_id,
        "email": clean_text(email),
        "created_at": datetime.utcnow().isoformat()
    }
    resp = supabase.table("users").insert(data).execute()
    if resp.data:
        return resp.data[0]
    return None

def get_user_by_email(email):
    resp = supabase.table("users").select("*").eq("email", email).limit(1).execute()
    if resp.data:
        return resp.data[0]
    return None

# ==============================
# CONVERSATIONS
# ==============================
def create_conversation(user_id, description="Nouvelle conversation"):
    conv_id = generate_uuid()
    data = {
        "conversation_id": conv_id,
        "user_id": user_id,
        "description": clean_text(description),
        "created_at": datetime.utcnow().isoformat()
    }
    resp = supabase.table("conversations").insert(data).execute()
    if resp.data:
        return resp.data[0]
    return None

def get_conversations(user_id):
    resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return resp.data or []

# ==============================
# MESSAGES
# ==============================
def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    msg_id = generate_uuid()
    data = {
        "message_id": msg_id,
        "conversation_id": conversation_id,
        "sender": sender,
        "content": clean_text(content),
        "type": msg_type,
        "image_data": image_data,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("messages").insert(data).execute()

def get_messages(conversation_id):
    resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()
    return resp.data or []


