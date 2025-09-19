import os
from supabase import create_client
from datetime import datetime
from dateutil import parser
import uuid
import re

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================

def get_supabase_client():
    """Initialise et retourne le client Supabase"""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_service_key:
        raise Exception("Variables d'environnement Supabase manquantes")

    return create_client(supabase_url, supabase_service_key)

# Instance globale
supabase = get_supabase_client()

# ===================================================
# UTILITAIRES
# ===================================================

def clean_message_content(content):
    """Nettoie le contenu d'un message"""
    if not content:
        return ""
    content = str(content).replace("\x00", "")
    if len(content) > 10000:
        content = content[:9950] + "... [tronqué]"
    return content

def now_iso():
    return datetime.utcnow().isoformat()

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    try:
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data and res.data[0]["password"] == password:
            u = res.data[0]
            return {"id": u["id"], "email": u["email"], "name": u.get("name")}
        return None
    except Exception as e:
        print("Erreur verify_user:", e)
        return None

def create_user(email, password, name=None):
    """Crée un utilisateur"""
    try:
        user_id = str(uuid.uuid4())
        data = {
            "id": user_id,
            "email": email,
            "password": password,  # ⚠️ en prod -> hash
            "name": name or email.split("@")[0],
            "created_at": now_iso()
        }
        res = supabase.table("users").insert(data).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur create_user:", e)
        return False

# ===================================================
# CONVERSATIONS
# ===================================================

def create_conversation(user_id, description="Nouvelle discussion"):
    try:
        data = {
            "user_id": user_id,
            "description": clean_message_content(description),
            "created_at": now_iso()
        }
        res = supabase.table("conversations").insert(data).execute()
        if res.data:
            conv = res.data[0]
            return {
                "conversation_id": conv["id"],   # ⚡ clé primaire = id
                "user_id": conv["user_id"],
                "description": conv["description"],
                "created_at": conv["created_at"]
            }
        return None
    except Exception as e:
        print("Erreur create_conversation:", e)
        return None

def get_conversations(user_id):
    try:
        res = (
            supabase.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [
            {
                "conversation_id": c["id"],
                "user_id": c["user_id"],
                "description": c.get("description", ""),
                "created_at": c.get("created_at")
            }
            for c in res.data
        ]
    except Exception as e:
        print("Erreur get_conversations:", e)
        return []

def delete_conversation(conversation_id):
    """Supprime une conversation et ses messages"""
    try:
        supabase.table("messager").delete().eq("conversation_id", conversation_id).execute()
        res = supabase.table("conversations").delete().eq("id", conversation_id).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur delete_conversation:", e)
        return False

# ===================================================
# MESSAGES (TABLE = messager)
# ===================================================

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    try:
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": clean_message_content(content),
            "type": msg_type,
            "image_data": image_data,
            "created_at": now_iso()
        }
        res = supabase.table("messager").insert(data).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur add_message:", e)
        return False

def get_messages(conversation_id):
    try:
        res = (
            supabase.table("messager")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
        return [
            {
                "message_id": m["id"],
                "conversation_id": m["conversation_id"],
                "sender": m["sender"],
                "content": m["content"],
                "type": m.get("type", "text"),
                "image_data": m.get("image_data"),
                "created_at": m.get("created_at")
            }
            for m in res.data
        ]
    except Exception as e:
        print("Erreur get_messages:", e)
        return []

def delete_message(message_id):
    try:
        res = supabase.table("messager").delete().eq("id", message_id).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur delete_message:", e)
        return False

# ===================================================
# DEBUG / TEST
# ===================================================

if __name__ == "__main__":
    print("=== TEST DB ===")

    # Créer utilisateur test
    user_email = "test@example.com"
    user_pwd = "123456"
    user = verify_user(user_email, user_pwd)
    if not user:
        create_user(user_email, user_pwd, "User Test")
        user = verify_user(user_email, user_pwd)

    print("User:", user)

    # Créer conversation
    conv = create_conversation(user["id"], "Ma première discussion")
    print("Conversation:", conv)

    # Ajouter message
    if conv:
        add_message(conv["conversation_id"], "user", "Hello world")
        add_message(conv["conversation_id"], "assistant", "Salut 👋", "text")

        msgs = get_messages(conv["conversation_id"])
        print("Messages:", msgs)
