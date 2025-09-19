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
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_service_key:
            raise Exception("Variables d'environnement Supabase manquantes")

        client = create_client(supabase_url, supabase_service_key)
        return client
    except Exception as e:
        print(f"Erreur connexion Supabase: {e}")
        return None

supabase = get_supabase_client()

# ===================================================
# FONCTIONS UTILITAIRES
# ===================================================

def clean_message_content(content):
    """Nettoie le contenu d'un message pour l'insertion en base"""
    if not content:
        return ""
    content = str(content)
    content = content.replace("\x00", "")
    content = content.replace("\\", "\\\\")
    content = content.replace("'", "''")
    content = content.replace('"', '""')
    if len(content) > 10000:
        content = content[:9950] + "... [contenu tronqué]"
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content

def safe_parse_datetime(date_str):
    """Parse une date de manière sécurisée"""
    try:
        if not date_str or date_str == "NULL":
            return datetime.now()
        return parser.isoparse(date_str)
    except:
        return datetime.now()

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    try:
        if not supabase:
            return None
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0])
                }
            return None
        except Exception:
            # Fallback direct table check
            response = supabase.table("users").select("*").eq("email", email).execute()
            if response.data and len(response.data) > 0:
                user = response.data[0]
                if user.get("password") == password:
                    return {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name", email.split("@")[0])
                    }
            return None
    except Exception as e:
        print(f"Erreur verify_user: {e}")
        return None

def create_user(email, password, name=None):
    """Crée un nouvel utilisateur"""
    try:
        if not supabase:
            return False
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name or email.split("@")[0]}
            })
            return response.user is not None
        except Exception:
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,  # ⚠️ en production, hasher le mot de passe
                "name": name or email.split("@")[0],
                "created_at": datetime.now().isoformat()
            }
            response = supabase.table("users").insert(user_data).execute()
            return bool(response.data and len(response.data) > 0)
    except Exception as e:
        print(f"Erreur create_user: {e}")
        return False

# ===================================================
# CONVERSATIONS
# ===================================================

def create_conversation(user_id, description):
    """Crée une conversation"""
    try:
        if not supabase:
            return None
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        if not user_check.data:
            print(f"Utilisateur {user_id} n'existe pas")
            return None
        clean_description = clean_message_content(description)
        data = {"user_id": user_id, "description": clean_description, "created_at": datetime.now().isoformat()}
        response = supabase.table("conversations").insert(data).execute()
        if hasattr(response, 'error') and response.error:
            print(f"Erreur Supabase conversations: {response.error}")
            return None
        if response.data and len(response.data) > 0:
            conv = response.data[0]
            conv_id = conv.get("conversation_id") or conv.get("id")
            if not conv_id:
                print(f"Aucun ID trouvé dans la réponse. Clés disponibles: {list(conv.keys())}")
                return None
            return {
                "conversation_id": conv_id,
                "description": conv["description"],
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
        print("Aucune donnée retournée après insertion conversation")
        return None
    except Exception as e:
        print(f"Erreur create_conversation: {e}")
        import traceback; traceback.print_exc()
        return None

def get_conversations(user_id):
    try:
        if not supabase:
            return []
        response = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        conversations = []
        for conv in response.data:
            conv_id = conv.get("conversation_id") or conv.get("id")
            if conv_id:
                conversations.append({
                    "conversation_id": conv_id,
                    "description": conv.get("description", "Conversation sans titre"),
                    "created_at": conv.get("created_at"),
                    "user_id": conv["user_id"]
                })
        return conversations
    except Exception as e:
        print(f"Erreur get_conversations: {e}")
        import traceback; traceback.print_exc()
        return []

def delete_conversation(conversation_id):
    try:
        if not supabase:
            return False
        supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
        conv_delete = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        return bool(conv_delete.data and len(conv_delete.data) > 0)
    except Exception as e:
        print(f"Erreur delete_conversation: {e}")
        return False

# ===================================================
# MESSAGES
# ===================================================

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    """
    Ajoute un message dans une conversation avec gestion image_data.
    Retourne True si succès, False sinon.
    """
    try:
        if not supabase:
            print("❌ Supabase non connecté")
            return False
        if not conversation_id:
            print("❌ conversation_id manquant")
            return False

        sender = str(sender).strip() if sender else "unknown"
        content = clean_message_content(content)
        msg_type = msg_type or "text"

        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            print(f"❌ Conversation {conversation_id} n'existe pas")
            return False

        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "created_at": datetime.now().isoformat()
        }
        if image_data:
            data["image_data"] = image_data

        print("DEBUG add_message - données envoyées:", data)
        response = supabase.table("messages").insert(data).execute()
        print("DEBUG add_message - réponse Supabase:", response)

        if hasattr(response, 'error') and response.error:
            print("❌ Erreur Supabase messages:", response.error)
            return False
        if not response.data or len(response.data) == 0:
            print("⚠️ Insertion vide, message non sauvegardé")
            return False
        print("✅ Message ajouté avec succès")
        return True
    except Exception as e:
        print(f"❌ Exception add_message: {e}")
        import traceback; traceback.print_exc()
        return False

