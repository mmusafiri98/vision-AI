import os
from supabase import create_client
from datetime import datetime
from dateutil import parser
import uuid

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

        # Recherche directe dans la table users (RLS désactivé)
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        print(f"🔍 Debug verify_user - email: {email}")
        print(f"🔍 Debug verify_user - response: {response.data}")
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            # Note: Ici vous devriez vérifier le mot de passe hashé
            # Pour les tests, on fait simple
            return {
                "id": user["id"],
                "email": user["email"],
                "name": user.get("name", email.split("@")[0])
            }
        return None

    except Exception as e:
        print(f"❌ Erreur verify_user: {e}")
        return None


def create_user(email, password, name=None):
    """Crée un nouvel utilisateur directement dans la table"""
    try:
        if not supabase:
            return False

        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": name or email.split("@")[0],
            "created_at": datetime.now().isoformat()
        }

        print(f"🔍 Debug create_user - data: {user_data}")
        response = supabase.table("users").insert(user_data).execute()
        print(f"🔍 Debug create_user - response: {response}")
        
        return len(response.data) > 0 if response.data else False

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

        print(f"🔍 Debug create_conversation - user_id: {user_id}")
        print(f"🔍 Debug create_conversation - description: {description}")

        # Vérifier d'abord que l'utilisateur existe
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        print(f"🔍 Debug user_check: {user_check.data}")
        
        if not user_check.data:
            print(f"❌ Utilisateur {user_id} n'existe pas")
            return None

        data = {
            "user_id": user_id,
            "description": description
        }

        print(f"🔍 Debug - Data à insérer dans conversations: {data}")
        response = supabase.table("conversations").insert(data).execute()
        print(f"🔍 Debug - Response complète conversations: {response}")
        print(f"🔍 Debug - Response.data conversations: {response.data}")

        # Vérifier les erreurs
        if hasattr(response, 'error') and response.error:
            print(f"❌ Erreur Supabase conversations: {response.error}")
            return None

        if response.data and len(response.data) > 0:
            conv = response.data[0]
            print(f"✅ Conversation créée avec succès: {conv}")
            return {
                "conversation_id": conv["conversation_id"],
                "description": conv["description"],
                "created_at": parser.isoparse(conv["created_at"]) if conv.get("created_at") else datetime.now(),
                "user_id": conv["user_id"]
            }
        
        print("❌ Aucune donnée retournée après insertion conversation")
        return None

    except Exception as e:
        print(f"❌ Erreur create_conversation: {e}")
        print(f"❌ Type d'erreur: {type(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_conversations(user_id):
    """Récupère toutes les conversations d'un utilisateur"""
    try:
        if not supabase:
            return []

        print(f"🔍 Debug get_conversations - user_id: {user_id}")

        response = (
            supabase.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        print(f"🔍 Debug get_conversations - response: {response.data}")

        conversations = []
        for conv in response.data:
            conversations.append({
                "conversation_id": conv["conversation_id"],
                "description": conv["description"],
                "created_at": parser.isoparse(conv["created_at"]) if conv.get("created_at") else datetime.now(),
                "user_id": conv["user_id"]
            })
        
        print(f"✅ {len(conversations)} conversations récupérées")
        return conversations

    except Exception as e:
        print(f"❌ Erreur get_conversations: {e}")
        import traceback
        traceback.print_exc()
        return []

# ===================================================
# MESSAGES
# ===================================================

def add_message(conversation_id, sender, content):
    """Ajoute un message dans une conversation"""
    try:
        if not supabase:
            return False

        print(f"🔍 Debug add_message - conversation_id: {conversation_id}")
        print(f"🔍 Debug add_message - sender: {sender}")
        print(f"🔍 Debug add_message - content: {content}")

        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        print(f"🔍 Debug conv_check: {conv_check.data}")
        
        if not conv_check.data:
            print(f"❌ Conversation {conversation_id} n'existe pas")
            return False

        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content
        }

        print(f"🔍 Debug - Data à insérer dans messages: {data}")
        response = supabase.table("messages").insert(data).execute()
        print(f"🔍 Debug - Response complète messages: {response}")
        print(f"🔍 Debug - Response.data messages: {response.data}")

        # Vérifier les erreurs
        if hasattr(response, 'error') and response.error:
            print(f"❌ Erreur Supabase messages: {response.error}")
            return False

        success = response.data and len(response.data) > 0
        if success:
            print(f"✅ Message ajouté avec succès")
        else:
            print("❌ Aucune donnée retournée après insertion message")
        
        return success

    except Exception as e:
        print(f"❌ Erreur add_message: {e}")
        print(f"❌ Type d'erreur: {type(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_messages(conversation_id):
    """Récupère les messages d'une conversation"""
    try:
        if not supabase:
            return []

        print(f"🔍 Debug get_messages - conversation_id: {conversation_id}")

        response = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)  # Ordre chronologique
            .execute()
        )

        print(f"🔍 Debug get_messages - response: {response.data}")

        messages = []
        for msg in response.data:
            messages.append({
                "sender": msg["sender"],
                "content": msg["content"],
                "created_at": parser.isoparse(msg["created_at"]) if msg.get("created_at") else datetime.now()
            })
        
        print(f"✅ {len(messages)} messages récupérés")
        return messages

    except Exception as e:
        print(f"❌ Erreur get_messages: {e}")
        import traceback
        traceback.print_exc()
        return []

