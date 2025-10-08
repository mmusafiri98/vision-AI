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
st.set_page_config(page_title="Vision AI Chat - Complete", layout="wide")

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
# Supabase Connection
# -------------------------

@st.cache_resource
def init_supabase():
    """Initialise Supabase avec gestion d'erreur complète"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            st.error("Variables Supabase manquantes")
            return None

        client = create_client(supabase_url, supabase_key)
        test = client.table("users").select("*").limit(1).execute()
        st.success("Supabase connecté avec succès")
        return client

    except Exception as e:
        st.error(f"Erreur connexion Supabase: {e}")
        return None

supabase = init_supabase()

# -------------------------
# Fonctions de récupération de mot de passe
# -------------------------

def generate_reset_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def store_reset_token(email, token):
    if not supabase:
        return False

    try:
        expiration = time.time() + 3600
        user_check = supabase.table("users").select("*").eq("email", email).execute()

        if not user_check.data:
            return False

        try:
            response = supabase.table("users").update({
                "reset_token": token,
                "reset_token_expires": expiration,
                "reset_token_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }).eq("email", email).execute()

            return bool(response.data)
        except:
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
                return bool(response.data)
            except:
                return False
    except:
        return False

def verify_reset_token(email, token):
    if not supabase:
        return False

    try:
        current_time = time.time()

        try:
            response = supabase.table("users").select("reset_token, reset_token_expires").eq("email", email).execute()
            if response.data:
                user_data = response.data[0]
                if user_data.get("reset_token") == token and user_data.get("reset_token_expires", 0) > current_time:
                    return True
        except:
            pass

        try:
            response = supabase.table("password_resets").select("*").eq("email", email).eq("reset_token", token).eq("used", False).execute()
            if response.data and response.data[0].get("expires_at", 0) > current_time:
                return True
        except:
            pass

        return False
    except:
        return False

def reset_password(email, token, new_password):
    if not supabase or not verify_reset_token(email, token):
        return False

    try:
        update_data = {
            "password": new_password,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reset_token": None,
            "reset_token_expires": None,
            "reset_token_created": None
        }

        update_response = supabase.table("users").update(update_data).eq("email", email).execute()

        if update_response.data:
            try:
                supabase.table("password_resets").update({
                    "used": True,
                    "used_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }).eq("email", email).eq("reset_token", token).execute()
            except:
                pass
            return True
        return False
    except:
        return False

# -------------------------
# Fonctions DB AVEC DEBUG
# -------------------------

def verify_user(email, password):
    if email == ADMIN_CREDENTIALS["email"] and password == ADMIN_CREDENTIALS["password"]:
        return {
            "id": "admin_special_id",
            "email": email,
            "name": "Jessica Admin",
            "role": "admin"
        }

    if not supabase:
        return None

    try:
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                user_data = supabase.table("users").select("*").eq("email", email).execute()
                role = user_data.data[0].get("role", "user") if user_data.data else "user"
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0]),
                    "role": role
                }
        except:
            pass

        response = supabase.table("users").select("*").eq("email", email).execute()
        if response.data:
            user = response.data[0]
            if user.get("password") == password:
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user.get("name", email.split("@")[0]),
                    "role": user.get("role", "user")
                }
        return None
    except:
        return None

def create_user(email, password, name, role="user"):
    if not supabase:
        return False

    try:
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name, "role": role}
            })
            return response.user is not None
        except:
            pass

        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": password,
            "name": name,
            "role": role,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        response = supabase.table("users").insert(user_data).execute()
        return bool(response.data)
    except:
        return False

def get_conversations(user_id):
    if not supabase or not user_id:
        return []

    try:
        response = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()

        if not response.data:
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
        return conversations
    except:
        return []

def create_conversation(user_id, description):
    if not supabase or not user_id:
        st.error("❌ DEBUG: Supabase non disponible ou user_id manquant")
        return None
    
    # Ne pas créer de conversation pour l'utilisateur invité
    if user_id == "guest":
        st.warning("Connectez-vous pour créer une conversation")
        return None

    try:
        st.info(f"🔍 DEBUG: Vérification utilisateur {user_id[:12]}...")
        
        # Vérifier que l'utilisateur existe dans la base de données
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if not user_check.data:
            st.warning(f"⚠️ DEBUG: Utilisateur {user_id[:12]} n'existe pas, création...")
            
            # Récupérer les infos de l'utilisateur depuis session_state
            user_info = st.session_state.user
            
            create_user_data = {
                "id": user_id,
                "email": user_info.get("email", f"user_{user_id}@temp.com"),
                "name": user_info.get("name", "Utilisateur"),
                "password": "temp_password",
                "role": user_info.get("role", "user"),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            try:
                user_create_response = supabase.table("users").insert(create_user_data).execute()
                if user_create_response.data:
                    st.success(f"✅ DEBUG: Utilisateur {user_id[:12]} créé avec succès!")
                else:
                    st.error("❌ DEBUG: Échec création utilisateur - pas de données retournées")
                    return None
            except Exception as e:
                st.error(f"❌ DEBUG: Impossible de créer l'utilisateur: {e}")
                return None
        else:
            st.success(f"✅ DEBUG: Utilisateur {user_id[:12]} existe")
        
        # Maintenant créer la conversation
        conv_id = str(uuid.uuid4())
        data = {
            "conversation_id": conv_id,
            "user_id": user_id,
            "description": description,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        st.info(f"🔍 DEBUG: Création conversation {conv_id[:12]}...")
        response = supabase.table("conversations").insert(data).execute()

        if response.data:
            conv = response.data[0]
            st.success(f"✅ DEBUG: Conversation {conv_id[:12]} créée avec succès!")
            return {
                "conversation_id": conv.get("conversation_id"),
                "description": conv["description"],
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
        else:
            st.error("❌ DEBUG: Échec création conversation - pas de données retournées")
            return None
    except Exception as e:
        st.error(f"❌ DEBUG: Erreur création conversation: {e}")
        st.error(f"❌ DEBUG: Type d'erreur: {type(e).__name__}")
        st.error(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
        return None

def get_messages(conversation_id):
    if not supabase or not conversation_id:
        return []

    try:
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()

        if not response.data:
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
        return messages
    except Exception as e:
        st.error(f"❌ DEBUG get_messages: {e}")
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None, edit_context=None):
    if not supabase:
        st.error("❌ DEBUG add_message: Supabase non disponible")
        return False
    
    if not conversation_id:
        st.error("❌ DEBUG add_message: conversation_id manquant")
        return False
    
    if not content:
        st.error("❌ DEBUG add_message: content vide")
        return False

    try:
        st.info(f"🔍 DEBUG add_message: Vérification conversation {conversation_id[:12]}...")
        
        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        
        if not conv_check.data:
            st.error(f"❌ DEBUG add_message: Conversation {conversation_id[:12]} n'existe pas!")
            return False
        
        st.success(f"✅ DEBUG add_message: Conversation {conversation_id[:12]} existe")

        # Préparer les données du message
        message_id = str(uuid.uuid4())
        message_data = {
            "id": message_id,
            "conversation_id": conversation_id,
            "sender": str(sender).strip(),
            "content": str(content).strip()[:10000],  # Limiter la taille du contenu
            "type": msg_type or "text",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if image_data:
            message_data["image_data"] = image_data
        if edit_context:
            message_data["edit_context"] = edit_context

        st.info(f"🔍 DEBUG add_message: Insertion message {message_id[:12]}...")
        st.info(f"   - sender: {message_data['sender']}")
        st.info(f"   - type: {message_data['type']}")
        st.info(f"   - content length: {len(message_data['content'])}")
        
        response = supabase.table("messages").insert(message_data).execute()
        
        if response.data:
            st.success(f"✅ DEBUG add_message: Message {message_id[:12]} sauvegardé avec succès!")
            return True
        else:
            st.error(f"❌ DEBUG add_message: Échec sauvegarde - pas de données retournées")
            st.error(f"   Response: {response}")
            return False
            
    except Exception as e:
        st.error(f"❌ DEBUG add_message: Erreur lors de la sauvegarde: {e}")
        st.error(f"   Type: {type(e).__name__}")
        st.error(f"   Details: {traceback.format_exc()}")
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
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
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
        client = Client("lmms-lab/LLaVA-OneVision-1.5")
        return client
    except Exception as e:
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
        return None

# -------------------------
# Fonction de description FUSION
# -------------------------

def generate_comprehensive_description(image, blip_processor, blip_model, llama_client, llava_client):
    """Génère une description RAPIDE"""
    descriptions = {}
    
    try:
        blip_desc = generate_caption(image, blip_processor, blip_model)
        descriptions['blip'] = blip_desc
    except Exception as e:
        descriptions['blip'] = "Image analysis unavailable"
    
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
    """Formate l'analyse pour le prompt Vision AI"""
    final_desc = descriptions.get('final', descriptions.get('blip', 'Image non analysée'))
    
    analysis_text = f"""[IMAGE] 📸 ANALYSE D'IMAGE

{final_desc}

==========================================
Utilisez cette description pour répondre aux questions sur l'image.
==========================================
"""
    
    return analysis_text

