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

# ------------------------- 
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Complete", layout="wide")

SYSTEM_PROMPT = """You are Vision AI. You were created by Pepe Musafiri, an Artificial Intelligence Engineer, with contributions from Meta AI. Your role is to help users with any task they need, from image analysis and editing to answering questions clearly and helpfully. Always answer naturally as Vision AI. 

When you receive an image description starting with [IMAGE], you should:
1. Acknowledge that you can see and analyze the image
2. Provide detailed analysis of what you observe
3. Answer any specific questions about the image
4. Be helpful and descriptive in your analysis

When you receive information about image editing starting with [EDIT_CONTEXT], you should:
1. Remember the editing history and context provided
2. Use this information to discuss the edits made
3. Answer questions about the editing process and results
4. Provide suggestions for further improvements if asked"""

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
# Fonctions de récupération de mot de passe
# -------------------------
def generate_reset_token():
    """Génère un token de récupération aléatoire"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def store_reset_token(email, token):
    """Stocke le token de récupération avec expiration - VERSION ALTERNATIVE dans users"""
    if not supabase:
        return False
    
    try:
        # Définir l'expiration (1 heure à partir de maintenant)
        expiration = time.time() + 3600  # 3600 secondes = 1 heure
        
        # Vérifier d'abord si l'utilisateur existe
        user_check = supabase.table("users").select("*").eq("email", email).execute()
        
        if not user_check.data or len(user_check.data) == 0:
            return False
        
        # Mise à jour directe dans la table users avec le token de récupération
        try:
            response = supabase.table("users").update({
                "reset_token": token,
                "reset_token_expires": expiration,
                "reset_token_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }).eq("email", email).execute()
            
            return bool(response.data and len(response.data) > 0)
            
        except Exception as e:
            st.error(f"Erreur lors de la mise à jour du token: {e}")
            # Fallback: utiliser la méthode avec table séparée si elle existe
            try:
                # Données du token pour table séparée
                token_data = {
                    "email": email,
                    "reset_token": token,
                    "expires_at": expiration,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "used": False
                }
                
                # Supprimer les anciens tokens
                supabase.table("password_resets").delete().eq("email", email).execute()
                
                # Insérer le nouveau token
                response = supabase.table("password_resets").insert(token_data).execute()
                return bool(response.data and len(response.data) > 0)
                
            except Exception as e2:
                st.error(f"Table password_resets non disponible. Vous devez soit créer cette table, soit ajouter les colonnes reset_token, reset_token_expires, reset_token_created à la table users.")
                return False
            
    except Exception as e:
        st.error(f"Erreur store_reset_token: {e}")
        return False

def verify_reset_token(email, token):
    """Vérifie si le token de récupération est valide - VERSION ALTERNATIVE"""
    if not supabase:
        return False
    
    try:
        current_time = time.time()
        
        # Essayer d'abord avec la table users (méthode alternative)
        try:
            response = supabase.table("users").select("reset_token, reset_token_expires").eq("email", email).execute()
            
            if response.data and len(response.data) > 0:
                user_data = response.data[0]
                stored_token = user_data.get("reset_token")
                expires_at = user_data.get("reset_token_expires")
                
                if stored_token == token and expires_at and expires_at > current_time:
                    return True
                    
        except Exception:
            pass
        
        # Fallback: essayer avec la table password_resets
        try:
            response = supabase.table("password_resets").select("*").eq("email", email).eq("reset_token", token).eq("used", False).execute()
            
            if response.data and len(response.data) > 0:
                token_data = response.data[0]
                
                # Vérifier l'expiration
                if token_data.get("expires_at", 0) > current_time:
                    return True
                    
        except Exception:
            pass
        
        return False
        
    except Exception as e:
        st.error(f"Erreur verify_reset_token: {e}")
        return False

def reset_password(email, token, new_password):
    """Réinitialise le mot de passe avec un token valide - VERSION ALTERNATIVE"""
    if not supabase:
        return False
    
    try:
        # Vérifier le token
        if not verify_reset_token(email, token):
            return False
        
        # Mettre à jour le mot de passe et nettoyer les tokens
        update_data = {
            "password": new_password,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            # Nettoyer les tokens de récupération
            "reset_token": None,
            "reset_token_expires": None,
            "reset_token_created": None
        }
        
        update_response = supabase.table("users").update(update_data).eq("email", email).execute()
        
        if update_response.data and len(update_response.data) > 0:
            # Nettoyer aussi dans la table password_resets si elle existe
            try:
                supabase.table("password_resets").update({
                    "used": True,
                    "used_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }).eq("email", email).eq("reset_token", token).execute()
            except:
                pass  # Table password_resets peut ne pas exister
            
            return True
        
        return False
        
    except Exception as e:
        st.error(f"Erreur reset_password: {e}")
        return False

def send_reset_email_simulation(email, token):
    """Simulation d'envoi d'email - Dans un vrai projet, utiliser un service comme SendGrid"""
    # Dans cette version, on affiche juste le token à l'utilisateur
    # Dans un vrai projet, vous enverriez un email avec le lien de récupération
    return True

# -------------------------
# Fonction pour afficher les instructions d'accès externe (optionnel)
# -------------------------
def show_external_admin_instructions():
    """Affiche les instructions pour accéder à streamlit_admin.py externe"""
    st.info("🔗 **Accès Interface Admin Externe**")
    
    st.markdown("""
    Si vous préférez utiliser un fichier `streamlit_admin.py` séparé :
    
    **Étapes à suivre :**
    1. Ouvrez un nouveau terminal
    2. Lancez: `streamlit run streamlit_admin.py --server.port 8502`
    3. Accédez à: http://localhost:8502
    
    **Ou copiez cette commande :**
    """)
    
    st.code("streamlit run streamlit_admin.py --server.port 8502")
    
    st.warning("⚠️ Assurez-vous que le fichier `streamlit_admin.py` existe dans votre répertoire.")
    
    # Retourner à l'interface intégrée
    if st.button("← Utiliser l'interface admin intégrée"):
        st.session_state.page = "admin"
        st.rerun()

# -------------------------
# Fonctions DB Corrigées avec gestion des rôles
# -------------------------
def verify_user(email, password):
    """Vérifie les identifiants utilisateur avec gestion admin"""
    # Vérification admin en premier
    if email == ADMIN_CREDENTIALS["email"] and password == ADMIN_CREDENTIALS["password"]:
        return {
            "id": "admin_special_id", 
            "email": email,
            "name": "Jessica Admin",
            "role": "admin"
        }
    
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
                # Récupérer le rôle depuis la table users
                user_data = supabase.table("users").select("*").eq("email", email).execute()
                role = "user"  # rôle par défaut
                if user_data.data and len(user_data.data) > 0:
                    role = user_data.data[0].get("role", "user")
                
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": response.user.user_metadata.get("name", email.split("@")[0]),
                    "role": role
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
                    "name": user.get("name", email.split("@")[0]),
                    "role": user.get("role", "user")
                }
        
        return None
        
    except Exception as e:
        st.error(f"Erreur verify_user: {e}")
        return None

def create_user(email, password, name, role="user"):
    """Crée un nouvel utilisateur avec rôle"""
    if not supabase:
        return False
        
    try:
        # Méthode auth admin
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
            
        # Fallback table directe
        user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": password,
            "name": name,
            "role": role,
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
    """Ajoute un message - VERSION ENTIÈREMENT CORRIGÉE avec edit_context"""
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
            
        # Préparer les données (sans message_id custom)
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
- Résultat: {edit_ctx.get('edited_description', 'N/A')}
- Date: {edit_ctx.get('timestamp', 'N/A')}
""")
            except:
                # Si on ne peut pas parser le contexte, on l'ignore
                continue
    
    return "\n".join(context_info) if context_info else ""

