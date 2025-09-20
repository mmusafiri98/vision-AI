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
# UTILITAIRES
# ==============================
def clean_text(text):
    return str(text).replace("\x00","").strip() if text else ""

# ==============================
# USERS
# ==============================
def create_user(email: str):
    """Créer un utilisateur avec un UUID généré côté client"""
    user_id = str(uuid.uuid4())
    data = {
        "user_id": user_id,
        "email": clean_text(email),
        "created_at": datetime.utcnow().isoformat()
    }
    resp = supabase.table("users").insert(data).execute()
    if resp.data:
        return resp.data[0]
    return None

def get_user_by_email(email: str):
    resp = supabase.table("users").select("*").eq("email", email).execute()
    if resp.data:
        return resp.data[0]
    return None

# ==============================
# CONVERSATIONS
# ==============================
def create_conversation(user_id: str, description="Nouvelle conversation"):
    conv_id = str(uuid.uuid4())
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

def get_conversations(user_id: str):
    resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return resp.data or []

# ==============================
# MESSAGES
# ==============================
def add_message(conversation_id: str, sender: str, content: str, msg_type="text", image_data=None):
    data = {
        "conversation_id": conversation_id,
        "sender": sender,
        "content": clean_text(content),
        "type": msg_type,
        "image_data": image_data,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("messages").insert(data).execute()

def get_messages(conversation_id: str):
    resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", asc=True).execute()
    return resp.data or []


