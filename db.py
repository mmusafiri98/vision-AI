import os
from supabase import create_client
from datetime import datetime
from dateutil import parser
import uuid
import re
import streamlit as st

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================

def get_supabase_client():
    """Initialise et retourne le client Supabase avec gestion d'erreur améliorée"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url:
            raise Exception("Variable SUPABASE_URL manquante dans les variables d'environnement")
        if not supabase_service_key:
            raise Exception("Variable SUPABASE_SERVICE_KEY manquante dans les variables d'environnement")

        # Validation basique de l'URL
        if not supabase_url.startswith(('http://', 'https://')):
            raise Exception(f"SUPABASE_URL invalide: {supabase_url}")

        client = create_client(supabase_url, supabase_service_key)
        
        # Test rapide de connexion
        try:
            test_response = client.table("users").select("*").limit(1).execute()
            print(f"✅ Connexion Supabase réussie")
        except Exception as test_e:
            print(f"⚠️ Connexion Supabase établie mais test échoué: {test_e}")
        
        return client
        
    except Exception as e:
        print(f"❌ Erreur connexion Supabase: {e}")
        # En mode développement, afficher dans Streamlit aussi
        try:
            st.error(f"Erreur connexion Supabase: {e}")
        except:
            pass
        return None

# Initialiser le client global
supabase = get_supabase_client()

# ===================================================
# FONCTIONS UTILITAIRES
# ===================================================

def clean_message_content(content):
    """Nettoie le contenu d'un message pour l'insertion en base"""
    if not content:
        return ""
    
    content = str(content)
    # Supprimer les caractères null
    content = content.replace("\x00", "")
    # Échapper les caractères spéciaux
    content = content.replace("\\", "\\\\")
    content = content.replace("'", "''")
    content = content.replace('"', '""')
    
    # Limiter la taille
    if len(content) > 10000:
        content = content[:9950] + "... [contenu tronqué]"
    
    # Nettoyer les sauts de ligne excessifs
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()

def safe_parse_datetime(date_str):
    """Parse une date de manière sécurisée"""
    try:
        if not date_str or date_str == "NULL":
            return datetime.now()
        return parser.isoparse(date_str)
    except Exception:
        return datetime.now()

def validate_uuid(uuid_string):
    """Valide qu'une chaîne est un UUID valide"""
    try:
        uuid.UUID(str(uuid_string))
        return True
    except (ValueError, TypeError):
        return False

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    try:
        if not supabase:
            print("❌ verify_user: Supabase non connecté")
            return None
            
        if not email or not password:
            print("❌ verify_user: Email ou mot de passe manquant")
            return None

        # Méthode 1: Auth Supabase
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email, 
                "password": password
            })
            
            if auth_response.user:
                user_data = {
                    "id": auth_response.user.id,
                    "email": auth_response.user.email,
                    "name": auth_response.user.user_metadata.get("name", email.split("@")[0])
                }
                print(f"✅ verify_user: Connexion auth réussie pour {email}")
                return user_data
                
        except Exception as auth_e:
            print(f"⚠️ verify_user: Auth Supabase échoué, tentative directe: {auth_e}")

        # Méthode 2: Vérification directe en table
        try:
            table_response = supabase.table("users").select("*").eq("email", email).execute()
            
            if hasattr(table_response, 'error') and table_response.error:
                print(f"❌ verify_user: Erreur table users: {table_response.error}")
                return None
                
            if table_response.data and len(table_response.data) > 0:
                user = table_response.data[0]
                # Vérification simple du mot de passe (à améliorer en production)
                if user.get("password") == password:
                    user_data = {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name", email.split("@")[0])
                    }
                    print(f"✅ verify_user: Connexion table réussie pour {email}")
                    return user_data
                else:
                    print(f"❌ verify_user: Mot de passe incorrect pour {email}")
                    
        except Exception as table_e:
            print(f"❌ verify_user: Erreur vérification table: {table_e}")

        return None
        
    except Exception as e:
        print(f"❌ verify_user: Exception générale: {e}")
        return None

