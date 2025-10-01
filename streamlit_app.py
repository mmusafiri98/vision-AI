                

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

You have access to:
- Current date and time information (provided in [DATETIME])
- Real-time web search capabilities (results in [WEB_SEARCH])
- Image analysis and editing tools

When you receive an image description starting with [IMAGE], you should:
1. Acknowledge that you can see and analyze the image
2. Provide detailed analysis of what you observe
3. Answer any specific questions about the image
4. Be helpful and descriptive in your analysis

When you receive information about image editing starting with [EDIT_CONTEXT], you should:
1. Remember the editing history and context provided
2. Use this information to discuss the edits made
3. Answer questions about the editing process and results
4. Provide suggestions for further improvements if asked

When you receive current time/date information starting with [DATETIME]:
- This is the ACTUAL, REAL current date and time
- YOU MUST USE this information to answer questions about the current date, time, day of week
- DO NOT say you don't have access to current time - you DO have it in [DATETIME]
- Calculate time differences or future/past dates based on this information

When you receive web search results starting with [WEB_SEARCH]:
- These are REAL search results from the internet RIGHT NOW
- YOU MUST analyze and use this information in your response
- Cite the sources provided in the search results
- Provide accurate and up-to-date information based on these results
- DO NOT rely only on your training data - USE THE SEARCH RESULTS PROVIDED"""

# Informations admin
ADMIN_CREDENTIALS = {
    "email": "jessice34@gmail.com",
    "password": "4Us,T}17"
}

# -------------------------
# Configuration des API Keys
# -------------------------
# IMPORTANT: Configurez ces clés dans les secrets Streamlit (Settings → Secrets)
# NE PAS mettre les clés directement dans le code !
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
        except Exception as e:
            st.error(f"Erreur update user: {e}")
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
            except Exception as e:
                st.error(f"Erreur insert token: {e}")
                return False
    except Exception as e:
        st.error(f"Erreur générale: {e}")
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
        except Exception as e:
            st.error(f"Erreur vérification user token: {e}")
            pass
        
        try:
            response = supabase.table("password_resets").select("*").eq("email", email).eq("reset_token", token).eq("used", False).execute()
            if response.data and response.data[0].get("expires_at", 0) > current_time:
                return True
        except Exception as e:
            st.error(f"Erreur vérification password_resets: {e}")
            pass
        
        return False
    except Exception as e:
        st.error(f"Erreur générale vérification: {e}")
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
            except Exception as e:
                st.error(f"Erreur marquage token utilisé: {e}")
                pass
            return True
        return False
    except Exception as e:
        st.error(f"Erreur réinitialisation mot de passe: {e}")
        return False

# -------------------------
# Fonctions DB
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
        except Exception as e:
            st.error(f"Erreur auth sign_in: {e}")
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
    except Exception as e:
        st.error(f"Erreur vérification utilisateur: {e}")
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
        except Exception as e:
            st.error(f"Erreur création user auth: {e}")
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
    except Exception as e:
        st.error(f"Erreur création utilisateur: {e}")
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
    except Exception as e:
        st.error(f"Erreur récupération conversations: {e}")
        return []

def create_conversation(user_id, description):
    if not supabase or not user_id:
        return None
        
    try:
        data = {
            "user_id": user_id,
            "description": description,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = supabase.table("conversations").insert(data).execute()
        
        if response.data:
            conv = response.data[0]
            return {
                "conversation_id": conv.get("conversation_id") or conv.get("id"),
                "description": conv["description"],
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
        return None
    except Exception as e:
        st.error(f"Erreur création conversation: {e}")
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
        st.error(f"Erreur récupération messages: {e}")
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None, edit_context=None):
    if not supabase or not conversation_id or not content:
        return False
        
    try:
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        if not conv_check.data:
            return False
            
        message_data = {
            "conversation_id": conversation_id,
            "sender": str(sender).strip(),
            "content": str(content).strip(),
            "type": msg_type or "text",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if image_data:
            message_data["image_data"] = image_data
        if edit_context:
            message_data["edit_context"] = edit_context
            
        response = supabase.table("messages").insert(message_data).execute()
        return bool(response.data)
    except Exception as e:
        st.error(f"Erreur ajout message: {e}")
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
# Fonctions Date/Heure et Web Search
# -------------------------
def get_current_datetime_info():
    """Récupère les informations de date et heure actuelles"""
    try:
        # Timezone par défaut (peut être configuré)
        tz = pytz.timezone('Europe/Brussels')  # Changez selon votre timezone
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
    """Formate les informations de date/heure pour le prompt de manière TRÈS explicite"""
    dt_info = get_current_datetime_info()
    
    if "error" in dt_info:
        return f"[DATETIME] Erreur: {dt_info['error']}"
    
    # Version TRÈS explicite et détaillée
    return f"""[DATETIME] ⚠️ IMPORTANT - INFORMATIONS TEMPORELLES ACTUELLES (RÉELLES):
