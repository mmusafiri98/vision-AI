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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import asyncio

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat + OperatorGPT", layout="wide")

SYSTEM_PROMPT = """You are Vision AI with OperatorGPT capabilities. You were created by Pepe Musafiri, an Artificial Intelligence Engineer, with contributions from Meta AI.

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE:
1. When you receive [DATETIME] information, YOU MUST USE IT to answer any time/date questions. This is the REAL current date and time.
2. When you receive [WEB_SEARCH] results, YOU MUST USE THEM to provide accurate, up-to-date information. These are REAL search results from the internet.
3. When you receive [BROWSER_ACTION] results, these are REAL actions performed by OperatorGPT in a browser.
4. NEVER say you don't know the current date/time when [DATETIME] information is provided.
5. ALWAYS cite and use the web search results when they are provided in [WEB_SEARCH].

You have access to:
- Current date and time information (provided in [DATETIME])
- Real-time web search capabilities (results in [WEB_SEARCH])
- Image analysis and editing tools
- OperatorGPT browser automation (actions in [BROWSER_ACTION])

OPERATORGPT CAPABILITIES:
You can control a browser to perform complex tasks:
- Navigate to websites
- Click buttons and links
- Fill forms and input fields
- Extract and read page content
- Take screenshots
- Execute multi-step workflows
- Make purchases, bookings, searches
- Summarize web content

When you receive browser automation requests:
1. Break down the task into clear steps
2. Execute actions sequentially
3. Verify each step's success
4. Report progress and results
5. Handle errors gracefully"""

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
BROWSER_SCREENSHOTS_DIR = "browser_screenshots"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(EDITED_IMAGES_DIR, exist_ok=True)
os.makedirs(BROWSER_SCREENSHOTS_DIR, exist_ok=True)

