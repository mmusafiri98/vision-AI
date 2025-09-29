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

# ------------------------- 
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Complete", layout="wide")

SYSTEM_PROMPT = """You are Vision AI. You were created by Pepe Musafiri, an Artificial Intelligence Engineer, with contributions from Meta AI. Your role is to help users with any task they need, from image analysis and editing to answering questions clearly and helpfully. Always answer naturally as Vision AI. 

You have access to:
- Current date and time information
- Real-time web search capabilities
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

When you receive current time/date information starting with [DATETIME], use this information to:
1. Answer questions about the current date, time, day of week, etc.
2. Calculate time differences or future/past dates
3. Provide time-sensitive information accurately

When you receive web search results starting with [WEB_SEARCH], you should:
1. Analyze and synthesize the information from search results
2. Provide accurate and up-to-date information from the web
3. Cite sources when providing factual information
4. Distinguish between general knowledge and current events"""

# Informations admin
ADMIN_CREDENTIALS = {
    "email": "jessice34@gmail.com",
    "password": "4Us,T}17"
}

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
    except:
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
    except:
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
    except:
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
    """Formate les informations de date/heure pour le prompt"""
    dt_info = get_current_datetime_info()
    
    if "error" in dt_info:
        return f"[DATETIME] Erreur: {dt_info['error']}"
    
    return f"""[DATETIME] Informations actuelles:
- Date complète: {dt_info['datetime']}
- Date: {dt_info['date']}
- Heure: {dt_info['time']}
- Jour de la semaine: {dt_info['day_of_week']}
- Mois: {dt_info['month']}
- Année: {dt_info['year']}
- Timezone: {dt_info['timezone']}"""

