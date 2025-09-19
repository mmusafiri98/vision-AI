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
    """Vérifie l'utilisateur avec Supabase Auth"""
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
    """Crée un utilisateur Supabase + entrée dans users_public"""
    if not supabase:
        return False
    try:
        # Création côté Auth
        resp = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or email.split("@")[0]}
        })
        if not hasattr(resp, "user") or not resp.user:
            return False

        # Sauvegarde côté table users_public
        user_data = {
            "id": resp.user.id,
            "email": email,
            "name": name or email.split("@")[0],
            "created_at": datetime.now().isoformat()
        }
        supabase.table("users_public").insert(user_data).execute()
        return True
    except Exception as e:
        print(f"Erreur create_user: {e}")
        return False

# =======================
# CONVERSATIONS
# =======================
def create_conversation(user_id=None, description=None):
    """Crée une nouvelle conversation et la sauvegarde en base"""
    if not supabase:
        return None
    try:
        conv_id = str(uuid.uuid4())
        data = {
            "id": conv_id,
            "description": description or "Nouvelle discussion",
            "created_at": datetime.now().isoformat(),
            "user_id": user_id
        }
        resp = supabase.table("conversations").insert(data).execute()
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        print(f"Erreur create_conversation: {e}")
        return None

def get_conversations(user_id=None):
    """Récupère les conversations d'un utilisateur (ou toutes si admin)"""
    if not supabase:
        return []
    try:
        query = supabase.table("conversations").select("*").order("created_at", desc=True)
        if user_id:
            query = query.eq("user_id", user_id)
        resp = query.execute()
        return resp.data or []
    except Exception as e:
        print(f"Erreur get_conversations: {e}")
        return []

# =======================
# MESSAGES
# =======================
def add_message(conversation_id, sender, content,
                message_type="text", status="sent",
                created_at=None, image_data=None):
    """Ajoute un message (texte ou image) lié à une conversation"""
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
        if image_data:
            data["image_data"] = image_data

        resp = supabase.table("messager").insert(data).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"Erreur add_message: {e}")
        return False

def get_messages(conversation_id):
    """Récupère tous les messages d'une conversation"""
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