# -------------------------
# OperatorGPT - Browser Automation
# -------------------------
class OperatorGPT:
    """Agent autonome pour le contrôle de navigateur"""
    
    def __init__(self):
        self.driver = None
        self.action_history = []
        self.max_retries = 3
    
    def initialize_browser(self, headless=True):
        """Initialise le navigateur Chrome/Chromium"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            st.error(f"Erreur initialisation navigateur: {e}")
            return False
    
    def close_browser(self):
        """Ferme le navigateur"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
    
    def navigate_to(self, url):
        """Navigue vers une URL"""
        try:
            self.driver.get(url)
            self.action_history.append(f"Navigation vers: {url}")
            time.sleep(2)
            return True, f"Navigation réussie vers {url}"
        except Exception as e:
            return False, f"Erreur navigation: {e}"
    
    def get_page_content(self):
        """Récupère le contenu textuel de la page"""
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            text = ' '.join(chunk for line in lines for chunk in line.split("  ") if chunk)
            return text[:5000]  # Limite à 5000 caractères
        except Exception as e:
            return f"Erreur lecture contenu: {e}"
    
    def click_element(self, selector, by=By.CSS_SELECTOR):
        """Clique sur un élément"""
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            self.action_history.append(f"Clic sur: {selector}")
            time.sleep(1)
            return True, f"Clic réussi sur {selector}"
        except Exception as e:
            return False, f"Erreur clic: {e}"
    
    def fill_input(self, selector, text, by=By.CSS_SELECTOR):
        """Remplit un champ de saisie"""
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((by, selector))
            )
            element.clear()
            element.send_keys(text)
            self.action_history.append(f"Rempli champ {selector}: {text[:20]}...")
            return True, f"Champ rempli: {selector}"
        except Exception as e:
            return False, f"Erreur saisie: {e}"
    
    def take_screenshot(self, filename=None):
        """Prend une capture d'écran"""
        try:
            if not filename:
                filename = f"screenshot_{int(time.time())}.png"
            filepath = os.path.join(BROWSER_SCREENSHOTS_DIR, filename)
            self.driver.save_screenshot(filepath)
            self.action_history.append(f"Screenshot: {filename}")
            return True, filepath
        except Exception as e:
            return False, f"Erreur screenshot: {e}"
    
    def execute_search(self, search_engine, query):
        """Effectue une recherche sur un moteur de recherche"""
        try:
            if search_engine.lower() == "google":
                self.navigate_to("https://www.google.com")
                self.fill_input("textarea[name='q']", query)
                self.click_element("textarea[name='q']")
                time.sleep(0.5)
                # Envoyer Enter
                element = self.driver.find_element(By.CSS_SELECTOR, "textarea[name='q']")
                element.send_keys(Keys.RETURN)
                time.sleep(3)
                
                # Extraire les résultats
                results = []
                search_results = self.driver.find_elements(By.CSS_SELECTOR, "div.g")
                for result in search_results[:5]:
                    try:
                        title = result.find_element(By.CSS_SELECTOR, "h3").text
                        link = result.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                        snippet = result.find_element(By.CSS_SELECTOR, "div.VwiC3b").text
                        results.append({"title": title, "link": link, "snippet": snippet})
                    except:
                        continue
                
                return True, results
            
            elif search_engine.lower() == "youtube":
                self.navigate_to(f"https://www.youtube.com/results?search_query={query}")
                time.sleep(3)
                
                results = []
                videos = self.driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer")
                for video in videos[:5]:
                    try:
                        title = video.find_element(By.CSS_SELECTOR, "#video-title").text
                        url = video.find_element(By.CSS_SELECTOR, "#video-title").get_attribute("href")
                        results.append({"title": title, "url": url})
                    except:
                        continue
                
                return True, results
            
            return False, "Moteur de recherche non supporté"
        except Exception as e:
            return False, f"Erreur recherche: {e}"
    
    def extract_data(self, selectors):
        """Extrait des données spécifiques de la page"""
        try:
            data = {}
            for key, selector in selectors.items():
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    data[key] = element.text
                except:
                    data[key] = None
            return True, data
        except Exception as e:
            return False, f"Erreur extraction: {e}"
    
    def execute_workflow(self, steps):
        """Exécute un workflow multi-étapes"""
        results = []
        for i, step in enumerate(steps):
            action = step.get("action")
            params = step.get("params", {})
            
            result = {"step": i+1, "action": action, "success": False}
            
            try:
                if action == "navigate":
                    success, msg = self.navigate_to(params.get("url"))
                elif action == "click":
                    success, msg = self.click_element(params.get("selector"))
                elif action == "fill":
                    success, msg = self.fill_input(params.get("selector"), params.get("text"))
                elif action == "screenshot":
                    success, msg = self.take_screenshot(params.get("filename"))
                elif action == "wait":
                    time.sleep(params.get("seconds", 2))
                    success, msg = True, f"Attendu {params.get('seconds')}s"
                elif action == "extract":
                    success, msg = self.extract_data(params.get("selectors"))
                else:
                    success, msg = False, f"Action inconnue: {action}"
                
                result["success"] = success
                result["message"] = msg
                results.append(result)
                
                if not success and step.get("critical", False):
                    break
                    
            except Exception as e:
                result["message"] = str(e)
                results.append(result)
                if step.get("critical", False):
                    break
        
        return results

# -------------------------
# Instance globale OperatorGPT
# -------------------------
if "operator_gpt" not in st.session_state:
    st.session_state.operator_gpt = OperatorGPT()

# -------------------------
# Supabase Connection (inchangé)
# -------------------------
@st.cache_resource
def init_supabase():
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
# Fonctions DB (complètes)
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
# BLIP loader (inchangé)
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
# Fonctions Date/Heure et Web Search (inchangées)
# -------------------------
def get_current_datetime_info():
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
    dt_info = get_current_datetime_info()
    
    if "error" in dt_info:
        return f"[DATETIME] Erreur: {dt_info['error']}"
    
    return f"""[DATETIME] ⚠️ INFORMATIONS TEMPORELLES ACTUELLES:
Date ACTUELLE: {dt_info['datetime']}
Jour: {dt_info['day_of_week']}
Mois: {dt_info['month']}
Année: {dt_info['year']}"""

# [Garder toutes les fonctions de recherche: search_google, search_youtube, etc.]

# -------------------------
# Détection des intentions OperatorGPT
# -------------------------
def detect_operator_intent(user_message):
    """Détecte si l'utilisateur demande une action OperatorGPT"""
    operator_keywords = [
        'navigate', 'navigue', 'va sur', 'ouvre',
        'click', 'clique', 'appuie',
        'search for', 'cherche', 'recherche',
        'fill', 'rempli', 'écris',
        'book', 'réserve', 'achète', 'commande',
        'extract', 'récupère', 'lis',
        'screenshot', 'capture', 'prends une photo',
        'automatise', 'automate', 'fais', 'exécute'
    ]
    
    message_lower = user_message.lower()
    return any(keyword in message_lower for keyword in operator_keywords)