# ===================================================
# FONCTIONS DE DEBUG
# ===================================================

def test_connection():
    """Test la connexion et les permissions"""
    try:
        if not supabase:
            print("❌ Supabase non connecté")
            return False
            
        print("🔍 Test de connexion Supabase...")
        
        # Test simple sur chaque table
        tables = ["users", "conversations", "messages"]
        for table in tables:
            try:
                response = supabase.table(table).select("*").limit(1).execute()
                print(f"✅ Table {table}: accessible ({len(response.data)} lignes)")
            except Exception as e:
                print(f"❌ Table {table}: erreur - {e}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur test_connection: {e}")
        return False

def create_test_user():
    """Crée un utilisateur de test"""
    test_email = "test@example.com"
    test_name = "Utilisateur Test"
    
    print(f"🔍 Création/vérification utilisateur test: {test_email}")
    
    # Vérifier si existe déjà
    existing = supabase.table("users").select("*").eq("email", test_email).execute()
    if existing.data:
        user_id = existing.data[0]['id']
        print(f"✅ Utilisateur test existe déjà: {user_id}")
        return user_id
    
    # Créer nouveau
    print("🔍 Création nouvel utilisateur test...")
    if create_user(test_email, "password123", test_name):
        user = supabase.table("users").select("*").eq("email", test_email).execute()
        if user.data:
            user_id = user.data[0]['id']
            print(f"✅ Utilisateur test créé: {user_id}")
            return user_id
    
    print("❌ Impossible de créer l'utilisateur test")
    return None

def check_rls_status():
    """Vérifie le statut RLS des tables"""
    try:
        print("🔍 Vérification statut RLS...")
        
        # Cette requête nécessite des permissions spéciales, on va juste tester l'accès
        tables = ["users", "conversations", "messages"]
        for table in tables:
            try:
                # Test d'insertion simple pour voir si RLS bloque
                test_response = supabase.table(table).select("*").limit(1).execute()
                print(f"✅ {table}: accès OK (RLS probablement désactivé)")
            except Exception as e:
                print(f"❌ {table}: accès bloqué - {e}")
                
    except Exception as e:
        print(f"❌ Erreur check_rls_status: {e}")

# ===================================================
# TEST PRINCIPAL
# ===================================================

if __name__ == "__main__":
    print("🧪 Test complet du module db.py...")
    print("=" * 50)

    # Test de connexion
    print("\n📡 Test de connexion...")
    if not test_connection():
        print("❌ Échec du test de connexion")
        exit(1)
    
    # Vérification RLS
    print("\n🔒 Vérification RLS...")
    check_rls_status()
    
    # Créer utilisateur test
    print("\n👤 Gestion utilisateur test...")
    user_id = create_test_user()
    if not user_id:
        print("❌ Impossible de créer/récupérer l'utilisateur test")
        exit(1)

    print(f"✅ Utilisateur test prêt: {user_id}")

    # Test conversation
    print("\n💬 Test création conversation...")
    conv = create_conversation(user_id, "Conversation de test avec debug complet")
    
    if conv:
        print(f"✅ Conversation créée: {conv['conversation_id']}")
        
        # Test ajout message
        print("\n📝 Test ajout message...")
        msg_ok = add_message(conv["conversation_id"], "user", "Premier message de test")
        
        if msg_ok:
            print("✅ Premier message ajouté")
            
            # Ajouter un second message
            msg_ok2 = add_message(conv["conversation_id"], "assistant", "Réponse de l'assistant")
            if msg_ok2:
                print("✅ Second message ajouté")
            
            # Récupérer tous les messages
            print("\n📬 Test récupération messages...")
            msgs = get_messages(conv["conversation_id"])
            print(f"✅ {len(msgs)} messages récupérés:")
            
            for i, msg in enumerate(msgs, 1):
                print(f"  {i}. [{msg['sender']}]: {msg['content']}")
                print(f"     📅 {msg['created_at']}")
            
            # Test récupération conversations
            print("\n📋 Test récupération conversations...")
            conversations = get_conversations(user_id)
            print(f"✅ {len(conversations)} conversations récupérées:")
            
            for conv_item in conversations:
                print(f"  - {conv_item['description']} (ID: {conv_item['conversation_id']})")
                
        else:
            print("❌ Erreur ajout message")
    else:
        print("❌ Erreur création conversation")
    
    print("\n" + "=" * 50)
    print("🏁 Test terminé!")
