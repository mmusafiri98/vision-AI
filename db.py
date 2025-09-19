import os
import uuid
from supabase import create_client
from datetime import datetime

# =======================
# SUPABASE INIT
# =======================
def get_supabase_client():
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Variables Supabase manquantes")
        return create_client(url, key)
    except Exception as e:
        print(f"Erreur connexion Supabase: {e}")
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
        return None
    except Exception as e:
        print(f"Erreur verify_user: {e}")
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
        print(f"Erreur create_user: {e}")
        return False

# =======================
# CONVERSATIONS
# =======================
def create_conversation(user_id=None, description=None):
    conv_id = f"conv_{uuid.uuid4()}"
    return {
        "conversation_id": conv_id,
        "description": description or "Nouvelle discussion",
        "created_at": datetime.now().isoformat(),
        "user_id": user_id
    }

def get_conversations(user_id=None):
    if not supabase:
        return []
    try:
        query = (
            supabase.table("messager")
            .select("conversation_id, created_at, sender")
            .order("created_at", desc=True)
        )
        if user_id:
            query = query.eq("sender", user_id)
        resp = query.execute()
        data = resp.data or []

        convs = {}
        for row in data:
            cid = row["conversation_id"]
            if cid not in convs:
                convs[cid] = {
                    "conversation_id": cid,
                    "description": f"Conversation {cid}",
                    "created_at": row["created_at"]
                }
        return list(convs.values())
    except Exception as e:
        print(f"Erreur get_conversations: {e}")
        return []

# =======================
# MESSAGES
# =======================
def add_message(conversation_id, sender, content,
                message_type="text", status="sent",
                created_at=None, image_data=None):
    """Ajoute un message (texte ou image) dans la table messager"""
    if not supabase:
        return False
    try:
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "message_type": message_type,
            "status": status,
            "created_at": created_at or datetime.now().isoformat()
        }
        if image_data:  # ✅ ajout du support d'image
            data["image_data"] = image_data

        resp = supabase.table("messager").insert(data).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"Erreur add_message: {e}")
        return False

def get_messages(conversation_id):
    """Récupère tous les messages d'une conversation donnée"""
    if not supabase:
        return []
    try:
        resp = (
            supabase.table("messager")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception as e:
        print(f"Erreur get_messages: {e}")
        return []