def parse_operator_command(user_message):
    """Parse la commande utilisateur en workflow OperatorGPT"""
    message_lower = user_message.lower()
    
    # Exemple simple de parsing - peut être amélioré avec du NLP
    if "google" in message_lower and ("cherche" in message_lower or "recherche" in message_lower):
        query = user_message.split("cherche")[-1].split("recherche")[-1].strip()
        return {
            "type": "search",
            "engine": "google",
            "query": query
        }
    
    elif "youtube" in message_lower:
        query = user_message.split("youtube")[-1].strip()
        return {
            "type": "search",
            "engine": "youtube",
            "query": query
        }
    
    elif "va sur" in message_lower or "ouvre" in message_lower or "navigue" in message_lower:
        # Extraire l'URL
        words = user_message.split()
        url = next((word for word in words if "http" in word or "www" in word or ".com" in word), None)
        return {
            "type": "navigate",
            "url": url
        }
    
    elif "screenshot" in message_lower or "capture" in message_lower:
        return {
            "type": "screenshot"
        }
    
    return {"type": "unknown"}

def execute_operator_action(command):
    """Exécute une action OperatorGPT"""
    operator = st.session_state.operator_gpt
    
    # Initialiser le navigateur si nécessaire
    if not operator.driver:
        if not operator.initialize_browser(headless=True):
            return False, "Impossible d'initialiser le navigateur"
    
    cmd_type = command.get("type")
    
    try:
        if cmd_type == "search":
            success, results = operator.execute_search(command["engine"], command["query"])
            if success:
                return True, {"action": "search", "results": results}
        
        elif cmd_type == "navigate":
            success, msg = operator.navigate_to(command["url"])
            if success:
                content = operator.get_page_content()
                screenshot_success, screenshot_path = operator.take_screenshot()
                return True, {"action": "navigate", "content": content[:1000], "screenshot": screenshot_path if screenshot_success else None}
        
        elif cmd_type == "screenshot":
            success, screenshot_path = operator.take_screenshot()
            if success:
                return True, {"action": "screenshot", "path": screenshot_path}
        
        return False, "Action non reconnue"
    
    except Exception as e:
        return False, f"Erreur exécution: {e}"

def format_operator_results(results):
    """Formate les résultats OperatorGPT pour le prompt"""
    if not results:
        return ""
    
    action = results.get("action")
    formatted = f"\n[BROWSER_ACTION] Action OperatorGPT exécutée: {action}\n"
    
    if action == "search":
        formatted += "Résultats de recherche:\n"
        for i, result in enumerate(results.get("results", []), 1):
            formatted += f"{i}. {result.get('title')}\n   {result.get('snippet', '')}\n   {result.get('link', result.get('url', ''))}\n\n"
    
    elif action == "navigate":
        formatted += f"Contenu de la page:\n{results.get('content', 'N/A')}\n"
        if results.get("screenshot"):
            formatted += f"Screenshot disponible: {results['screenshot']}\n"
    
    elif action == "screenshot":
        formatted += f"Screenshot sauvegardé: {results.get('path')}\n"
    
    return formatted

# -------------------------
# AI functions avec OperatorGPT
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
    show_vision_ai_thinking(placeholder)
    time.sleep(0.5)
    
    full_text = ""
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "▋")
        time.sleep(0.02)
    placeholder.markdown(full_text)

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

# -------------------------
# Interface principale
# -------------------------
st.title("🤖 Vision AI Chat + OperatorGPT")
st.caption("IA avec vision, édition d'images et contrôle de navigateur autonome")

# [Garder toute la sidebar d'authentification existante]

# -------------------------
# Nouvelle interface avec tabs
# -------------------------
tab1, tab2, tab3 = st.tabs(["💬 Chat Normal", "🎨 Mode Éditeur", "🌐 OperatorGPT"])

with tab1:
    st.write("Mode chat avec analyse d'images et recherche web")
    # [Garder le code existant du tab chat]

with tab2:
    st.write("Mode éditeur avec Qwen-Image-Edit")
    # [Garder le code existant du tab éditeur]

