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

            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0])
                }
            return None
            
        except Exception as auth_error:
            print(f"Erreur auth Supabase: {auth_error}")
            
            # Option 2: Fallback - vérification directe en base
            response = supabase.table("users").select("*").eq("email", email).execute()
            
            if response.data and len(response.data) > 0:
                user = response.data[0]
                stored_password = user.get("password", "")
                
                if stored_password == password:
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

        # Option 1: Utiliser l'authentification Supabase
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name or email.split("@")[0]}
            })

            return response.user is not None
            
        except Exception as auth_error:
            print(f"Erreur auth create: {auth_error}")
            
            # Option 2: Fallback - insertion directe en base
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,  # ATTENTION: En production, hashez le mot de passe!
                "name": name or email.split("@")[0],
                "created_at": datetime.now().isoformat()
            }

            response = supabase.table("users").insert(user_data).execute()
            return len(response.data) > 0 if response.data else False

    except Exception as e:
        print(f"Erreur create_user: {e}")
        return False

# ===================================================
# CONVERSATIONS - VERSION CORRIGÉE
# ===================================================

def create_conversation(user_id, description):
    """Crée une nouvelle conversation - VERSION CORRIGÉE"""
    try:
        if not supabase:
            print("Supabase non connecté")
            return None

        # Vérifier que l'utilisateur existe
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if not user_check.data:
            print(f"Utilisateur {user_id} n'existe pas")
            return None

        # Nettoyer la description
        clean_description = clean_message_content(description)

        data = {
            "user_id": user_id,
            "description": clean_description,
            "created_at": datetime.now().isoformat()
        }

        response = supabase.table("conversations").insert(data).execute()

        # Vérifier les erreurs
        if hasattr(response, 'error') and response.error:
            print(f"Erreur Supabase conversations: {response.error}")
            return None

        if response.data and len(response.data) > 0:
            conv = response.data[0]
            
            # CORRECTION PRINCIPALE : Gérer les différents noms de clés ID
            conv_id = conv.get("conversation_id") or conv.get("id")
            
            if not conv_id:
                print(f"Aucun ID trouvé dans la réponse. Clés disponibles: {list(conv.keys())}")
                return None
            
            # Retourner avec la structure standardisée
            return {
                "conversation_id": conv_id,  # Clé standardisée
                "description": conv["description"],
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
        
        print("Aucune donnée retournée après insertion conversation")
        return None

    except Exception as e:
        print(f"Erreur create_conversation: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_conversations(user_id):
    """Récupère toutes les conversations d'un utilisateur - VERSION CORRIGÉE"""
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
            # Gérer les différents noms de clés possibles
            conv_id = conv.get("conversation_id") or conv.get("id")
            
            if conv_id:  # Seulement si on a un ID valide
                conversation_data = {
                    "conversation_id": conv_id,  # Clé standardisée
                    "description": conv.get("description", "Conversation sans titre"),
                    "created_at": conv.get("created_at"),
                    "user_id": conv["user_id"]
                }
                conversations.append(conversation_data)
        
        return conversations

    except Exception as e:
        print(f"Erreur get_conversations: {e}")
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
        
        # Puis supprimer la conversation
        conv_delete = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        
        success = conv_delete.data and len(conv_delete.data) > 0
        return success

    except Exception as e:
        print(f"Erreur delete_conversation: {e}")
        return False

# ===================================================
# MESSAGES - VERSION CORRIGÉE AVEC NOUVEAUX PARAMÈTRES
# ===================================================

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    """Ajoute un message dans une conversation - VERSION CORRIGÉE"""
    try:
        if not supabase:
            return False

        # Nettoyer et valider les données d'entrée
        sender = str(sender).strip() if sender else "unknown"
        content = clean_message_content(content)

        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        
        if not conv_check.data:
            print(f"Conversation {conversation_id} n'existe pas")
            return False

        # Préparer les données avec les nouveaux champs
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type or "text",  # Nouveau champ type
            "created_at": datetime.now().isoformat()
        }
        
        # Ajouter image_data si fourni (vérifier d'abord si la colonne existe)
        if image_data:
            data["image_data"] = image_data

        response = supabase.table("messages").insert(data).execute()

        # Vérifier les erreurs
        if hasattr(response, 'error') and response.error:
            print(f"Erreur Supabase messages: {response.error}")
            return False

        success = response.data and len(response.data) > 0
        return success

    except Exception as e:
        print(f"Erreur add_message: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_messages(conversation_id):
    """Récupère les messages d'une conversation - VERSION CORRIGÉE"""
    try:
        if not supabase:
            return []

        response = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)  # Ordre chronologique
            .execute()
        )

        messages = []
        for msg in response.data:
            # Gérer les différents noms de clés possibles
            msg_id = msg.get("message_id") or msg.get("id")
            
            message_data = {
                "message_id": msg_id,
                "sender": msg["sender"],
                "content": msg["content"],
                "created_at": msg.get("created_at"),
                "type": msg.get("type", "text"),  # Nouveau champ
                "image_data": msg.get("image_data")  # Nouveau champ
            }
            messages.append(message_data)
        
        return messages

    except Exception as e:
        print(f"Erreur get_messages: {e}")
        import traceback
        traceback.print_exc()
        return []