def get_messages(conversation_id):
    try:
        if not supabase:
            return []
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        messages = []
        for msg in response.data:
            msg_id = msg.get("message_id") or msg.get("id")
            messages.append({
                "message_id": msg_id,
                "sender": msg["sender"],
                "content": msg["content"],
                "created_at": msg.get("created_at"),
                "type": msg.get("type", "text"),
                "image_data": msg.get("image_data")
            })
        return messages
    except Exception as e:
        print(f"Erreur get_messages: {e}")
        import traceback; traceback.print_exc()
        return []

def add_messages_batch(conversation_id, messages_list):
    try:
        if not supabase or not messages_list:
            return False
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            print(f"Conversation {conversation_id} n'existe pas")
            return False

        cleaned_messages = []
        for msg in messages_list:
            sender = str(msg.get("sender", "unknown")).strip()
            content = clean_message_content(msg.get("content", ""))
            created_at = msg.get("created_at") or datetime.now().isoformat()
            msg_type = msg.get("type", "text")
            image_data = msg.get("image_data")
            message_data = {
                "conversation_id": conversation_id,
                "sender": sender,
                "content": content,
                "type": msg_type,
                "created_at": created_at
            }
            if image_data:
                message_data["image_data"] = image_data
            cleaned_messages.append(message_data)

        response = supabase.table("messages").insert(cleaned_messages).execute()
        if hasattr(response, 'error') and response.error:
            print(f"Erreur batch: {response.error}")
            return False
        return bool(response.data and len(response.data) > 0)
    except Exception as e:
        print(f"Erreur add_messages_batch: {e}")
        import traceback; traceback.print_exc()
        return False

def delete_message(message_id):
    try:
        if not supabase:
            return False
        response = supabase.table("messages").delete().eq("message_id", message_id).execute()
        return bool(response.data and len(response.data) > 0)
    except Exception as e:
        print(f"Erreur delete_message: {e}")
        return False

# ===================================================
# Statistiques et debug
# ===================================================

def test_connection():
    try:
        if not supabase:
            print("Supabase non connecté")
            return False
        print("Test connexion Supabase...")
        for table in ["users", "conversations", "messages"]:
            try:
                r = supabase.table(table).select("*").limit(1).execute()
                print(f"Table {table}: accessible ({len(r.data)} lignes)")
            except Exception as e:
                print(f"Table {table}: erreur - {e}")
        return True
    except Exception as e:
        print(f"Erreur test_connection: {e}")
        return False

def get_database_stats():
    try:
        print("Stats DB:")
        users_count = supabase.table("users").select("id", count="exact").execute()
        conv_count = supabase.table("conversations").select("conversation_id", count="exact").execute()
        msg_count = supabase.table("messages").select("message_id", count="exact").execute()
        print(f"Utilisateurs: {users_count.count}, Conversations: {conv_count.count}, Messages: {msg_count.count}")
    except Exception as e:
        print(f"Erreur get_database_stats: {e}")

