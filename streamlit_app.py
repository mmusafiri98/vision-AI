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
# Supabase Connection
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
    """Stocke le token de récupération avec expiration"""
    if not supabase:
        return False
    
    try:
        expiration = time.time() + 3600
        user_check = supabase.table("users").select("*").eq("email", email).execute()
        
        if not user_check.data or len(user_check.data) == 0:
            return False
        
        try:
            response = supabase.table("users").update({
                "reset_token": token,
                "reset_token_expires": expiration,
                "reset_token_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }).eq("email", email).execute()
            
            return bool(response.data and len(response.data) > 0)
            
        except Exception:
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
                return bool(response.data and len(response.data) > 0)
            except Exception:
                return False
            
    except Exception as e:
        st.error(f"Erreur store_reset_token: {e}")
        return False

def verify_reset_token(email, token):
    """Vérifie si le token de récupération est valide"""
    if not supabase:
        return False
    
    try:
        current_time = time.time()
        
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
        
        try:
            response = supabase.table("password_resets").select("*").eq("email", email).eq("reset_token", token).eq("used", False).execute()
            
            if response.data and len(response.data) > 0:
                token_data = response.data[0]
                if token_data.get("expires_at", 0) > current_time:
                    return True
        except Exception:
            pass
        
        return False
        
    except Exception as e:
        st.error(f"Erreur verify_reset_token: {e}")
        return False

def reset_password(email, token, new_password):
    """Réinitialise le mot de passe avec un token valide"""
    if not supabase:
        return False
    
    try:
        if not verify_reset_token(email, token):
            return False
        
        update_data = {
            "password": new_password,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reset_token": None,
            "reset_token_expires": None,
            "reset_token_created": None
        }
        
        update_response = supabase.table("users").update(update_data).eq("email", email).execute()
        
        if update_response.data and len(update_response.data) > 0:
            try:
                supabase.table("password_resets").update({
                    "used": True,
                    "used_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }).eq("email", email).eq("reset_token", token).execute()
            except:
                pass
            
            return True
        
        return False
        
    except Exception as e:
        st.error(f"Erreur reset_password: {e}")
        return False

def send_reset_email_simulation(email, token):
    """Simulation d'envoi d'email"""
    return True

# -------------------------
# Fonctions DB
# -------------------------
def verify_user(email, password):
    """Vérifie les identifiants utilisateur avec gestion admin"""
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
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if response.user:
                user_data = supabase.table("users").select("*").eq("email", email).execute()
                role = "user"
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
    """Récupère les messages d'une conversation"""
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
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None, edit_context=None):
    """Ajoute un message"""
    if not supabase:
        st.error("add_message: Supabase non connecté")
        return False
        
    if not conversation_id or not content:
        st.error(f"add_message: Paramètres manquants")
        return False
        
    try:
        conv_check = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).execute()
        
        if hasattr(conv_check, 'error') and conv_check.error:
            st.error(f"add_message: Erreur vérification conversation: {conv_check.error}")
            return False
            
        if not conv_check.data:
            st.error(f"add_message: Conversation {conversation_id} n'existe pas")
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
        
        if hasattr(response, 'error') and response.error:
            st.error(f"add_message: Erreur Supabase: {response.error}")
            return False
            
        if not response.data or len(response.data) == 0:
            st.error("add_message: Aucune donnée retournée")
            return False
            
        return True
        
    except Exception as e:
        st.error(f"add_message: Exception: {e}")
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
# AI functions avec thinking indicator
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

def stream_response_with_thinking(text, placeholder):
    """Affiche d'abord 'Vision AI thinking...' puis stream la réponse"""
    # Phase de thinking
    thinking_text = "🤔 Vision AI thinking"
    for i in range(3):
        placeholder.markdown(thinking_text + "." * (i + 1))
        time.sleep(0.3)
    
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
    """Édite une image avec Qwen en utilisant l'API /global_edit"""
    client = st.session_state.get("qwen_client")
    if not client:
        st.error("Client Qwen non disponible.")
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
        
        if result:
            if isinstance(result, (list, tuple)) and len(result) >= 2:
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
                else:
                    return None, f"Fichier image non trouvé: {result_path}"
            else:
                return None, f"Format de résultat inattendu: {type(result)}"
        else:
            return None, "Aucun résultat retourné par l'API"
            
    except Exception as e:
        st.error(f"Erreur lors de l'édition: {e}")
        return None, str(e)

def create_edit_context(original_caption, edit_instruction, edited_caption, success_info):
    """Crée un contexte détaillé de l'édition"""
    context = {
        "original_description": original_caption,
        "edit_instruction": edit_instruction,
        "edited_description": edited_caption,
        "edit_info": success_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return context

def process_image_edit_request(image: Image.Image, edit_instruction: str, conv_id: str):
    """Traite une demande d'édition d'image avec indicateurs de chargement"""
    
    # Progress bar et status
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Étape 1: Analyse de l'image originale
        status_text.info("🔍 Analyse de l'image originale...")
        progress_bar.progress(20)
        time.sleep(0.5)
        
        original_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        
        # Étape 2: Édition de l'image
        status_text.info(f"🎨 Édition en cours: '{edit_instruction}'...")
        progress_bar.progress(40)
        
        edited_img, result_info = edit_image_with_qwen(image, edit_instruction)
        
        if edited_img:
            # Étape 3: Analyse de l'image éditée
            status_text.info("🔍 Analyse de l'image éditée...")
            progress_bar.progress(70)
            time.sleep(0.5)
            
            edited_caption = generate_caption(edited_img, st.session_state.processor, st.session_state.model)
            
            # Étape 4: Finalisation
            status_text.info("💾 Sauvegarde et finalisation...")
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
            
            st.subheader("📊 Détails de l'édition")
            st.success("✅ Édition terminée avec succès !")
            
            with st.expander("🔍 Voir les détails techniques"):
                st.json({
                    "instruction": edit_instruction,
                    "statut": "Succès",
                    "image_originale": original_caption,
                    "image_editee": edited_caption,
                    "info_technique": result_info
                })
            
            response_content = f"""✨ **Édition d'image terminée !**

**Instruction d'édition:** {edit_instruction}

**Analyse comparative:**
- **Image originale:** {original_caption}
- **Image éditée:** {edited_caption}

**Modifications détectées:**
J'ai appliqué votre demande "{edit_instruction}" à l'image. L'image éditée montre maintenant: {edited_caption}

**Info technique:** {result_info}

Je garde en mémoire cette édition et peux discuter des changements apportés!"""
            
            edited_b64 = image_to_base64(edited_img.convert("RGB"))
            success = add_message(
                conv_id,
                "assistant",
                response_content,
                "image",
                edited_b64,
                None
            )
            
            if success:
                progress_bar.progress(100)
                status_text.success("✅ Traitement terminé!")
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
                
                st.subheader("Télécharger l'image éditée")
                img_buffer = io.BytesIO()
                edited_img.convert("RGB").save(img_buffer, format="PNG")
                
                st.download_button(
                    label="⬇️ Télécharger PNG",
                    data=img_buffer.getvalue(),
                    file_name=f"edited_image_{int(time.time())}.png",
                    mime="image/png"
                )
                
                return True
            else:
                status_text.error("❌ Erreur lors de la sauvegarde")
                progress_bar.empty()
                return False
        else:
            status_text.error(f"❌ Échec de l'édition: {result_info}")
            progress_bar.empty()
            return False
            
    except Exception as e:
        status_text.error(f"❌ Erreur: {e}")
        progress_bar.empty()
        return False

def get_editing_context_from_conversation():
    """Récupère le contexte d'édition de la conversation"""
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
    """Affiche l'interface de récupération de mot de passe"""
    st.subheader("🔑 Récupération de mot de passe")
    
    if st.session_state.reset_step == "request":
        st.write("Entrez votre adresse email pour recevoir un code de récupération :")
        
        with st.form("password_reset_request"):
            reset_email = st.text_input("Adresse email", placeholder="votre.email@exemple.com")
            submit_reset = st.form_submit_button("Envoyer le code de récupération")
            
            if submit_reset and reset_email.strip():
                if supabase:
                    try:
                        user_check = supabase.table("users").select("*").eq("email", reset_email.strip()).execute()
                        
                        if user_check.data and len(user_check.data) > 0:
                            reset_token = generate_reset_token()
                            
                            if store_reset_token(reset_email.strip(), reset_token):
                                st.session_state.reset_email = reset_email.strip()
                                st.session_state.reset_token = reset_token
                                st.session_state.reset_step = "verify"
                                
                                send_reset_email_simulation(reset_email.strip(), reset_token)
                                
                                st.success("✅ Code de récupération généré!")
                                st.info(f"📧 Email envoyé à {reset_email.strip()}")
                                st.warning(f"🔐 **Code:** {reset_token}")
                                
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la génération")
                        else:
                            st.error("❌ Email introuvable")
                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
        
        if st.button("← Retour à la connexion"):
            st.session_state.reset_step = "request"
            st.rerun()
    
    elif st.session_state.reset_step == "verify":
        st.write(f"Code généré pour: **{st.session_state.reset_email}**")
        
        with st.form("password_reset_verify"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                token_input = st.text_input("Code de récupération")
                new_password = st.text_input("Nouveau mot de passe", type="password")
                confirm_password = st.text_input("Confirmer", type="password")
            
            with col2:
                st.write("**Code généré:**")
                st.code(st.session_state.reset_token)
                st.caption("⏰ Expire dans 1h")
            
            submit_new_password = st.form_submit_button("Réinitialiser")
            
            if submit_new_password:
                if not token_input.strip():
                    st.error("❌ Entrez le code")
                elif not new_password:
                    st.error("❌ Entrez un mot de passe")
                elif len(new_password) < 6:
                    st.error("❌ Minimum 6 caractères")
                elif new_password != confirm_password:
                    st.error("❌ Mots de passe différents")
                elif token_input.strip() != st.session_state.reset_token:
                    st.error("❌ Code incorrect")
                else:
                    if reset_password(st.session_state.reset_email, token_input.strip(), new_password):
                        st.success("✅ Mot de passe réinitialisé!")
                        st.session_state.reset_step = "request"
                        st.session_state.reset_email = ""
                        st.session_state.reset_token = ""
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Erreur réinitialisation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Nouveau code"):
                new_token = generate_reset_token()
                if store_reset_token(st.session_state.reset_email, new_token):
                    st.session_state.reset_token = new_token
                    st.success("✅ Nouveau code généré!")
                    st.rerun()
        
        with col2:
            if st.button("← Changer d'email"):
                st.session_state.reset_step = "request"
                st.session_state.reset_email = ""
                st.session_state.reset_token = ""
                st.rerun()

# -------------------------
# Gestion admin
# -------------------------
def show_external_admin_instructions():
    """Instructions pour accès admin externe"""
    st.info("🔗 **Accès Interface Admin Externe**")
    
    st.markdown("""
    **Étapes:**
    1. Terminal: `streamlit run streamlit_admin.py --server.port 8502`
    2. Accès: http://localhost:8502
    """)
    
    st.code("streamlit run streamlit_admin.py --server.port 8502")
    
    if st.button("← Interface admin intégrée"):
        st.session_state.page = "admin"
        st.rerun()

def show_admin_page():
    """Interface administrateur intégrée"""
    st.title("🔑 Interface Administrateur")
    st.write(f"Connecté: **{st.session_state.user.get('name')}**")
    
    if st.button("← Retour interface utilisateur"):
        st.session_state.page = "main"
        st.rerun()
    
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
                users_response = supabase.table("users").select("*").order("created_at", desc=True).execute()
                
                if users_response.data:
                    users_df = pd.DataFrame(users_response.data)
                    st.write(f"**Total: {len(users_df)} utilisateurs**")
                    
                    for idx, user in users_df.iterrows():
                        with st.expander(f"👤 {user.get('name', 'N/A')} ({user.get('email')})"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write(f"**ID:** {user.get('id', 'N/A')[:8]}...")
                                st.write(f"**Email:** {user.get('email')}")
                                st.write(f"**Nom:** {user.get('name')}")
                            
                            with col2:
                                current_role = user.get('role', 'user')
                                st.write(f"**Rôle:** {current_role}")
                                st.write(f"**Créé:** {user.get('created_at', 'N/A')[:10]}")
                            
                            with col3:
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
                                            st.success(f"Rôle: {new_role}")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")
                else:
                    st.info("Aucun utilisateur")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab2:
        st.subheader("Conversations & Messages")
        
        if supabase:
            try:
                convs_response = supabase.table("conversations").select("*").order("created_at", desc=True).limit(50).execute()
                
                if convs_response.data:
                    st.write(f"**{len(convs_response.data)} conversations**")
                    
                    all_users = list(set([conv.get('user_id') for conv in convs_response.data if conv.get('user_id')]))
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        selected_user = st.selectbox("Filtrer:", ["Tous"] + all_users, key="user_filter")
                    with col2:
                        show_messages = st.checkbox("Messages", value=True)
                    
                    filtered_convs = convs_response.data
                    if selected_user != "Tous":
                        filtered_convs = [conv for conv in convs_response.data if conv.get('user_id') == selected_user]
                    
                    for idx, conv in enumerate(filtered_convs):
                        conv_id = conv.get('conversation_id') or conv.get('id') or f"conv_{idx}"
                        conv_display_id = str(conv_id)[:8]
                        
                        user_id = conv.get('user_id', 'N/A')
                        try:
                            user_info = supabase.table("users").select("name, email").eq("id", user_id).execute()
                            user_display = f"{user_info.data[0].get('name')} ({user_info.data[0].get('email')})" if user_info.data else f"User: {user_id}"
                        except:
                            user_display = f"User: {user_id}"
                        
                        try:
                            messages = get_messages(conv_id) if conv_id != f"conv_{idx}" else []
                            msg_count = len(messages)
                        except:
                            messages = []
                            msg_count = "Err"
                        
                        with st.expander(f"💬 {conv.get('description', 'Sans titre')} | {user_display} | {msg_count} msg"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write(f"**ID:** {conv_display_id}")
                                st.write(f"**Desc:** {conv.get('description')}")
                            
                            with col2:
                                st.write(f"**User:** {user_display}")
                                st.write(f"**Date:** {conv.get('created_at', 'N/A')[:10]}")
                            
                            with col3:
                                if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                                    try:
                                        supabase.table("messages").delete().eq("conversation_id", conv_id).execute()
                                        supabase.table("conversations").delete().eq("conversation_id", conv_id).execute()
                                        st.success("Supprimé!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")
                            
                            if show_messages and messages:
                                st.markdown("---")
                                for msg in messages[:10]:
                                    sender = msg.get('sender', 'unknown')
                                    content = msg.get('content', '')[:200]
                                    icon = "👤" if sender == "user" else "🤖"
                                    st.markdown(f"**{icon} {sender}:** {content}")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab3:
        st.subheader("Statistiques")
        
        if supabase:
            try:
                users_count = supabase.table("users").select("id", count="exact").execute()
                convs_count = supabase.table("conversations").select("id", count="exact").execute()
                msgs_count = supabase.table("messages").select("id", count="exact").execute()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Utilisateurs", users_count.count or "N/A")
                with col2:
                    st.metric("💬 Conversations", convs_count.count or "N/A")
                with col3:
                    st.metric("💬 Messages", msgs_count.count or "N/A")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab4:
        st.subheader("Paramètres Système")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Connexions:**")
            st.write(f"- Supabase: {'✅' if supabase else '❌'}")
            st.write(f"- LLaMA: {'✅' if st.session_state.llama_client else '❌'}")
            st.write(f"- Qwen: {'✅' if st.session_state.qwen_client else '❌'}")
        
        with col2:
            st.write("**Actions:**")
            if st.button("🧹 Nettoyer"):
                cleanup_temp_files()
                st.success("Fait!")

def cleanup_temp_files():
    """Nettoie les fichiers temporaires"""
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
def check_admin_redirect():
    """Vérifie admin et propose interface"""
    if (st.session_state.user.get("role") == "admin" and 
        st.session_state.user.get("email") == ADMIN_CREDENTIALS["email"]):
        
        st.success(f"🔑 Admin: {st.session_state.user.get('name')}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🚀 Interface Admin", type="primary"):
                st.session_state.page = "admin"
                st.rerun()
        with col2:
            if st.button("🔗 Instructions Externe"):
                st.session_state.page = "external_admin"
                st.rerun()
        with col3:
            if st.button("👤 Continuer ici"):
                pass

if st.session_state.page == "admin":
    show_admin_page()
    st.stop()
elif st.session_state.page == "external_admin":
    show_external_admin_instructions()
    st.stop()

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("Debug Info")
st.sidebar.write(f"User: {st.session_state.user.get('email')}")
st.sidebar.write(f"Role: {st.session_state.user.get('role', 'N/A')}")
st.sidebar.write(f"Conv: {st.session_state.conversation.get('description') if st.session_state.conversation else 'Aucune'}")
st.sidebar.write(f"Messages: {len(st.session_state.messages_memory)}")

st.sidebar.title("Authentification")

if st.session_state.user["id"] == "guest":
    tab1, tab2, tab3 = st.sidebar.tabs(["Connexion", "Inscription", "Reset"])
    
    with tab1:
        st.write("**Se connecter**")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        
        if st.button("Se connecter", type="primary"):
            if email and password:
                with st.spinner("🔐 Connexion en cours..."):
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.success("✅ Connecté!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Identifiants invalides")
            else:
                st.error("❌ Remplir tous les champs")

    with tab2:
        st.write("**Créer un compte**")
        email_reg = st.text_input("Email", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe", type="password", key="reg_pass")
        pass_confirm = st.text_input("Confirmer", type="password", key="reg_pass_confirm")
        
        if st.button("Créer compte"):
            if email_reg and name_reg and pass_reg and pass_confirm:
                if pass_reg != pass_confirm:
                    st.error("❌ Mots de passe différents")
                elif len(pass_reg) < 6:
                    st.error("❌ Minimum 6 caractères")
                else:
                    with st.spinner("📝 Création du compte..."):
                        if create_user(email_reg, pass_reg, name_reg):
                            st.success("✅ Compte créé!")
                            time.sleep(1)
                        else:
                            st.error("❌ Erreur création")
            else:
                st.error("❌ Remplir tous les champs")

    with tab3:
        show_password_reset()
    
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    
    role_display = st.session_state.user.get('role', 'user').upper()
    if st.session_state.user.get('role') == 'admin':
        st.sidebar.markdown(f"**🔑 Rôle: {role_display}**")
    else:
        st.sidebar.markdown(f"**👤 Rôle: {role_display}**")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Vérification admin
# -------------------------
if st.session_state.user.get("role") == "admin":
    check_admin_redirect()

# -------------------------
# Gestion Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("Conversations")
    
    if st.sidebar.button("➕ Nouvelle conversation"):
        with st.spinner("Création..."):
            conv = create_conversation(st.session_state.user["id"], "Nouvelle discussion")
            if conv:
                st.session_state.conversation = conv
                st.session_state.messages_memory = []
                st.success("✅ Créée!")
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
            
            with st.spinner("📂 Chargement..."):
                st.session_state.conversation = selected_conv
                conv_id = selected_conv.get("conversation_id")
                messages = get_messages(conv_id)
                st.session_state.messages_memory = messages
                time.sleep(0.5)
                st.rerun()

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat - Analyse & Édition d'Images")

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")

tab1, tab2 = st.tabs(["💬 Chat Normal", "🎨 Mode Éditeur"])

with tab1:
    st.write("Mode chat avec analyse d'images et mémoire des éditions")
    
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
            
            with st.spinner("🔍 Analyse..."):
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
        
        if st.button("🎨 Éditer", type="primary", disabled=not (editor_file and edit_instruction.strip())):
            if not st.session_state.conversation:
                conv = create_conversation(st.session_state.user["id"], "Édition d'images")
                if conv:
                    st.session_state.conversation = conv
            
            if st.session_state.conversation:
                original_caption = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                user_msg = f"📸 **Édition demandée**\n\n**Image:** {original_caption}\n\n**Instruction:** {edit_instruction}"
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
        with st.spinner("📝 Création conversation..."):
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
        with st.spinner("🔍 Analyse de l'image..."):
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
            
            prompt = f"{SYSTEM_PROMPT}\n\n"
            if edit_context:
                prompt += f"[EDIT_CONTEXT] {edit_context}\n\n"
            prompt += f"Utilisateur: {message_content}"
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                if edit_context and any(w in user_input.lower() for w in ["edit", "image", "avant", "après"]):
                    with st.spinner("🧠 Consultation mémoire..."):
                        time.sleep(1)
                
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
# Footer
# -------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.write("**🤖 Vision AI:**")
    st.write("- Analyse intelligente")
    st.write("- Édition avec Qwen")
    st.write("- Mémoire des éditions")

with col2:
    st.write("**💭 Chat:**")
    st.write("- Conversations sauvegardées")
    st.write("- Contexte des éditions")
    st.write("- Discussion modifications")

with col3:
    st.write("**🎨 Éditeur:**")
    st.write("- Prompts personnalisés")
    st.write("- API /global_edit")
    st.write("- Analyse avant/après")