def add_messages_batch(conversation_id, messages_list):
    """Ajoute plusieurs messages d'un coup (plus efficace)"""
    try:
        if not supabase or not messages_list:
            return False

        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            print(f"Conversation {conversation_id} n'existe pas")
            return False

        # Préparer tous les messages
        cleaned_messages = []
        for msg in messages_list:
            sender = str(msg.get("sender", "unknown")).strip()
            content = clean_message_content(msg.get("content", ""))
            created_at = msg.get("created_at")
            msg_type = msg.get("type", "text")
            image_data = msg.get("image_data")
            
            # Si pas de timestamp, en générer un
            if not created_at or created_at == "NULL":
                created_at = datetime.now().isoformat()
            
            message_data = {
                "conversation_id": conversation_id,
                "sender": sender,
                "content": content,
                "type": msg_type,
                "created_at": created_at
            }
            
            # Ajouter image_data si présent
            if image_data:
                message_data["image_data"] = image_data
                
            cleaned_messages.append(message_data)
        
        # Insertion en lot
        response = supabase.table("messages").insert(cleaned_messages).execute()
        
        if hasattr(response, 'error') and response.error:
            print(f"Erreur batch: {response.error}")
            return False

        success = response.data and len(response.data) > 0
        return success

    except Exception as e:
        print(f"Erreur add_messages_batch: {e}")
        import traceback
        traceback.print_exc()
        return False


def delete_message(message_id):
    """Supprime un message spécifique"""
    try:
        if not supabase:
            return False

        response = supabase.table("messages").delete().eq("message_id", message_id).execute()
        success = response.data and len(response.data) > 0
        
        return success

    except Exception as e:
        print(f"Erreur delete_message: {e}")
        return False

# ===================================================
# FONCTIONS DE DEBUG ET MAINTENANCE
# ===================================================

def test_connection():
    """Test la connexion et les permissions"""
    try:
        if not supabase:
            print("Supabase non connecté")
            return False
            
        print("Test de connexion Supabase...")
        
        # Test simple sur chaque table
        tables = ["users", "conversations", "messages"]
        for table in tables:
            try:
                response = supabase.table(table).select("*").limit(1).execute()
                print(f"Table {table}: accessible ({len(response.data)} lignes)")
            except Exception as e:
                print(f"Table {table}: erreur - {e}")
        
        return True
    except Exception as e:
        print(f"Erreur test_connection: {e}")
        return False


def create_test_user():
    """Crée un utilisateur de test"""
    test_email = "test@example.com"
    test_password = "password123"
    test_name = "Utilisateur Test"
    
    print(f"Création/vérification utilisateur test: {test_email}")
    
    # Vérifier si existe déjà
    existing = supabase.table("users").select("*").eq("email", test_email).execute()
    if existing.data:
        user_id = existing.data[0]['id']
        print(f"Utilisateur test existe déjà: {user_id}")
        
        # Vérifier la connexion avec le mot de passe
        user_verified = verify_user(test_email, test_password)
        if user_verified:
            print("Connexion utilisateur test OK")
            return user_id
        else:
            print("Utilisateur existe mais connexion échoue, mise à jour du mot de passe...")
            supabase.table("users").update({"password": test_password}).eq("email", test_email).execute()
            return user_id
    
    # Créer nouveau
    print("Création nouvel utilisateur test...")
    if create_user(test_email, test_password, test_name):
        user = supabase.table("users").select("*").eq("email", test_email).execute()
        if user.data:
            user_id = user.data[0]['id']
            print(f"Utilisateur test créé: {user_id}")
            return user_id
    
    print("Impossible de créer l'utilisateur test")
    return None


def cleanup_test_data():
    """Nettoie les données de test"""
    try:
        print("Nettoyage des données de test...")
        
        # Supprimer les conversations de test
        test_conversations = supabase.table("conversations").select("*").ilike("description", "%test%").execute()
        
        for conv in test_conversations.data:
            conv_id = conv.get("conversation_id") or conv.get("id")
            if conv_id:
                delete_conversation(conv_id)
        
        print(f"{len(test_conversations.data)} conversations de test supprimées")
        
    except Exception as e:
        print(f"Erreur cleanup_test_data: {e}")