==========================================
VOUS DEVEZ UTILISER CES INFORMATIONS POUR RÉPONDRE AUX QUESTIONS SUR LA DATE/HEURE !

Date et heure ACTUELLES (EN CE MOMENT MÊME):
- Date complète MAINTENANT: {dt_info['datetime']}
- Date AUJOURD'HUI: {dt_info['date']}
- Heure ACTUELLE: {dt_info['time']}
- Jour de la semaine AUJOURD'HUI: {dt_info['day_of_week']}
- Mois ACTUEL: {dt_info['month']}
- Année ACTUELLE: {dt_info['year']}
- Timezone: {dt_info['timezone']}

RAPPEL: Si l'utilisateur demande "quelle heure est-il?" ou "quel jour sommes-nous?", 
VOUS DEVEZ répondre avec ces informations ci-dessus. Ne dites PAS que vous ne savez pas!
=========================================="""

def search_google(query, max_results=10):
    """Recherche avec Google Custom Search API"""
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        st.warning("Google API credentials manquantes")
        return []
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "num": max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for item in data.get('items', []):
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'display_url': item.get('displayLink', '')
                })
            
            return results
        elif response.status_code == 429:
            st.error("⚠️ Quota Google API dépassé pour aujourd'hui")
            return []
        else:
            st.error(f"Google API erreur: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Erreur Google Search: {e}")
        return []

def search_youtube(query, max_results=5):
    """Recherche de vidéos YouTube avec API officielle"""
    if not YOUTUBE_API_KEY:
        st.warning("YouTube API key manquante")
        return []
    
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "key": YOUTUBE_API_KEY,
            "maxResults": max_results,
            "type": "video",
            "order": "date",
            "relevanceLanguage": "fr"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for item in data.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                
                results.append({
                    'title': snippet.get('title', ''),
                    'video_id': video_id,
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'description': snippet.get('description', ''),
                    'channel': snippet.get('channelTitle', ''),
                    'published': snippet.get('publishedAt', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', '')
                })
            
            return results
        elif response.status_code == 403:
            st.error("⚠️ Quota YouTube API dépassé ou clé invalide")
            return []
        else:
            st.error(f"YouTube API erreur: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Erreur YouTube Search: {e}")
        return []

def get_youtube_transcript(video_id):
    """Récupère la transcription d'une vidéo YouTube"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['fr', 'en'])
        full_text = " ".join([item['text'] for item in transcript[:50]])
        return full_text
    except:
        return None

