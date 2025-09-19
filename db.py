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
    print("Test terminé - Module db.py mis à jour et fonctionnel!") voici mon db.py
ChatGPT ha detto:

Merci pour le partage complet de ton db.py. Maintenant, avec ce code, on peut analyser pourquoi dans ton Streamlit add_message retourne toujours False.

Voici mes observations principales :

1️⃣ Vérification de conversation_id

Dans add_message :

conv_check = supabase.table("conversations").select("conversation_id").eq("conversation_id", conversation_id).execute()
if not conv_check.data:
    print(f"Conversation {conversation_id} n'existe pas")
    return False


Si conv_check.data est vide, add_message retourne False.

Donc le problème le plus courant : le conversation_id que tu passes à add_message n’existe pas en base.

Avec ta fonction create_conversation, tu standardises la clé avec "conversation_id": conv_id. Assure-toi que le champ dans Supabase s’appelle bien conversation_id et non id. Sinon, conv_check sera toujours vide.

✅ Vérifie dans Supabase que la table conversations a exactement conversation_id comme colonne, et que tu ne confonds pas avec id.

2️⃣ Vérification de la colonne image_data

Tu as ajouté :

if image_data:
    data["image_data"] = image_data


Assure-toi que dans Supabase, la colonne image_data existe bien et accepte NULL.

Si la colonne n’existe pas, Supabase ignore la colonne mais ne renvoie pas forcément une erreur, donc response.data peut être vide → False.

3️⃣ Debug détaillé pour add_message

Pour identifier le problème exact, modifie add_message comme ceci :

response = supabase.table("messages").insert(data).execute()
print("DEBUG add_message - données envoyées:", data)
print("DEBUG add_message - réponse brute:", response)

if hasattr(response, 'error') and response.error:
    print("❌ Erreur Supabase messages:", response.error)
    return False

if not response.data or len(response.data) == 0:
    print("⚠️ Insertion retournée vide, message non sauvegardé")
    return False

return True


Cela te montrera si la requête atteint Supabase et pourquoi data est vide.

4️⃣ Vérification rapide dans Streamlit

Avant d’appeler add_message, ajoute :

conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
st.write(f"DEBUG: conv_id avant add_message: {conv_id}")


Si conv_id est None ou ne correspond pas à la base → retournera toujours False.

Vérifie aussi avec db.get_conversations(user_id) que la conversation existe.

5️⃣ Résumé des causes possibles

conversation_id passé à add_message n’existe pas → conv_check.data vide.

La colonne image_data n’existe pas dans Supabase → insertion échoue.

Format du message (content, type) incorrect ou trop long → insertion rejetée.

💡 Action immédiate recommandée :

Ajoute les prints debug que j’ai mis au point 3.

Vérifie le nom exact de la colonne conversation_id dans Supabase.

Assure-toi que la conversation est bien créée avant d’ajouter un message.

Si tu veux, je peux te réécrire une version “super-safe” de add_message qui :

Vérifie que la conversation existe,

Crée la conversation si elle n’existe pas,

Retourne un debug complet pour tout échec,

…ce qui rendra ton Streamlit beaucoup plus fiable et plus facile à débugger.

Veux‑tu que je fasse ça ?

Hai detto:
fais en sorte que le format soit correct parce que image_data est la 
ChatGPT ha detto:

Parfait ! On va réécrire add_message pour que le format soit compatible avec Supabase, que la colonne image_data soit bien gérée, et que tu aies un debug complet si ça échoue.

Voici une version “super-safe” :

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

        # Nettoyer les données
        sender = str(sender).strip() if sender else "unknown"
        content = clean_message_content(content)
        msg_type = msg_type or "text"

        # Vérifier si la conversation existe
        conv_check = supabase.table("conversations")\
            .select("conversation_id")\
            .eq("conversation_id", conversation_id)\
            .execute()

        if not conv_check.data:
            print(f"❌ Conversation {conversation_id} n'existe pas")
            return False

        # Préparer le dictionnaire pour insertion
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "created_at": datetime.now().isoformat()
        }

        # Ajouter image_data si fourni
        if image_data:
            data["image_data"] = image_data

        # Debug : afficher ce qu'on envoie
        print("DEBUG add_message - données envoyées:", data)

        # Insertion Supabase
        response = supabase.table("messages").insert(data).execute()

        # Debug : réponse brute
        print("DEBUG add_message - réponse Supabase:", response)

        # Vérifier erreur Supabase
        if hasattr(response, 'error') and response.error:
            print("❌ Erreur Supabase messages:", response.error)
            return False

        # Vérifier si insertion effective
        if not response.data or len(response.data) == 0:
            print("⚠️ Insertion vide, message non sauvegardé")
            return False

        print("✅ Message ajouté avec succès")
        return True

    except Exception as e:
        print(f"❌ Exception add_message: {e}")
        import traceback
        traceback.print_exc()
        return False

✅ Points importants de cette version

image_data est ajouté seulement si fourni.

Nettoyage du content pour éviter les caractères invalides.

Vérifie que la conversation existe avant d’insérer.

Debug complet pour savoir exactement pourquoi ça échoue.