with tab3:
    st.write("🤖 Agent autonome pour le contrôle de navigateur")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Commandes OperatorGPT")
        
        operator_input = st.text_area(
            "Donnez une instruction en langage naturel:",
            placeholder="Ex: Cherche sur Google 'IA 2025'\nOuvre YouTube et cherche 'tutorial Python'\nVa sur example.com et prends un screenshot",
            height=100
        )
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("🚀 Exécuter", type="primary"):
                if operator_input.strip():
                    with st.spinner("OperatorGPT en action..."):
                        # Parser la commande
                        command = parse_operator_command(operator_input)
                        
                        if command["type"] != "unknown":
                            # Exécuter
                            success, results = execute_operator_action(command)
                            
                            if success:
                                st.success("Action terminée!")
                                
                                # Afficher les résultats
                                if results.get("action") == "search":
                                    st.subheader("Résultats de recherche:")
                                    for r in results.get("results", []):
                                        with st.expander(r.get("title", "Résultat")):
                                            st.write(r.get("snippet", r.get("url", "")))
                                            if r.get("link"):
                                                st.markdown(f"[Lien]({r['link']})")
                                
                                elif results.get("action") == "navigate":
                                    st.subheader("Contenu de la page:")
                                    st.text_area("Extrait:", results.get("content", ""), height=200)
                                    if results.get("screenshot"):
                                        st.image(results["screenshot"], caption="Screenshot")
                                
                                elif results.get("action") == "screenshot":
                                    st.image(results.get("path"), caption="Screenshot")
                                
                                # Sauvegarder dans la conversation si connecté
                                if st.session_state.conversation:
                                    formatted_results = format_operator_results(results)
                                    # [Ajouter à la DB et messages_memory]
                            else:
                                st.error(f"Erreur: {results}")
                        else:
                            st.warning("Commande non reconnue. Essayez d'être plus explicite.")
        
        with col_btn2:
            if st.button("📸 Screenshot"):
                operator = st.session_state.operator_gpt
                if not operator.driver:
                    operator.initialize_browser()
                success, path = operator.take_screenshot()
                if success:
                    st.image(path)
        
        with col_btn3:
            if st.button("🔴 Fermer navigateur"):
                st.session_state.operator_gpt.close_browser()
                st.info("Navigateur fermé")
    
    with col2:
        st.subheader("Exemples de commandes")
        
        examples = [
            "Cherche sur Google 'Fantastic Four 2025'",
            "Ouvre YouTube et cherche 'AI tutorial'",
            "Va sur www.example.com",
            "Prends un screenshot de la page actuelle",
            "Recherche sur Google 'météo Paris'",
            "Navigue vers https://www.wikipedia.org"
        ]
        
        for ex in examples:
            if st.button(f"📝 {ex}", key=f"ex_{ex[:20]}"):
                st.session_state.operator_example = ex
        
        st.markdown("---")
        st.subheader("Historique des actions")
        if st.session_state.operator_gpt.action_history:
            for action in st.session_state.operator_gpt.action_history[-10:]:
                st.text(f"• {action}")
        else:
            st.info("Aucune action encore")

# -------------------------
# Traitement chat avec intégration OperatorGPT
# -------------------------
# [Dans votre section de traitement du chat existant, ajouter:]

# Après la détection de recherche web, ajouter:
if detect_operator_intent(user_input):
    with st.spinner("🤖 OperatorGPT analyse la demande..."):
        command = parse_operator_command(user_input)
        
        if command["type"] != "unknown":
            success, results = execute_operator_action(command)
            
            if success:
                operator_results_text = format_operator_results(results)
                prompt += f"{operator_results_text}\n\n"

# -------------------------
# Footer mis à jour
# -------------------------
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.write("**Vision AI:**")
    st.write("- Analyse d'images")
    st.write("- Édition Qwen")
    st.write("- Mémoire éditions")

with col2:
    st.write("**Chat:**")
    st.write("- Conversations")
    st.write("- Contexte")
    st.write("- Multi-modal")

with col3:
    st.write("**Web:**")
    st.write("- Google Search")
    st.write("- YouTube")
    st.write("- Wikipedia")

with col4:
    st.write("**OperatorGPT:**")
    st.write("- Navigation auto")
    st.write("- Scraping")
    st.write("- Workflows")