def create_user(email, password, name=None):
    """Crée un nouvel utilisateur"""
    try:
        if not supabase:
            print("❌ create_user: Supabase non connecté")
            return False
            
        if not email or not password:
            print("❌ create_user: Email ou mot de passe manquant")
            return False

        # Méthode 1: Auth Admin
        try:
            auth_response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name or email.split("@")[0]}
            })
            
            if auth_response.user:
                print(f"✅ create_user: Utilisateur créé via auth: {email}")
                return True
                
        except Exception as auth_e:
            print(f"⚠️ create_user: Auth admin échoué, tentative directe: {auth_e}")

        # Méthode 2: Insertion directe
        try:
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,  # À hasher en production !
                "name": name or email.split("@")[0],
                "created_at": datetime.now().isoformat()
            }
            
            table_response = supabase.table("users").insert(user_data).execute()
            
            if hasattr(table_response, 'error') and table_response.error:
                print(f"❌ create_user: Erreur insertion: {table_response.error}")
                return False
                
            if table_response.data and len(table_response.data) > 0:
                print(f"✅ create_user: Utilisateur créé via table: {email}")
                return True
                
        except Exception as table_e:
            print(f"❌ create_user: Erreur table: {table_e}")

        return False
        
    except Exception as e:
        print(f"❌ create_user: Exception générale: {e}")
        return False

# ===================================================
# CONVERSATIONS
# ===================================================

