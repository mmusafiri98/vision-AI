import os
from supabase import create_client
from datetime import datetime
import uuid

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
# USERS (via Supabase Auth)
# -------------------------
def verify_user(email, password):
    """Vérifie un utilisateur avec Supabase Auth"""
    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if res.user:
            # Récupération ou synchro du profil dans la table users
            user_id = res.user.id
            email = res.user.email
            name = res.user.user_metadata.get("name", email.split("@")[0])

            # Vérifie si déjà en DB, sinon insère
            existing = supabase.table("users").select("id").eq("id", user_id).execute()
            if not existing.data:
                supabase.table("users").insert({
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "created_at": now_iso()
                }).execute()

            return {"id": user_id, "email": email, "name": name}
        return None
    except Exception as e:
        print("Erreur verify_user:", e)
        return None

def create_user(email, password, name=None):
    """Crée un utilisateur via Supabase Auth + synchro profil DB"""
    try:
        res = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"name": name or email.split("@")[0]}}
        })
        if res.user:
            user_id = res.user.id
            supabase.table("users").insert({
                "id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "created_at": now_iso()
            }).execute()
            return True
        return False
    except Exception as e:
        print("Erreur create_user:", e)
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
        res = (supabase.table("conversations")
               .select("*")
               .eq("user_id", user_id)
               .order("created_at", desc=True)
               .execute())
        return res.data or []
    except Exception as e:
        print("Erreur get_conversations:", e)
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
        res = supabase.table("messager").insert(data).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur add_message:", e)
        return False

def get_messages(conversation_id):
    try:
        res = (supabase.table("messager")
               .select("*")
               .eq("conversation_id", conversation_id)
               .order("created_at", desc=True)
               .execute())
        return res.data or []
    except Exception as e:
        print("Erreur get_messages:", e)
        return []

# -------------------------
# DELETE
# -------------------------
def delete_conversation(conversation_id):
    try:
        supabase.table("messager").delete().eq("conversation_id", conversation_id).execute()
        res = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur delete_conversation:", e)
        return False

def delete_message(message_id):
    try:
        res = supabase.table("messager").delete().eq("message_id", message_id).execute()
        return bool(res.data)
    except Exception as e:
        print("Erreur delete_message:", e)
        return False
