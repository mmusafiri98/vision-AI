import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client, handle_file
import time
import pandas as pd
import io
import base64
import os
import uuid
import traceback
from supabase import create_client
import random
import string
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup
import json
import re

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Debug", layout="wide")

# Debug Mode Toggle
DEBUG_MODE = True  # Activé par défaut pour voir les logs

def debug_log(message, data=None):
    """Fonction de logging pour le debug"""
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        st.sidebar.markdown(f"**[{timestamp}]** {message}")
        if data is not None:
            st.sidebar.code(str(data))

SYSTEM_PROMPT = """You are Vision AI. You were created by Pepe Musafiri, an Artificial Intelligence Engineer, with contributions from Meta AI.

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE:
1. When you receive [DATETIME] information, YOU MUST USE IT to answer any time/date questions. This is the REAL current date and time.
2. When you receive [WEB_SEARCH] results, YOU MUST USE THEM to provide accurate, up-to-date information. These are REAL search results from the internet.
3. NEVER say you don't know the current date/time when [DATETIME] information is provided.
4. ALWAYS cite and use the web search results when they are provided in [WEB_SEARCH].
5. Your knowledge cutoff is January 2025, but you can access current information through web searches.
6. WEB SEARCH COVERS ALL YEARS: The search results include content from ALL years available on the web (2000-2025 and beyond).
7. YOUTUBE DATA IS COMPREHENSIVE: You have access to video titles, descriptions, view counts, like counts, comment counts, upload dates, and channel information from ALL years.

You have access to:
- Current date and time information (provided in [DATETIME])
- Real-time web search capabilities covering ALL YEARS (results in [WEB_SEARCH])
- YouTube data including statistics, comments, and content from ALL YEARS
- Image analysis and editing tools

When you receive web search results starting with [WEB_SEARCH]:
- These are REAL search results covering content from ALL YEARS (not just 2025)
- The data includes historical content, recent content, and everything in between
- For YouTube: you receive view counts, like counts, comment counts, upload dates, and more
- YOU MUST analyze and use this information in your response
- Cite the sources, dates, and statistics provided
- DO NOT rely only on your training data - USE THE COMPREHENSIVE SEARCH RESULTS PROVIDED"""

# Informations admin
ADMIN_CREDENTIALS = {
    "email": "jessice34@gmail.com",
    "password": "4Us,T}17"
}

# -------------------------
# Configuration des API Keys
# -------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# -------------------------
# Dossiers locaux
# -------------------------
TMP_DIR = "tmp_files"
EDITED_IMAGES_DIR = "edited_images"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(EDITED_IMAGES_DIR, exist_ok=True)

# -------------------------
# Supabase Connection AMÉLIORÉE
# -------------------------

@st.cache_resource
def init_supabase():
    """Initialise Supabase avec gestion d'erreur complète et debug"""
    try:
        debug_log("🔄 Initialisation de Supabase...")
        
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        debug_log("🔍 Vérification des variables d'environnement", {
            "SUPABASE_URL": "✅ Présente" if supabase_url else "❌ Manquante",
            "SUPABASE_SERVICE_KEY": "✅ Présente" if supabase_key else "❌ Manquante"
        })
        
        if not supabase_url or not supabase_key:
            st.error("❌ Variables Supabase manquantes dans les secrets")
            debug_log("❌ Échec: Variables manquantes")
            return None
            
        debug_log("🔌 Création du client Supabase...")
        client = create_client(supabase_url, supabase_key)
        
        debug_log("🧪 Test de connexion à la table 'users'...")
        test = client.table("users").select("*").limit(1).execute()
        
        debug_log("✅ Supabase connecté avec succès!", {
            "Nombre d'utilisateurs (sample)": len(test.data) if test.data else 0
        })
        
        st.success("✅ Supabase connecté avec succès")
        return client
        
    except Exception as e:
        error_msg = f"❌ Erreur connexion Supabase: {str(e)}"
        st.error(error_msg)
        debug_log(error_msg, traceback.format_exc())
        return None

supabase = init_supabase()

# -------------------------
# Fonctions de récupération de mot de passe
# -------------------------

def generate_reset_token():
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    debug_log("🔑 Token de réinitialisation généré", {"longueur": len(token)})
    return token