# -------------------------
# Fonctions Date/Heure
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

# [NOTE: Les fonctions de recherche web restent identiques - je les omets pour la brièveté]
# Inclure ici toutes les fonctions: extract_number, search_duckduckgo, search_google, 
# get_youtube_video_stats, get_youtube_comments, search_youtube_comprehensive,
# get_youtube_transcript, scrape_page_content, search_wikipedia, search_news,
# format_web_search_for_prompt, detect_search_intent, detect_datetime_intent

# -------------------------
# AI functions
# -------------------------

def get_ai_response(query):
    if not st.session_state.get('llama_client'):
        return "Vision AI non disponible."

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

# [NOTE: Fonctions d'édition d'image, password reset, admin page - identiques]
# Inclure toutes ces fonctions sans modification

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
    except:
        st.session_state.llava_client = None

if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        st.session_state.llama_client = None

if "qwen_client" not in st.session_state:
    try:
        st.session_state.qwen_client = Client("Selfit/ImageEditPro")
    except:
        st.session_state.qwen_client = None

if "reset_step" not in st.session_state:
    st.session_state.reset_step = "request"

if "reset_email" not in st.session_state:
    st.session_state.reset_email = ""

if "reset_token" not in st.session_state:
    st.session_state.reset_token = ""

if "page" not in st.session_state:
    st.session_state.page = "main"

# Mode DEBUG
if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = True  # Activer par défaut

# -------------------------
# Navigation
# -------------------------
# [Sidebar, authentification, conversations - code identique mais conservé]

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat - Analyse & Édition d'Images")

# Toggle debug mode
with st.sidebar:
    st.session_state.debug_mode = st.checkbox("🐛 Mode Debug", value=st.session_state.debug_mode)

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")
    if st.session_state.debug_mode:
        st.info(f"🔍 DEBUG: Conv ID: {st.session_state.conversation.get('conversation_id')[:12]}...")
        st.info(f"🔍 DEBUG: User ID: {st.session_state.user.get('id')[:12]}...")

# [Reste du code de l'interface - tabs, forms, etc.]

# NOTE: Je ne peux pas réécrire TOUT le code ici (limite de tokens)
# Les modifications clés sont:
# 1. add_message() avec debug complet
# 2. create_conversation() avec debug
# 3. get_messages() avec gestion d'erreur
# 4. Mode debug activable dans l'UI

# Le reste des fonctions (recherche web, édition image, etc.) reste identique
