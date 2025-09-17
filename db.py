import os
import uuid
from supabase import create_client
from datetime import datetime

# =======================
# INITIALISATION SUPABASE
# =======================
def get_supabase_client():
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_service_key:
            raise Exception("❌ Variables d'environnement Supabase manquantes")
        return create_client(supabase_url, supabase_service_key)
    except Exception as e:
        print(f"❌ Erreur connexion Supabase: {e}")
        return None

supabase = get_supabase_client()

# =======================
# UTILISATEURS
# =======================
def verify_user(email, password):
    """
    Vérifie l'utilisateur via Supabase Auth ou fallback table users
    """
    if not supabase:
        return None
    try:
        resp = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        if hasattr(resp, "user") and resp.user:
            return {
                "id": resp.user.id,
                "email": resp.user.email,
                "name": resp.user.user_metadata.get("name", email.split("@")[0])
            }
        # fallback table "users"
        data = supabase.table("users").select("*").eq("email", email).execute()
        if data.data and len(data.data) > 0:
            user = data.data[0]
            if user.get("password") == password:
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user.get("name", email.split("@")[0])
                }
        return None
    except Exception as e:
        print(f"❌ verify_user error: {e}")
        return None

def create_user(email, password, name=None):
    """
    Crée un utilisateur via Supabase Auth ou fallback table "users"
    """
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
        print(f"❌ create_user auth error, fallback insert: {e}")
        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": password,
            "name": name or email.split("@")[0],
            "created_at": datetime.now().isoformat()
        }
        resp = supabase.table("users").insert(user_data).execute()
        return bool(resp.data)

# =======================
# CONVERSATIONS
# =======================
def create_conversation(user_id=None, description=None):
    """
    Génère un nouvel ID conversation (UUID). 
    Pas de table conversation : on utilise messager.
    """
    conv_id = f"conv_{uuid.uuid4()}"
    return {
        "conversation_id": conv_id,
        "description": description or "Nouvelle discussion",
        "created_at": datetime.now().isoformat(),
        "user_id": user_id
    }

def get_conversations(user_id=None):
    """
    Retourne la liste des conversations distinctes (depuis messager)
    """
    if not supabase:
        return []
    try:
        query = supabase.table("messager").select("conversation_id, created_at")
        if user_id:
            query = query.eq("sender", user_id)
        resp = query.order("created_at", desc=True).execute()
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
        print(f"❌ get_conversations error: {e}")
        return []

# =======================
# MESSAGES
# =======================
def add_message(conversation_id, sender, content, message_type="text", status="sent", created_at=None):
    """
    Ajoute un message dans la table messager
    """
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
        resp = supabase.table("messager").insert(data).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"❌ add_message error: {e}")
        return False

def get_messages(conversation_id):
    """
    Récupère tous les messages d'une conversation donnée
    """
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
        print(f"❌ get_messages error: {e}")
        return []

# =======================
# TEST
# =======================
if __name__ == "__main__":
    conv = create_conversation(user_id="test_user")
    cid = conv["conversation_id"]

    add_message(cid, "user", "Bonjour 👋", "text", created_at="2025-09-17 10:00:00")
    add_message(cid, "assistant", "Salut ! Je suis Vision AI 😃", "text", created_at="2025-09-17 10:01:00")

    print(get_messages(cid))
    print(get_conversations("test_user"))