# -------------------------
# Guide OperatorGPT
# -------------------------
with st.expander("📚 Guide OperatorGPT"):
    st.markdown("""
    ### 🤖 OperatorGPT - Agent Autonome
    
    **Qu'est-ce que OperatorGPT ?**
    OperatorGPT est un agent autonome qui contrôle un navigateur en temps réel pour exécuter des tâches complexes.
    
    **Capacités principales:**
    - 🌐 Navigation automatique sur le web
    - 🔍 Recherche et extraction de données
    - 📝 Remplissage de formulaires
    - 🖱️ Clics et interactions avec les pages
    - 📸 Captures d'écran
    - 🔄 Workflows multi-étapes
    - 📊 Scraping de contenu
    
    **Exemples d'utilisation:**
    
    1. **Recherche intelligente:**
       - "Cherche sur Google les dernières actualités IA"
       - "Trouve des vidéos YouTube sur Python"
    
    2. **Navigation:**
       - "Va sur example.com et lis le contenu"
       - "Ouvre Wikipedia et cherche Einstein"
    
    3. **Automatisation:**
       - "Cherche un vol Paris-New York"
       - "Compare les prix sur Amazon"
       - "Récupère les horaires de cinéma"
    
    4. **Capture:**
       - "Prends un screenshot de la page actuelle"
       - "Capture la page d'accueil de Google"
    
    **Comment ça marche ?**
    1. Vous donnez une instruction en langage naturel
    2. OperatorGPT analyse et décompose la tâche
    3. Le navigateur exécute les actions séquentiellement
    4. Les résultats sont présentés et sauvegardés
    
    **Workflows personnalisés:**
    Vous pouvez créer des workflows complexes en JSON:
    ```json
    [
        {"action": "navigate", "params": {"url": "https://example.com"}},
        {"action": "fill", "params": {"selector": "#search", "text": "query"}},
        {"action": "click", "params": {"selector": "#submit"}},
        {"action": "wait", "params": {"seconds": 3}},
        {"action": "screenshot", "params": {"filename": "result.png"}}
    ]
    ```
    
    **Sécurité:**
    - Le navigateur fonctionne en mode headless (sans interface)
    - Toutes les actions sont enregistrées dans l'historique
    - Pas d'accès aux données sensibles sans autorisation
    """)

# -------------------------
# Workflow Builder
# -------------------------
with st.expander("⚙️ Workflow Builder - Créer des automatisations"):
    st.subheader("Créateur de workflow personnalisé")
    
    workflow_name = st.text_input("Nom du workflow:", "Mon workflow")
    
    num_steps = st.number_input("Nombre d'étapes:", min_value=1, max_value=10, value=3)
    
    workflow_steps = []
    
    for i in range(num_steps):
        st.markdown(f"**Étape {i+1}**")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            action_type = st.selectbox(
                "Action:",
                ["navigate", "click", "fill", "wait", "screenshot", "extract"],
                key=f"action_{i}"
            )
        
        with col2:
            if action_type == "navigate":
                url = st.text_input("URL:", key=f"url_{i}")
                workflow_steps.append({"action": "navigate", "params": {"url": url}})
            
            elif action_type == "click":
                selector = st.text_input("Sélecteur CSS:", key=f"selector_{i}")
                workflow_steps.append({"action": "click", "params": {"selector": selector}})
            
            elif action_type == "fill":
                selector = st.text_input("Sélecteur:", key=f"fill_sel_{i}")
                text = st.text_input("Texte:", key=f"fill_text_{i}")
                workflow_steps.append({"action": "fill", "params": {"selector": selector, "text": text}})
            
            elif action_type == "wait":
                seconds = st.number_input("Secondes:", min_value=1, max_value=30, value=2, key=f"wait_{i}")
                workflow_steps.append({"action": "wait", "params": {"seconds": seconds}})
            
            elif action_type == "screenshot":
                filename = st.text_input("Nom fichier:", key=f"screenshot_{i}")
                workflow_steps.append({"action": "screenshot", "params": {"filename": filename}})
            
            elif action_type == "extract":
                st.text("Configuration extraction (JSON):")
                extract_config = st.text_area("Sélecteurs:", key=f"extract_{i}")
                workflow_steps.append({"action": "extract", "params": {"selectors": {}}})
        
        is_critical = st.checkbox("Étape critique (arrêter si échec)", key=f"critical_{i}")
        if is_critical:
            workflow_steps[i]["critical"] = True
    
    if st.button("🚀 Exécuter le workflow"):
        if workflow_steps:
            with st.spinner("Exécution du workflow..."):
                operator = st.session_state.operator_gpt
                
                if not operator.driver:
                    operator.initialize_browser()
                
                results = operator.execute_workflow(workflow_steps)
                
                st.subheader("Résultats du workflow:")
                for result in results:
                    status = "✅" if result["success"] else "❌"
                    st.write(f"{status} Étape {result['step']}: {result['action']} - {result['message']}")
    
    st.markdown("---")
    st.json(workflow_steps)

