import os
from supabase import create_client
from datetime import datetime
import uuid

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise Exception("Variables d'environnement Supabase manquantes")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ===================================================
# FONCTIONS UTILISATEUR
# ===================================================
def create_user(email, name=None):
    """Créer un utilisateur test (ou récupère existant)"""
    user_data = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name or email.split("@")[0],
        "created_at": datetime.utcnow().isoformat()
    }
    # Vérifie si l'utilisateur existe déjà
    existing = supabase.table("users").select("*").eq("email", email).execute()
    if existing.data:
        return existing.data[0]["id"]
    
    res = supabase.table("users").insert(user_data).execute()
    if res.data:
        return res.data[0]["id"]
    return None

# ===================================================
# FONCTIONS CONVERSATION
# ===================================================
def create_conversation(user_id, description):
    """Créer une conversation pour un utilisateur"""
    conv_data = {
        "conversation_id": str(uuid.uuid4()),
        "user_id": user_id,
        "description": description,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("conversations").insert(conv_data).execute()
    if res.data:
        return res.data[0]["conversation_id"]
    return None

def add_message(conversation_id, sender, content):
    """Ajouter un message dans une conversation"""
    msg_data = {
        "message_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender": sender,
        "content": content,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("messages").insert(msg_data).execute()
    return bool(res.data)

# ===================================================
# EXEMPLE D'UTILISATION AVEC UN MODELE AI
# ===================================================
def handle_user_query(user_email, user_query, model_response):
    """
    Cette fonction simule la réception d'une requête utilisateur et
    la réponse d'un modèle AI, puis les sauvegarde dans Supabase.
    """
    # Crée ou récupère l'utilisateur
    user_id = create_user(user_email)
    
    # Crée une conversation automatique
    conv_id = create_conversation(user_id, "Conversation automatique")
    
    # Ajoute le message utilisateur
    add_message(conv_id, "user", user_query)
    
    # Ajoute la réponse du modèle AI
    add_message(conv_id, "assistant", model_response)
    
    print(f"✅ Conversation enregistrée pour {user_email} (ID: {conv_id})")

# ===================================================
# TEST
# ===================================================
if __name__ == "__main__":
    # Simule une interaction
    handle_user_query(
        user_email="testuser@example.com",
        user_query="Bonjour, peux-tu me décrire cette image ?",
        model_response="Bien sûr ! L'image contient un chat assis sur un tapis rouge."
    )