def create_conversation(user_id, description):
    """Crée une conversation avec validation améliorée"""
    try:
        if not supabase:
            print("❌ create_conversation: Supabase non connecté")
            return None
            
        if not user_id or not description:
            print("❌ create_conversation: user_id ou description manquant")
            return None

        # Vérifier que l'utilisateur existe
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if hasattr(user_check, 'error') and user_check.error:
            print(f"❌ create_conversation: Erreur vérification user: {user_check.error}")
            return None
            
        if not user_check.data:
            print(f"❌ create_conversation: Utilisateur {user_id} n'existe pas")
            return None

        # Préparer les données
        clean_description = clean_message_content(description)
        conversation_data = {
            "user_id": user_id,
            "description": clean_description,
            "created_at": datetime.now().isoformat()
        }

        # Insérer la conversation
        response = supabase.table("conversations").insert(conversation_data).execute()
        
        if hasattr(response, 'error') and response.error:
            print(f"❌ create_conversation: Erreur Supabase: {response.error}")
            return None

        if not response.data or len(response.data) == 0:
            print("❌ create_conversation: Aucune donnée retournée")
            return None

        # Traiter la réponse
        conv = response.data[0]
        conv_id = conv.get("conversation_id") or conv.get("id")
        
        if not conv_id:
            print(f"❌ create_conversation: ID manquant. Clés: {list(conv.keys())}")
            return None

        result = {
            "conversation_id": conv_id,
            "description": conv.get("description", ""),
            "created_at": conv.get("created_at"),
            "user_id": conv["user_id"]
        }
        
        print(f"✅ create_conversation: Conversation créée: {conv_id}")
        return result
        
    except Exception as e:
        print(f"❌ create_conversation: Exception: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_conversations(user_id):
    """Récupère les conversations d'un utilisateur avec validation"""
    try:
        if not supabase:
            print("❌ get_conversations: Supabase non connecté")
            return []
            
        if not user_id:
            print("❌ get_conversations: user_id manquant")
            return []

        # Requête avec gestion d'erreur
        response = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        if hasattr(response, 'error') and response.error:
            print(f"❌ get_conversations: Erreur Supabase: {response.error}")
            return []

        if not response.data:
            print(f"⚠️ get_conversations: Aucune conversation pour user {user_id}")
            return []

        # Traiter les conversations
        conversations = []
        for conv in response.data:
            conv_id = conv.get("conversation_id") or conv.get("id")
            
            if conv_id:  # Seulement si on a un ID valide
                conversations.append({
                    "conversation_id": conv_id,
                    "description": conv.get("description", "Conversation sans titre"),
                    "created_at": conv.get("created_at"),
                    "user_id": conv["user_id"]
                })

        print(f"✅ get_conversations: {len(conversations)} conversations trouvées")
        return conversations
        
    except Exception as e:
        print(f"❌ get_conversations: Exception: {e}")
        import traceback
        traceback.print_exc()
        return []

def delete_conversation(conversation_id):
    """Supprime une conversation et ses messages"""
    try:
        if not supabase:
            print("❌ delete_conversation: Supabase non connecté")
            return False
            
        if not conversation_id:
            print("❌ delete_conversation: conversation_id manquant")
            return False

        # Supprimer d'abord les messages
        msg_delete = supabase.table("messages").delete().eq("conversation_id", conversation_id).execute()
        print(f"Messages supprimés: {len(msg_delete.data) if msg_delete.data else 0}")

        # Puis la conversation
        conv_delete = supabase.table("conversations").delete().eq("conversation_id", conversation_id).execute()
        
        if hasattr(conv_delete, 'error') and conv_delete.error:
            print(f"❌ delete_conversation: Erreur: {conv_delete.error}")
            return False

        success = bool(conv_delete.data and len(conv_delete.data) > 0)
        print(f"✅ delete_conversation: {'Succès' if success else 'Échec'}")
        return success
        
    except Exception as e:
        print(f"❌ delete_conversation: Exception: {e}")
        return False

# ===================================================
# MESSAGES - VERSION CORRIGÉE
# ===================================================

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    """Ajoute un message avec validation complète"""
    try:
        if not supabase:
            print("❌ add_message: Supabase non connecté")
            return False
            
        if not conversation_id:
            print("❌ add_message: conversation_id manquant")
            return False
            
        if not content or not str(content).strip():
            print("❌ add_message: contenu vide")
            return False

        # Nettoyer les données
        sender = str(sender).strip() if sender else "unknown"
        content = clean_message_content(content)
        msg_type = msg_type or "text"

        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("conversation_id, id").eq("conversation_id", conversation_id).execute()
        
        if hasattr(conv_check, 'error') and conv_check.error:
            print(f"❌ add_message: Erreur vérification conversation: {conv_check.error}")
            return False
            
        if not conv_check.data:
            print(f"❌ add_message: Conversation {conversation_id} n'existe pas")
            return False

        # Préparer les données du message
        message_data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "created_at": datetime.now().isoformat()
        }
        
        if image_data:
            message_data["image_data"] = image_data

        print(f"🔍 add_message: Données à insérer: {message_data}")

        # Insérer le message
        response = supabase.table("messages").insert(message_data).execute()
        
        print(f"🔍 add_message: Réponse Supabase: {response}")

        if hasattr(response, 'error') and response.error:
            print(f"❌ add_message: Erreur Supabase: {response.error}")
            return False

        if not response.data or len(response.data) == 0:
            print("❌ add_message: Insertion échoué, aucune donnée retournée")
            return False

        print(f"✅ add_message: Message ajouté avec succès")
        return True
        
    except Exception as e:
        print(f"❌ add_message: Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_messages(conversation_id):
    """
    FONCTION CORRIGÉE - Récupère les messages d'une conversation
    """
    print(f"\n🔍 ==> get_messages appelée avec conversation_id: {conversation_id}")
    
    try:
        # Vérification 1: Client Supabase
        if not supabase:
            print("❌ get_messages: Client Supabase non connecté")
            try:
                st.error("❌ Client Supabase non connecté dans get_messages")
            except:
                pass
            return []

        # Vérification 2: Paramètre
        if not conversation_id:
            print("❌ get_messages: conversation_id manquant ou vide")
            return []

        conversation_id = str(conversation_id).strip()
        print(f"🔍 get_messages: conversation_id nettoyé: '{conversation_id}'")

        # Vérification 3: Test de connexion rapide
        try:
            connection_test = supabase.table("messages").select("*").limit(1).execute()
            print(f"✅ get_messages: Test de connexion réussi")
        except Exception as conn_e:
            print(f"❌ get_messages: Test de connexion échoué: {conn_e}")
            return []

        # Requête principale avec debug détaillé
        print(f"🔍 get_messages: Exécution de la requête...")
        
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        
        print(f"🔍 get_messages: Réponse reçue")
        print(f"🔍 get_messages: Type de réponse: {type(response)}")
        
        # Vérification 4: Erreurs Supabase
        if hasattr(response, 'error') and response.error:
            print(f"❌ get_messages: Erreur Supabase: {response.error}")
            try:
                st.error(f"❌ Erreur Supabase dans get_messages: {response.error}")
            except:
                pass
            return []

        # Vérification 5: Données de réponse
        if not hasattr(response, 'data'):
            print(f"❌ get_messages: Réponse sans attribut 'data'")
            return []

        if response.data is None:
            print(f"⚠️ get_messages: response.data est None")
            return []

        print(f"🔍 get_messages: Nombre de messages bruts: {len(response.data)}")

        if len(response.data) == 0:
            print(f"⚠️ get_messages: Aucun message trouvé pour conversation_id: {conversation_id}")
            
            # Debug: Vérifier tous les conversation_id existants
            try:
                all_convs_test = supabase.table("messages").select("conversation_id").limit(10).execute()
                existing_conv_ids = [msg.get("conversation_id") for msg in all_convs_test.data] if all_convs_test.data else []
                print(f"🔍 get_messages: Conversation IDs existants en DB: {set(existing_conv_ids)}")
                print(f"🔍 get_messages: Recherché: {conversation_id}")
                print(f"🔍 get_messages: Trouvé dans la liste: {conversation_id in existing_conv_ids}")
            except Exception as debug_e:
                print(f"⚠️ get_messages: Debug des conv_ids échoué: {debug_e}")
            
            return []

        # Traitement des messages
        messages = []
        print(f"🔍 get_messages: Traitement de {len(response.data)} messages...")

        for i, msg in enumerate(response.data):
            try:
                # Identifier la clé ID (message_id ou id)
                msg_id = msg.get("message_id") or msg.get("id")
                
                # Construire le message formaté
                formatted_message = {
                    "message_id": msg_id,
                    "sender": msg.get("sender", "unknown"),
                    "content": msg.get("content", ""),
                    "created_at": msg.get("created_at"),
                    "type": msg.get("type", "text"),
                    "image_data": msg.get("image_data")
                }
                
                messages.append(formatted_message)
                
                # Debug pour les premiers messages
                if i < 2:
                    print(f"✅ get_messages: Message {i+1} - {msg.get('sender')}: {msg.get('content', '')[:30]}...")
                    
            except Exception as msg_e:
                print(f"❌ get_messages: Erreur traitement message {i}: {msg_e}")
                continue

        print(f"✅ get_messages: {len(messages)} messages traités avec succès")
        
        # Afficher dans Streamlit si possible
        try:
            st.success(f"✅ get_messages: {len(messages)} messages chargés pour la conversation")
        except:
            pass

        return messages

    except Exception as e:
        print(f"❌ get_messages: Exception générale: {e}")
        print(f"❌ get_messages: Type d'exception: {type(e).__name__}")
        
        # Stack trace complète
        import traceback
        print("❌ get_messages: Stack trace:")
        traceback.print_exc()
        
        # Afficher dans Streamlit si possible
        try:
            st.error(f"❌ Exception dans get_messages: {e}")
            st.code(traceback.format_exc(), language="python")
        except:
            pass
        
        return []

def add_messages_batch(conversation_id, messages_list):
    """Ajoute plusieurs messages en une fois"""
    try:
        if not supabase or not messages_list:
            print("❌ add_messages_batch: Paramètres invalides")
            return False
            
        if not conversation_id:
            print("❌ add_messages_batch: conversation_id manquant")
            return False

        # Vérifier la conversation
        conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
        
        if hasattr(conv_check, 'error') and conv_check.error:
            print(f"❌ add_messages_batch: Erreur vérification: {conv_check.error}")
            return False
            
        if not conv_check.data:
            print(f"❌ add_messages_batch: Conversation {conversation_id} n'existe pas")
            return False

        # Nettoyer les messages
        cleaned_messages = []
        for msg in messages_list:
            sender = str(msg.get("sender", "unknown")).strip()
            content = clean_message_content(msg.get("content", ""))
            created_at = msg.get("created_at") or datetime.now().isoformat()
            msg_type = msg.get("type", "text")
            image_data = msg.get("image_data")
            
            if content:  # Seulement si il y a du contenu
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

        if not cleaned_messages:
            print("⚠️ add_messages_batch: Aucun message valide à insérer")
            return False

        # Insertion batch
        response = supabase.table("messages").insert(cleaned_messages).execute()
        
        if hasattr(response, 'error') and response.error:
            print(f"❌ add_messages_batch: Erreur batch: {response.error}")
            return False

        success = bool(response.data and len(response.data) > 0)
        print(f"✅ add_messages_batch: {len(cleaned_messages)} messages ajoutés")
        return success
        
    except Exception as e:
        print(f"❌ add_messages_batch: Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def delete_message(message_id):
    """Supprime un message par son ID"""
    try:
        if not supabase:
            print("❌ delete_message: Supabase non connecté")
            return False
            
        if not message_id:
            print("❌ delete_message: message_id manquant")
            return False

        response = supabase.table("messages").delete().eq("message_id", message_id).execute()
        
        if hasattr(response, 'error') and response.error:
            print(f"❌ delete_message: Erreur: {response.error}")
            return False

        success = bool(response.data and len(response.data) > 0)
        print(f"✅ delete_message: {'Supprimé' if success else 'Non trouvé'}")
        return success
        
    except Exception as e:
        print(f"❌ delete_message: Exception: {e}")
        return False

# ===================================================
# STATISTIQUES ET DEBUG
# ===================================================

def test_connection():
    """Test complet de la connexion Supabase"""
    try:
        if not supabase:
            print("❌ test_connection: Client Supabase non connecté")
            return False

        print("🔍 Test de connexion Supabase...")
        
        # Tester chaque table
        tables = ["users", "conversations", "messages"]
        results = {}
        
        for table_name in tables:
            try:
                response = supabase.table(table_name).select("*").limit(1).execute()
                
                if hasattr(response, 'error') and response.error:
                    results[table_name] = f"❌ Erreur: {response.error}"
                else:
                    count = len(response.data) if response.data else 0
                    results[table_name] = f"✅ OK ({count} exemple(s))"
                    
            except Exception as table_e:
                results[table_name] = f"❌ Exception: {table_e}"

        # Afficher les résultats
        for table, result in results.items():
            print(f"Table {table}: {result}")

        # Test global
        all_success = all("✅" in result for result in results.values())
        print(f"🔍 Test global: {'✅ Succès' if all_success else '❌ Échec'}")
        
        return all_success
        
    except Exception as e:
        print(f"❌ test_connection: Exception générale: {e}")
        return False

def get_database_stats():
    """Récupère les statistiques de la base de données"""
    try:
        if not supabase:
            print("❌ get_database_stats: Supabase non connecté")
            return
            
        print("📊 Statistiques de la base de données:")
        
        # Compter les utilisateurs
        try:
            users_response = supabase.table("users").select("*", count="exact").execute()
            users_count = users_response.count if hasattr(users_response, 'count') else len(users_response.data or [])
            print(f"👥 Utilisateurs: {users_count}")
        except Exception as e:
            print(f"👥 Utilisateurs: Erreur ({e})")
        
        # Compter les conversations
        try:
            conv_response = supabase.table("conversations").select("*", count="exact").execute()
            conv_count = conv_response.count if hasattr(conv_response, 'count') else len(conv_response.data or [])
            print(f"💬 Conversations: {conv_count}")
        except Exception as e:
            print(f"💬 Conversations: Erreur ({e})")
        
        # Compter les messages
        try:
            msg_response = supabase.table("messages").select("*", count="exact").execute()
            msg_count = msg_response.count if hasattr(msg_response, 'count') else len(msg_response.data or [])
            print(f"📨 Messages: {msg_count}")
        except Exception as e:
            print(f"📨 Messages: Erreur ({e})")
            
    except Exception as e:
        print(f"❌ get_database_stats: Exception: {e}")

# ===================================================
# FONCTIONS DE DEBUG SPÉCIFIQUES
# ===================================================

def debug_conversation_messages(conversation_id):
    """Debug spécifique pour une conversation"""
    print(f"\n🔍 DEBUG CONVERSATION: {conversation_id}")
    
    if not supabase:
        print("❌ Supabase non connecté")
        return
    
    try:
        # Test 1: Requête directe
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).execute()
        print(f"📊 Messages trouvés: {len(response.data) if response.data else 0}")
        
        # Test 2: Afficher quelques exemples
        if response.data:
            for i, msg in enumerate(response.data[:3]):
                print(f"Msg {i+1}: {msg.get('sender')} - {msg.get('content', '')[:50]}...")
        
        # Test 3: Vérifier la structure
        if response.data:
            first_msg = response.data[0]
            print(f"🔍 Colonnes message: {list(first_msg.keys())}")
        
    except Exception as e:
        print(f"❌ Debug échoué: {e}")

def reset_supabase_client():
    """Réinitialise le client Supabase"""
    global supabase
    print("🔄 Réinitialisation du client Supabase...")
    supabase = get_supabase_client()
    return supabase is not None