def scrape_page_content(url, max_chars=2000):
    """Scrape le contenu complet d'une page web"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Supprimer scripts et styles
            for script in soup(["script", "style"]):
                script.decompose()
            # Extraire le texte
            text = soup.get_text()
            # Nettoyer
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text[:max_chars]
        return None
    except Exception as e:
        return None
    
def search_wikipedia(query):
    """Recherche rapide sur Wikipedia"""
    try:
        wiki_url = f"https://fr.wikipedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': query,
            'utf8': 1,
            'srlimit': 3
        }
        
        response = requests.get(wiki_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for item in data.get('query', {}).get('search', []):
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', '').replace('<span class="searchmatch">', '').replace('</span>', ''),
                    'url': f"https://fr.wikipedia.org/wiki/{item.get('title', '').replace(' ', '_')}"
                })
            
            return results
        return []
    except Exception as e:
        return []

def search_news(query):
    """Recherche d'actualités récentes"""
    try:
        # Utilisation de Google News RSS (gratuit)
        news_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=fr&gl=FR&ceid=FR:fr"
        
        response = requests.get(news_url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'xml')
            items = soup.find_all('item')[:5]
            
            results = []
            for item in items:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                description = item.find('description')
                
                if title and link:
                    results.append({
                        'title': title.text,
                        'url': link.text,
                        'date': pub_date.text if pub_date else 'N/A',
                        'snippet': description.text if description else ''
                    })
            
            return results
        return []
    except Exception as e:
        return []

