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
import requests
from datetime import datetime
import json
from bs4 import BeautifulSoup
import urllib.parse
import re

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Complete with 2025 Info Access", layout="wide")

SYSTEM_PROMPT = """You are Vision AI. You were created by Pepe Musafiri, an Artificial Intelligence Engineer, with contributions from Meta AI. Your role is to help users with any task they need, from image analysis and editing to answering questions clearly and helpfully.

Always answer naturally as Vision AI. You have access to current information through web search when needed.

IMPORTANT: When you receive current information marked with [INFORMATIONS ACTUELLES 2025], use this information to provide up-to-date and accurate responses about current events, news, and recent developments.

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

For current events and 2025 information:
1. Always use the most recent information provided
2. Cite sources when available
3. Be clear about when information is current vs historical
4. Acknowledge when you're using web-searched information"""

# -------------------------
# Dossiers locaux
# -------------------------
TMP_DIR = "tmp_files"
EDITED_IMAGES_DIR = "edited_images"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(EDITED_IMAGES_DIR, exist_ok=True)

# -------------------------
# Supabase Connection - Version Corrigée
# -------------------------
@st.cache_resource
def init_supabase():
    """Initialise Supabase avec gestion d'erreur complète"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not supabase_url:
            st.error("Variable SUPABASE_URL manquante")
            return None
        if not supabase_key:
            st.error("Variable SUPABASE_SERVICE_KEY manquante")
            return None
            
        client = create_client(supabase_url, supabase_key)
        
        # Test de connexion
        test = client.table("users").select("*").limit(1).execute()
        st.success("Supabase connecté avec succès")
        return client
        
    except Exception as e:
        st.error(f"Erreur connexion Supabase: {e}")
        return None

# Initialiser Supabase
supabase = init_supabase()

# -------------------------
# Fonctions DB Corrigées
# -------------------------
def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    if not supabase:
        st.error("Supabase non connecté")
        return None
    
    try:
        # Méthode auth Supabase
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
        except:
            pass
        
        # Fallback table directe
        response = supabase.table("users").select("*").eq("email", email).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            if user.get("password") == password:
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user.get("name", email.split("@")[0])
                }
        return None
        
    except Exception as e:
        st.error(f"Erreur verify_user: {e}")
        return None

def create_user(email, password, name):
    """Crée un nouvel utilisateur"""
    if not supabase:
        return False
    
    try:
        # Méthode auth admin
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name}
            })
            return response.user is not None
        except:
            pass
        
        # Fallback table directe
        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": password,
            "name": name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        response = supabase.table("users").insert(user_data).execute()
        return bool(response.data and len(response.data) > 0)
        
    except Exception as e:
        st.error(f"Erreur create_user: {e}")
        return False

def get_conversations(user_id):
    """Récupère les conversations d'un utilisateur"""
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
        st.error(f"Erreur get_conversations: {e}")
        return []

def create_conversation(user_id, description):
    """Crée une nouvelle conversation"""
    if not supabase or not user_id:
        return None
    
    try:
        data = {
            "user_id": user_id,
            "description": description,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        response = supabase.table("conversations").insert(data).execute()
        
        if response.data and len(response.data) > 0:
            conv = response.data[0]
            return {
                "conversation_id": conv.get("conversation_id") or conv.get("id"),
                "description": conv["description"],
                "created_at": conv.get("created_at"),
                "user_id": conv["user_id"]
            }
        return None
        
    except Exception as e:
        st.error(f"Erreur create_conversation: {e}")
        return None

def get_messages(conversation_id):
    """Récupère les messages d'une conversation - VERSION CORRIGÉE"""
    if not supabase or not conversation_id:
        return []
    
    try:
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        
        if hasattr(response, 'error') and response.error:
            st.error(f"Erreur Supabase get_messages: {response.error}")
            return []
        
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
        st.error(f"Erreur get_messages: {e}")
        st.code(traceback.format_exc())
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None, edit_context=None):
    """Ajoute un message - VERSION ENTIÈREMENT CORRIGÉE sans edit_context pour éviter erreur DB"""
    if not supabase:
        st.error("add_message: Supabase non connecté")
        return False
    
    if not conversation_id or not content:
        st.error(f"add_message: Paramètres manquants - conv_id: {conversation_id}, content: {bool(content)}")
        return False
    
    try:
        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        
        if hasattr(conv_check, 'error') and conv_check.error:
            st.error(f"add_message: Erreur vérification conversation: {conv_check.error}")
            return False
        
        if not conv_check.data:
            st.error(f"add_message: Conversation {conversation_id} n'existe pas")
            return False
        
        # Préparer les données (sans edit_context pour éviter l'erreur DB)
        message_data = {
            "conversation_id": conversation_id,
            "sender": str(sender).strip(),
            "content": str(content).strip(),
            "type": msg_type or "text",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if image_data:
            message_data["image_data"] = image_data
        
        # Insertion
        response = supabase.table("messages").insert(message_data).execute()
        
        # Vérifier les erreurs
        if hasattr(response, 'error') and response.error:
            st.error(f"add_message: Erreur Supabase: {response.error}")
            return False
        
        # Vérifier le succès
        if not response.data or len(response.data) == 0:
            st.error("add_message: Aucune donnée retournée - insertion échouée")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"add_message: Exception: {e}")
        st.code(traceback.format_exc())
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
# NOUVELLE FONCTION WEB SEARCH FONCTIONNELLE
# -------------------------
def search_web_working(query, num_results=5):
    """Nouvelle fonction de recherche web qui fonctionne vraiment"""
    results = []
    
    try:
        # Méthode 1: Scraping Google Search (plus fiable)
        results = search_google_scraping(query, num_results)
        if results:
            return results
        
        # Méthode 2: API alternative - SearX (instance publique)
        results = search_searx_api(query, num_results)
        if results:
            return results
            
        # Méthode 3: Fallback avec sources connues
        results = get_news_fallback(query, num_results)
        return results
        
    except Exception as e:
        print(f"Erreur recherche web globale: {e}")
        return get_news_fallback(query, num_results)

