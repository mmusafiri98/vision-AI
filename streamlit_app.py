
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

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Complete", layout="wide")

SYSTEM_PROMPT = """You are Vision AI. You were created by Pepe Musafiri, an Artificial Intelligence Engineer, with contributions from Meta AI. Your role is to help users with any task they need, from image analysis and editing to answering questions clearly and helpfully.

Always answer naturally as Vision AI.

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
    """Ajoute un message - VERSION ENTIÈREMENT CORRIGÉE con edit_context"""
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
# Sidebar Debug
# -------------------------
st.sidebar.title("Debug Info")
st.sidebar.write(f"Utilisateur: {st.session_state.user.get('email')}")
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
            
            # Générer réponse IA avec contexte
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                # Ajouter un indicateur si l'AI utilise le contexte d'édition
                if edit_context and any(word in user_input.lower() 
                    for word in ["edit", "édition", "modif", "image", "avant", "après", 
                                "changement", "précédent", "transformation", "amélioration"]):
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
# Footer con informazioni
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
    st.write("    **🎨 Mode Éditeur:**")
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
    2. Cliquez sur "Éditer automatiquement"
    3. Téléchargez le résultat
    
    **Fonctionnalités avancées:**
    - Mémoire persistante des conversations
    - Analyse comparative avant/après édition
    - Contexte d'édition pour discussions ultérieures
    - Sauvegarde automatique en base de données
    
    **Modèles utilisés:**
    - **BLIP**: Description automatique d'images
    - **LLaMA 3.1 70B**: Conversations intelligentes  
    - **Qwen ImageEditPro**: Édition d'images avec prompts (/global_edit)
    
    **Exemple d'instruction:** "woman in the car!!" ou "add flowers to the garden"
    """)

# -------------------------
# Test de l'API Qwen pour debug
# -------------------------
if st.sidebar.button("🧪 Test API Qwen"):
    if st.session_state.qwen_client:
        try:
            # Test simple avec une image par défaut
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
# Statistiques utilisateur (optionnel)
# -------------------------
if st.session_state.user["id"] != "guest" and supabase:
    try:
        # Compter conversations
        conv_count = len(get_conversations(st.session_state.user["id"]))
        
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
            edit_count = sum(1 for msg in st.session_state.messages_memory 
                           if msg.get("edit_context"))
            st.write(f"Éditions d'images: {edit_count}")
            
    except Exception as e:
        pass  # Ignorer les erreurs de stats