def search_web(query, max_results=5):
    """Recherche sur le web avec DuckDuckGo (sans API key)"""
    try:
        # Utilisation de DuckDuckGo HTML (pas besoin d'API)
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Extraire les résultats de recherche
            for result in soup.find_all('div', class_='result')[:max_results]:
                try:
                    title_elem = result.find('a', class_='result__a')
                    snippet_elem = result.find('a', class_='result__snippet')
                    
                    if title_elem and snippet_elem:
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True)
                        
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                except:
                    continue
            
            return results
        else:
            return []
    except Exception as e:
        st.error(f"Erreur recherche web: {e}")
        return []

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
    results_text = f"[WEB_SEARCH] Résultats de recherche pour: '{query}'\n\n"
    
    if search_type == "web":
        results = search_web(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"{i}. {result['title']}\n"
                results_text += f"   Source: {result['url']}\n"
                results_text += f"   Résumé: {result['snippet']}\n\n"
        else:
            results_text += "Aucun résultat trouvé.\n"
    
    elif search_type == "wikipedia":
        results = search_wikipedia(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"{i}. {result['title']}\n"
                results_text += f"   URL: {result['url']}\n"
                results_text += f"   Extrait: {result['snippet']}\n\n"
        else:
            results_text += "Aucun résultat Wikipedia trouvé.\n"
    
    elif search_type == "news":
        results = search_news(query)
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"{i}. {result['title']}\n"
                results_text += f"   Date: {result['date']}\n"
                results_text += f"   Source: {result['url']}\n\n"
        else:
            results_text += "Aucune actualité trouvée.\n"
    
    return results_text

def detect_search_intent(user_message):
    """Détecte si l'utilisateur demande une recherche web"""
    search_keywords = [
        'recherche', 'cherche', 'trouve', 'informations sur', 'actualité', 
        'news', 'dernières nouvelles', 'quoi de neuf', 'what is', 'who is',
        'définition', 'expliquer', 'c\'est quoi', 'météo', 'weather',
        'actualités sur', 'information récente', 'dernières infos'
    ]
    
    news_keywords = [
        'actualité', 'news', 'nouvelles', 'dernières nouvelles',
        'quoi de neuf', 'info du jour'
    ]
    
    wiki_keywords = [
        'définition', 'c\'est quoi', 'qui est', 'what is', 'who is',
        'expliquer', 'wikipedia'
    ]
    
    message_lower = user_message.lower()
    
    # Vérifier si c'est une demande de recherche
    needs_search = any(keyword in message_lower for keyword in search_keywords)
    
    if not needs_search:
        return None, None
    
    # Déterminer le type de recherche
    if any(keyword in message_lower for keyword in news_keywords):
        return "news", user_message
    elif any(keyword in message_lower for keyword in wiki_keywords):
        return "wikipedia", user_message
    else:
        return "web", user_message

def detect_datetime_intent(user_message):
    """Détecte si l'utilisateur demande la date/heure"""
    datetime_keywords = [
        'quelle heure', 'quel jour', 'quelle date', 'aujourd\'hui',
        'maintenant', 'heure actuelle', 'date actuelle', 'quel mois',
        'quelle année', 'what time', 'what date', 'current time',
        'current date', 'today', 'now'
    ]
    
    message_lower = user_message.lower()
    return any(keyword in message_lower for keyword in datetime_keywords)

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
                    edit_msg += f" (instruction: {edit_instruction})"
                    
                return edited_img, edit_msg
        
        return None, "Erreur traitement image"
    except Exception as e:
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
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.info("Analyse de l'image originale...")
        progress_bar.progress(20)
        time.sleep(0.5)
        
        original_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        
        status_text.info(f"Édition en cours: '{edit_instruction}'...")
        progress_bar.progress(40)
        
        edited_img, result_info = edit_image_with_qwen(image, edit_instruction)
        
        if edited_img:
            status_text.info("Analyse de l'image éditée...")
            progress_bar.progress(70)
            time.sleep(0.5)
            
            edited_caption = generate_caption(edited_img, st.session_state.processor, st.session_state.model)
            
            status_text.info("Sauvegarde et finalisation...")
            progress_bar.progress(90)
            
            edit_context = create_edit_context(original_caption, edit_instruction, edited_caption, result_info)
            
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
            success = add_message(conv_id, "assistant", response_content, "image", edited_b64, None)
            
            if success:
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
                status_text.error("Erreur sauvegarde")
                progress_bar.empty()
                return False
        else:
            status_text.error(f"Échec édition: {result_info}")
            progress_bar.empty()
            return False
    except Exception as e:
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
                except Exception as e:
                    st.error(f"Erreur: {e}")
        
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
    
    tab1, tab2, tab3 = st.tabs(["Utilisateurs", "Conversations", "Statistiques"])
    
    with tab1:
        if supabase:
            try:
                users = supabase.table("users").select("*").order("created_at", desc=True).execute()
                if users.data:
                    for user in users.data:
                        with st.expander(f"{user.get('name')} ({user.get('email')})"):
                            st.write(f"**ID:** {user.get('id')[:8]}...")
                            st.write(f"**Rôle:** {user.get('role', 'user')}")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab2:
        if supabase:
            try:
                convs = supabase.table("conversations").select("*").limit(20).execute()
                if convs.data:
                    for conv in convs.data:
                        st.write(f"- {conv.get('description')} ({conv.get('created_at')[:10]})")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab3:
        if supabase:
            try:
                users_count = supabase.table("users").select("id", count="exact").execute()
                convs_count = supabase.table("conversations").select("id", count="exact").execute()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Utilisateurs", users_count.count or 0)
                with col2:
                    st.metric("Conversations", convs_count.count or 0)
            except Exception as e:
                st.error(f"Erreur: {e}")

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

# -------------------------
# Navigation
# -------------------------
if st.session_state.page == "admin":
    show_admin_page()
    st.stop()

# -------------------------
# Sidebar
# -------------------------
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
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Identifiants invalides")

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
                            time.sleep(1)

    with tab3:
        show_password_reset()
    
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    
    if st.session_state.user.get('role') == 'admin':
        st.sidebar.markdown("**Admin**")
        if st.sidebar.button("Interface Admin"):
            st.session_state.page = "admin"
            st.rerun()
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Gestion Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("Conversations")
    
    if st.sidebar.button("Nouvelle conversation"):
        with st.spinner("Création..."):
            conv = create_conversation(st.session_state.user["id"], "Nouvelle discussion")
            if conv:
                st.session_state.conversation = conv
                st.session_state.messages_memory = []
                st.success("Créée!")
                time.sleep(1)
                st.rerun()
    
    convs = get_conversations(st.session_state.user["id"])
    if convs:
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
            
            with st.spinner("Chargement..."):
                st.session_state.conversation = selected_conv
                messages = get_messages(selected_conv.get("conversation_id"))
                st.session_state.messages_memory = messages
                time.sleep(0.5)
                st.rerun()

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat - Analyse & Édition d'Images")

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")

tab1, tab2 = st.tabs(["Chat Normal", "Mode Éditeur"])

with tab1:
    st.write("Mode chat avec analyse d'images")
    
    if st.session_state.messages_memory:
        for msg in st.session_state.messages_memory:
            role = "user" if msg.get("sender") == "user" else "assistant"
            
            with st.chat_message(role):
                if msg.get("type") == "image" and msg.get("image_data"):
                    try:
                        st.image(base64_to_image(msg["image_data"]), width=300)
                    except:
                        pass
                
                st.markdown(msg.get("content", ""))
    
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
                type=["png","jpg","jpeg"],
                key="chat_upload"
            )
        
        submit_chat = st.form_submit_button("Envoyer")

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
                original_desc = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                st.write(f"**Description:** {original_desc}")
    
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
        
        if st.button("Éditer", type="primary", disabled=not (editor_file and edit_instruction.strip())):
            if not st.session_state.conversation:
                conv = create_conversation(st.session_state.user["id"], "Édition d'images")
                if conv:
                    st.session_state.conversation = conv
            
            if st.session_state.conversation:
                original_caption = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                user_msg = f"**Édition demandée**\n\n**Image:** {original_caption}\n\n**Instruction:** {edit_instruction}"
                original_b64 = image_to_base64(editor_image.convert("RGB"))
                
                add_message(
                    st.session_state.conversation.get("conversation_id"),
                    "user",
                    user_msg,
                    "image",
                    original_b64
                )
                
                st.session_state.messages_memory.append({
                    "message_id": str(uuid.uuid4()),
                    "sender": "user",
                    "content": user_msg,
                    "type": "image",
                    "image_data": original_b64,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                success = process_image_edit_request(
                    editor_image,
                    edit_instruction,
                    st.session_state.conversation.get("conversation_id")
                )
                
                if success:
                    st.rerun()

# -------------------------
# Traitement chat
# -------------------------
if 'submit_chat' in locals() and submit_chat and (user_input.strip() or uploaded_file):
    if not st.session_state.conversation:
        with st.spinner("Création conversation..."):
            conv = create_conversation(st.session_state.user["id"], "Discussion")
            if conv:
                st.session_state.conversation = conv
            else:
                st.error("Impossible de créer conversation")
                st.stop()
    
    conv_id = st.session_state.conversation.get("conversation_id")
    
    message_content = user_input.strip()
    image_data = None
    msg_type = "text"
    
    if uploaded_file:
        with st.spinner("Analyse de l'image..."):
            image = Image.open(uploaded_file)
            image_data = image_to_base64(image)
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            message_content = f"[IMAGE] {caption}"
            
            if user_input.strip():
                message_content += f"\n\nQuestion: {user_input.strip()}"
            msg_type = "image"
            time.sleep(0.5)
    
    if message_content:
        add_message(conv_id, "user", message_content, msg_type, image_data)
        
        user_msg = {
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages_memory.append(user_msg)
        
        lower = user_input.lower()
        if (any(k in lower for k in ["edit", "édite", "modifie"]) and uploaded_file):
            edit_instruction = user_input.strip()
            success = process_image_edit_request(
                Image.open(uploaded_file).convert("RGBA"),
                edit_instruction,
                conv_id
            )
            if success:
                st.rerun()
        else:
            edit_context = get_editing_context_from_conversation()
            
            # Construction du prompt enrichi avec date/heure et recherche web si nécessaire
            prompt = f"{SYSTEM_PROMPT}\n\n"
            
            # Ajouter les informations de date/heure si pertinent
            if detect_datetime_intent(user_input):
                datetime_info = format_datetime_for_prompt()
                prompt += f"{datetime_info}\n\n"
            
            # Détecter et effectuer une recherche web si nécessaire
            search_type, search_query = detect_search_intent(user_input)
            if search_type and search_query:
                with st.spinner(f"🔍 Recherche en cours sur {search_type}..."):
                    web_results = format_web_search_for_prompt(search_query, search_type)
                    prompt += f"{web_results}\n\n"
                    time.sleep(0.5)
            
            # Ajouter le contexte d'édition si disponible
            if edit_context:
                prompt += f"[EDIT_CONTEXT] {edit_context}\n\n"
            
            # Ajouter le message utilisateur
            prompt += f"Utilisateur: {message_content}"
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                if edit_context and any(w in user_input.lower() for w in ["edit", "image", "avant", "après"]):
                    with st.spinner("Consultation mémoire..."):
                        time.sleep(1)
                
                # Appel API avec Vision AI thinking
                response = get_ai_response(prompt)
                
                # Afficher Vision AI thinking puis la réponse
                stream_response_with_thinking(response, placeholder)
                
                add_message(conv_id, "assistant", response, "text")
                
                ai_msg = {
                    "sender": "assistant",
                    "content": response,
                    "type": "text",
                    "image_data": None,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.messages_memory.append(ai_msg)
                
                st.rerun()

# -------------------------
# Footer
# -------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.write("**Vision AI:**")
    st.write("- Analyse intelligente")
    st.write("- Édition avec Qwen")
    st.write("- Mémoire des éditions")

with col2:
    st.write("**Chat:**")
    st.write("- Conversations sauvegardées")
    st.write("- Contexte des éditions")
    st.write("- Discussion modifications")

with col3:
    st.write("**Éditeur:**")
    st.write("- Prompts personnalisés")
    st.write("- API /global_edit")
    st.write("- Analyse avant/après")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.write("**Nouvelles fonctionnalités:**")
    st.write("- Date et heure en temps réel")
    st.write("- Recherche web intégrée")
    st.write("- Actualités récentes")

with col2:
    st.write("**Sources disponibles:**")
    st.write("- DuckDuckGo")
    st.write("- Wikipedia")
    st.write("- Google News")

# -------------------------
# Guide d'utilisation
# -------------------------
with st.expander("Guide d'utilisation"):
    st.markdown("""
    ### Comment utiliser Vision AI Chat
    
    **Mode Chat Normal:**
    1. Uploadez une image pour l'analyser
    2. Posez des questions sur l'image
    3. Discutez des éditions précédentes
    4. **Nouveau:** Demandez la date/heure actuelle
    5. **Nouveau:** Recherchez des informations sur le web
    
    **Mode Éditeur:**
    1. Uploadez une image à éditer
    2. Sélectionnez ou écrivez une instruction
    3. Cliquez sur "Éditer l'image"
    4. Téléchargez le résultat
    
    **Exemples de questions avec recherche web:**
    - "Cherche des informations sur Paris"
    - "Quelle heure est-il ?"
    - "Actualités du jour"
    - "Définition de intelligence artificielle"
    - "Météo aujourd'hui"
    
    **Modèles utilisés:**
    - **BLIP**: Description d'images
    - **LLaMA 3.1 70B**: Conversations
    - **Qwen ImageEditPro**: Édition d'images
    - **DuckDuckGo/Wikipedia/Google News**: Recherche web
    
    **Note:** Vision AI affiche "Vision AI thinking..." pendant qu'il traite votre demande.
    """)

# -------------------------
# Test des nouvelles fonctionnalités
# -------------------------
if st.sidebar.button("🧪 Test Date/Heure & Web"):
    st.sidebar.subheader("Tests")
    
    # Test date/heure
    dt_info = get_current_datetime_info()
    if "error" not in dt_info:
        st.sidebar.success("Date/Heure OK")
        st.sidebar.write(f"📅 {dt_info['date']}")
        st.sidebar.write(f"🕐 {dt_info['time']}")
    else:
        st.sidebar.error("Erreur Date/Heure")
    
    # Test recherche web
    with st.sidebar.expander("Test Web Search"):
        test_query = st.text_input("Query de test:", "Python programming")
        if st.button("Tester"):
            with st.spinner("Recherche..."):
                results = search_web(test_query, max_results=3)
                if results:
                    st.success(f"{len(results)} résultats trouvés")
                    for r in results:
                        st.write(f"- {r['title']}")
                else:
                    st.warning("Aucun résultat")

# -------------------------
# Admin sidebar
# -------------------------
if st.session_state.user.get("role") == "admin":
    with st.sidebar.expander("Fonctions Admin"):
        st.write("Interface Administrateur disponible")
        if st.button("Accéder Interface Admin", key="admin_launch"):
            st.session_state.page = "admin"
            st.rerun()

# -------------------------
# Diagnostics
# -------------------------
if st.sidebar.button("Diagnostics"):
    st.sidebar.subheader("Tests")
    
    if supabase:
        try:
            supabase.table("users").select("*").limit(1).execute()
            st.sidebar.success("Supabase OK")
        except:
            st.sidebar.error("Supabase KO")
    
    if st.session_state.llama_client:
        st.sidebar.success("LLaMA OK")
    else:
        st.sidebar.error("LLaMA KO")
    
    if st.session_state.qwen_client:
        st.sidebar.success("Qwen OK")
    else:
        st.sidebar.error("Qwen KO")

if st.sidebar.button("Nettoyer fichiers temp"):
    cleanup_temp_files()
    st.sidebar.success("Nettoyage effectué!")

# -------------------------
# Statistiques utilisateur
# -------------------------
if st.session_state.user["id"] != "guest" and supabase:
    try:
        conv_count = len(get_conversations(st.session_state.user["id"]))
        msg_count = len(st.session_state.messages_memory) if st.session_state.conversation else 0
        
        with st.sidebar.expander("Vos statistiques"):
            st.write(f"Conversations: {conv_count}")
            st.write(f"Messages: {msg_count}")
            
            edit_count = sum(1 for msg in st.session_state.messages_memory if msg.get("edit_context"))
            st.write(f"Éditions: {edit_count}")
    except:
        pass