def store_reset_token(email, token):
    if not supabase:
        debug_log("❌ store_reset_token: Supabase non disponible")
        return False
    try:
        debug_log(f"💾 Stockage du token pour {email}")
        expiration = time.time() + 3600
        
        debug_log("🔍 Vérification de l'existence de l'utilisateur...")
        user_check = supabase.table("users").select("*").eq("email", email).execute()
        
        if not user_check.data:
            debug_log(f"❌ Utilisateur {email} non trouvé")
            return False
            
        debug_log(f"✅ Utilisateur trouvé, mise à jour du token...")
        
        try:
            response = supabase.table("users").update({
                "reset_token": token,
                "reset_token_expires": expiration,
                "reset_token_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }).eq("email", email).execute()
            
            debug_log("✅ Token stocké dans la table users", {
                "success": bool(response.data)
            })
            return bool(response.data)
            
        except Exception as e:
            debug_log(f"⚠️ Tentative alternative avec table password_resets...", str(e))
            try:
                token_data = {
                    "email": email,
                    "reset_token": token,
                    "expires_at": expiration,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "used": False
                }
                supabase.table("password_resets").delete().eq("email", email).execute()
                response = supabase.table("password_resets").insert(token_data).execute()
                
                debug_log("✅ Token stocké dans password_resets", {
                    "success": bool(response.data)
                })
                return bool(response.data)
            except Exception as e2:
                debug_log("❌ Échec stockage token", str(e2))
                return False
    except Exception as e:
        debug_log("❌ Erreur store_reset_token", str(e))
        return False

def verify_reset_token(email, token):
    if not supabase:
        debug_log("❌ verify_reset_token: Supabase non disponible")
        return False
    try:
        debug_log(f"🔍 Vérification du token pour {email}")
        current_time = time.time()
        
        try:
            response = supabase.table("users").select("reset_token, reset_token_expires").eq("email", email).execute()
            if response.data:
                user_data = response.data[0]
                is_valid = user_data.get("reset_token") == token and user_data.get("reset_token_expires", 0) > current_time
                debug_log(f"Token vérifié dans users: {'✅ Valide' if is_valid else '❌ Invalide'}")
                if is_valid:
                    return True
        except Exception as e:
            debug_log("⚠️ Vérification users échouée, tentative password_resets...", str(e))
            
        try:
            response = supabase.table("password_resets").select("*").eq("email", email).eq("reset_token", token).eq("used", False).execute()
            if response.data:
                is_valid = response.data[0].get("expires_at", 0) > current_time
                debug_log(f"Token vérifié dans password_resets: {'✅ Valide' if is_valid else '❌ Expiré'}")
                return is_valid
        except Exception as e:
            debug_log("❌ Vérification password_resets échouée", str(e))
            
        debug_log("❌ Token non trouvé ou invalide")
        return False
        
    except Exception as e:
        debug_log("❌ Erreur verify_reset_token", str(e))
        return False

def reset_password(email, token, new_password):
    if not supabase:
        debug_log("❌ reset_password: Supabase non disponible")
        return False
        
    if not verify_reset_token(email, token):
        debug_log("❌ Token invalide ou expiré")
        return False
        
    try:
        debug_log(f"🔄 Réinitialisation du mot de passe pour {email}")
        
        update_data = {
            "password": new_password,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reset_token": None,
            "reset_token_expires": None,
            "reset_token_created": None
        }
        
        update_response = supabase.table("users").update(update_data).eq("email", email).execute()
        
        if update_response.data:
            debug_log("✅ Mot de passe réinitialisé avec succès")
            try:
                supabase.table("password_resets").update({
                    "used": True,
                    "used_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }).eq("email", email).eq("reset_token", token).execute()
                debug_log("✅ Token marqué comme utilisé")
            except:
                pass
            return True
            
        debug_log("❌ Échec de la mise à jour du mot de passe")
        return False
        
    except Exception as e:
        debug_log("❌ Erreur reset_password", str(e))
        return False

# -------------------------
# Fonctions DB AVEC DEBUG COMPLET
# -------------------------

def verify_user(email, password):
    debug_log(f"🔐 Tentative de connexion pour {email}")
    
    # Vérification admin
    if email == ADMIN_CREDENTIALS["email"] and password == ADMIN_CREDENTIALS["password"]:
        debug_log("✅ Connexion admin réussie")
        return {
            "id": "admin_special_id",
            "email": email,
            "name": "Jessica Admin",
            "role": "admin"
        }
    
    if not supabase:
        debug_log("❌ Supabase non disponible pour verify_user")
        return None
        
    try:
        # Tentative avec Supabase Auth
        debug_log("🔄 Tentative avec Supabase Auth...")
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                debug_log("✅ Authentification Supabase Auth réussie")
                user_data = supabase.table("users").select("*").eq("email", email).execute()
                role = user_data.data[0].get("role", "user") if user_data.data else "user"
                
                user_obj = {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0]),
                    "role": role
                }
                debug_log("✅ Utilisateur connecté via Auth", user_obj)
                return user_obj
        except Exception as e:
            debug_log("⚠️ Auth échouée, tentative avec table users...", str(e))
            
        # Tentative avec table users
        debug_log("🔄 Vérification dans la table users...")
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        debug_log(f"📊 Résultat de la requête users", {
            "Nombre de résultats": len(response.data) if response.data else 0
        })
        
        if response.data:
            user = response.data[0]
            debug_log("🔍 Utilisateur trouvé, vérification du mot de passe...")
            
            if user.get("password") == password:
                user_obj = {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user.get("name", email.split("@")[0]),
                    "role": user.get("role", "user")
                }
                debug_log("✅ Connexion réussie via table users", user_obj)
                return user_obj
            else:
                debug_log("❌ Mot de passe incorrect")
        else:
            debug_log("❌ Utilisateur non trouvé dans la base")
            
        return None
        
    except Exception as e:
        debug_log("❌ Erreur verify_user", str(e))
        return None

def create_user(email, password, name, role="user"):
    if not supabase:
        debug_log("❌ create_user: Supabase non disponible")
        return False
        
    try:
        debug_log(f"👤 Création d'utilisateur: {email}")
        
        # Vérifier si l'utilisateur existe déjà
        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            debug_log("❌ Utilisateur existe déjà")
            st.error("Cet email est déjà utilisé")
            return False
        
        # Tentative avec Supabase Auth
        debug_log("🔄 Création via Supabase Auth...")
        try:
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "role": role
                    }
                }
            })
            
            if auth_response.user:
                debug_log("✅ Utilisateur créé via Auth", {
                    "user_id": auth_response.user.id
                })
                
                # Insertion dans la table users
                user_data = {
                    "id": auth_response.user.id,
                    "email": email,
                    "password": password,
                    "name": name,
                    "role": role,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                debug_log("💾 Insertion dans la table users...", user_data)
                response = supabase.table("users").insert(user_data).execute()
                
                if response.data:
                    debug_log("✅ Utilisateur inséré dans la table users")
                    return True
                else:
                    debug_log("⚠️ Utilisateur créé via Auth mais pas dans la table")
                    return True  # Auth a réussi
                    
        except Exception as e:
            debug_log("⚠️ Création Auth échouée, tentative directe dans table...", str(e))
            
        # Tentative directe dans la table users
        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": password,
            "name": name,
            "role": role,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        debug_log("💾 Insertion directe dans users...", user_data)
        response = supabase.table("users").insert(user_data).execute()
        
        if response.data:
            debug_log("✅ Utilisateur créé directement dans la table")
            return True
        else:
            debug_log("❌ Échec de l'insertion", response)
            return False
            
    except Exception as e:
        debug_log("❌ Erreur create_user", str(e))
        st.error(f"Erreur lors de la création de compte: {e}")
        return False

def get_conversations(user_id):
    if not supabase or not user_id:
        debug_log("❌ get_conversations: Paramètres manquants", {
            "supabase": bool(supabase),
            "user_id": user_id
        })
        return []
        
    try:
        debug_log(f"📂 Récupération des conversations pour user_id: {user_id}")
        
        response = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        debug_log(f"📊 Conversations trouvées", {
            "Nombre": len(response.data) if response.data else 0
        })
        
        if not response.data:
            debug_log("ℹ️ Aucune conversation trouvée")
            return []
            
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
                
        debug_log(f"✅ {len(conversations)} conversations récupérées")
        return conversations
        
    except Exception as e:
        debug_log("❌ Erreur get_conversations", str(e))
        return []

def create_conversation(user_id, description):
    if not supabase or not user_id:
        debug_log("❌ create_conversation: Paramètres manquants", {
            "supabase": bool(supabase),
            "user_id": user_id
        })
        return None
        
    try:
        conv_id = str(uuid.uuid4())
        debug_log(f"➕ Création d'une conversation", {
            "conversation_id": conv_id,
            "user_id": user_id,
            "description": description
        })
        
        data = {
            "conversation_id": conv_id,
            "user_id": user_id,
            "description": description,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        debug_log("💾 Données à insérer dans conversations", data)
        
        response = supabase.table("conversations").insert(data).execute()
        
        debug_log("📊 Réponse de l'insertion", {
            "success": bool(response.data),
            "data": response.data if response.data else "Aucune donnée retournée"
        })
        
        if response.data:
            conv = response.data[0]
            result = {
                "conversation_id": conv.get("conversation_id"),
                "description": conv["description"],
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
            debug_log("✅ Conversation créée avec succès", result)
            return result
        else:
            debug_log("❌ Aucune donnée retournée lors de la création")
            return None
            
    except Exception as e:
        debug_log("❌ Erreur create_conversation", str(e))
        st.error(f"Erreur création conversation: {e}")
        return None

def get_messages(conversation_id):
    if not supabase or not conversation_id:
        debug_log("❌ get_messages: Paramètres manquants", {
            "supabase": bool(supabase),
            "conversation_id": conversation_id
        })
        return []
        
    try:
        debug_log(f"💬 Récupération des messages pour conversation: {conversation_id[:12]}...")
        
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        
        debug_log(f"📊 Messages trouvés", {
            "Nombre": len(response.data) if response.data else 0
        })
        
        if not response.data:
            debug_log("ℹ️ Aucun message trouvé")
            return []
            
        messages = []
        for msg in response.data:
            messages.append({
                "message_id": msg.get("id", str(uuid.uuid4())),
                "sender": msg.get("sender", "unknown"),
                "content": msg.get("content", ""),
                "created_at": msg.get("created_at"),
                "type": msg.get("type", "text"),
                "image_data": msg.get("image_data"),
                "edit_context": msg.get("edit_context")
            })
            
        debug_log(f"✅ {len(messages)} messages récupérés")
        return messages
        
    except Exception as e:
        debug_log("❌ Erreur get_messages", str(e))
        return []

# -------------------------
# Fonction add_message AVEC DEBUG ULTRA-DÉTAILLÉ
# -------------------------

def add_message(conversation_id, sender, content, msg_type="text", image_data=None, edit_context=None):
    """
    Ajoute un message à la base de données avec debug complet
    """
    debug_log("="*50)
    debug_log("📝 DÉBUT add_message")
    debug_log("="*50)
    
    # Vérification des paramètres
    debug_log("🔍 Vérification des paramètres d'entrée", {
        "conversation_id": conversation_id[:12] + "..." if conversation_id else "❌ MANQUANT",
        "sender": sender,
        "content_length": len(content) if content else 0,
        "msg_type": msg_type,
        "has_image_data": bool(image_data),
        "has_edit_context": bool(edit_context),
        "supabase_available": bool(supabase)
    })
    
    # Validation des paramètres requis
    if not supabase:
        debug_log("❌ ERREUR: Supabase non disponible")
        st.error("❌ Base de données non disponible")
        return False
        
    if not conversation_id:
        debug_log("❌ ERREUR: conversation_id manquant")
        st.error("❌ ID de conversation manquant")
        return False
        
    if not content:
        debug_log("❌ ERREUR: content manquant")
        st.error("❌ Contenu du message manquant")
        return False
    
    try:
        # Vérification de l'existence de la conversation
        debug_log(f"🔍 Vérification de l'existence de la conversation {conversation_id[:12]}...")
        
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        
        debug_log("📊 Résultat de la vérification conversation", {
            "found": bool(conv_check.data),
            "count": len(conv_check.data) if conv_check.data else 0,
            "data": conv_check.data[0] if conv_check.data else "Aucune conversation trouvée"
        })
        
        if not conv_check.data:
            debug_log(f"❌ ERREUR CRITIQUE: Conversation {conversation_id} n'existe pas!")
            st.error(f"❌ Conversation introuvable: {conversation_id[:12]}...")
            
            # Tentative de création de la conversation si elle n'existe pas
            debug_log("🔄 Tentative de récupération/création de la conversation...")
            if st.session_state.get("user") and st.session_state.user.get("id"):
                new_conv = create_conversation(
                    st.session_state.user["id"],
                    "Conversation récupérée"
                )
                if new_conv:
                    debug_log("✅ Conversation créée automatiquement", new_conv)
                    conversation_id = new_conv["conversation_id"]
                else:
                    debug_log("❌ Impossible de créer la conversation")
                    return False
            else:
                debug_log("❌ Impossible de créer la conversation: utilisateur non connecté")
                return False
        
        # Préparation des données du message
        message_id = str(uuid.uuid4())
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        message_data = {
            "id": message_id,
            "conversation_id": str(conversation_id).strip(),
            "sender": str(sender).strip(),
            "content": str(content).strip(),
            "type": msg_type or "text",
            "created_at": current_time
        }
        
        # Ajout des champs optionnels
        if image_data:
            message_data["image_data"] = image_data
            debug_log("📷 Image data ajoutée", {
                "length": len(image_data) if image_data else 0
            })
            
        if edit_context:
            message_data["edit_context"] = edit_context
            debug_log("✏️ Edit context ajouté")
        
        debug_log("💾 Données du message préparées", {
            "id": message_id[:12] + "...",
            "conversation_id": message_data["conversation_id"][:12] + "...",
            "sender": message_data["sender"],
            "content_preview": message_data["content"][:50] + "..." if len(message_data["content"]) > 50 else message_data["content"],
            "type": message_data["type"],
            "created_at": message_data["created_at"],
            "has_image": "image_data" in message_data,
            "has_context": "edit_context" in message_data
        })
        
        # Insertion dans la base de données
        debug_log("🚀 Tentative d'insertion dans la table messages...")
        
        response = supabase.table("messages").insert(message_data).execute()
        
        debug_log("📊 Réponse de l'insertion", {
            "success": bool(response.data),
            "data_returned": response.data if response.data else "Aucune donnée retournée",
            "count": len(response.data) if response.data else 0
        })
        
        if response.data:
            debug_log("✅ MESSAGE AJOUTÉ AVEC SUCCÈS!")
            debug_log("="*50)
            return True
        else:
            debug_log("❌ ÉCHEC: Aucune donnée retournée par l'insertion")
            debug_log("="*50)
            st.error("❌ Échec de l'ajout du message (aucune donnée retournée)")
            return False
            
    except Exception as e:
        debug_log("❌ EXCEPTION dans add_message", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        st.error(f"❌ Erreur lors de l'ajout du message: {str(e)}")
        debug_log("="*50)
        return False

# -------------------------
# Utility functions
# -------------------------

def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

# -------------------------
# BLIP loader
# -------------------------

@st.cache_resource
def load_blip():
    debug_log("🤖 Chargement de BLIP...")
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    debug_log("✅ BLIP chargé")
    return processor, model

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model = model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

# -------------------------
# LLaVA-OneVision loader
# -------------------------

@st.cache_resource
def load_llava_onevision():
    """Charge le client LLaVA-OneVision pour description avancée d'images"""
    try:
        debug_log("🤖 Chargement de LLaVA-OneVision...")
        client = Client("lmms-lab/LLaVA-OneVision-1.5")
        debug_log("✅ LLaVA-OneVision chargé")
        return client
    except Exception as e:
        debug_log("⚠️ LLaVA-OneVision non disponible", str(e))
        st.warning(f"LLaVA-OneVision non disponible: {e}")
        return None

def generate_llava_description(image, llava_client, custom_prompt="Describe this image in detail"):
    """Génère une description détaillée avec LLaVA-OneVision"""
    if not llava_client:
        return None
    try:
        temp_path = os.path.join(TMP_DIR, f"temp_input_{uuid.uuid4().hex}.png")
        image.save(temp_path)
        result = llava_client.predict(
            message={
                "text": custom_prompt,
                "files": [handle_file(temp_path)]
            },
            model_name="LLaVA-OneVision-1.5-8B-Instruct",
            api_name="/chat"
        )
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if isinstance(result, dict):
            return result.get('text', str(result))
        return str(result)
    except Exception as e:
        debug_log("❌ Erreur LLaVA description", str(e))
        return None

# -------------------------
# Fonction de description FUSION
# -------------------------

def generate_comprehensive_description(image, blip_processor, blip_model, llama_client, llava_client):
    """Génère une description RAPIDE en utilisant les modèles de manière optimisée"""
    descriptions = {}
    try:
        blip_desc = generate_caption(image, blip_processor, blip_model)
        descriptions['blip'] = blip_desc
    except Exception as e:
        descriptions['blip'] = "Image analysis unavailable"
        debug_log("❌ Erreur BLIP", str(e))
    
    if llava_client:
        try:
            llava_desc = generate_llava_description(
                image, 
                llava_client,
                "Describe this image concisely (max 100 words). Focus on: main subjects, colors, composition."
            )
            if llava_desc and len(llava_desc) > 20:
                descriptions['final'] = llava_desc
                return descriptions
        except:
            pass
    
    descriptions['final'] = descriptions['blip']
    return descriptions

def format_image_analysis_for_prompt(descriptions):
    """Formate l'analyse pour le prompt Vision AI de manière optimisée"""
    final_desc = descriptions.get('final', descriptions.get('blip', 'Image non analysée'))
    analysis_text = f"""[IMAGE] 📸 ANALYSE D'IMAGE

{final_desc}

==========================================
Utilisez cette description pour répondre aux questions sur l'image.
==========================================
"""
    return analysis_text

# -------------------------
# Fonctions Date/Heure AMÉLIORÉES
# -------------------------

def get_current_datetime_info():
    """Récupère les informations de date et heure actuelles"""
    try:
        tz = pytz.timezone('Europe/Brussels')
        now = datetime.now(tz)
        datetime_info = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "month": now.strftime("%B"),
            "year": now.year,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "timezone": str(tz),
            "timestamp": int(now.timestamp())
        }
        return datetime_info
    except Exception as e:
        debug_log("❌ Erreur get_current_datetime_info", str(e))
        return {"error": str(e)}

def format_datetime_for_prompt():
    """Formate les informations de date/heure pour le prompt"""
    dt_info = get_current_datetime_info()
    if "error" in dt_info:
        return f"[DATETIME] Erreur: {dt_info['error']}"
    return f"""[DATETIME] ⚠️ INFORMATIONS TEMPORELLES ACTUELLES (TEMPS RÉEL):
==========================================
Date et heure ACTUELLES: {dt_info['datetime']}
Date AUJOURD'HUI: {dt_info['date']}
Heure ACTUELLE: {dt_info['time']}
Jour: {dt_info['day_of_week']}
Mois: {dt_info['month']}
Année: {dt_info['year']}
Timezone: {dt_info['timezone']}
=========================================="""

# -------------------------
# AI functions avec Vision AI thinking
# -------------------------

def get_ai_response(query):
    if not st.session_state.get('llama_client'):
        debug_log("❌ LLaMA client non disponible")
        return "Vision AI non disponible."
    try:
        debug_log("🤖 Génération de la réponse AI...")
        resp = st.session_state.llama_client.predict(
            message=query,
            api_name="/chat"
        )
        debug_log("✅ Réponse AI générée")
        return str(resp)
    except Exception as e:
        debug_log("❌ Erreur get_ai_response", str(e))
        return f"Erreur modèle: {e}"

def show_vision_ai_thinking(placeholder):
    """Affiche l'animation Vision AI thinking..."""
    thinking_frames = [
        "Vision AI thinking",
        "Vision AI thinking.",
        "Vision AI thinking..",
        "Vision AI thinking..."
    ]
    for _ in range(2):
        for frame in thinking_frames:
            placeholder.markdown(f"**{frame}**")
            time.sleep(0.3)

def stream_response_with_thinking(text, placeholder):
    """Affiche Vision AI thinking puis stream la réponse"""
    show_vision_ai_thinking(placeholder)
    time.sleep(0.5)
    full_text = ""
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "▋")
        time.sleep(0.02)
    placeholder.markdown(full_text)

# -------------------------
# Edition d'image avec Qwen
# -------------------------

def edit_image_with_qwen(image: Image.Image, edit_instruction: str = ""):
    client = st.session_state.get("qwen_client")
    if not client:
        debug_log("❌ Client Qwen non disponible")
        return None, "Client Qwen non disponible."
    
    try:
        debug_log("✏️ Édition d'image avec Qwen", {
            "instruction": edit_instruction
        })
        
        temp_path = os.path.join(TMP_DIR, f"input_{uuid.uuid4().hex}.png")
        image.save(temp_path)
        
        prompt_message = edit_instruction if edit_instruction.strip() else "enhance and improve the image"
        
        result = client.predict(
            input_image=handle_file(temp_path),
            prompt=prompt_message,
            api_name="/edit_image_interface"
        )
        
        if result and isinstance(result, (list, tuple)) and len(result) >= 2:
            result_path = result[0]
            status_message = result[1]
            
            if isinstance(result_path, str) and os.path.exists(result_path):
                edited_img = Image.open(result_path).convert("RGBA")
                final_path = os.path.join(EDITED_IMAGES_DIR, f"edited_{uuid.uuid4().hex}.png")
                edited_img.save(final_path)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                edit_msg = f"Image éditée avec succès - {status_message}"
                if edit_instruction:
                    edit_msg += f" (instruction: {edit_instruction})"
                
                debug_log("✅ Image éditée avec succès")
                return edited_img, edit_msg
        
        debug_log("❌ Erreur traitement image Qwen")
        return None, "Erreur traitement image"
        
    except Exception as e:
        debug_log("❌ Erreur edit_image_with_qwen", str(e))
        return None, str(e)

def create_edit_context(original_caption, edit_instruction, edited_caption, success_info):
    return {
        "original_description": original_caption,
        "edit_instruction": edit_instruction,
        "edited_description": edited_caption,
        "edit_info": success_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def process_image_edit_request(image: Image.Image, edit_instruction: str, conv_id: str):
    debug_log("🖼️ Début du traitement d'édition d'image")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.info("Analyse de l'image originale...")
        progress_bar.progress(20)
        time.sleep(0.5)
        
        original_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        debug_log("📝 Caption originale générée", {"caption": original_caption})
        
        status_text.info(f"Édition en cours: '{edit_instruction}'...")
        progress_bar.progress(40)
        
        edited_img, result_info = edit_image_with_qwen(image, edit_instruction)
        
        if edited_img:
            status_text.info("Analyse de l'image éditée...")
            progress_bar.progress(70)
            time.sleep(0.5)
            
            edited_caption = generate_caption(edited_img, st.session_state.processor, st.session_state.model)
            debug_log("📝 Caption éditée générée", {"caption": edited_caption})
            
            status_text.info("Sauvegarde et finalisation...")
            progress_bar.progress(90)
            
            edit_context = create_edit_context(original_caption, edit_instruction, edited_caption, result_info)
            
            # Affichage côte à côte
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Image originale")
                st.image(image, caption="Avant", use_column_width=True)
                st.write(f"**Description:** {original_caption}")
            
            with col2:
                st.subheader("Image éditée")
                st.image(edited_img, caption=f"Après: {edit_instruction}", use_column_width=True)
                st.write(f"**Description:** {edited_caption}")
                st.write(f"**Info technique:** {result_info}")
            
            st.success("Édition terminée avec succès !")
            
            response_content = f"""**Édition d'image terminée !**

**Instruction:** {edit_instruction}

**Analyse comparative:**
- **Image originale:** {original_caption}
- **Image éditée:** {edited_caption}

**Modifications:** J'ai appliqué "{edit_instruction}". L'image montre maintenant: {edited_caption}

**Info technique:** {result_info}"""
            
            edited_b64 = image_to_base64(edited_img.convert("RGB"))
            
            debug_log("💾 Ajout du message d'édition à la base...")
            success = add_message(conv_id, "assistant", response_content, "image", edited_b64, str(edit_context))
            
            if success:
                debug_log("✅ Message d'édition ajouté avec succès")
                progress_bar.progress(100)
                status_text.success("Traitement terminé!")
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()
                
                st.session_state.messages_memory.append({
                    "message_id": str(uuid.uuid4()),
                    "sender": "assistant",
                    "content": response_content,
                    "type": "image",
                    "image_data": edited_b64,
                    "edit_context": str(edit_context),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Bouton téléchargement
                img_buffer = io.BytesIO()
                edited_img.convert("RGB").save(img_buffer, format="PNG")
                st.download_button(
                    label="Télécharger PNG",
                    data=img_buffer.getvalue(),
                    file_name=f"edited_image_{int(time.time())}.png",
                    mime="image/png"
                )
                
                return True
            else:
                debug_log("❌ Échec de l'ajout du message d'édition")
                status_text.error("Erreur sauvegarde")
                progress_bar.empty()
                return False
        else:
            debug_log("❌ Échec de l'édition d'image")
            status_text.error(f"Échec édition: {result_info}")
            progress_bar.empty()
            return False
    
    except Exception as e:
        debug_log("❌ Exception dans process_image_edit_request", str(e))
        status_text.error(f"Erreur: {e}")
        progress_bar.empty()
        return False

def get_editing_context_from_conversation():
    context_info = []
    for msg in st.session_state.messages_memory:
        if msg.get("edit_context"):
            try:
                if isinstance(msg["edit_context"], str):
                    import ast
                    edit_ctx = ast.literal_eval(msg["edit_context"])
                else:
                    edit_ctx = msg["edit_context"]
                
                context_info.append(f"""
Édition précédente:
- Image originale: {edit_ctx.get('original_description', 'N/A')}
- Résultat: {edit_ctx.get('edited_description', 'N/A')}
- Date: {edit_ctx.get('timestamp', 'N/A')}
""")
            except:
                continue
    
    return "\n".join(context_info) if context_info else ""

# -------------------------
# Interface de récupération de mot de passe
# -------------------------

def show_password_reset():
    st.subheader("Récupération de mot de passe")
    
    if st.session_state.reset_step == "request":
        with st.form("password_reset_request"):
            reset_email = st.text_input("Adresse email")
            submit_reset = st.form_submit_button("Envoyer le code")
            
            if submit_reset and reset_email.strip() and supabase:
                debug_log(f"🔐 Demande de réinitialisation pour {reset_email}")
                try:
                    user_check = supabase.table("users").select("*").eq("email", reset_email.strip()).execute()
                    if user_check.data:
                        reset_token = generate_reset_token()
                        if store_reset_token(reset_email.strip(), reset_token):
                            st.session_state.reset_email = reset_email.strip()
                            st.session_state.reset_token = reset_token
                            st.session_state.reset_step = "verify"
                            st.success("Code généré!")
                            st.warning(f"**Code:** {reset_token}")
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.error("Email introuvable")
                        debug_log("❌ Email introuvable")
                except Exception as e:
                    st.error(f"Erreur: {e}")
                    debug_log("❌ Erreur reset request", str(e))
        
        if st.button("← Retour connexion"):
            st.session_state.reset_step = "request"
            st.rerun()
    
    elif st.session_state.reset_step == "verify":
        with st.form("password_reset_verify"):
            col1, col2 = st.columns([2, 1])
            with col1:
                token_input = st.text_input("Code de récupération")
                new_password = st.text_input("Nouveau mot de passe", type="password")
                confirm_password = st.text_input("Confirmer", type="password")
            
            with col2:
                st.write("**Code généré:**")
                st.code(st.session_state.reset_token)
            
            submit = st.form_submit_button("Réinitialiser")
            
            if submit:
                if not token_input.strip():
                    st.error("Entrez le code")
                elif not new_password:
                    st.error("Entrez un mot de passe")
                elif len(new_password) < 6:
                    st.error("Minimum 6 caractères")
                elif new_password != confirm_password:
                    st.error("Mots de passe différents")
                elif token_input.strip() != st.session_state.reset_token:
                    st.error("Code incorrect")
                else:
                    if reset_password(st.session_state.reset_email, token_input.strip(), new_password):
                        st.success("Mot de passe réinitialisé!")
                        st.session_state.reset_step = "request"
                        st.session_state.reset_email = ""
                        st.session_state.reset_token = ""
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Erreur réinitialisation")

# -------------------------
# Interface Admin
# -------------------------

def show_admin_page():
    st.title("Interface Administrateur")
    
    if st.button("← Retour"):
        st.session_state.page = "main"
        st.rerun()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Utilisateurs", "Conversations", "Messages", "Statistiques"])
    
    with tab1:
        st.subheader("Gestion des Utilisateurs")
        if supabase:
            try:
                users = supabase.table("users").select("*").order("created_at", desc=True).execute()
                if users.data:
                    for user in users.data:
                        with st.expander(f"{user.get('name', 'N/A')} ({user.get('email', 'N/A')})"):
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.write(f"**ID:** {user.get('id', 'N/A')[:12]}...")
                                st.write(f"**Email:** {user.get('email', 'N/A')}")
                                st.write(f"**Nom:** {user.get('name', 'N/A')}")
                                st.write(f"**Rôle actuel:** {user.get('role', 'user')}")
                                st.write(f"**Créé le:** {user.get('created_at', 'N/A')[:16]}")
                            
                            with col2:
                                new_role = st.selectbox(
                                    "Changer rôle:",
                                    ["user", "admin"],
                                    index=0 if user.get('role', 'user') == 'user' else 1,
                                    key=f"role_{user.get('id')}"
                                )
                                if st.button(f"Mettre à jour", key=f"update_{user.get('id')}"):
                                    try:
                                        response = supabase.table("users").update({
                                            "role": new_role,
                                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                                        }).eq("id", user.get('id')).execute()
                                        if response.data:
                                            st.success(f"Rôle changé en {new_role}!")
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error("Échec mise à jour")
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")
                else:
                    st.info("Aucun utilisateur trouvé")
            except Exception as e:
                st.error(f"Erreur chargement utilisateurs: {e}")
    
    with tab2:
        st.subheader("Toutes les Conversations")
        if supabase:
            try:
                convs = supabase.table("conversations").select("*").order("created_at", desc=True).limit(50).execute()
                if convs.data:
                    for conv in convs.data:
                        conv_id = conv.get('conversation_id') or conv.get('id')
                        with st.expander(f"📝 {conv.get('description', 'Sans titre')} - {conv.get('created_at', 'N/A')[:16]}"):
                            st.write(f"**ID Conversation:** {conv_id[:12]}...")
                            st.write(f"**User ID:** {conv.get('user_id', 'N/A')[:12]}...")
                            st.write(f"**Description:** {conv.get('description', 'N/A')}")
                            st.write(f"**Créée le:** {conv.get('created_at', 'N/A')}")
                            
                            try:
                                msg_count = supabase.table("messages").select("id", count="exact").eq("conversation_id", conv_id).execute()
                                st.write(f"**Nombre de messages:** {msg_count.count or 0}")
                            except:
                                st.write("**Nombre de messages:** N/A")
                else:
                    st.info("Aucune conversation trouvée")
            except Exception as e:
                st.error(f"Erreur chargement conversations: {e}")
    
    with tab3:
        st.subheader("Messages par Conversation")
        if supabase:
            try:
                convs = supabase.table("conversations").select("*").order("created_at", desc=True).limit(20).execute()
                if convs.data:
                    conv_options = {f"{c.get('description', 'Sans titre')} - {c.get('created_at', 'N/A')[:16]}": c.get('conversation_id') or c.get('id') for c in convs.data}
                    selected_conv_name = st.selectbox("Sélectionner une conversation:", list(conv_options.keys()))
                    selected_conv_id = conv_options[selected_conv_name]
                    
                    if selected_conv_id:
                        messages = supabase.table("messages").select("*").eq("conversation_id", selected_conv_id).order("created_at", desc=False).execute()
                        if messages.data:
                            st.write(f"**{len(messages.data)} messages trouvés**")
                            for msg in messages.data:
                                sender = msg.get('sender', 'unknown')
                                msg_type = "👤 Utilisateur" if sender == "user" else "🤖 Assistant"
                                
                                with st.expander(f"{msg_type} - {msg.get('created_at', 'N/A')[:16]}"):
                                    st.write(f"**Type:** {msg.get('type', 'text')}")
                                    st.write(f"**Contenu:**")
                                    st.text(msg.get('content', 'N/A')[:500])
                                    
                                    if msg.get('image_data'):
                                        st.write("📷 Contient une image")
                        else:
                            st.info("Aucun message dans cette conversation")
                else:
                    st.info("Aucune conversation disponible")
            except Exception as e:
                st.error(f"Erreur chargement messages: {e}")
    
    with tab4:
        st.subheader("Statistiques Globales")
        if supabase:
            try:
                users_count = supabase.table("users").select("*", count="exact").execute()
                convs_count = supabase.table("conversations").select("*", count="exact").execute()
                messages_count = supabase.table("messages").select("*", count="exact").execute()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Utilisateurs", users_count.count or 0)
                with col2:
                    st.metric("💬 Conversations", convs_count.count or 0)
                with col3:
                    st.metric("📨 Messages", messages_count.count or 0)
                
                st.markdown("---")
                st.subheader("Détails")
                
                try:
                    admins = supabase.table("users").select("*", count="exact").eq("role", "admin").execute()
                    users_regular = supabase.table("users").select("*", count="exact").eq("role", "user").execute()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Admins", admins.count or 0)
                    with col2:
                        st.metric("Users", users_regular.count or 0)
                except Exception as e:
                    st.warning(f"Erreur stats rôles: {e}")
                
                try:
                    text_msgs = supabase.table("messages").select("*", count="exact").eq("type", "text").execute()
                    image_msgs = supabase.table("messages").select("*", count="exact").eq("type", "image").execute()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Messages texte", text_msgs.count or 0)
                    with col2:
                        st.metric("Messages image", image_msgs.count or 0)
                except Exception as e:
                    st.warning(f"Erreur stats messages: {e}")
                    
            except Exception as e:
                st.error(f"Erreur statistiques: {e}")

def cleanup_temp_files():
    try:
        current_time = time.time()
        for filename in os.listdir(TMP_DIR):
            filepath = os.path.join(TMP_DIR, filename)
            if os.path.isfile(filepath) and current_time - os.path.getctime(filepath) > 3600:
                os.remove(filepath)
    except:
        pass

# -------------------------
# Session State
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}

if "conversation" not in st.session_state:
    st.session_state.conversation = None

if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

if "processor" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

if "llava_client" not in st.session_state:
    try:
        st.session_state.llava_client = load_llava_onevision()
        if st.session_state.llava_client:
            st.success("✅ LLaVA-OneVision chargé avec succès!")
    except:
        st.session_state.llava_client = None

if "llama_client" not in st.session_state:
    try:
        debug_log("🤖 Chargement de LLaMA...")
        st.session_state.llama_client = Client("akhaliq/Apertus-8B-Instruct-2509")
        debug_log("✅ LLaMA chargé")
    except Exception as e:
        debug_log("❌ Erreur chargement LLaMA", str(e))
        st.session_state.llama_client = None

if "qwen_client" not in st.session_state:
    try:
        debug_log("🤖 Chargement de Qwen...")
        st.session_state.qwen_client = Client("Selfit/ImageEditPro")
        debug_log("✅ Qwen chargé")
    except Exception as e:
        debug_log("❌ Erreur chargement Qwen", str(e))
        st.session_state.qwen_client = None

if "reset_step" not in st.session_state:
    st.session_state.reset_step = "request"

if "reset_email" not in st.session_state:
    st.session_state.reset_email = ""

if "reset_token" not in st.session_state:
    st.session_state.reset_token = ""

if "page" not in st.session_state:
    st.session_state.page = "main"

# -------------------------
# Navigation
# -------------------------
if st.session_state.page == "admin":
    show_admin_page()
    st.stop()

# -------------------------
# Sidebar AVEC DEBUG
# -------------------------
with st.sidebar:
    st.markdown("### 🐛 DEBUG MODE")
    debug_enabled = st.checkbox("Activer les logs", value=DEBUG_MODE)
    if debug_enabled != DEBUG_MODE:
        DEBUG_MODE = debug_enabled
        st.rerun()
    
    if st.button("🗑️ Effacer logs"):
        st.rerun()
    
    st.markdown("---")

st.sidebar.title("Authentification")

if st.session_state.user["id"] == "guest":
    tab1, tab2, tab3 = st.sidebar.tabs(["Connexion", "Inscription", "Reset"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        
        if st.button("Se connecter", type="primary"):
            if email and password:
                with st.spinner("Connexion..."):
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.success("Connecté!")
                        debug_log(f"✅ Utilisateur connecté: {user['email']}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Identifiants invalides")
                        debug_log("❌ Connexion échouée")
    
    with tab2:
        email_reg = st.text_input("Email", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe", type="password", key="reg_pass")
        pass_confirm = st.text_input("Confirmer", type="password", key="reg_confirm")
        
        if st.button("Créer compte"):
            if email_reg and name_reg and pass_reg and pass_confirm:
                if pass_reg != pass_confirm:
                    st.error("Mots de passe différents")
                elif len(pass_reg) < 6:
                    st.error("Minimum 6 caractères")
                else:
                    with st.spinner("Création..."):
                        if create_user(email_reg, pass_reg, name_reg):
                            st.success("Compte créé!")
                            debug_log(f"✅ Nouveau compte créé: {email_reg}")
                            time.sleep(1)
    
    with tab3:
        show_password_reset()
    
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    st.sidebar.info(f"ID: {st.session_state.user.get('id')[:12]}...")
    
    if st.session_state.user.get('role') == 'admin':
        st.sidebar.markdown("**🔧 Admin**")
        if st.sidebar.button("Interface Admin"):
            st.session_state.page = "admin"
            st.rerun()
    
    if st.sidebar.button("Déconnexion"):
        debug_log(f"👋 Déconnexion: {st.session_state.user.get('email')}")
        st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Gestion Conversations AVEC DEBUG
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("Conversations")
    
    if st.sidebar.button("➕ Nouvelle conversation"):
        debug_log("➕ Création d'une nouvelle conversation...")
        with st.spinner("Création..."):
            conv = create_conversation(st.session_state.user["id"], "Nouvelle discussion")
            if conv:
                st.session_state.conversation = conv
                st.session_state.messages_memory = []
                st.success("Créée!")
                debug_log("✅ Nouvelle conversation créée", conv)
                time.sleep(1)
                st.rerun()
            else:
                debug_log("❌ Échec de création de conversation")
    
    convs = get_conversations(st.session_state.user["id"])
    if convs:
        st.sidebar.write(f"📊 {len(convs)} conversation(s)")
        options = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
        current_idx = 0
        
        if st.session_state.conversation:
            current_id = st.session_state.conversation.get("conversation_id")
            for i, c in enumerate(convs):
                if c.get("conversation_id") == current_id:
                    current_idx = i
                    break
        
        selected_idx = st.sidebar.selectbox(
            "Vos conversations:",
            range(len(options)),
            format_func=lambda i: options[i],
            index=current_idx
        )
        
        selected_conv = convs[selected_idx]
        
        if (not st.session_state.conversation or
            st.session_state.conversation.get("conversation_id") != selected_conv.get("conversation_id")):
            debug_log(f"🔄 Changement de conversation vers: {selected_conv.get('conversation_id')[:12]}...")
            with st.spinner("Chargement..."):
                st.session_state.conversation = selected_conv
                messages = get_messages(selected_conv.get("conversation_id"))
                st.session_state.messages_memory = messages
                debug_log(f"✅ {len(messages)} messages chargés")
                time.sleep(0.5)
                st.rerun()
    else:
        st.sidebar.info("Aucune conversation")
        debug_log("ℹ️ Aucune conversation disponible")

# -------------------------
# Interface principale
# -------------------------
st.title("🤖 Vision AI Chat - Analyse & Édition d'Images (DEBUG MODE)")

if DEBUG_MODE:
    st.warning("⚠️ Mode DEBUG activé - Les logs apparaissent dans la sidebar")

# Affichage des informations de conversation en debug
if st.session_state.conversation:
    st.subheader(f"💬 Conversation: {st.session_state.conversation.get('description')}")
    if DEBUG_MODE:
        with st.expander("🔍 Détails de la conversation"):
            st.json({
                "conversation_id": st.session_state.conversation.get("conversation_id"),
                "user_id": st.session_state.conversation.get("user_id"),
                "description": st.session_state.conversation.get("description"),
                "created_at": st.session_state.conversation.get("created_at"),
                "messages_in_memory": len(st.session_state.messages_memory)
            })
else:
    st.info("ℹ️ Créez ou sélectionnez une conversation pour commencer")
    if DEBUG_MODE:
        debug_log("⚠️ Aucune conversation active")

tab1, tab2 = st.tabs(["💬 Chat Normal", "✏️ Mode Éditeur"])

with tab1:
    st.write("Mode chat avec analyse d'images et recherche web")
    
    # Affichage des messages
    if st.session_state.messages_memory:
        debug_log(f"📝 Affichage de {len(st.session_state.messages_memory)} messages")
        for idx, msg in enumerate(st.session_state.messages_memory):
            role = "user" if msg.get("sender") == "user" else "assistant"
            with st.chat_message(role):
                if msg.get("type") == "image" and msg.get("image_data"):
                    try:
                        st.image(base64_to_image(msg["image_data"]), width=300)
                    except Exception as e:
                        debug_log(f"❌ Erreur affichage image message {idx}", str(e))
                        st.error("Erreur d'affichage de l'image")
                st.markdown(msg.get("content", ""))
                
                if DEBUG_MODE:
                    with st.expander("🔍 Détails du message"):
                        st.json({
                            "message_id": msg.get("message_id", "N/A")[:12] + "...",
                            "sender": msg.get("sender"),
                            "type": msg.get("type"),
                            "created_at": msg.get("created_at"),
                            "has_image": bool(msg.get("image_data")),
                            "has_context": bool(msg.get("edit_context"))
                        })
    
    # Formulaire de chat
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            user_input = st.text_area(
                "Votre message:",
                height=100,
                placeholder="Posez vos questions..."
            )
        with col2:
            uploaded_file = st.file_uploader(
                "Image",
                type=["png", "jpg", "jpeg"],
                key="chat_upload"
            )
        
        submit_chat = st.form_submit_button("📤 Envoyer")

with tab2:
    st.write("Mode éditeur avec Qwen-Image-Edit")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Image à éditer")
        editor_file = st.file_uploader(
            "Image",
            type=["png", "jpg", "jpeg"],
            key="editor_upload"
        )
        
        if editor_file:
            editor_image = Image.open(editor_file).convert("RGBA")
            st.image(editor_image, caption="Original", use_column_width=True)
            
            with st.spinner("Analyse..."):
                descriptions = generate_comprehensive_description(
                    editor_image,
                    st.session_state.processor,
                    st.session_state.model,
                    st.session_state.llama_client,
                    st.session_state.llava_client
                )
                
                final_desc = descriptions.get('final', descriptions.get('blip', 'N/A'))
                
                if len(final_desc) > 250:
                    st.write("**Description:**", final_desc[:250] + "...")
                    with st.expander("📖 Voir description complète"):
                        st.write(final_desc)
                else:
                    st.write("**Description:**", final_desc)
    
    with col2:
        st.subheader("Instructions d'édition")
        
        example_prompts = [
            "Add a beautiful sunset background",
            "Change to black and white",
            "Add flowers",
            "Make it look like a painting",
            "Add snow falling",
            "Cyberpunk style",
            "Remove background",
            "Add a person",
            "More colorful",
            "Add magic effects"
        ]
        
        selected_example = st.selectbox("Exemples", ["Custom..."] + example_prompts)
        
        if selected_example == "Custom...":
            edit_instruction = st.text_area(
                "Instruction (en anglais):",
                height=120,
                placeholder="ex: Add a man, change sky..."
            )
        else:
            edit_instruction = st.text_area(
                "Instruction:",
                value=selected_example,
                height=120
            )
        
        if st.button("✏️ Éditer", type="primary", disabled=not (editor_file and edit_instruction.strip())):
            debug_log("✏️ Début de l'édition d'image")
            
            if not st.session_state.conversation:
                debug_log("⚠️ Pas de conversation active, création...")
                conv = create_conversation(st.session_state.user["id"], "Édition d'images")
                if conv:
                    st.session_state.conversation = conv
                    debug_log("✅ Conversation créée pour l'édition")
            
            if st.session_state.conversation:
                # Ajout du message utilisateur
                original_caption = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                user_msg = f"**Édition demandée**\n\n**Image:** {original_caption}\n\n**Instruction:** {edit_instruction}"
                original_b64 = image_to_base64(editor_image.convert("RGB"))
                
                debug_log("💾 Ajout du message utilisateur (édition)...")
                add_success = add_message(
                    st.session_state.conversation.get("conversation_id"),
                    "user",
                    user_msg,
                    "image",
                    original_b64
                )
                
                if add_success:
                    debug_log("✅ Message utilisateur ajouté")
                    st.session_state.messages_memory.append({
                        "message_id": str(uuid.uuid4()),
                        "sender": "user",
                        "content": user_msg,
                        "type": "image",
                        "image_data": original_b64,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                # Traitement de l'édition
                success = process_image_edit_request(
                    editor_image,
                    edit_instruction,
                    st.session_state.conversation.get("conversation_id")
                )
                
                if success:
                    debug_log("✅ Édition complète réussie")
                    st.rerun()
                else:
                    debug_log("❌ Échec de l'édition")

# -------------------------
# Traitement du chat AVEC DEBUG COMPLET
# -------------------------
if 'submit_chat' in locals() and submit_chat and (user_input.strip() or uploaded_file):
    debug_log("="*50)
    debug_log("📨 NOUVEAU MESSAGE UTILISATEUR")
    debug_log("="*50)
    
    # Vérification/création de la conversation
    if not st.session_state.conversation:
        debug_log("⚠️ Pas de conversation active, création...")
        with st.spinner("Création conversation..."):
            conv = create_conversation(st.session_state.user["id"], "Discussion")
            if conv:
                st.session_state.conversation = conv
                debug_log("✅ Conversation créée", conv)
            else:
                st.error("Impossible de créer conversation")
                debug_log("❌ ÉCHEC CRITIQUE: Impossible de créer la conversation")
                st.stop()
    
    conv_id = st.session_state.conversation.get("conversation_id")
    debug_log(f"📂 Conversation active: {conv_id[:12]}...")
    
    message_content = user_input.strip()
    image_data = None
    msg_type = "text"
    
    # Traitement de l'image si uploadée
    if uploaded_file:
        debug_log("🖼️ Traitement de l'image uploadée...")
        with st.spinner("Analyse rapide de l'image..."):
            image = Image.open(uploaded_file)
            image_data = image_to_base64(image)
            debug_log(f"✅ Image encodée en base64 (taille: {len(image_data)} chars)")
            
            descriptions = generate_comprehensive_description(
                image,
                st.session_state.processor,
                st.session_state.model,
                st.session_state.llama_client,
                st.session_state.llava_client
            )
            
            preview = descriptions.get('final', descriptions.get('blip', 'N/A'))
            if len(preview) > 120:
                preview = preview[:120] + "..."
            st.success(f"✅ {preview}")
            debug_log("✅ Description générée", {"preview": preview})
            
            message_content = format_image_analysis_for_prompt(descriptions)
            if user_input.strip():
                message_content += f"\n\nQuestion utilisateur: {user_input.strip()}"
            msg_type = "image"
            debug_log(f"📝 Type de message: {msg_type}")
    
    if message_content:
        debug_log("💾 Sauvegarde du message utilisateur...")
        
        # Sauvegarde du message utilisateur
        user_add_success = add_message(conv_id, "user", message_content, msg_type, image_data)
        
        if user_add_success:
            debug_log("✅ Message utilisateur sauvegardé dans la DB")
        else:
            debug_log("❌ ÉCHEC sauvegarde message utilisateur")
            st.error("⚠️ Le message n'a pas pu être sauvegardé dans la base")
        
        user_msg = {
            "message_id": str(uuid.uuid4()),
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages_memory.append(user_msg)
        debug_log("✅ Message ajouté à la mémoire de session")
        
        # Vérification si édition d'image demandée
        lower = user_input.lower()
        if (any(k in lower for k in ["edit", "édite", "modifie"]) and uploaded_file):
            debug_log("✏️ Édition d'image détectée")
            edit_instruction = user_input.strip()
            success = process_image_edit_request(
                Image.open(uploaded_file).convert("RGBA"),
                edit_instruction,
                conv_id
            )
            if success:
                debug_log("✅ Édition réussie, rechargement...")
                st.rerun()
        else:
            debug_log("🤖 Génération de la réponse IA...")
            # Génération de la réponse IA
            edit_context = get_editing_context_from_conversation()
            
            # Construction du prompt
            prompt = f"{SYSTEM_PROMPT}\n\n"
            
            # Ajout des informations de date/heure
            datetime_info = format_datetime_for_prompt()
            prompt += f"{datetime_info}\n\n"
            
            if edit_context:
                prompt += f"[EDIT_CONTEXT] {edit_context}\n\n"
            
            prompt += f"""
==========================================
INSTRUCTIONS FINALES:
1. Utilisez [DATETIME] pour les questions de date/heure
2. Soyez précis et citez vos sources
==========================================

Utilisateur: {message_content}"""
            
            debug_log("📤 Envoi du prompt à l'IA...")
            
            # Génération de la réponse avec animation
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                if edit_context and any(w in user_input.lower() for w in ["edit", "image", "avant", "après"]):
                    with st.spinner("Consultation mémoire..."):
                        time.sleep(1)
                
                response = get_ai_response(prompt)
                debug_log("✅ Réponse IA reçue", {"length": len(response)})
                
                stream_response_with_thinking(response, placeholder)
                
                # Sauvegarde de la réponse
                debug_log("💾 Sauvegarde de la réponse IA...")
                ai_add_success = add_message(conv_id, "assistant", response, "text")
                
                if ai_add_success:
                    debug_log("✅ Réponse IA sauvegardée dans la DB")
                else:
                    debug_log("❌ ÉCHEC sauvegarde réponse IA")
                    st.warning("⚠️ La réponse n'a pas pu être sauvegardée dans la base")
                
                ai_msg = {
                    "message_id": str(uuid.uuid4()),
                    "sender": "assistant",
                    "content": response,
                    "type": "text",
                    "image_data": None,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.messages_memory.append(ai_msg)
                debug_log("✅ Réponse ajoutée à la mémoire de session")
                
                debug_log("="*50)
                debug_log("✅ TRAITEMENT DU MESSAGE TERMINÉ")
                debug_log("="*50)
                
                st.rerun()

# -------------------------
# Footer informatif
# -------------------------
st.markdown("---")
st.markdown("### 📊 Informations de Debug")

col1, col2, col3 = st.columns(3)

with col1:
    st.write("**État de la session:**")
    st.write(f"- Utilisateur: {st.session_state.user.get('email')}")
    st.write(f"- Role: {st.session_state.user.get('role')}")
    st.write(f"- User ID: {st.session_state.user.get('id')[:12]}..." if st.session_state.user.get('id') != 'guest' else "- User ID: guest")

with col2:
    st.write("**Conversation active:**")
    if st.session_state.conversation:
        st.write(f"- Conv ID: {st.session_state.conversation.get('conversation_id')[:12]}...")
        st.write(f"- Description: {st.session_state.conversation.get('description')}")
        st.write(f"- Messages: {len(st.session_state.messages_memory)}")
    else:
        st.write("- Aucune conversation active")

with col3:
    st.write("**Services:**")
    st.write(f"- Supabase: {'✅' if supabase else '❌'}")
    st.write(f"- BLIP: {'✅' if st.session_state.processor else '❌'}")
    st.write(f"- LLaVA: {'✅' if st.session_state.llava_client else '❌'}")
    st.write(f"- LLaMA: {'✅' if st.session_state.llama_client else '❌'}")
    st.write(f"- Qwen: {'✅' if st.session_state.qwen_client else '❌'}")

st.markdown("---")

# Test de connexion Supabase
with st.expander("🧪 Tests de connexion"):
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🧪 Test Supabase"):
            if supabase:
                try:
                    debug_log("🧪 Test de connexion Supabase...")
                    test = supabase.table("users").select("*").limit(1).execute()
                    st.success(f"✅ Supabase OK - {len(test.data)} résultat(s)")
                    debug_log("✅ Test Supabase réussi")
                except Exception as e:
                    st.error(f"❌ Supabase KO: {e}")
                    debug_log("❌ Test Supabase échoué", str(e))
            else:
                st.error("❌ Supabase non initialisé")
    
    with col2:
        if st.button("🧪 Test Conversation"):
            if st.session_state.conversation:
                conv_id = st.session_state.conversation.get("conversation_id")
                debug_log(f"🧪 Test de la conversation {conv_id[:12]}...")
                try:
                    conv_check = supabase.table("conversations").select("*").eq("conversation_id", conv_id).execute()
                    if conv_check.data:
                        st.success(f"✅ Conversation existe dans la DB")
                        debug_log("✅ Conversation trouvée dans la DB")
                        st.json(conv_check.data[0])
                    else:
                        st.error("❌ Conversation introuvable dans la DB!")
                        debug_log("❌ Conversation introuvable")
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")
                    debug_log("❌ Erreur test conversation", str(e))
            else:
                st.warning("⚠️ Aucune conversation active")

# Cleanup
cleanup_temp_files()



