import os
import uuid
from datetime import datetime
from supabase import create_client
import streamlit as st

# ==============================
# INITIALISATION SUPABASE
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
# UTILISATEURS
# ==============================
def create_user(email, name):
    user_id = str(uuid.uuid4())
    data = {
        "user_id": user_id,
        "email": clean_content(email),
        "name": clean_content(name),
        "created_at": datetime.now().isoformat()
    }
    resp = supabase.table("users").insert(data).execute()
    if resp.data:
        return {"id": user_id, "email": email, "name": name}
    return None

def get_user_by_email(email):
    resp = supabase.table("users").select("*").eq("email", email).execute()
    if resp.data:
        u = resp.data[0]
        return {"id": u["user_id"], "email": u["email"], "name": u.get("name", "")}
    return None

# ==============================
# CONVERSATIONS
# ==============================
def create_conversation(user_id, description="Nouvelle conversation"):
    conv_id = str(uuid.uuid4())
    data = {
        "conversation_id": conv_id,
        "user_id": user_id,
        "description": clean_content(description),
        "created_at": datetime.now().isoformat()
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
    msg = {
        "message_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender": sender,
        "content": clean_content(content),
        "type": msg_type,
        "image_data": image_data,
        "created_at": datetime.now().isoformat()
    }
    supabase.table("messages").insert(msg).execute()

def get_messages(conversation_id):
    resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()
    return resp.data or []