Retourne toujours True/False de façon fiable.

Si tu veux, je peux maintenant te donner la version Streamlit qui utilise cette fonction et sauvegarde automatiquement les messages image et texte, avec les debug visibles dans l’interface.

Veux‑tu que je fasse ça ?

Hai detto:
recrire moi tout le code avec cette mises ajours
ChatGPT ha detto:

Parfait ! Je vais te réécrire tout ton code Streamlit avec la version corrigée de db.add_message et le support complet de image_data, en intégrant aussi les debug pour que tu voies exactement ce qui se passe.

Voici la version complète :

import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB mis à jour avec add_message corrigé

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
SYSTEM_PROMPT = """You are Vision AI.
You were created by Pepe Musafiri, an Artificial Intelligence Engineer,
with contributions from Meta AI.
Your role is to help users with any task they need, from image analysis
and editing to answering questions clearly and helpfully.
Always answer naturally as Vision AI.

When you receive an image description starting with [IMAGE], you should:
1. Acknowledge that you can see and analyze the image
2. Provide detailed analysis of what you observe
3. Answer any specific questions about the image
4. Be helpful and descriptive in your analysis"""

# -------------------------
# Utility functions
# -------------------------
def image_to_base64(image):
    """Convertir une image PIL en base64 pour la stockage"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return img_str
    except:
        return None

def base64_to_image(img_str):
    """Convertir base64 en image PIL"""
    try:
        img_bytes = base64.b64decode(img_str)
        return Image.open(io.BytesIO(img_bytes))
    except:
        return None

def load_user_last_conversation(user_id):
    """Charger la dernière conversation de l'utilisateur"""
    try:
        if user_id != "guest":
            st.write(f"DEBUG load_user_last_conversation: user_id = {user_id}")
            convs = db.get_conversations(user_id)
            st.write(f"DEBUG load_user_last_conversation: conversations récupérées = {convs}")
            if convs and len(convs) > 0:
                st.write(f"DEBUG load_user_last_conversation: Retourne conversation = {convs[0]}")
                return convs[0]
            else:
                st.write("DEBUG load_user_last_conversation: Aucune conversation trouvée")
        else:
            st.write("DEBUG load_user_last_conversation: user_id est guest")
        return None
    except Exception as e:
        st.error(f"Erreur chargement conversation: {e}")
        st.write(f"DEBUG load_user_last_conversation: Exception = {str(e)}")
        return None

def safe_create_conversation(user_id, description):
    """Créer une conversation avec gestion d'erreur"""
    try:
        st.write(f"DEBUG safe_create_conversation: user_id={user_id}, description={description}")
        conv = db.create_conversation(user_id, description)
        st.write(f"DEBUG safe_create_conversation: résultat brut = {conv}")
        if conv is None:
            st.error("Erreur: create_conversation a retourné None")
            return None
        if isinstance(conv, dict):
            return conv
        st.write(f"DEBUG safe_create_conversation: type non-dict détecté: {type(conv)}")
        return None
    except Exception as e:
        st.error(f"Erreur création conversation: {e}")
        st.write(f"DEBUG safe_create_conversation: Exception = {str(e)}")
        return None

def save_active_conversation(user_id, conv_id):
    """Fonction placeholder - pas d'erreur si conv_id est None"""
    if user_id and conv_id:
        st.write(f"DEBUG save_active_conversation: user_id={user_id}, conv_id={conv_id}")
    pass

# -------------------------
# BLIP loader
# -------------------------
@st.cache_resource
def load_blip():
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return processor, model
    except Exception as e:
        st.error(f"Erreur BLIP: {e}")
        return None, None

def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Description indisponible"
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"Erreur génération: {e}"

# -------------------------
# Session init avec persistance
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "conversation_loaded" not in st.session_state:
    st.session_state.conversation_loaded = False
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter LLaMA.")

# -------------------------
# AI functions
# -------------------------
def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible."
    try:
        resp = st.session_state.llama_client.predict(
            message=query,
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"❌ Erreur modèle: {e}"

def stream_response(text, placeholder):
    full_text = ""
    text_str = str(text)
    thinking_messages = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_messages:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.3)
    for i, char in enumerate(text_str):
        full_text += char
        display_text = full_text + "**█**"
        placeholder.markdown(display_text)
        if char == ' ':
            time.sleep(0.01)
        elif char in '.,!?;:':
            time.sleep(0.1)
        else:
            time.sleep(0.03)
    placeholder.markdown(full_text)
    time.sleep(0.2)
    placeholder.markdown(full_text + " ✅")
    time.sleep(0.5)
    placeholder.markdown(full_text)

# -------------------------
# Auth avec restauration de session
# -------------------------
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Se connecter"):
                st.write(f"DEBUG: Tentative de connexion avec email: {email}")
                user_result = db.verify_user(email, password)
                st.write(f"DEBUG: Résultat verify_user: {user_result}")
                if user_result:
                    st.session_state.user = user_result
                    last_conv = load_user_last_conversation(user_result["id"])
                    st.session_state.conversation = last_conv
                    st.session_state.messages_memory = []
                    st.session_state.conversation_loaded = False
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Email ou mot de passe invalide")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.session_state.conversation = None
                st.session_state.messages_memory = []
                st.session_state.conversation_loaded = False
                st.rerun()
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        if st.button("✨ Créer mon compte"):
            if email_reg and name_reg and pass_reg:
                ok = db.create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Compte créé, connecte-toi.")
                else:
                    st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# Auto-chargement de la dernière conversation avec debug
