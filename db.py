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
        print(f"❌ Erreur connexion Supabase: {e}")
        return None

# Instance globale
supabase = get_supabase_client()

# ===================================================
# FONCTIONS UTILITAIRES
# ===================================================

def clean_message_content(content):
    """Nettoie le contenu d'un message pour l'insertion en base"""
    if not content:
        return ""
    
    # Convertir en string si ce n'est pas déjà le cas
    content = str(content)
    
    # Remplacer les caractères problématiques
    content = content.replace("\x00", "")  # Caractères null
    content = content.replace("\\", "\\\\")  # Échapper les backslashes
    content = content.replace("'", "''")  # Échapper les apostrophes
    content = content.replace('"', '""')  # Échapper les guillemets
    
    # Limiter la taille (ex: 10000 caractères max)
    if len(content) > 10000:
        content = content[:9950] + "... [contenu tronqué]"
    
    # Nettoyer les retours à la ligne excessifs
    content = re.sub(r'\n{3,}', '\n\n', content)  # Max 2 retours à la ligne consécutifs
    
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

        # Option 1: Utiliser l'authentification Supabase (recommandé)
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            print(f"🔍 Debug verify_user - email: {email}")
            print(f"🔍 Debug verify_user - auth response: {response}")

            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0])
                }
            return None
            
        except Exception as auth_error:
            print(f"🔍 Debug - Erreur auth Supabase: {auth_error}")
            
            # Option 2: Fallback - vérification directe en base (pour les tests)
            response = supabase.table("users").select("*").eq("email", email).execute()
            
            print(f"🔍 Debug verify_user - table response: {response.data}")
            
            if response.data and len(response.data) > 0:
                user = response.data[0]
                # ATTENTION: Comparaison en texte brut pour les tests uniquement!
                # En production, utilisez bcrypt ou équivalent
                stored_password = user.get("password", "")
                
                if stored_password == password:
                    print("✅ Mot de passe correct (comparaison directe)")
                    return {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name", email.split("@")[0])
                    }
                else:
                    print(f"❌ Mot de passe incorrect. Stocké: '{stored_password}', Fourni: '{password}'")
            return None

    except Exception as e:
        print(f"❌ Erreur verify_user: {e}")
        return None


def create_user(email, password, name=None):
    """Crée un nouvel utilisateur"""
    try:
        if not supabase:
            return False

        # Option 1: Utiliser l'authentification Supabase (recommandé)
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name or email.split("@")[0]}
            })

            print(f"🔍 Debug create_user - auth response: {response}")
            return response.user is not None
            
        except Exception as auth_error:
            print(f"🔍 Debug - Erreur auth create: {auth_error}")
            
            # Option 2: Fallback - insertion directe en base (pour les tests)
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,  # ATTENTION: En production, hashez le mot de passe!
                "name": name or email.split("@")[0],
                "created_at": datetime.now().isoformat()
            }

            print(f"🔍 Debug create_user - data directe: {user_data}")
            response = supabase.table("users").insert(user_data).execute()
            print(f"🔍 Debug create_user - response directe: {response}")
            
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

        # Nettoyer la description
        clean_description = clean_message_content(description)

        data = {
            "user_id": user_id,
            "description": clean_description,
            "created_at": datetime.now().isoformat()
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
                "created_at": safe_parse_datetime(conv.get("created_at")),
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
                "created_at": safe_parse_datetime(conv.get("created_at")),
                "user_id": conv["user_id"]
            })
        
        print(f"✅ {len(conversations)} conversations récupérées")
        return conversations

    except Exception as e:
        print(f"❌ Erreur get_conversations: {e}")
        import traceback
        traceback.print_exc()
        return []

def delete_conversation(conversation_id):
    """Supprime une conversation et tous ses messages"""
    try:
        if not supabase:
            return False

        # Supprimer d'abord tous les messages de la conversation
        msg_delete = supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
        print(f"🗑️ Messages supprimés: {len(msg_delete.data) if msg_delete.data else 0}")
        
        # Puis supprimer la conversation
        conv_delete = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        
        success = conv_delete.data and len(conv_delete.data) > 0
        if success:
            print(f"✅ Conversation {conversation_id} supprimée")
        
        return success

    except Exception as e:
        print(f"❌ Erreur delete_conversation: {e}")
        return False

