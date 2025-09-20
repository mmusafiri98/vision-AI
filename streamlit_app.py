import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import os
from supabase import create_client

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Fixed", layout="wide")

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
        import uuid
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
        st.write(f"Chargement messages pour: {conversation_id}")
        
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
        
        if hasattr(response, 'error') and response.error:
            st.error(f"Erreur Supabase get_messages: {response.error}")
            return []
            
        if not response.data:
            st.info(f"Aucun message trouvé pour {conversation_id}")
            return []
        
        messages = []
        for msg in response.data:
            messages.append({
                "message_id": msg.get("message_id") or msg.get("id"),
                "sender": msg.get("sender", "unknown"),
                "content": msg.get("content", ""),
                "created_at": msg.get("created_at"),
                "type": msg.get("type", "text"),
                "image_data": msg.get("image_data")
            })
        
        st.success(f"{len(messages)} messages chargés")
        return messages
        
    except Exception as e:
        st.error(f"Erreur get_messages: {e}")
        import traceback
        st.code(traceback.format_exc())
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None):
    """Ajoute un message - VERSION ENTIÈREMENT CORRIGÉE"""
    if not supabase:
        st.error("add_message: Supabase non connecté")
        return False
        
    if not conversation_id or not content:
        st.error(f"add_message: Paramètres manquants - conv_id: {conversation_id}, content: {bool(content)}")
        return False
    
    try:
        st.info(f"add_message: Début sauvegarde - {sender} dans {conversation_id}")
        
        # Vérifier que la conversation existe
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        
        if hasattr(conv_check, 'error') and conv_check.error:
            st.error(f"add_message: Erreur vérification conversation: {conv_check.error}")
            return False
            
        if not conv_check.data:
            st.error(f"add_message: Conversation {conversation_id} n'existe pas")
            return False
        
        st.success(f"add_message: Conversation {conversation_id} trouvée")
        
        # Préparer les données
        message_data = {
            "conversation_id": conversation_id,
            "sender": str(sender).strip(),
            "content": str(content).strip(),
            "type": msg_type or "text",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if image_data:
            message_data["image_data"] = image_data
        
        st.info(f"add_message: Données préparées: {list(message_data.keys())}")
        
        # Insertion
        response = supabase.table("messages").insert(message_data).execute()
        
        st.info(f"add_message: Réponse Supabase: {type(response)}")
        
        # Vérifier les erreurs
        if hasattr(response, 'error') and response.error:
            st.error(f"add_message: Erreur Supabase: {response.error}")
            return False
        
        # Vérifier le succès
        if not response.data or len(response.data) == 0:
            st.error("add_message: Aucune donnée retournée - insertion échouée")
            
            # Test debug - vérifier les permissions
            try:
                test_select = supabase.table("messages").select("*").limit(1).execute()
                st.info(f"add_message: Test SELECT réussi - {len(test_select.data)} messages accessibles")
            except Exception as test_e:
                st.error(f"add_message: Test SELECT échoué: {test_e}")
            
            return False
        
        inserted_msg = response.data[0]
        msg_id = inserted_msg.get("message_id") or inserted_msg.get("id")
        
        st.success(f"add_message: Message sauvegardé avec ID: {msg_id}")
        return True
        
    except Exception as e:
        st.error(f"add_message: Exception: {e}")
        import traceback
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

def stream_response(text, placeholder):
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

# -------------------------
# Sidebar Debug
# -------------------------
st.sidebar.title("Debug Info")
st.sidebar.write(f"Utilisateur: {st.session_state.user.get('email')}")
st.sidebar.write(f"Conversation: {st.session_state.conversation.get('description') if st.session_state.conversation else 'Aucune'}")
st.sidebar.write(f"Messages: {len(st.session_state.messages_memory)}")
st.sidebar.write(f"Supabase: {'OK' if supabase else 'KO'}")

# Test add_message
if st.sidebar.button("Test add_message"):
    if st.session_state.conversation:
        conv_id = st.session_state.conversation.get("conversation_id")
        result = add_message(conv_id, "test", "Message de test", "text")
        st.sidebar.write(f"Résultat test: {result}")

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
        current_desc = st.session_state.conversation.get('description') if st.session_state.conversation else "Aucune"
        
        options = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
        
        # Trouver l'index actuel
        current_idx = 0
        if st.session_state.conversation:
            current_id = st.session_state.conversation.get("conversation_id")
            for i, c in enumerate(convs):
                if c.get("conversation_id") == current_id:
                    current_idx = i
                    break
        
        selected_idx = st.sidebar.selectbox("Vos conversations:", 
                                          range(len(options)), 
                                          format_func=lambda i: options[i],
                                          index=current_idx)
        
        selected_conv = convs[selected_idx]
        
        # Charger si différente
        if (not st.session_state.conversation or 
            st.session_state.conversation.get("conversation_id") != selected_conv.get("conversation_id")):
            
            st.session_state.conversation = selected_conv
            conv_id = selected_conv.get("conversation_id")
            
            # Charger messages
            st.info(f"Chargement conversation: {selected_conv.get('description')}")
            messages = get_messages(conv_id)
            st.session_state.messages_memory = messages
            st.rerun()

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat")

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")

# Affichage messages
if st.session_state.messages_memory:
    for msg in st.session_state.messages_memory:
        role = "user" if msg.get("sender") == "user" else "assistant"
        with st.chat_message(role):
            if msg.get("type") == "image" and msg.get("image_data"):
                st.image(base64_to_image(msg["image_data"]), width=300)
            st.markdown(msg.get("content", ""))

# Formulaire nouveau message
with st.form("message_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_area("Votre message:", height=100)
    with col2:
        uploaded_file = st.file_uploader("Image", type=["png","jpg","jpeg"])
    
    submit = st.form_submit_button("Envoyer")

# Traitement message
if submit and (user_input.strip() or uploaded_file):
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
        
        if save_success:
            st.success("Message sauvegardé en DB")
        else:
            st.error("Échec sauvegarde DB")
        
        # Ajouter à la session
        user_msg = {
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages_memory.append(user_msg)
        
        # Afficher message utilisateur
        with st.chat_message("user"):
            if msg_type == "image" and image_data:
                st.image(base64_to_image(image_data), width=300)
            st.markdown(message_content)
        
        # Générer réponse IA
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_content}"
        
        with st.chat_message("assistant"):
            placeholder = st.empty()
            response = get_ai_response(prompt)
            stream_response(response, placeholder)
        
        # Sauvegarder réponse IA
        ai_save_success = add_message(conv_id, "assistant", response, "text")
        
        if ai_save_success:
            st.success("Réponse IA sauvegardée")
        else:
            st.error("Échec sauvegarde réponse IA")
        
        # Ajouter réponse à la session
        ai_msg = {
            "sender": "assistant",
            "content": response,
            "type": "text",
            "image_data": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages_memory.append(ai_msg)
        
        # Vérification finale
        verification_messages = get_messages(conv_id)
        db_count = len(verification_messages) if verification_messages else 0
        session_count = len(st.session_state.messages_memory)
        
        st.info(f"Vérification: DB={db_count}, Session={session_count}")
        
        if db_count != session_count:
            st.warning("Désynchronisation détectée!")
            if st.button("Synchroniser"):
                st.session_state.messages_memory = verification_messages
                st.rerun()
        
        st.rerun()
