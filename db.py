import os
import uuid
from datetime import datetime
import streamlit as st
from supabase import create_client, Client

# ==============================
# CONFIGURATION SUPABASE
# ==============================
def get_supabase_client() -> Client:
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
def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    msg = {
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