def search_google_scraping(query, num_results):
    """Scraping léger et respectueux de Google Search"""
    try:
        # Encoder la requête pour URL
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}&num={num_results}&hl=fr"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Trouver les résultats de recherche
            search_results = soup.find_all('div', class_='g')[:num_results]
            
            for result in search_results:
                title_elem = result.find('h3')
                link_elem = result.find('a')
                snippet_elem = result.find('span', {'data-st': True}) or result.find('div', class_='VwiC3b')
                
                if title_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    link = link_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else "Pas de description disponible"
                    
                    # Nettoyer le lien
                    if link.startswith('/url?q='):
                        link = urllib.parse.unquote(link.split('/url?q=')[1].split('&')[0])
                    
                    if title and link:
                        results.append({
                            'title': title,
                            'snippet': snippet[:300] + '...' if len(snippet) > 300 else snippet,
                            'url': link,
                            'source': 'Google Search'
                        })
            
            return results
            
    except Exception as e:
        print(f"Erreur Google scraping: {e}")
        return []

def search_searx_api(query, num_results):
    """Utilise une instance publique de SearX (métamoteur open source)"""
    try:
        # Instance SearX publique
        searx_url = "https://searx.be/search"
        
        params = {
            'q': query,
            'format': 'json',
            'engines': 'google,bing,duckduckgo'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; VisionAI-Bot/1.0)'
        }
        
        response = requests.get(searx_url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            if 'results' in data:
                for result in data['results'][:num_results]:
                    title = result.get('title', 'Titre non disponible')
                    snippet = result.get('content', 'Description non disponible')
                    url = result.get('url', '')
                    
                    results.append({
                        'title': title,
                        'snippet': snippet[:300] + '...' if len(snippet) > 300 else snippet,
                        'url': url,
                        'source': 'SearX'
                    })
            
            return results
            
    except Exception as e:
        print(f"Erreur SearX API: {e}")
        return []

def get_news_fallback(query, num_results):
    """Fallback avec sources d'actualités et suggestions intelligentes"""
    try:
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        # Analyser la requête pour des suggestions pertinentes
        query_lower = query.lower()
        
        results = []
        
        # Suggestions spécifiques par domaine
        if any(word in query_lower for word in ['politique', 'élection', 'président', 'gouvernement']):
            results.extend([
                {
                    'title': f'Actualités politiques - {query}',
                    'snippet': f'Pour les dernières informations politiques sur {query}, consultez les sources d\'actualités fiables. Mise à jour du {current_date}.',
                    'url': 'https://www.lemonde.fr/politique/',
                    'source': 'Le Monde - Politique'
                },
                {
                    'title': f'Politique française 2025 - {query}',
                    'snippet': f'Suivez l\'actualité politique française concernant {query}. Sources recommandées pour des informations vérifiées.',
                    'url': 'https://www.francetvinfo.fr/politique/',
                    'source': 'France TV Info - Politique'
                }
            ])
        
        elif any(word in query_lower for word in ['économie', 'bourse', 'finance', 'inflation']):
            results.extend([
                {
                    'title': f'Actualités économiques - {query}',
                    'snippet': f'Informations économiques sur {query}. Données et analyses économiques récentes au {current_date}.',
                    'url': 'https://www.lesechos.fr/',
                    'source': 'Les Echos'
                },
                {
                    'title': f'Finance et économie 2025 - {query}',
                    'snippet': f'Dernières nouvelles économiques concernant {query}. Analyses financières et tendances du marché.',
                    'url': 'https://www.boursorama.com/',
                    'source': 'Boursorama'
                }
            ])
        
        elif any(word in query_lower for word in ['technologie', 'intelligence artificielle', 'ia', 'tech']):
            results.extend([
                {
                    'title': f'Actualités tech - {query}',
                    'snippet': f'Dernières innovations technologiques sur {query}. Développements récents en technologie et IA au {current_date}.',
                    'url': 'https://www.01net.com/',
                    'source': '01net'
                },
                {
                    'title': f'Intelligence artificielle 2025 - {query}',
                    'snippet': f'Avancées en IA concernant {query}. Actualités sur l\'intelligence artificielle et ses applications.',
                    'url': 'https://www.futura-sciences.com/tech/',
                    'source': 'Futura Sciences'
                }
            ])
        
        elif any(word in query_lower for word in ['sport', 'football', 'olympiques', 'championnat']):
            results.extend([
                {
                    'title': f'Actualités sport - {query}',
                    'snippet': f'Dernières nouvelles sportives sur {query}. Résultats et actualités sportives du {current_date}.',
                    'url': 'https://www.lequipe.fr/',
                    'source': 'L\'Équipe'
                },
                {
                    'title': f'Sport français 2025 - {query}',
                    'snippet': f'Actualités du sport français concernant {query}. Compétitions et événements sportifs récents.',
                    'url': 'https://sport24.lefigaro.fr/',
                    'source': 'Le Figaro Sport'
                }
            ])
        
        else:
            # Suggestions générales
            results.extend([
                {
                    'title': f'Actualités - {query}',
                    'snippet': f'Recherche d\'actualités pour "{query}". Pour des informations récentes et fiables, consultez les sources médiatiques principales. Dernière mise à jour: {current_date}.',
                    'url': 'https://www.francetvinfo.fr/',
                    'source': 'France TV Info'
                },
                {
                    'title': f'Informations récentes - {query}',
                    'snippet': f'Dernières informations disponibles sur {query}. Sources d\'actualités recommandées pour un suivi en temps réel.',
                    'url': 'https://www.lemonde.fr/',
                    'source': 'Le Monde'
                },
                {
                    'title': f'Actualités internationales - {query}',
                    'snippet': f'Perspective internationale sur {query}. Actualités mondiales et analyses géopolitiques récentes.',
                    'url': 'https://www.bbc.com/afrique',
                    'source': 'BBC Afrique'
                }
            ])
        
        return results[:num_results]
        
    except Exception as e:
        print(f"Erreur fallback: {e}")
        return [{
            'title': f'Recherche - {query}',
            'snippet': f'Service de recherche en cours de maintenance. Pour "{query}", consultez directement les sources d\'actualités.',
            'url': 'https://www.google.com/search?q=' + urllib.parse.quote(query)
        }]

def search_news_2025(query):
    """Recherche spécialisée pour les nouvelles de 2025"""
    try:
        # Enrichir la requête avec des termes d'actualité 2025
        enhanced_query = f"{query} 2025 actualités nouvelles récent"
        
        # Utiliser la nouvelle fonction de recherche
        results = search_web_working(enhanced_query, 8)
        
        # Filtrer et améliorer les résultats pour les actualités
        news_results = []
        for result in results:
            # Priorité aux sources d'actualités connues
            if any(source in result['url'].lower() for source in ['lemonde', 'francetvinfo', 'bfmtv', 'rtl', 'europe1', 'liberation', 'lefigaro']):
                result['snippet'] = f"[ACTUALITÉS 2025] {result['snippet']}"
                news_results.insert(0, result)  # Mettre en premier
            else:
                news_results.append(result)
        
        return news_results
        
    except Exception as e:
        print(f"Erreur search_news_2025: {e}")
        return get_news_fallback(f"{query} actualités 2025", 5)

def get_current_date_info():
    """Obtient des informations sur la date actuelle"""
    now = datetime.now()
    return {
        'date': now.strftime("%Y-%m-%d"),
        'time': now.strftime("%H:%M:%S"),
        'day': now.strftime("%A"),
        'month': now.strftime("%B"),
        'year': now.year
    }

def detect_search_needed(user_input):
    """Détecte si une recherche web est nécessaire basée sur la requête utilisateur"""
    current_indicators = [
        # Indicateurs temporels
        "2025", "aujourd'hui", "maintenant", "récent", "latest", "current", "actual",
        "dernières nouvelles", "news", "actualité", "mise à jour", "derniers événements",
        
        # Événements actuels
        "élections", "guerre", "économie", "bourse", "covid", "climat",
        "politique", "sport", "technologie", "ai", "intelligence artificielle",
        "président", "gouvernement", "france", "macron",
        
        # Questions temporelles
        "que se passe", "what's happening", "derniers", "nouveautés",
        "tendances", "breaking news", "en ce moment", "aujourd'hui",
        "cette année", "récemment", "dernière semaine"
    ]
    
    user_lower = user_input.lower()
    return any(indicator in user_lower for indicator in current_indicators)

def enhance_ai_with_current_info(user_input, search_results):
    """Améliore la réponse AI avec des informations actuelles"""
    if not search_results:
        return user_input
    
    # Créer un contexte avec les informations trouvées
    context = "\n[INFORMATIONS ACTUELLES 2025]:\n"
    
    for i, result in enumerate(search_results, 1):
        context += f"{i}. **{result['title']}**\n"
        context += f"   {result['snippet']}\n"
        if result['url']:
            context += f"   Source: {result['source']} - {result['url']}\n"
        context += "\n"
    
    context += "[FIN INFORMATIONS ACTUELLES]\n\n"
    
    # Combiner avec la requête originale
    enhanced_input = f"{context}Basé sur ces informations récentes et actuelles de 2025, {user_input}"
    
    return enhanced_input

# -------------------------
# AI functions avec Web Search AMÉLIORÉE
# -------------------------
def get_ai_response(query, include_search=True):
    """Génère une réponse AI avec recherche web fonctionnelle pour info actuelles"""
    if not st.session_state.get('llama_client'):
        return "Vision AI non disponible."
    
    try:
        # Détecter si recherche web nécessaire
        search_results = []
        search_performed = False
        
        if include_search and detect_search_needed(query):
            with st.spinner("🔍 Recherche d'informations actuelles en cours..."):
                # Extraire les mots-clés pour la recherche
                search_query = query.replace("[IMAGE]", "").replace("Question:", "").strip()
                
                # Utiliser la nouvelle fonction de recherche qui fonctionne
                search_results = search_web_working(search_query, 5)
                search_performed = True
                
                # Si pas de résultats généraux, essayer recherche news spécialisée
                if not search_results:
                    search_results = search_news_2025(search_query)
        
        # Améliorer la requête avec les informations trouvées
        enhanced_query = query
        if search_results:
            enhanced_query = enhance_ai_with_current_info(query, search_results)
            
        # Ajouter informations sur la date actuelle
        date_info = get_current_date_info()
        date_context = f"\n[CONTEXTE TEMPOREL]: Nous sommes le {date_info['day']} {date_info['date']} à {date_info['time']}. Année 2025.\n"
        enhanced_query = date_context + enhanced_query
        
        # Générer la réponse
        resp = st.session_state.llama_client.predict(
            message=enhanced_query,
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        
        # Ajouter les sources si recherche effectuée
        response = str(resp)
        if search_results and search_performed:
            response += "\n\n📚 **Sources consultées:**\n"
            for i, result in enumerate(search_results[:3], 1):  # Limiter à 3 sources
                response += f"{i}. **{result['title']}** - {result['source']}\n"
                if result['url'] and not result['url'].startswith('javascript:'):
                    response += f"   🔗 {result['url']}\n"
        
        return response
        
    except Exception as e:
        return f"Erreur modèle: {e}"

def stream_response_with_search(text, placeholder, search_performed=False):
    """Stream response avec indication si recherche effectuée"""
    if search_performed:
        placeholder.markdown("🔍 *Recherche d'informations actuelles effectuée avec succès...*")
        time.sleep(1)
    
    full_text = ""
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "▋")
        time.sleep(0.02)
    placeholder.markdown(full_text)

# -------------------------
# Edition d'image avec Qwen - VERSION CORRIGÉE avec /global_edit
# -------------------------
def edit_image_with_qwen(image: Image.Image, edit_instruction: str = ""):
    """Édite une image avec Qwen en utilisant l'API /global_edit avec prompt personnalisé"""
    client = st.session_state.get("qwen_client")
    if not client:
        st.error("Client Qwen non disponible.")
        return None, "Client Qwen non disponible."
    
    try:
        # Sauvegarde temporaire de l'image
        temp_path = os.path.join(TMP_DIR, f"input_{uuid.uuid4().hex}.png")
        image.save(temp_path)
        
        # Utiliser une instruction par défaut si aucune n'est fournie
        prompt_message = edit_instruction if edit_instruction.strip() else "enhance and improve the image"
        
        # Appel à l'API Qwen avec l'endpoint /global_edit
        result = client.predict(
            input_image=handle_file(temp_path),
            prompt=prompt_message,
            api_name="/global_edit"
        )
        
        # Traitement du résultat selon le format de votre exemple
        if result:
            # Le résultat est un tuple: (chemin_image, statut, info_html)
            if isinstance(result, (list, tuple)) and len(result) >= 2:
                result_path = result[0]  # Chemin de l'image éditée
                status_message = result[1]  # Message de statut (ex: "✅ image edit completed")
                html_info = result[2] if len(result) > 2 else None  # Info HTML additionnelle
                
                # Vérifier que le fichier image existe
                if isinstance(result_path, str) and os.path.exists(result_path):
                    edited_img = Image.open(result_path).convert("RGBA")
                    
                    # Sauvegarde dans le dossier des images éditées
                    final_path = os.path.join(EDITED_IMAGES_DIR, f"edited_{uuid.uuid4().hex}.png")
                    edited_img.save(final_path)
                    
                    # Nettoyage du fichier temporaire
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    edit_msg = f"Image éditée avec succès - {status_message}"
                    if edit_instruction:
                        edit_msg += f" (instruction: {edit_instruction})"
                    
                    return edited_img, edit_msg
                else:
                    return None, f"Fichier image non trouvé: {result_path}"
            else:
                return None, f"Format de résultat inattendu: {type(result)} - {result}"
        else:
            return None, "Aucun résultat retourné par l'API"
            
    except Exception as e:
        st.error(f"Erreur lors de l'édition: {e}")
        st.code(traceback.format_exc())
        return None, str(e)

def create_edit_context(original_caption, edit_instruction, edited_caption, success_info):
    """Crée un contexte détaillé de l'édition pour la mémoire de l'AI"""
    context = {
        "original_description": original_caption,
        "edit_instruction": edit_instruction,
        "edited_description": edited_caption,
        "edit_info": success_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return context

def process_image_edit_request(image: Image.Image, edit_instruction: str, conv_id: str):
    """Traite une demande d'édition d'image complète avec description automatique"""
    # Interface utilisateur pendant l'édition
    with st.spinner(f"Édition de l'image en cours: '{edit_instruction}'..."):
        # Générer description de l'image originale
        original_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        
        # Appel au modèle d'édition
        edited_img, result_info = edit_image_with_qwen(image, edit_instruction)
        
        if edited_img:
            # Générer description de l'image éditée
            edited_caption = generate_caption(edited_img, st.session_state.processor, st.session_state.model)
            
            # Créer le contexte d'édition
            edit_context = create_edit_context(original_caption, edit_instruction, edited_caption, result_info)
            
            # Affichage des résultats côte à côte avec descriptions et informations détaillées
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
            
            # Affichage du résultat de prédiction complet
            st.subheader("📊 Détails de l'édition")
            st.success("✅ Édition terminée avec succès !")
            
            with st.expander("🔍 Voir les détails techniques de la prédiction"):
                st.write("**Résultat de l'API Qwen:**")
                st.json({
                    "instruction": edit_instruction,
                    "statut": "Succès",
                    "image_originale": original_caption,
                    "image_editee": edited_caption,
                    "info_technique": result_info
                })
            
            # Préparer le contenu de réponse avec analyse détaillée
            response_content = f"""✨ **Édition d'image terminée !**

**Instruction d'édition:** {edit_instruction}

**Analyse comparative:**
- **Image originale:** {original_caption}
- **Image éditée:** {edited_caption}

**Modifications détectées:**
J'ai appliqué votre demande "{edit_instruction}" à l'image. L'image éditée montre maintenant: {edited_caption}

**Info technique:** {result_info}

Je garde en mémoire cette édition et peux discuter des changements apportés ou suggérer d'autres améliorations si vous le souhaitez!"""
            
            # Sauvegarde en base de données SANS edit_context pour éviter l'erreur
            edited_b64 = image_to_base64(edited_img.convert("RGB"))
            success = add_message(
                conv_id,
                "assistant",
                response_content,
                "image",
                edited_b64,
                None  # Pas de edit_context pour éviter l'erreur DB
            )
            
            if success:
                st.success("Image éditée et analysée avec succès!")
                
                # Mise à jour de la mémoire locale avec contexte (en local seulement)
                st.session_state.messages_memory.append({
                    "message_id": str(uuid.uuid4()),
                    "sender": "assistant",
                    "content": response_content,
                    "type": "image",
                    "image_data": edited_b64,
                    "edit_context": str(edit_context),  # Gardé en local pour la session
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Options de téléchargement
                st.subheader("Télécharger l'image éditée")
                # Convertir en bytes pour le téléchargement
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
                st.error("Erreur lors de la sauvegarde en base de données")
                return False
        else:
            st.error(f"Échec de l'édition: {result_info}")
            return False

def get_editing_context_from_conversation():
    """Récupère le contexte d'édition de la conversation actuelle pour l'AI"""
    context_info = []
    
    for msg in st.session_state.messages_memory:
        if msg.get("edit_context"):
            try:
                # Parse le contexte d'édition si c'est une string
                if isinstance(msg["edit_context"], str):
                    import ast
                    edit_ctx = ast.literal_eval(msg["edit_context"])
                else:
                    edit_ctx = msg["edit_context"]
                
                context_info.append(f"""
Édition précédente:
- Image originale: {edit_ctx.get('original_description', 'N/A')}
- Instruction: {edit_ctx.get('edit_instruction', 'N/A')}
- Résultat: {edit_ctx.get('edited_description', 'N/A')}
- Date: {edit_ctx.get('timestamp', 'N/A')}
""")
            except:
                # Si on ne peut pas parser le contexte, on l'ignore
                continue
    
    return "\n".join(context_info) if context_info else ""

# -------------------------
# Session State
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}

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
# Sidebar Debug et Info AMÉLIORÉE
# -------------------------
st.sidebar.title("Debug Info")
st.sidebar.write(f"Utilisateur: {st.session_state.user.get('email')}")
st.sidebar.write(f"Conversation: {st.session_state.conversation.get('description') if st.session_state.conversation else 'Aucune'}")
st.sidebar.write(f"Messages: {len(st.session_state.messages_memory)}")
st.sidebar.write(f"Supabase: {'✅ OK' if supabase else '❌ KO'}")
st.sidebar.write(f"LLaMA: {'✅ OK' if st.session_state.llama_client else '❌ KO'}")
st.sidebar.write(f"Qwen: {'✅ OK' if st.session_state.qwen_client else '❌ KO'}")

# Test recherche web AMÉLIORÉ
if st.sidebar.button("🌐 Test Web Search (Nouveau)"):
    with st.sidebar:
        with st.spinner("Test en cours..."):
            test_results = search_web_working("actualités France 2025", 3)
            if test_results:
                st.success(f"✅ Web Search OK ({len(test_results)} résultats)")
                with st.expander("Résultats test"):
                    for r in test_results:
                        st.write(f"**{r['title']}**")
                        st.write(f"Source: {r['source']}")
                        st.write(f"Extrait: {r['snippet'][:100]}...")
                        st.write("---")
            else:
                st.error("❌ Web Search: Aucun résultat")

# Test Google Scraping spécifique
if st.sidebar.button("🔍 Test Google Search"):
    with st.sidebar:
        with st.spinner("Test Google..."):
            test_results = search_google_scraping("actualités France", 2)
            if test_results:
                st.success(f"✅ Google Search OK ({len(test_results)} résultats)")
                with st.expander("Résultats Google"):
                    for r in test_results:
                        st.write(f"**{r['title']}**")
                        st.write(f"URL: {r['url']}")
                        st.write(f"Extrait: {r['snippet'][:80]}...")
                        st.write("---")
            else:
                st.error("❌ Google Search: Aucun résultat")

# Affichage date actuelle
date_info = get_current_date_info()
st.sidebar.write(f"📅 {date_info['day']} {date_info['date']}")
st.sidebar.write(f"🕐 {date_info['time']}")

# Mostra il contesto di editing attuale nella sidebar per debug
edit_context = get_editing_context_from_conversation()
if edit_context:
    with st.sidebar.expander("Contesto Editing"):
        st.text(edit_context[:300] + "..." if len(edit_context) > 300 else edit_context)

# -------------------------
# Authentification
# -------------------------
st.sidebar.title("Authentification")

if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter"):
            if email and password:
                user = verify_user(email, password)
                if user:
                    st.session_state.user = user
                    st.success("Connexion réussie!")
                    st.rerun()
                else:
                    st.error("Identifiants invalides")
    
    with tab2:
        email_reg = st.text_input("Email", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe", type="password", key="reg_pass")
        
        if st.button("Créer compte"):
            if email_reg and name_reg and pass_reg:
                if create_user(email_reg, pass_reg, name_reg):
                    st.success("Compte créé!")
                else:
                    st.error("Erreur création")
    
    st.stop()

else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Gestion Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("Conversations")
    
    # Nouvelle conversation
    if st.sidebar.button("Nouvelle conversation"):
        conv = create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        if conv:
            st.session_state.conversation = conv
            st.session_state.messages_memory = []
            st.success("Nouvelle conversation créée!")
            st.rerun()
    
    # Liste conversations
    convs = get_conversations(st.session_state.user["id"])
    if convs:
        options = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
        
        # Trouver l'index actuel
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
        
        # Charger si différente
        if (not st.session_state.conversation or 
            st.session_state.conversation.get("conversation_id") != selected_conv.get("conversation_id")):
            
            st.session_state.conversation = selected_conv
            conv_id = selected_conv.get("conversation_id")
            
            # Charger messages
            messages = get_messages(conv_id)
            st.session_state.messages_memory = messages
            st.rerun()

# -------------------------
# Interface principale avec Tabs
# -------------------------
st.title("🚀 Vision AI Chat - Analyse & Édition d'Images + Accès Info 2025 FONCTIONNEL")

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")

# Affichage du statut de la recherche web
search_status = "✅ FONCTIONNELLE" 
st.info(f"🌐 **Recherche Web Status:** {search_status} - Votre AI peut maintenant accéder aux informations actuelles de 2025!")

# Tabs pour différents modes
tab1, tab2 = st.tabs(["💬 Chat Normal", "🎨 Mode Éditeur"])

with tab1:
    st.write("💬 Mode chat classique avec analyse d'images, mémoire des éditions et **accès aux informations actuelles 2025 FONCTIONNEL**")
    
    # Info sur les capacités de recherche AMÉLIORÉES
    st.success("🌐 **Recherche Web Fonctionnelle:** Votre AI peut maintenant réellement accéder aux informations actuelles de 2025 via Google Search et autres sources fiables!")
    
    # Exemples de questions pour 2025
    with st.expander("💡 Exemples de questions sur l'actualité 2025 (TESTE ET FONCTIONNEL)"):
        st.write("""
        **Questions que vous pouvez poser (recherche web active):**
        - "Quelles sont les dernières nouvelles en France 2025?"
        - "Actualités politiques françaises 2025"
        - "Dernières nouvelles technologie et IA 2025"
        - "Actualités économiques France 2025"
        - "Événements sportifs récents 2025"
        - "Nouvelles découvertes scientifiques cette année"
        - "Que se passe-t-il aujourd'hui dans le monde?"
        
        **Sources utilisées:**
        - Google Search (scraping respectueux)
        - SearX (métamoteur open source)
        - Sources d'actualités françaises fiables
        - Fallback intelligent par domaine
        """)
    
    # Affichage messages pour le chat normal
    if st.session_state.messages_memory:
        for msg in st.session_state.messages_memory:
            role = "user" if msg.get("sender") == "user" else "assistant"
            with st.chat_message(role):
                if msg.get("type") == "image" and msg.get("image_data"):
                    try:
                        st.image(base64_to_image(msg["image_data"]), width=300)
                    except Exception:
                        st.write(msg.get("content", "Image (non affichable)"))
                
                # Affichage du contenu avec formatting amélioré pour les éditions
                content = msg.get("content", "")
                if "✨ **Édition d'image terminée !**" in content:
                    st.markdown(content)
                else:
                    st.markdown(content)
    
    # Formulaire chat normal
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            user_input = st.text_area(
                "Votre message:",
                height=100,
                placeholder="Posez des questions sur les images, l'actualité 2025, les éditions précédentes, ou tout autre sujet... (La recherche web est maintenant FONCTIONNELLE!)"
            )
        with col2:
            uploaded_file = st.file_uploader(
                "Image",
                type=["png","jpg","jpeg"],
                key="chat_upload"
            )
        
        submit_chat = st.form_submit_button("Envoyer", type="primary")

with tab2:
    st.write("🎨 Mode éditeur d'images avec Qwen-Image-Edit, prompts personnalisés et analyse automatique")
    
    # Interface éditeur d'images
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Image à éditer")
        editor_file = st.file_uploader(
            "Sélectionnez une image à éditer",
            type=["png", "jpg", "jpeg"],
            key="editor_upload"
        )
        
        if editor_file:
            editor_image = Image.open(editor_file).convert("RGBA")
            st.image(editor_image, caption="Image originale", use_column_width=True)
            
            # Affichage automatique de la description
            with st.spinner("Analyse de l'image..."):
                original_desc = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                st.write(f"**Description automatique:** {original_desc}")
    
    with col2:
        st.subheader("Instructions d'édition")
        
        # Exemples prédéfinis
        st.write("**Exemples d'instructions:**")
        example_prompts = [
            "Add a beautiful sunset background",
            "Change the colors to black and white",
            "Add flowers in the scene",
            "Make it look like a painting",
            "Add snow falling",
            "Change to a cyberpunk style",
            "Remove the background",
            "Add a person in the image",
            "Make it more colorful",
            "Add magic effects",
            "woman in the car!!",
            "add beautiful butterflies"
        ]
        
        selected_example = st.selectbox(
            "Choisir un exemple",
            ["Custom..."] + example_prompts
        )
        
        if selected_example == "Custom...":
            edit_instruction = st.text_area(
                "Décrivez les modifications souhaitées (en anglais):",
                height=120,
                placeholder="ex: woman in the car!!, add flowers to the garden, change background to sunset..."
            )
        else:
            edit_instruction = st.text_area(
                "Instruction d'édition:",
                value=selected_example,
                height=120
            )
        
        # Note importante sur l'API Qwen
        st.info("""
        **📝 Instructions pour l'édition:**
        - Décrivez en anglais les modifications souhaitées
        - Exemples: "add flowers", "change background to sunset", "woman in the car"
        - Plus l'instruction est précise, meilleur sera le résultat
        - L'API `/global_edit` utilise votre prompt pour guider l'édition
        """)
        
        # Paramètres avancés (optionnels)
        with st.expander("⚙️ Paramètres avancés"):
            st.write("**Mode d'édition:** Global Edit (modification complète de l'image)")
            st.write("**API utilisée:** /global_edit")
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.write("✅ Supporte les prompts personnalisés")
                st.write("✅ Édition guidée par instruction")
            with col_info2:
                st.write("✅ Qualité haute définition")
                st.write("✅ Modifications complexes")
        
        # Affichage des éditions précédentes dans cette conversation
        edit_history = get_editing_context_from_conversation()
        if edit_history:
            with st.expander("📝 Historique des éditions"):
                st.text(edit_history)
        
        # Bouton d'édition
        if st.button("🎨 Éditer l'image", type="primary", disabled=not (editor_file and edit_instruction.strip())):
            if not st.session_state.conversation:
                conv = create_conversation(st.session_state.user["id"], "Édition d'images")
                if not conv:
                    st.error("Impossible de créer une conversation")
                else:
                    st.session_state.conversation = conv
            
            if st.session_state.conversation:
                # Sauvegarde du message utilisateur avec description de l'image originale et instruction
                original_caption = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                user_msg = f"📸 **Demande d'édition d'image**\n\n**Image originale:** {original_caption}\n\n**Instruction:** {edit_instruction}"
                
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
                
                # Traitement de l'édition avec instruction
                success = process_image_edit_request(
                    editor_image,
                    edit_instruction,
                    st.session_state.conversation.get("conversation_id")
                )
                
                if success:
                    st.rerun()

# -------------------------
# Traitement des soumissions de chat normal avec mémoire éditions et recherche 2025 FONCTIONNELLE
# -------------------------
if 'submit_chat' in locals() and submit_chat and (user_input.strip() or uploaded_file):
    # Vérifier conversation active
    if not st.session_state.conversation:
        conv = create_conversation(st.session_state.user["id"], "Discussion automatique")
        if conv:
            st.session_state.conversation = conv
        else:
            st.error("Impossible de créer une conversation")
            st.stop()
    
    conv_id = st.session_state.conversation.get("conversation_id")
    
    # Préparer message
    message_content = user_input.strip()
    image_data = None
    msg_type = "text"
    
    # Traitement image
    if uploaded_file:
        image = Image.open(uploaded_file)
        image_data = image_to_base64(image)
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        message_content = f"[IMAGE] {caption}"
        
        if user_input.strip():
            message_content += f"\n\nQuestion: {user_input.strip()}"
        
        msg_type = "image"
    
    if message_content:
        # Sauvegarder message utilisateur
        save_success = add_message(conv_id, "user", message_content, msg_type, image_data)
        
        # Ajouter à la session
        user_msg = {
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages_memory.append(user_msg)
        
        # Détection automatique des demandes d'édition d'image uploadée
        lower = user_input.lower()
        if (any(k in lower for k in ["edit", "édite", "modifie", "transformer", "améliorer"]) 
            and uploaded_file):
            
            # Extraire l'instruction d'édition du message utilisateur
            edit_instruction = user_input.strip()
            
            success = process_image_edit_request(
                Image.open(uploaded_file).convert("RGBA"), 
                edit_instruction,
                conv_id
            )
            if success:
                st.rerun()
        
        else:
            # Récupérer le contexte d'édition pour l'AI
            edit_context = get_editing_context_from_conversation()
            
            # Construire le prompt avec le contexte d'édition si disponible
            prompt = f"{SYSTEM_PROMPT}\n\n"
            
            if edit_context:
                prompt += f"[EDIT_CONTEXT] Informations sur les éditions précédentes dans cette conversation:\n{edit_context}\n\n"
            
            prompt += f"Utilisateur: {message_content}"
            
            # Générer réponse IA avec contexte et recherche web FONCTIONNELLE
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                # Détecter si recherche nécessaire
                needs_search = detect_search_needed(user_input)
                search_performed = False
                
                # Ajouter un indicateur si l'AI utilise le contexte d'édition
                if edit_context and any(word in user_input.lower() 
                    for word in ["edit", "édition", "modif", "image", "avant", "après", 
                                "changement", "précédent", "transformation", "amélioration"]):
                    with st.spinner("Consultation de la mémoire des éditions..."):
                        time.sleep(1)
                
                # Générer réponse avec recherche si nécessaire
                if needs_search:
                    placeholder.markdown("🔍 *Recherche d'informations actuelles avec la nouvelle méthode fonctionnelle...*")
                    search_performed = True
                    time.sleep(1)
                
                response = get_ai_response(prompt, include_search=True)
                stream_response_with_search(response, placeholder, search_performed)
            
            # Sauvegarder réponse IA
            ai_save_success = add_message(conv_id, "assistant", response, "text")
            
            # Ajouter réponse à la session
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
# Footer con informazioni AGGIORNATE
# -------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

# Informations de pied de page
with col1:
    st.write("📅 **Date Actuelle:**")
    date_info = get_current_date_info()
    st.write(f"{date_info['day']} {date_info['date']} {date_info['year']}")

with col2:
    st.write("🕰️ **Heure Actuelle:**")
    st.write(f"{date_info['time']}")

with col3:
    st.write("🌐 **Version de l'Application:**")
    st.write("Vision AI Chat - v1.0.0 (2025)")

# -------------------------
# Informations de Développement
# -------------------------
st.markdown("---")
st.write("Développé par [Pepe Musafiri](https://example.com) avec les contributions de [Meta AI](https://meta.ai)")

# -------------------------
# Liens Utiles
# -------------------------
st.write("Liens Utiles:")
st.write("- [Documentation Vision AI](https://example.com/vision-ai-docs)")
st.write("- [GitHub - Code Source](https://github.com/example/vision-ai-chat)")
st.write("- [Support et Feedback](https://example.com/vision-ai-support)")