# -------------------------
# Statistiques OperatorGPT
# -------------------------
with st.expander("📊 Statistiques OperatorGPT"):
    operator = st.session_state.operator_gpt
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Actions totales", len(operator.action_history))
    
    with col2:
        browser_status = "🟢 Actif" if operator.driver else "🔴 Inactif"
        st.metric("Navigateur", browser_status)
    
    with col3:
        screenshots = len([f for f in os.listdir(BROWSER_SCREENSHOTS_DIR) if f.endswith('.png')])
        st.metric("Screenshots", screenshots)
    
    st.markdown("**Historique complet des actions:**")
    if operator.action_history:
        history_df = pd.DataFrame({
            "Action": operator.action_history,
            "Horodatage": [f"{i+1}" for i in range(len(operator.action_history))]
        })
        st.dataframe(history_df, use_container_width=True)
    else:
        st.info("Aucune action encore effectuée")

# -------------------------
# Galerie de screenshots
# -------------------------
with st.expander("🖼️ Galerie de screenshots"):
    screenshots = [f for f in os.listdir(BROWSER_SCREENSHOTS_DIR) if f.endswith('.png')]
    
    if screenshots:
        cols = st.columns(3)
        for i, screenshot in enumerate(screenshots[-9:]):  # Derniers 9 screenshots
            with cols[i % 3]:
                img_path = os.path.join(BROWSER_SCREENSHOTS_DIR, screenshot)
                st.image(img_path, caption=screenshot, use_column_width=True)
                
                if st.button("🗑️", key=f"del_{screenshot}"):
                    os.remove(img_path)
                    st.rerun()
    else:
        st.info("Aucun screenshot disponible")