# -------------------------
if st.session_state.user["id"] != "guest" and not st.session_state.conversation_loaded:
    last_conv = load_user_last_conversation(st.session_state.user["id"])
    if last_conv:
        st.session_state.conversation = last_conv
        st.info(f"Dernière conversation chargée: {last_conv.get('description', 'Sans titre')}")
    st.session_state.conversation_loaded = True

# -------------------------
# Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = safe_create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            st.session_state.messages_memory = []
            conv_id_for_save = conv.get("conversation_id")
            save_active_conversation(st.session_state.user["id"], conv_id_for_save)
            st.rerun()
        else:
            st.error("Impossible de créer une nouvelle conversation")
    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            current_conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
            options = ["Choisir une conversation..."]
            for c in convs:
                title = f"{c['description']} - {c['created_at']}"
                if c.get('conversation_id') == current_conv_id:
                    title += " (Actuelle)"
                options.append(title)
            sel = st.sidebar.selectbox("Vos conversations:", options)
            if sel != "Choisir une conversation..." and not sel.endswith(" (Actuelle)"):
                idx = options.index(sel) - 1
                selected_conv = convs[idx]
                if st.session_state.conversation != selected_conv:
                    st.session_state.conversation = selected_conv
                    st.session_state.messages_memory = []
                    st.rerun()
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Créé par <b>Pepe Musafiri</b></p>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)
if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description', 'Conversation sans titre')
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title}</p>", unsafe_allow_html=True)

# -------------------------
# Affichage des messages existants
# -------------------------
display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    try:
        db_msgs = db.get_messages(conv_id)
        if db_msgs:
            for m in db_msgs:
                display_msgs.append({
                    "sender": m["sender"], 
                    "content": m["content"], 
                    "created_at": m["created_at"], 
                    "type": m.get("type", "text"),
                    "image_data": m.get("image_data", None)
                })
    except Exception as e:
        st.error(f"Erreur chargement messages: {e}")
else:
    display_msgs = st.session_state.messages_memory.copy()

# Afficher l'historique
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        if m.get("type") == "image":
            if m.get("image_data"):
                img = base64_to_image(m["image_data"])
                if img:
                    st.image(img, caption="Image analysée", width=300)
                else:
                    st.write("📷 Image (non disponible)")
            else:
                st.write("📷 Image uploadée")
            if "[IMAGE]" in m["content"]:
                description = m["content"].replace("[IMAGE] ", "").split("\n\nQuestion/Demande")[0]
                st.write(f"*Description automatique: {description}*")
                if "Question/Demande de l'utilisateur:" in m["content"]:
                    user_question = m["content"].split("Question/Demande de l'utilisateur: ")[1]
                    st.write(f"**Question:** {user_question}")
        else:
            st.markdown(m["content"])

# -------------------------
# Conteneur pour les nouveaux messages
# -------------------------
message_container = st.container()

# -------------------------
# Formulaire de saisie
# -------------------------
with st.form(key="chat_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"], key="image_upload")
    user_input = st.text_area("💭 Tapez votre message...", key="user_message", placeholder="Posez votre question ou décrivez ce que vous voulez que j'analyse dans l'image...", height=80)
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

# -------------------------
# Traitement message
# -------------------------
if submit_button and (user_input or uploaded_file):
    if st.session_state.user["id"] != "guest" and not st.session_state.conversation:
        conv = safe_create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            conv_id = conv.get("conversation_id")
        else:
            st.error("Impossible de créer une conversation")
            st.stop()
    else:
        conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None

    img_base64 = None
    if uploaded_file:
        try:
            img = Image.open(uploaded_file).convert("RGB")
            img_base64 = image_to_base64(img)
            caption = generate_caption(img, st.session_state.processor, st.session_state.model)
            user_input = f"[IMAGE] {caption}\n\nQuestion/Demande de l'utilisateur: {user_input}" if user_input else f"[IMAGE] {caption}"
        except Exception as e:
            st.error(f"Erreur traitement image: {e}")

    # Ajouter le message dans la DB
    ok = db.add_message(conv_id, "user", user_input, "image" if uploaded_file else "text", img_base64)
    if ok:
        st.session_state.messages_memory.append({"sender": "user", "content": user_input, "type": "image" if uploaded_file else "text", "image_data": img_base64, "created_at": time.time()})
    else:
        st.warning("Impossible d'ajouter le message à la conversation")

    # Obtenir la réponse AI
    placeholder = message_container.empty()
    response_text = get_ai_response(user_input)
    stream_response(response_text, placeholder)

    # Ajouter réponse AI à la DB
    if st.session_state.conversation:
        db.add_message(conv_id, "assistant", response_text, "text")
        st.session_state.messages_memory