# ===================================================
# MESSAGES
# ===================================================

def add_message(conversation_id, sender, content):
    """Ajoute un message dans une conversation"""
    try:
        if not supabase:
            return False

        # Nettoyer et valider les données d'entrée
        sender = str(sender).strip() if sender else "unknown"
        content = clean_message_content(content)
        
        print(f"🔍 Debug add_message - conversation_id: {conversation_id}")
        print(f"🔍 Debug add_message - sender: {sender}")
        print(f"🔍 Debug add_message - content length: {len(content)}")
        print(f"🔍 Debug add_message - content preview: {content[:200]}...")

        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        print(f"🔍 Debug conv_check: {conv_check.data}")
        
        if not conv_check.data:
            print(f"❌ Conversation {conversation_id} n'existe pas")
            return False

        # Préparer les données avec timestamp explicite
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "created_at": datetime.now().isoformat()  # Timestamp explicite
        }

        print(f"🔍 Debug - Data nettoyée à insérer: {data}")
        response = supabase.table("messages").insert(data).execute()
        print(f"🔍 Debug - Response complète messages: {response}")

        # Vérifier les erreurs spécifiques
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


def add_messages_batch(conversation_id, messages_list):
    """Ajoute plusieurs messages d'un coup (plus efficace)"""
    try:
        if not supabase or not messages_list:
            return False

        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            print(f"❌ Conversation {conversation_id} n'existe pas")
            return False

        # Préparer tous les messages
        cleaned_messages = []
        for msg in messages_list:
            sender = str(msg.get("sender", "unknown")).strip()
            content = clean_message_content(msg.get("content", ""))
            created_at = msg.get("created_at")
            
            # Si pas de timestamp, en générer un
            if not created_at or created_at == "NULL":
                created_at = datetime.now().isoformat()
            
            cleaned_messages.append({
                "conversation_id": conversation_id,
                "sender": sender,
                "content": content,
                "created_at": created_at
            })

        print(f"🔍 Insertion batch de {len(cleaned_messages)} messages...")
        
        # Insertion en lot
        response = supabase.table("messages").insert(cleaned_messages).execute()
        
        if hasattr(response, 'error') and response.error:
            print(f"❌ Erreur batch: {response.error}")
            return False

        success = response.data and len(response.data) > 0
        if success:
            print(f"✅ {len(response.data)} messages ajoutés en batch")
        else:
            print("❌ Échec insertion batch")
        
        return success

    except Exception as e:
        print(f"❌ Erreur add_messages_batch: {e}")
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
                "message_id": msg.get("message_id"),
                "sender": msg["sender"],
                "content": msg["content"],
                "created_at": safe_parse_datetime(msg.get("created_at"))
            })
        
        print(f"✅ {len(messages)} messages récupérés")
        return messages

    except Exception as e:
        print(f"❌ Erreur get_messages: {e}")
        import traceback
        traceback.print_exc()
        return []


def delete_message(message_id):
    """Supprime un message spécifique"""
    try:
        if not supabase:
            return False

        response = supabase.table("messages").delete().eq("message_id", message_id).execute()
        success = response.data and len(response.data) > 0
        
        if success:
            print(f"✅ Message {message_id} supprimé")
        
        return success

    except Exception as e:
        print(f"❌ Erreur delete_message: {e}")
        return False