# -------------------------
# Configuration OperatorGPT
# -------------------------
with st.expander("⚙️ Configuration OperatorGPT"):
    st.markdown("""
    ### Configuration du navigateur
    
    **Installation requise:**
    ```bash
    pip install selenium
    pip install webdriver-manager
    ```
    
    **Pour Streamlit Cloud:**
    Ajoutez dans `packages.txt`:
    ```
    chromium-chromedriver
    chromium
    ```
    
    **Variables d'environnement:**
    ```
    CHROME_BIN=/usr/bin/chromium
    CHROMEDRIVER_PATH=/usr/bin/chromedriver
    ```
    
    **Mode headless:**
    - Par défaut: navigateur invisible (headless=True)
    - Pour déboguer: headless=False (nécessite display)
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Réinitialiser navigateur"):
            st.session_state.operator_gpt.close_browser()
            if st.session_state.operator_gpt.initialize_browser():
                st.success("Navigateur réinitialisé")
    
    with col2:
        if st.button("🧹 Nettoyer l'historique"):
            st.session_state.operator_gpt.action_history = []
            st.success("Historique nettoyé")

# -------------------------
# Intégration complète dans le chat
# -------------------------
# Modification de la section de traitement du chat existant

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
    
    # Traitement image existant
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
        
        # Construction du prompt enrichi
        prompt = f"{SYSTEM_PROMPT}\n\n"
        
        # Date/heure
        datetime_info = format_datetime_for_prompt()
        prompt += f"{datetime_info}\n\n"
        
        # Détection OperatorGPT AVANT la recherche web
        operator_results_text = ""
        if detect_operator_intent(user_input):
            with st.spinner("🤖 OperatorGPT en action..."):
                command = parse_operator_command(user_input)
                
                if command["type"] != "unknown":
                    success, results = execute_operator_action(command)
                    
                    if success:
                        operator_results_text = format_operator_results(results)
                        st.success("✅ Action OperatorGPT terminée")
                        
                        # Afficher un aperçu des résultats
                        with st.expander("Voir les résultats OperatorGPT"):
                            if results.get("action") == "screenshot" and results.get("path"):
                                st.image(results["path"])
                            elif results.get("action") == "navigate" and results.get("screenshot"):
                                st.image(results["screenshot"])
                            st.json(results)
        
        if operator_results_text:
            prompt += f"{operator_results_text}\n\n"
        
        # Recherche web (si pas d'action OperatorGPT)
        if not operator_results_text:
            search_type, search_query = detect_search_intent(user_input)
            if search_type and search_query:
                with st.spinner(f"🔍 Recherche {search_type}..."):
                    web_results = format_web_search_for_prompt(search_query, search_type)
                    prompt += f"{web_results}\n\n"
        
        # Contexte édition
        edit_context = get_editing_context_from_conversation()
        if edit_context:
            prompt += f"[EDIT_CONTEXT] {edit_context}\n\n"
        
        prompt += f"\nUtilisateur: {message_content}"
        
        # Réponse AI
        with st.chat_message("assistant"):
            placeholder = st.empty()
            
            response = get_ai_response(prompt)
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
# Sidebar OperatorGPT
# -------------------------
if st.session_state.user["id"] != "guest":
    with st.sidebar.expander("🤖 OperatorGPT Quick Actions"):
        quick_action = st.selectbox(
            "Action rapide:",
            [
                "Aucune",
                "Google Search",
                "YouTube Search",
                "Screenshot",
                "Navigate to URL"
            ]
        )
        
        if quick_action == "Google Search":
            query = st.text_input("Recherche:", key="quick_google")
            if st.button("Chercher") and query:
                with st.spinner("Recherche..."):
                    operator = st.session_state.operator_gpt
                    if not operator.driver:
                        operator.initialize_browser()
                    success, results = operator.execute_search("google", query)
                    if success:
                        st.success(f"{len(results)} résultats")
        
        elif quick_action == "YouTube Search":
            query = st.text_input("Vidéo:", key="quick_youtube")
            if st.button("Chercher") and query:
                with st.spinner("Recherche..."):
                    operator = st.session_state.operator_gpt
                    if not operator.driver:
                        operator.initialize_browser()
                    success, results = operator.execute_search("youtube", query)
                    if success:
                        st.success(f"{len(results)} vidéos")
        
        elif quick_action == "Screenshot":
            if st.button("Capturer"):
                operator = st.session_state.operator_gpt
                if operator.driver:
                    success, path = operator.take_screenshot()
                    if success:
                        st.image(path)
                else:
                    st.warning("Navigateur non initialisé")
        
        elif quick_action == "Navigate to URL":
            url = st.text_input("URL:", key="quick_url")
            if st.button("Naviguer") and url:
                operator = st.session_state.operator_gpt
                if not operator.driver:
                    operator.initialize_browser()
                success, msg = operator.navigate_to(url)
                if success:
                    st.success(msg)

# -------------------------
# Cleanup au démarrage
# -------------------------
def cleanup_on_startup():
    """Nettoie les ressources au démarrage"""
    # Fermer tout navigateur zombie
    if st.session_state.operator_gpt.driver:
        try:
            st.session_state.operator_gpt.close_browser()
        except:
            pass
    
    # Nettoyer vieux screenshots (plus de 24h)
    try:
        current_time = time.time()
        for filename in os.listdir(BROWSER_SCREENSHOTS_DIR):
            filepath = os.path.join(BROWSER_SCREENSHOTS_DIR, filename)
            if os.path.isfile(filepath):
                if current_time - os.path.getctime(filepath) > 86400:  # 24h
                    os.remove(filepath)
    except:
        pass

# Exécuter au démarrage
if "cleanup_done" not in st.session_state:
    cleanup_on_startup()
    st.session_state.cleanup_done = True

# -------------------------
# Footer final
# -------------------------
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p><strong>Vision AI Chat + OperatorGPT</strong></p>
    <p>Créé par Pepe Musafiri | Powered by Meta AI, Qwen, BLIP, Selenium</p>
    <p>🤖 Agent autonome avec vision, édition et contrôle de navigateur</p>
</div>
""", unsafe_allow_html=True)