# -------------------------
# Interface de récupération de mot de passe
# -------------------------
def show_password_reset():
    """Affiche l'interface de récupération de mot de passe"""
    st.subheader("🔑 Récupération de mot de passe")
    
    if st.session_state.reset_step == "request":
        st.write("Entrez votre adresse email pour recevoir un code de récupération :")
        
        with st.form("password_reset_request"):
            reset_email = st.text_input("Adresse email", placeholder="votre.email@exemple.com")
            submit_reset = st.form_submit_button("Envoyer le code de récupération")
            
            if submit_reset and reset_email.strip():
                # Vérifier si l'email existe
                if supabase:
                    try:
                        user_check = supabase.table("users").select("*").eq("email", reset_email.strip()).execute()
                        
                        if user_check.data and len(user_check.data) > 0:
                            # Générer et stocker le token
                            reset_token = generate_reset_token()
                            
                            if store_reset_token(reset_email.strip(), reset_token):
                                st.session_state.reset_email = reset_email.strip()
                                st.session_state.reset_token = reset_token
                                st.session_state.reset_step = "verify"
                                
                                # Simulation d'envoi d'email
                                send_reset_email_simulation(reset_email.strip(), reset_token)
                                
                                st.success("✅ Code de récupération généré avec succès!")
                                st.info(f"📧 Dans un vrai système, un email serait envoyé à {reset_email.strip()}")
                                st.warning(f"🔐 **Code de récupération temporaire:** {reset_token}")
                                st.write("Copiez ce code et cliquez sur 'Continuer' pour réinitialiser votre mot de passe.")
                                
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la génération du code de récupération")
                        else:
                            st.error("❌ Cette adresse email n'existe pas dans notre système")
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la vérification: {e}")
                else:
                    st.error("❌ Service non disponible")
        
        # Bouton retour à la connexion
        if st.button("← Retour à la connexion"):
            st.session_state.reset_step = "request"
            st.rerun()
    
    elif st.session_state.reset_step == "verify":
        st.write(f"Un code de récupération a été généré pour: **{st.session_state.reset_email}**")
        st.info("Dans un vrai système, vous recevriez ce code par email.")
        
        with st.form("password_reset_verify"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                token_input = st.text_input("Code de récupération", placeholder="Collez le code ici")
                new_password = st.text_input("Nouveau mot de passe", type="password", placeholder="Minimum 6 caractères")
                confirm_password = st.text_input("Confirmer le mot de passe", type="password")
            
            with col2:
                st.write("**Code généré:**")
                st.code(st.session_state.reset_token)
                st.caption("⏰ Expire dans 1 heure")
            
            submit_new_password = st.form_submit_button("Réinitialiser le mot de passe")
            
            if submit_new_password:
                # Vérifications
                if not token_input.strip():
                    st.error("❌ Veuillez entrer le code de récupération")
                elif not new_password:
                    st.error("❌ Veuillez entrer un nouveau mot de passe")
                elif len(new_password) < 6:
                    st.error("❌ Le mot de passe doit contenir au moins 6 caractères")
                elif new_password != confirm_password:
                    st.error("❌ Les mots de passe ne correspondent pas")
                elif token_input.strip() != st.session_state.reset_token:
                    st.error("❌ Code de récupération incorrect")
                else:
                    # Réinitialiser le mot de passe
                    if reset_password(st.session_state.reset_email, token_input.strip(), new_password):
                        st.success("✅ Mot de passe réinitialisé avec succès!")
                        st.info("Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.")
                        
                        # Reset des variables
                        st.session_state.reset_step = "request"
                        st.session_state.reset_email = ""
                        st.session_state.reset_token = ""
                        
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de la réinitialisation du mot de passe")
        
        # Boutons d'action
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Générer un nouveau code"):
                # Regénérer un nouveau token
                new_token = generate_reset_token()
                if store_reset_token(st.session_state.reset_email, new_token):
                    st.session_state.reset_token = new_token
                    st.success("✅ Nouveau code généré!")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la génération du nouveau code")
        
        with col2:
            if st.button("← Changer d'email"):
                st.session_state.reset_step = "request"
                st.session_state.reset_email = ""
                st.session_state.reset_token = ""
                st.rerun()

# -------------------------
# Gestion de navigation par pages
# -------------------------
def show_admin_page():
    """Affiche l'interface administrateur intégrée"""
    st.title("🔑 Interface Administrateur")
    st.write(f"Connecté en tant que: **{st.session_state.user.get('name')}**")
    
    # Bouton retour
    if st.button("← Retour à l'interface utilisateur"):
        st.session_state.page = "main"
        st.rerun()
    
    # Tabs admin
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Utilisateurs", 
        "💬 Conversations", 
        "📊 Statistiques", 
        "⚙️ Paramètres"
    ])
    
    with tab1:
        st.subheader("Gestion des Utilisateurs")
        
        if supabase:
            try:
                # Récupérer tous les utilisateurs
                users_response = supabase.table("users").select("*").order("created_at", desc=True).execute()
                
                if users_response.data:
                    users_df = pd.DataFrame(users_response.data)
                    
                    # Affichage des utilisateurs
                    st.write(f"**Total utilisateurs: {len(users_df)}**")
                    
                    # Tableau des utilisateurs avec options de modification
                    for idx, user in users_df.iterrows():
                        with st.expander(f"👤 {user.get('name', 'N/A')} ({user.get('email')})"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write(f"**ID:** {user.get('id', 'N/A')[:8]}...")
                                st.write(f"**Email:** {user.get('email')}")
                                st.write(f"**Nom:** {user.get('name')}")
                            
                            with col2:
                                current_role = user.get('role', 'user')
                                st.write(f"**Rôle actuel:** {current_role}")
                                st.write(f"**Créé le:** {user.get('created_at', 'N/A')[:10]}")
                            
                            with col3:
                                # Changer le rôle
                                new_role = st.selectbox(
                                    "Nouveau rôle:",
                                    ["user", "admin"],
                                    index=0 if current_role == "user" else 1,
                                    key=f"role_{user.get('id')}"
                                )
                                
                                if st.button("Mettre à jour", key=f"update_{user.get('id')}"):
                                    try:
                                        update_response = supabase.table("users").update(
                                            {"role": new_role}
                                        ).eq("id", user.get('id')).execute()
                                        
                                        if update_response.data:
                                            st.success(f"Rôle mis à jour: {new_role}")
                                            st.rerun()
                                        else:
                                            st.error("Erreur lors de la mise à jour")
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")
                else:
                    st.info("Aucun utilisateur trouvé")
                    
            except Exception as e:
                st.error(f"Erreur lors du chargement des utilisateurs: {e}")
        else:
            st.error("Connexion Supabase non disponible")
    
    # [Les autres tabs admin - tab2, tab3, tab4 restent identiques - je les ajoute dans la prochaine partie...]

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

# States pour la récupération de mot de passe
if "reset_step" not in st.session_state:
    st.session_state.reset_step = "request"

if "reset_email" not in st.session_state:
    st.session_state.reset_email = ""

if "reset_token" not in st.session_state:
    st.session_state.reset_token = ""

if "page" not in st.session_state:
    st.session_state.page = "main"

# -------------------------
# Vérification admin et redirection - VERSION SIMPLIFIÉE
# -------------------------
def check_admin_redirect():
    """Vérifie si l'utilisateur est admin et propose l'interface admin"""
    if (st.session_state.user.get("role") == "admin" and 
        st.session_state.user.get("email") == ADMIN_CREDENTIALS["email"]):
        
        st.success(f"🔑 Bienvenue Administrateur: {st.session_state.user.get('name')}")
        
        # Navigation simplifiée
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🚀 Interface Admin Intégrée", type="primary"):
                st.session_state.page = "admin"
                st.rerun()
        
        with col2:
            if st.button("🔗 Instructions Admin Externe"):
                st.session_state.page = "external_admin"
                st.rerun()
        
        with col3:
            if st.button("👤 Continuer ici"):
                st.info("Vous continuez avec l'interface utilisateur normale.")

# -------------------------
# Gestion de navigation par pages
# -------------------------
def show_admin_page():
    """Affiche l'interface administrateur intégrée"""
    st.title("🔑 Interface Administrateur")
    st.write(f"Connecté en tant que: **{st.session_state.user.get('name')}**")
    
    # Bouton retour
    if st.button("← Retour à l'interface utilisateur"):
        st.session_state.page = "main"
        st.rerun()
    
    # Tabs admin
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Utilisateurs", 
        "💬 Conversations", 
        "📊 Statistiques", 
        "⚙️ Paramètres"
    ])
    
    with tab1:
        st.subheader("Gestion des Utilisateurs")
        
        if supabase:
            try:
                # Récupérer tous les utilisateurs
                users_response = supabase.table("users").select("*").order("created_at", desc=True).execute()
                
                if users_response.data:
                    users_df = pd.DataFrame(users_response.data)
                    
                    # Affichage des utilisateurs
                    st.write(f"**Total utilisateurs: {len(users_df)}**")
                    
                    # Tableau des utilisateurs avec options de modification
                    for idx, user in users_df.iterrows():
                        with st.expander(f"👤 {user.get('name', 'N/A')} ({user.get('email')})"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write(f"**ID:** {user.get('id', 'N/A')[:8]}...")
                                st.write(f"**Email:** {user.get('email')}")
                                st.write(f"**Nom:** {user.get('name')}")
                            
                            with col2:
                                current_role = user.get('role', 'user')
                                st.write(f"**Rôle actuel:** {current_role}")
                                st.write(f"**Créé le:** {user.get('created_at', 'N/A')[:10]}")
                            
                            with col3:
                                # Changer le rôle
                                new_role = st.selectbox(
                                    "Nouveau rôle:",
                                    ["user", "admin"],
                                    index=0 if current_role == "user" else 1,
                                    key=f"role_{user.get('id')}"
                                )
                                
                                if st.button("Mettre à jour", key=f"update_{user.get('id')}"):
                                    try:
                                        update_response = supabase.table("users").update(
                                            {"role": new_role}
                                        ).eq("id", user.get('id')).execute()
                                        
                                        if update_response.data:
                                            st.success(f"Rôle mis à jour: {new_role}")
                                            st.rerun()
                                        else:
                                            st.error("Erreur lors de la mise à jour")
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")
                else:
                    st.info("Aucun utilisateur trouvé")
                    
            except Exception as e:
                st.error(f"Erreur lors du chargement des utilisateurs: {e}")
        else:
            st.error("Connexion Supabase non disponible")
    
    with tab2:
        st.subheader("Toutes les Conversations & Messages")
        
        if supabase:
            try:
                # Récupérer toutes les conversations avec informations utilisateur
                convs_response = supabase.table("conversations").select("*").order("created_at", desc=True).limit(50).execute()
                
                if convs_response.data:
                    st.write(f"**{len(convs_response.data)} conversations récentes**")
                    
                    # Filtre par utilisateur
                    all_users = list(set([conv.get('user_id') for conv in convs_response.data if conv.get('user_id')]))
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        selected_user = st.selectbox(
                            "Filtrer par utilisateur:",
                            ["Tous"] + all_users,
                            key="user_filter"
                        )
                    with col2:
                        show_messages = st.checkbox("Afficher les messages", value=True)
                    
                    # Filtrer les conversations
                    filtered_convs = convs_response.data
                    if selected_user != "Tous":
                        filtered_convs = [conv for conv in convs_response.data if conv.get('user_id') == selected_user]
                    
                    st.write(f"**{len(filtered_convs)} conversations affichées**")
                    
                    for idx, conv in enumerate(filtered_convs):
                        # Créer un ID unique pour éviter les collisions
                        conv_id = conv.get('conversation_id') or conv.get('id') or f"conv_{idx}"
                        conv_display_id = str(conv_id)[:8] if conv_id != f"conv_{idx}" else f"conv_{idx}"
                        
                        # Récupérer info utilisateur
                        user_id = conv.get('user_id', 'N/A')
                        try:
                            user_info = supabase.table("users").select("name, email").eq("id", user_id).execute()
                            if user_info.data:
                                user_display = f"{user_info.data[0].get('name', 'N/A')} ({user_info.data[0].get('email', 'N/A')})"
                            else:
                                user_display = f"User ID: {user_id}"
                        except:
                            user_display = f"User ID: {user_id}"
                        
                        # Compter les messages
                        try:
                            if conv_id and conv_id != f"conv_{idx}":
                                messages = get_messages(conv_id)
                                msg_count = len(messages)
                            else:
                                messages = []
                                msg_count = 0
                        except Exception as e:
                            messages = []
                            msg_count = f"Erreur ({str(e)[:30]}...)"
                        
                        # Expander principal pour la conversation
                        with st.expander(f"💬 {conv.get('description', 'Sans titre')} | {user_display} | {msg_count} msg | {conv.get('created_at', '')[:16]}"):
                            
                            # Informations de la conversation
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write("**📋 Info Conversation:**")
                                st.write(f"- **ID Conv:** {conv_display_id}")
                                st.write(f"- **Description:** {conv.get('description', 'N/A')}")
                                st.write(f"- **Créée le:** {conv.get('created_at', 'N/A')}")
                            
                            with col2:
                                st.write("**👤 Info Utilisateur:**")
                                st.write(f"- **User ID:** {user_id}")
                                st.write(f"- **Utilisateur:** {user_display}")
                                st.write(f"- **Messages:** {msg_count}")
                            
                            with col3:
                                st.write("**🛠️ Actions Admin:**")
                                
                                # Bouton de suppression avec clé unique
                                if st.button("🗑️ Supprimer Conv", key=f"del_conv_{idx}_{conv_id}"):
                                    if conv_id and conv_id != f"conv_{idx}":
                                        try:
                                            # Supprimer d'abord les messages
                                            msg_del = supabase.table("messages").delete().eq("conversation_id", conv_id).execute()
                                            # Puis supprimer la conversation
                                            conv_del = supabase.table("conversations").delete().eq("conversation_id", conv_id).execute()
                                            
                                            if conv_del.data is not None:  # Supabase peut retourner [] pour un succès
                                                st.success(f"✅ Conversation {conv_display_id} supprimée!")
                                                st.rerun()
                                            else:
                                                st.error("❌ Erreur lors de la suppression")
                                        except Exception as e:
                                            st.error(f"❌ Erreur suppression: {e}")
                                    else:
                                        st.error("❌ ID de conversation invalide")
                                
                                # Bouton d'export de la conversation
                                if st.button("📄 Exporter", key=f"export_conv_{idx}_{conv_id}"):
                                    if messages:
                                        # Créer un DataFrame des messages
                                        export_data = []
                                        for msg in messages:
                                            export_data.append({
                                                "Timestamp": msg.get('created_at', 'N/A'),
                                                "Sender": msg.get('sender', 'N/A'),
                                                "Type": msg.get('type', 'text'),
                                                "Content": msg.get('content', 'N/A')[:100] + "..." if len(msg.get('content', '')) > 100 else msg.get('content', 'N/A'),
                                                "Full_Content": msg.get('content', 'N/A')
                                            })
                                        
                                        df_export = pd.DataFrame(export_data)
                                        csv_data = df_export.to_csv(index=False)
                                        
                                        st.download_button(
                                            label="⬇️ Télécharger CSV",
                                            data=csv_data,
                                            file_name=f"conversation_{conv_display_id}_{int(time.time())}.csv",
                                            mime="text/csv",
                                            key=f"download_conv_{idx}"
                                        )
                                    else:
                                        st.info("Pas de messages à exporter")
                            
                            # Affichage des messages si demandé
                            if show_messages and messages and len(messages) > 0:
                                st.markdown("---")
                                st.write("**💬 Messages de la conversation:**")
                                
                                # Pagination pour les longues conversations
                                messages_per_page = 10
                                total_pages = (len(messages) + messages_per_page - 1) // messages_per_page
                                
                                if total_pages > 1:
                                    page_num = st.selectbox(
                                        f"Page (Total: {len(messages)} messages):",
                                        range(1, total_pages + 1),
                                        key=f"page_conv_{idx}"
                                    )
                                    start_idx = (page_num - 1) * messages_per_page
                                    end_idx = min(start_idx + messages_per_page, len(messages))
                                    display_messages = messages[start_idx:end_idx]
                                else:
                                    display_messages = messages
                                
                                # Affichage des messages
                                for msg_idx, msg in enumerate(display_messages):
                                    sender = msg.get('sender', 'unknown')
                                    content = msg.get('content', 'Contenu vide')
                                    msg_type = msg.get('type', 'text')
                                    timestamp = msg.get('created_at', 'N/A')
                                    
                                    # Style selon le sender
                                    if sender == "user":
                                        icon = "👤"
                                        color = "#e3f2fd"  # Bleu clair
                                    else:
                                        icon = "🤖"
                                        color = "#f3e5f5"  # Violet clair
                                    
                                    # Affichage du message avec style
                                    st.markdown(f"""
                                    <div style="
                                        background-color: {color}; 
                                        padding: 10px; 
                                        border-radius: 8px; 
                                        margin: 5px 0;
                                        border-left: 4px solid {'#2196f3' if sender == 'user' else '#9c27b0'};
                                    ">
                                        <strong>{icon} {sender.title()}</strong> 
                                        <small style="color: #666;">({timestamp[:16]})</small><br>
                                        <div style="margin-top: 5px;">
                                            {content[:300] + "..." if len(content) > 300 else content}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    # Afficher image si c'est un message image
                                    if msg_type == "image" and msg.get('image_data'):
                                        try:
                                            col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
                                            with col_img2:
                                                img = base64_to_image(msg['image_data'])
                                                st.image(img, caption=f"Image - {sender}", width=200)
                                        except Exception as e:
                                            st.error(f"Erreur affichage image: {e}")
                                    
                                    # Bouton pour voir le message complet si tronqué
                                    if len(content) > 300:
                                        if st.button(f"Voir message complet", key=f"show_full_{idx}_{msg_idx}"):
                                            st.text_area(
                                                "Message complet:",
                                                content,
                                                height=200,
                                                key=f"full_content_{idx}_{msg_idx}"
                                            )
                            
                            elif show_messages and (not messages or len(messages) == 0):
                                st.info("🔍 Aucun message dans cette conversation")
                
                else:
                    st.info("Aucune conversation trouvée")
                    
            except Exception as e:
                st.error(f"Erreur lors du chargement des conversations: {e}")
                st.write("**Détails de l'erreur:**")
                st.code(str(e))
                st.write("**Trace complète:**")
                st.code(traceback.format_exc())
    
    with tab3:
        st.subheader("Statistiques Globales")
        
        if supabase:
            try:
                # Statistiques utilisateurs
                users_count = supabase.table("users").select("id", count="exact").execute()
                
                # Statistiques conversations
                convs_count = supabase.table("conversations").select("id", count="exact").execute()
                
                # Statistiques messages
                msgs_count = supabase.table("messages").select("id", count="exact").execute()
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("👥 Utilisateurs", users_count.count if users_count.count else "N/A")
                
                with col2:
                    st.metric("💬 Conversations", convs_count.count if convs_count.count else "N/A")
                
                with col3:
                    st.metric("💬 Messages Total", msgs_count.count if msgs_count.count else "N/A")
                
                # Graphiques (si vous avez des données temporelles)
                st.subheader("📈 Activité Récente")
                
                # Récupérer les données des 7 derniers jours
                try:
                    recent_convs = supabase.table("conversations").select("created_at").gte("created_at", 
                        (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
                    ).execute()
                    
                    if recent_convs.data:
                        df_recent = pd.DataFrame(recent_convs.data)
                        df_recent['date'] = pd.to_datetime(df_recent['created_at']).dt.date
                        daily_counts = df_recent['date'].value_counts().sort_index()
                        
                        st.bar_chart(daily_counts)
                    else:
                        st.info("Pas d'activité récente à afficher")
                        
                except Exception as e:
                    st.error(f"Erreur graphiques: {e}")
                    
            except Exception as e:
                st.error(f"Erreur statistiques: {e}")
    
    with tab4:
        st.subheader("Paramètres Système")
        
        # Informations système
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**🔗 Connexions:**")
            st.write(f"- Supabase: {'✅ OK' if supabase else '❌ KO'}")
            st.write(f"- LLaMA: {'✅ OK' if st.session_state.llama_client else '❌ KO'}")
            st.write(f"- Qwen: {'✅ OK' if st.session_state.qwen_client else '❌ KO'}")
            st.write(f"- BLIP: {'✅ OK' if st.session_state.processor else '❌ KO'}")
        
        with col2:
            st.write("**📁 Fichiers:**")
            try:
                tmp_count = len([f for f in os.listdir(TMP_DIR) if os.path.isfile(os.path.join(TMP_DIR, f))])
                edited_count = len([f for f in os.listdir(EDITED_IMAGES_DIR) if os.path.isfile(os.path.join(EDITED_IMAGES_DIR, f))])
                st.write(f"- Fichiers temp: {tmp_count}")
                st.write(f"- Images éditées: {edited_count}")
            except:
                st.write("- Erreur accès fichiers")
        
        # Actions admin
        st.subheader("🛠️ Actions Administrateur")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🧹 Nettoyer fichiers"):
                cleanup_temp_files()
                st.success("Nettoyage effectué!")
        
        with col2:
            if st.button("🔄 Tester connexions"):
                # Tester toutes les connexions
                st.write("Test en cours...")
                # Ajouter vos tests ici
        
        with col3:
            if st.button("📊 Exporter données"):
                st.info("Fonctionnalité d'export à implémenter")

# -------------------------
# Gestion de la navigation - VERSION CORRIGÉE
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "main"

# Affichage selon la page
if st.session_state.page == "admin":
    show_admin_page()
    st.stop()  # Empêche l'affichage du reste
elif st.session_state.page == "external_admin":
    show_external_admin_instructions()
    st.stop()

# -------------------------
# Sidebar Debug
# -------------------------
st.sidebar.title("Debug Info")
st.sidebar.write(f"Utilisateur: {st.session_state.user.get('email')}")
st.sidebar.write(f"Rôle: {st.session_state.user.get('role', 'N/A')}")
st.sidebar.write(f"Conversation: {st.session_state.conversation.get('description') if st.session_state.conversation else 'Aucune'}")
st.sidebar.write(f"Messages: {len(st.session_state.messages_memory)}")
st.sidebar.write(f"Supabase: {'OK' if supabase else 'KO'}")
st.sidebar.write(f"LLaMA: {'OK' if st.session_state.llama_client else 'KO'}")
st.sidebar.write(f"Qwen: {'OK' if st.session_state.qwen_client else 'KO'}")

# Mostra il contesto di editing attuale nella sidebar per debug
edit_context = get_editing_context_from_conversation()
if edit_context:
    with st.sidebar.expander("Contesto Editing"):
        st.text(edit_context[:300] + "..." if len(edit_context) > 300 else edit_context)

# -------------------------
# ...existing code...

st.sidebar.title("Authentification")

if st.session_state.user["id"] == "guest":
    tab1, tab2, tab3 = st.sidebar.tabs(["Connexion", "Inscription", "Mot de passe"])
    
    with tab1:
        st.write("**Se connecter**")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Se connecter", type="primary"):
                if email and password:
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.success("Connexion réussie!")
                        st.rerun()
                    else:
                        st.error("Identifiants invalides")
                else:
                    st.error("Veuillez remplir tous les champs")
        
        st.markdown("---")
        if st.button("🔐 J'ai oublié mon mot de passe", key="forgot_password_link"):
            # Optionnel: tu peux ajouter ici la logique pour basculer vers tab3
            pass

    with tab2:
        st.write("**Créer un compte**")
        email_reg = st.text_input("Email", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe", type="password", key="reg_pass")
        pass_confirm = st.text_input("Confirmer mot de passe", type="password", key="reg_pass_confirm")
        
        if st.button("Créer compte"):
            if email_reg and name_reg and pass_reg and pass_confirm:
                if pass_reg != pass_confirm:
                    st.error("Les mots de passe ne correspondent pas")
                elif len(pass_reg) < 6:
                    st.error("Le mot de passe doit contenir au moins 6 caractères")
                else:
                    if create_user(email_reg, pass_reg, name_reg):
                        st.success("Compte créé avec succès!")
                        st.info("Vous pouvez maintenant vous connecter.")
                    else:
                        st.error("Erreur lors de la création du compte")
            else:
                st.error("Veuillez remplir tous les champs")

    with tab3:
        st.write("**Récupération de mot de passe**")
        show_password_reset()
    
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    
    # Afficher le rôle de l'utilisateur
    role_display = st.session_state.user.get('role', 'user').upper()
    if st.session_state.user.get('role') == 'admin':
        st.sidebar.markdown(f"**🔑 Rôle: {role_display}**")
    else:
        st.sidebar.markdown(f"**👤 Rôle: {role_display}**")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.reset_step = "request"
        st.session_state.reset_email = ""
        st.session_state.reset_token = ""
        st.rerun()

# ...existing code...

# -------------------------
# Vérification admin après connexion
# -------------------------
if st.session_state.user.get("role") == "admin":
    check_admin_redirect()

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
st.title("Vision AI Chat - Analyse & Édition d'Images")

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")

# Tabs pour différents modes
tab1, tab2 = st.tabs(["💬 Chat Normal", "🎨 Mode Éditeur"])

with tab1:
    st.write("Mode chat classique avec analyse d'images et mémoire des éditions")
    
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
                placeholder="Posez des questions sur les images, demandez des informations sur les éditions précédentes..."
            )
        
        with col2:
            uploaded_file = st.file_uploader(
                "Image",
                type=["png","jpg","jpeg"],
                key="chat_upload"
            )
        
        submit_chat = st.form_submit_button("Envoyer")

with tab2:
    st.write("Mode éditeur d'images avec Qwen-Image-Edit et analyse automatique")
    
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
            "Add magic effects"
        ]
        
        selected_example = st.selectbox(
            "Choisir un exemple",
            ["Custom..."] + example_prompts
        )
        
        if selected_example == "Custom...":
            edit_instruction = st.text_area(
                "Décrivez les modifications souhaitées (en anglais):",
                height=120,
                placeholder="ex: Add a man in the house, change the sky to sunset, make it look artistic..."
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
        - L'API /global_edit utilise votre prompt pour guider l'édition
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
# Traitement des soumissions de chat normal avec mémoire éditions
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
        if (any(k in lower for k in ["edit", "édite", "modifie", "transformer", "améliorer"]) and uploaded_file):
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
            
            # Générer réponse IA avec contexte
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                # Ajouter un indicateur si l'AI utilise le contexte d'édition
                if edit_context and any(word in user_input.lower() for word in ["edit", "édition", "modif", "image", "avant", "après", "changement", "précédent", "transformation", "amélioration"]):
                    with st.spinner("Consultation de la mémoire des éditions..."):
                        time.sleep(1)
                
                response = get_ai_response(prompt)
                stream_response(response, placeholder)
                
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
# Footer avec informations
# -------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.write("**🤖 Vision AI Features:**")
    st.write("- Analyse d'images intelligente")
    st.write("- Édition d'images avec Qwen")
    st.write("- Mémoire des éditions")

with col2:
    st.write("**💭 Fonctionnalités Chat:**")
    st.write("- Conversations sauvegardées")
    st.write("- Contexte des éditions")
    st.write("- Discussion sur les modifications")

with col3:
    st.write("**🎨 Mode Éditeur:**")
    st.write("- Édition avec prompts personnalisés")
    st.write("- API /global_edit de Qwen")
    st.write("- Analyse comparative avant/après")

# -------------------------
# Section d'aide et informations supplémentaires
# -------------------------
with st.expander("ℹ️ Guide d'utilisation"):
    st.markdown("""
    ### 🚀 Comment utiliser Vision AI Chat
    
    **Mode Chat Normal:**
    1. Uploadez une image pour l'analyser
    2. Posez des questions sur l'image
    3. Discutez des éditions précédentes
    
    **Mode Éditeur:**
    1. Uploadez une image à éditer
    2. Sélectionnez ou écrivez une instruction d'édition
    3. Cliquez sur "Éditer l'image"
    4. Téléchargez le résultat
    
    **Fonctionnalités Admin:**
    - Les administrateurs ont accès à une interface spéciale
    - Redirection automatique vers streamlit_admin.py
    - Gestion avancée des utilisateurs et conversations
    
    **Fonctionnalités avancées:**
    - Mémoire persistante des conversations
    - Analyse comparative avant/après édition
    - Contexte d'édition pour discussions ultérieures
    - Sauvegarde automatique en base de données
    
    **Modèles utilisés:**
    - **BLIP**: Description automatique d'images
    - **LLaMA 3.1 70B**: Conversations intelligentes
    - **Qwen ImageEditPro**: Édition d'images avec prompts (/global_edit)
    
    **Exemple d'instruction:**
    "woman in the car!!" ou "add flowers to the garden"
    """)

# -------------------------
# Section Admin dans la sidebar si admin connecté - VERSION CORRIGÉE
# -------------------------
if st.session_state.user.get("role") == "admin":
    with st.sidebar.expander("🔑 Fonctions Admin"):
        st.write("**Interface Administrateur disponible**")
        if st.button("🚀 Accéder Interface Admin", key="admin_launch"):
            st.session_state.page = "admin"
            st.rerun()
        
        st.write("**Statut actuel:**")
        st.write(f"- Email: {st.session_state.user.get('email')}")
        st.write(f"- Nom: {st.session_state.user.get('name')}")
        st.write(f"- ID: {st.session_state.user.get('id')}")
        
        st.info("Vous avez accès à toutes les fonctionnalités administrateur.")

# -------------------------
# Test de l'API Qwen pour debug
# -------------------------
if st.sidebar.button("🧪 Test API Qwen"):
    if st.session_state.qwen_client:
        try:
            st.sidebar.write("Test en cours...")
            test_result = st.session_state.qwen_client.predict(
                input_image=handle_file('https://raw.githubusercontent.com/gradio-app/gradio/main/test/test_files/bus.png'),
                prompt="woman in the car!!",
                api_name="/global_edit"
            )
            st.sidebar.success("✅ API Qwen fonctionnelle")
            st.sidebar.write(f"Type de résultat: {type(test_result)}")
            if isinstance(test_result, (list, tuple)):
                st.sidebar.write(f"Nombre d'éléments: {len(test_result)}")
        except Exception as e:
            st.sidebar.error(f"❌ Erreur API Qwen: {e}")
    else:
        st.sidebar.error("❌ Client Qwen non disponible")

# -------------------------
# Gestion des erreurs et diagnostics
# -------------------------
if st.sidebar.button("🔧 Diagnostics"):
    st.sidebar.subheader("Tests de connexion")
    
    # Test Supabase
    if supabase:
        try:
            test_result = supabase.table("users").select("*").limit(1).execute()
            st.sidebar.success("✅ Supabase OK")
        except Exception as e:
            st.sidebar.error(f"❌ Supabase: {e}")
    else:
        st.sidebar.error("❌ Supabase non connecté")
    
    # Test LLaMA
    if st.session_state.llama_client:
        st.sidebar.success("✅ LLaMA Client OK")
    else:
        st.sidebar.error("❌ LLaMA Client non disponible")
    
    # Test Qwen
    if st.session_state.qwen_client:
        st.sidebar.success("✅ Qwen Client OK")
    else:
        st.sidebar.error("❌ Qwen Client non disponible")
    
    # Test BLIP
    try:
        if st.session_state.processor and st.session_state.model:
            st.sidebar.success("✅ BLIP Models OK")
        else:
            st.sidebar.error("❌ BLIP Models non chargés")
    except:
        st.sidebar.error("❌ Erreur BLIP Models")

# -------------------------
# Nettoyage des fichiers temporaires
# -------------------------
def cleanup_temp_files():
    """Nettoie les fichiers temporaires anciens"""
    try:
        current_time = time.time()
        
        # Nettoyage TMP_DIR (fichiers > 1 heure)
        for filename in os.listdir(TMP_DIR):
            filepath = os.path.join(TMP_DIR, filename)
            if os.path.isfile(filepath):
                file_time = os.path.getctime(filepath)
                if current_time - file_time > 3600:  # 1 heure
                    os.remove(filepath)
        
        # Nettoyage EDITED_IMAGES_DIR (fichiers > 24 heures)
        for filename in os.listdir(EDITED_IMAGES_DIR):
            filepath = os.path.join(EDITED_IMAGES_DIR, filename)
            if os.path.isfile(filepath):
                file_time = os.path.getctime(filepath)
                if current_time - file_time > 86400:  # 24 heures
                    os.remove(filepath)
                    
    except Exception as e:
        st.sidebar.warning(f"Nettoyage fichiers: {e}")

# Exécuter le nettoyage périodiquement
if st.sidebar.button("🧹 Nettoyer fichiers temp"):
    cleanup_temp_files()
    st.sidebar.success("Nettoyage effectué!")

# -------------------------
    # Compter messages total
    if st.session_state.conversation:
        msg_count = len(get_messages(st.session_state.conversation.get("conversation_id")))
    else:
        msg_count = 0
    
    # Affichage stats dans sidebar
    with st.sidebar.expander("📊 Vos statistiques"):
        st.write(f"Conversations: {conv_count}")
        st.write(f"Messages (conversation actuelle): {msg_count}")
        
        # Stats éditions dans conversation actuelle
        edit_count = sum(1 for msg in st.session_state.messages_memory if msg.get("edit_context"))
        st.write(f"Éditions d'images: {edit_count}")
        
        # Affichage spécial pour admin
        if st.session_state.user.get("role") == "admin":
            st.write("**🔑 Privilèges Admin:**")
            st.write("- Accès interface admin")
            st.write("- Gestion utilisateurs")
            st.write("- Statistiques globales")
            
except Exception as e:
    pass  # Ignorer les erreurs de stats
 -------------------------
# Note de bas de page pour admin
# -------------------------
if st.session_state.user.get("role") == "admin":
    st.markdown("---")
    st.info("""
    🔑 **Mode Administrateur Actif**
    
    Vous êtes connecté avec des privilèges administrateur. Vous pouvez :
    - Accéder à l'interface d'administration complète
    - Gérer les utilisateurs et leurs rôles
    - Voir les statistiques globales de l'application
    - Modérer les conversations et contenus
    
    Cliquez sur "Accéder à l'interface Administrateur" pour ouvrir streamlit_admin.py
    """)

# -------------------------
# Gestion des erreurs critiques
# -------------------------
try:
    # Vérification de l'intégrité des données de session
    if st.session_state.user and not isinstance(st.session_state.user, dict):
        st.error("Erreur de session utilisateur - Reconnexion requise")
        st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}
        st.rerun()
    
    # Vérification de la conversation active
    if (st.session_state.conversation and 
        not st.session_state.conversation.get("conversation_id")):
        st.warning("Conversation corrompue - Création d'une nouvelle conversation recommandée")
        
except Exception as e:
    st.error(f"Erreur système critique: {e}")
    st.info("Veuillez recharger la page ou contacter l'administrateur.")