# ===================================================
# FONCTIONS DE DEBUG ET MAINTENANCE
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
    test_password = "password123"  # Mot de passe en dur pour les tests
    test_name = "Utilisateur Test"
    
    print(f"🔍 Création/vérification utilisateur test: {test_email}")
    
    # Vérifier si existe déjà
    existing = supabase.table("users").select("*").eq("email", test_email).execute()
    if existing.data:
        user_id = existing.data[0]['id']
        print(f"✅ Utilisateur test existe déjà: {user_id}")
        
        # Vérifier la connexion avec le mot de passe
        user_verified = verify_user(test_email, test_password)
        if user_verified:
            print("✅ Connexion utilisateur test OK")
            return user_id
        else:
            print("⚠️ Utilisateur existe mais connexion échoue, mise à jour du mot de passe...")
            # Mettre à jour le mot de passe dans la table pour les tests
            supabase.table("users").update({"password": test_password}).eq("email", test_email).execute()
            return user_id
    
    # Créer nouveau
    print("🔍 Création nouvel utilisateur test...")
    if create_user(test_email, test_password, test_name):
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


def cleanup_test_data():
    """Nettoie les données de test"""
    try:
        print("🧹 Nettoyage des données de test...")
        
        # Supprimer les conversations de test
        test_conversations = supabase.table("conversations").select("*").ilike("description", "%test%").execute()
        
        for conv in test_conversations.data:
            delete_conversation(conv["conversation_id"])
        
        print(f"✅ {len(test_conversations.data)} conversations de test supprimées")
        
    except Exception as e:
        print(f"❌ Erreur cleanup_test_data: {e}")


def get_database_stats():
    """Affiche les statistiques de la base de données"""
    try:
        print("📊 Statistiques de la base de données:")
        
        # Compter les utilisateurs
        users_count = supabase.table("users").select("id", count="exact").execute()
        print(f"👤 Utilisateurs: {users_count.count}")
        
        # Compter les conversations
        conv_count = supabase.table("conversations").select("conversation_id", count="exact").execute()
        print(f"💬 Conversations: {conv_count.count}")
        
        # Compter les messages
        msg_count = supabase.table("messages").select("message_id", count="exact").execute()
        print(f"📝 Messages: {msg_count.count}")
        
    except Exception as e:
        print(f"❌ Erreur get_database_stats: {e}")

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
    
    # Statistiques initiales
    print("\n📊 Statistiques initiales...")
    get_database_stats()
    
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
        
        # Test ajout message simple
        print("\n📝 Test ajout message simple...")
        msg_ok = add_message(conv["conversation_id"], "user", "Premier message de test simple")
        
        if msg_ok:
            print("✅ Premier message ajouté")
            
            # Test message avec contenu complexe
            print("\n📝 Test message complexe...")
            complex_content = """**Message avec formatage**
            
            Voici un message avec:
            - Des *caractères* spéciaux
            - Des "guillemets" et 'apostrophes'
            - Des retours à la ligne multiples


            Et même des émojis! 🎉"""
            
            msg_ok2 = add_message(conv["conversation_id"], "assistant", complex_content)
            if msg_ok2:
                print("✅ Message complexe ajouté")
            
            # Test batch de messages
            print("\n📦 Test insertion batch...")
            batch_messages = [
                {"sender": "user", "content": "Message batch 1", "created_at": None},
                {"sender": "assistant", "content": "Réponse batch 1", "created_at": None},
                {"sender": "user", "content": "Message batch 2", "created_at": None}
            ]
            
            batch_ok = add_messages_batch(conv["conversation_id"], batch_messages)
            if batch_ok:
                print("✅ Messages batch ajoutés")
            
            # Récupérer tous les messages
            print("\n📬 Test récupération messages...")
            msgs = get_messages(conv["conversation_id"])
            print(f"✅ {len(msgs)} messages récupérés:")
            
            for i, msg in enumerate(msgs, 1):
                print(f"  {i}. [{msg['sender']}]: {msg['content'][:50]}...")
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
    
    # Statistiques finales
    print("\n📊 Statistiques finales...")
    get_database_stats()
    
    print("\n" + "=" * 50)
    print("🏁 Test terminé!")
    
    # Demander si on nettoie les données de test
    try:
        response = input("\n🧹 Voulez-vous nettoyer les données de test? (y/N): ")
        if response.lower() == 'y':
            cleanup_test_data()
            print("✅ Nettoyage effectué")
    except:
        print("⏭️ Nettoyage ignoré")