def get_database_stats():
    """Affiche les statistiques de la base de données"""
    try:
        print("Statistiques de la base de données:")
        
        # Compter les utilisateurs
        users_count = supabase.table("users").select("id", count="exact").execute()
        print(f"Utilisateurs: {users_count.count}")
        
        # Compter les conversations
        conv_count = supabase.table("conversations").select("conversation_id", count="exact").execute()
        print(f"Conversations: {conv_count.count}")
        
        # Compter les messages
        msg_count = supabase.table("messages").select("message_id", count="exact").execute()
        print(f"Messages: {msg_count.count}")
        
    except Exception as e:
        print(f"Erreur get_database_stats: {e}")

# ===================================================
# NOUVELLES FONCTIONS POUR STREAMLIT
# ===================================================

def update_conversation_description(conversation_id, new_description):
    """Met à jour la description d'une conversation"""
    try:
        if not supabase:
            return False
            
        clean_desc = clean_message_content(new_description)
        response = supabase.table("conversations").update({"description": clean_desc}).eq("conversation_id", conversation_id).execute()
        
        return response.data and len(response.data) > 0
        
    except Exception as e:
        print(f"Erreur update_conversation_description: {e}")
        return False


def get_user_conversation_count(user_id):
    """Récupère le nombre de conversations d'un utilisateur"""
    try:
        if not supabase:
            return 0
            
        response = supabase.table("conversations").select("conversation_id", count="exact").eq("user_id", user_id).execute()
        return response.count or 0
        
    except Exception as e:
        print(f"Erreur get_user_conversation_count: {e}")
        return 0


def get_conversation_message_count(conversation_id):
    """Récupère le nombre de messages dans une conversation"""
    try:
        if not supabase:
            return 0
            
        response = supabase.table("messages").select("message_id", count="exact").eq("conversation_id", conversation_id).execute()
        return response.count or 0
        
    except Exception as e:
        print(f"Erreur get_conversation_message_count: {e}")
        return 0

# ===================================================
# TEST PRINCIPAL
# ===================================================

if __name__ == "__main__":
    print("Test complet du module db.py mis à jour...")
    print("=" * 50)

    # Test de connexion
    print("\nTest de connexion...")
    if not test_connection():
        print("Échec du test de connexion")
        exit(1)
    
    # Statistiques initiales
    print("\nStatistiques initiales...")
    get_database_stats()
    
    # Créer utilisateur test
    print("\nGestion utilisateur test...")
    user_id = create_test_user()
    if not user_id:
        print("Impossible de créer/récupérer l'utilisateur test")
        exit(1)

    print(f"Utilisateur test prêt: {user_id}")

    # Test conversation avec nouvelle structure
    print("\nTest création conversation...")
    conv = create_conversation(user_id, "Test conversation avec nouvelles fonctionnalités")
    
    if conv:
        conv_id = conv["conversation_id"]
        print(f"Conversation créée: {conv_id}")
        
        # Test ajout message avec type
        print("\nTest ajout messages avec types...")
        msg_ok1 = add_message(conv_id, "user", "Message texte simple", "text")
        msg_ok2 = add_message(conv_id, "assistant", "Réponse de l'assistant", "text")
        msg_ok3 = add_message(conv_id, "user", "[IMAGE] Description d'une image test", "image", "base64_image_data_fake")
        
        if msg_ok1 and msg_ok2 and msg_ok3:
            print("Messages avec types ajoutés avec succès")
            
            # Récupérer les messages
            print("\nTest récupération messages...")
            msgs = get_messages(conv_id)
            print(f"{len(msgs)} messages récupérés:")
            
            for i, msg in enumerate(msgs, 1):
                print(f"  {i}. [{msg['sender']}] ({msg['type']}): {msg['content'][:50]}...")
                if msg.get('image_data'):
                    print(f"     -> Avec données image: {len(msg['image_data'])} caractères")
            
            # Test récupération conversations
            print("\nTest récupération conversations...")
            conversations = get_conversations(user_id)
            print(f"{len(conversations)} conversations récupérées:")
            
            for conv_item in conversations:
                print(f"  - {conv_item['description']} (ID: {conv_item['conversation_id']})")
                
        else:
            print("Erreur ajout des messages")
    else:
        print("Erreur création conversation")
    
    # Statistiques finales
    print("\nStatistiques finales...")
    get_database_stats()
    
    print("\n" + "=" * 50)
    print("Test terminé - Module db.py mis à jour et fonctionnel!")
