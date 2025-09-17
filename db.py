import os
from supabase import create_client
from datetime import datetime

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================

def get_supabase_client():
    """Initialise et retourne le client Supabase"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_service_key:
            raise Exception("Variables d'environnement Supabase manquantes")

        client = create_client(supabase_url, supabase_service_key)
        return client
    except Exception as e:
        print(f"❌ Erreur connexion Supabase: {e}")
        return None

# Instance globale
supabase = get_supabase_client()

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    try:
        if not supabase:
            return None

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user:
            return {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name", email.split("@")[0])
            }
        return None

    except Exception as e:
        print(f"❌ Erreur verify_user: {e}")
        return None


def create_user(email, password, name=None):
    """Crée un nouvel utilisateur"""
    try:
        if not supabase:
            return False

        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or email.split("@")[0]}
        })

        return response.user is not None

    except Exception as e:
        print(f"❌ Erreur create_user: {e}")
        return False

# ===================================================
# CONVERSATIONS
# ===================================================

def create_conversation(user_id, description):
    """Crée une nouvelle conversation"""
    try:
        if not supabase:
            return None

        data = {
            "user_id": user_id,
            "description": description
        }

        response = supabase.table("conversations").insert(data).select("*").execute()
        print("DEBUG insert conversation:", response)

        if response.data and len(response.data) > 0:
            conv = response.data[0]
            return {
                "conversation_d": conv["conversation_id"],
                "description": conv["description"],
                "created_at": datetime.fromisoformat(conv["created_at"]),
                "user_id": conv["user_id"]
            }
        return None

    except Exception as e:
        print(f"❌ Erreur create_conversation: {e}")
        return None


def get_conversations(user_id):
    """Récupère toutes les conversations d'un utilisateur"""
    try:
        if not supabase:
            return []

        response = (
            supabase.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        conversations = []
        for conv in response.data:
            conversations.append({
                "conversation_id": conv["conversation_id"],
                "description": conv["descritpion"],
                "created_at": datetime.fromisoformat(conv["created_at"]),
                "user_id": conv["user_id"]
            })
        return conversations

    except Exception as e:
        print(f"❌ Erreur get_conversations: {e}")
        return []

# ===================================================
# MESSAGES
# ===================================================

def add_message(conversation_id, sender, content):
    """Ajoute un message dans une conversation"""
    try:
        if not supabase:
            return False

        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content
        }

        response = supabase.table("messages").insert(data).select("*").execute()
        print("DEBUG insert message:", response)

        return len(response.data) > 0

    except Exception as e:
        print(f"❌ Erreur add_message: {e}")
        return False


def get_messages(conversation_id):
    """Récupère les messages d'une conversation"""
    try:
        if not supabase:
            return []

        response = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .execute()
        )

        messages = []
        for msg in response.data:
            messages.append({
                "sender": msg["sender"],
                "content": msg["content"],
                "created_at": datetime.fromisoformat(msg["created_at"])
            })
        return messages

    except Exception as e:
        print(f"❌ Erreur get_messages: {e}")
        return []

# ===================================================
# TEST
# ===================================================

if __name__ == "__main__":
    print("🧪 Test module db.py...")

    if not supabase:
        print("❌ Supabase non initialisé. Vérifie SUPABASE_URL et SUPABASE_SERVICE_KEY")
    else:
        # Test simple
        conv = create_conversation("test-user-1", "Nouvelle conversation de test")
        if conv:
            print("✅ Conversation créée:", conv)

            msg_ok = add_message(conv["id"], "user", "Bonjour, ceci est un test")
            if msg_ok:
                print("✅ Message ajouté avec succès")

                msgs = get_messages(conv["conversation_id"])
                print("📩 Messages récupérés:", msgs)
            else:
                print("❌ Erreur ajout message")
        else:
            print("❌ Erreur création conversation")