def format_web_search_for_prompt(query, search_type="web"):
    """Formate les résultats de recherche pour le prompt"""
    results_text = f"""[WEB_SEARCH] ⚠️ RÉSULTATS DE RECHERCHE EN TEMPS RÉEL - VOUS DEVEZ LES UTILISER !
==========================================
Question de recherche: "{query}"
Type de recherche: {search_type}

⚠️ IMPORTANT: Ces résultats proviennent d'Internet MAINTENANT (en temps réel).
VOUS DEVEZ utiliser ces informations pour répondre à la question de l'utilisateur.
NE dites PAS que vous n'avez pas accès à Internet - ces résultats SONT d'Internet!

RÉSULTATS TROUVÉS:
"""
    
    if search_type == "google":
        results = search_google(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"\n🔍 RÉSULTAT GOOGLE #{i}:\n"
                results_text += f"   Titre: {result['title']}\n"
                results_text += f"   Source URL: {result['url']}\n"
                results_text += f"   Domaine: {result.get('display_url', 'N/A')}\n"
                results_text += f"   Contenu: {result['snippet']}\n"
                
                page_content = scrape_page_content(result['url'])
                if page_content:
                    results_text += f"   📄 Extrait de la page: {page_content[:800]}...\n"
                
                results_text += f"   ---\n"
        else:
            results_text += "\n❌ Aucun résultat Google trouvé.\n"
    
    elif search_type == "youtube":
        results = search_youtube(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"\n🎥 VIDÉO YOUTUBE #{i}:\n"
                results_text += f"   Titre: {result['title']}\n"
                results_text += f"   URL: {result['url']}\n"
                results_text += f"   Chaîne: {result['channel']}\n"
                results_text += f"   Publié: {result['published']}\n"
                results_text += f"   Description: {result['description'][:300]}...\n"
                
                transcript = get_youtube_transcript(result['video_id'])
                if transcript:
                    results_text += f"   📝 Transcription: {transcript[:500]}...\n"
                
                results_text += f"   ---\n"
        else:
            results_text += "\n❌ Aucune vidéo YouTube trouvée.\n"
    
    elif search_type == "wikipedia":
        results = search_wikipedia(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"\n📚 ARTICLE WIKIPEDIA #{i}:\n"
                results_text += f"   Titre: {result['title']}\n"
                results_text += f"   URL: {result['url']}\n"
                results_text += f"   Extrait: {result['snippet']}\n"
                results_text += f"   ---\n"
        else:
            results_text += "\n❌ Aucun article Wikipedia trouvé.\n"
    
    elif search_type == "news":
        results = search_news(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"\n📰 ACTUALITÉ #{i}:\n"
                results_text += f"   Titre: {result['title']}\n"
                results_text += f"   Date: {result['date']}\n"
                results_text += f"   Source: {result['url']}\n"
                results_text += f"   ---\n"
        else:
            results_text += "\n❌ Aucune actualité trouvée.\n"
    
    results_text += """
==========================================
⚠️ RAPPEL: Vous DEVEZ utiliser ces résultats de recherche dans votre réponse.
Citez les sources et fournissez des informations basées sur ces résultats réels.
=========================================="""
    
    return results_text

def detect_search_intent(user_message):
    """Détecte le type de recherche"""
    search_keywords = [
        'recherche', 'cherche', 'trouve', 'informations sur', 'actualité', 
        'news', 'dernières nouvelles', 'quoi de neuf', 'what is', 'who is',
        'définition', 'expliquer', 'c\'est quoi', 'météo', 'weather',
        'actualités sur', 'information récente', 'dernières infos',
        'video', 'vidéo', 'youtube', 'regarde', 'montre', 'voir'
    ]
    
    news_keywords = [
        'actualité', 'news', 'nouvelles', 'dernières nouvelles',
        'quoi de neuf', 'info du jour', 'breaking', 'flash'
    ]
    
    wiki_keywords = [
        'définition', 'c\'est quoi', 'qui est', 'what is', 'who is',
        'expliquer', 'wikipedia', 'définir'
    ]
    
    youtube_keywords = [
        'video', 'vidéo', 'youtube', 'regarde', 'montre moi', 
        'voir video', 'regarder', 'visionner', 'film'
    ]
    
    message_lower = user_message.lower()
    needs_search = any(keyword in message_lower for keyword in search_keywords)
    
    if not needs_search:
        return None, None
    
    # Priorité: YouTube → News → Wiki → Google
    if any(keyword in message_lower for keyword in youtube_keywords):
        return "youtube", user_message
    elif any(keyword in message_lower for keyword in news_keywords):
        return "news", user_message
    elif any(keyword in message_lower for keyword in wiki_keywords):
        return "wikipedia", user_message
    else:
        return "google", user_message

def detect_datetime_intent(user_message):
    """Détecte si l'utilisateur demande la date/heure - VERSION ÉTENDUE"""
    datetime_keywords = [
        'quelle heure', 'quel jour', 'quelle date', 'aujourd\'hui',
        'maintenant', 'heure actuelle', 'date actuelle', 'quel mois',
        'quelle année', 'what time', 'what date', 'current time',
        'current date', 'today', 'now', 'heure', 'date', 'jour',
        'sommes-nous', 'est-il', 'c\'est quel jour', 'on est quel jour',
        'quelle est la date', 'quelle est l\'heure', 'il est quelle heure',
        'nous sommes le', 'quel est le jour'
    ]
    
    message_lower = user_message.lower()
    return any(keyword in message_lower for keyword in datetime_keywords)

def should_always_add_datetime():
    """Toujours ajouter la date/heure pour que le modèle ait toujours le contexte temporel"""
    return True  # On ajoute TOUJOURS la date/heure maintenant

# -------------------------
# AI functions avec Vision AI thinking
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
    
    for _ in range(2):  # 2 cycles d'animation
        for frame in thinking_frames:
            placeholder.markdown(f"**{frame}**")
            time.sleep(0.3)

def stream_response_with_thinking(text, placeholder):
    """Affiche Vision AI thinking puis stream la réponse"""
    # Phase thinking
    show_vision_ai_thinking(placeholder)
    
    # Petite pause avant la réponse
    time.sleep(0.5)
    
    # Stream de la réponse
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
        return None, "Client Qwen non disponible."
    
    try:
        temp_path = os.path.join(TMP_DIR, f"input_{uuid.uuid4().hex}.png")
        image.save(temp_path)
        
        prompt_message = edit_instruction if edit_instruction.strip() else "enhance and improve the image"
        
        result = client.predict(
            input_image=handle_file(temp_path),
            prompt=prompt_message,
            api_name="/global_edit"
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
                    edit_msg += f" (instruction:          edit_msg = f"Image éditée avec succès - {status_message}"
                if edit_instruction:
                    edit_msg += f" (instruction: {edit_instruction})"
                return edited_img, edit_msg
            else:
                return None, "Erreur lors de l'édition de l'image."
        else:
            return None, "Résultat invalide du modèle Qwen."
    except Exception as e:
        traceback.print_exc()
        return None, f"Erreur lors de l'édition de l'image: {str(e)}"

# -------------------------
# Interface Streamlit
# -------------------------
def main():
    st.title("Vision AI Chat - Complet")

    # Initialisation des clients
    if 'llama_client' not in st.session_state:
        st.session_state.llama_client = Client("https://your-llama-api-endpoint.com")
    if 'qwen_client' not in st.session_state:
        st.session_state.qwen_client = Client("https://your-qwen-api-endpoint.com")

    # Chargement du modèle BLIP
    processor, model = load_blip()

    # Gestion de l'authentification
    if 'user' not in st.session_state:
        st.session_state.user = None

    def login():
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Connexion")
            if submitted:
                user = verify_user(email, password)
                if user:
                    st.session_state.user = user
                    st.experimental_rerun()
                else:
                    st.error("Identifiants invalides")

    def logout():
        st.session_state.user = None
        st.experimental_rerun()

    if not st.session_state.user:
        login()
        return

    # Affichage des conversations
    conversations = get_conversations(st.session_state.user['id'])
    selected_conv = st.selectbox("Conversations", [f"{conv['description']} ({conv['created_at']})" for conv in conversations], format_func=lambda x: x.split(' (')[0])
    selected_conv_id = conversations[st.session_state.selectbox_indices[0]]['conversation_id'] if conversations else None

    # Création de conversation
    new_conv_desc = st.text_input("Nouvelle conversation", key="new_conv")
    if st.button("Créer"):
        new_conv = create_conversation(st.session_state.user['id'], new_conv_desc)
        if new_conv:
            st.experimental_rerun()

    # Affichage des messages
    if selected_conv_id:
        messages = get_messages(selected_conv_id)
        for msg in messages:
            if msg['sender'] == 'user':
                st.write(f"**Vous ({msg['created_at']})**: {msg['content']}")
            else:
                st.write(f"**Vision AI ({msg['created_at']})**: {msg['content']}")

    # Upload d'image
    uploaded_file = st.file_uploader("Téléverser une image", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="Image téléchargée", use_column_width=True)

        # Analyse d'image
        if st.button("Analyser l'image"):
            caption = generate_caption(image, processor, model)
            add_message(selected_conv_id, "user", "[IMAGE] " + caption)
            st.success("Image analysée avec succès")

    # Edition d'image
    edit_instruction = st.text_input("Instruction d'édition", key="edit_instruction")
    if st.button("Éditer l'image"):
        if uploaded_file:
            edited_img, status = edit_image_with_qwen(image, edit_instruction)
            if edited_img:
                st.image(edited_img, caption="Image éditée", use_column_width=True)
                add_message(selected_conv_id, "user", "[EDIT_CONTEXT] " + status)
            else:
                st.error(status)
        else:
            st.warning("Aucune image à éditer")

    # Chat avec Vision AI
    user_input = st.text_area("Votre message", key="user_input")
    if st.button("Envoyer"):
        if user_input:
            # Détection des intentions
            search_type, search_query = detect_search_intent(user_input)
            datetime_intent = detect_datetime_intent(user_input)

            # Construction du prompt
            prompt = user_input
            if datetime_intent or should_always_add_datetime():
                prompt += "\n\n" + format_datetime_for_prompt()
            if search_type:
                prompt += "\n\n" + format_web_search_for_prompt(search_query, search_type)

            # Ajout du message utilisateur
            add_message(selected_conv_id, "user", user_input)

            # Réponse de Vision AI
            with st.spinner("Vision AI thinking..."):
                response = get_ai_response(prompt)
                add_message(selected_conv_id, "ai", response)
                st.write(f"**Vision AI**: {response}")
        else:
            st.warning("Veuillez entrer un message")

    # Bouton de déconnexion
    if st.button("Déconnexion"):
        logout()

if __name__ == "__main__":
    main()
