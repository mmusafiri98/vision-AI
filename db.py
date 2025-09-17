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
# CONVERSATIONS
# =======================
def create_conversation(user_id=None, description=None):
    """
    Génère un nouvel ID de conversation (UUID).
    Pas de table dédiée, on utilise directement messager.
    """
    conv_id = f"conv_{uuid.uuid4()}"
    return {
        "conversation_id": conv_id,
        "description": description or "Nouvelle discussion",
        "created_at": datetime.now().isoformat()
    }

def get_conversations(user_id=None):
    """
    Retourne la liste des conversations distinctes depuis messager.
    """
    if not supabase:
        return []
    try:
        resp = (
            supabase.table("messager")
            .select("conversation_id, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        data = resp.data or []
        # Grouper par conversation_id
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
    Ajoute un message (user ou assistant) dans la table messager
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
            .order("created_at", desc=False)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        print(f"❌ get_messages error: {e}")
        return []

# =======================
# TEST LOCAL (Exemple)
# =======================
if __name__ == "__main__":
    # Création conversation
    conv = create_conversation()
    conv_id = conv["conversation_id"]

    # Ajout messages exemple
    add_message(conv_id, "user_api_request", "[IMAGE] the reception area in the lobby of the hotel", "image", created_at="2025-09-17 12:00:00")
    add_message(conv_id, "assistant", "Voici la description détaillée du hall d’hôtel ...", "text", created_at="2025-09-17 12:01:00")

    # Autre conversation
    conv2 = create_conversation()
    conv2_id = conv2["conversation_id"]
    add_message(conv2_id, "user", "come stai", "text", created_at="2025-09-17 12:05:00")
    add_message(conv2_id, "assistant", "Ciao! Sono Vision AI, sto funzionando ottimamente!", "text", created_at="2025-09-17 12:06:00")

    # Vérif
    print("Messages conv1:", get_messages(conv_id))
    print("Messages conv2:", get_messages(conv2_id))
    print("Toutes conversations:", get_conversations())

