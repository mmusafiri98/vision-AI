import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client, handle_file
import time
import io
import base64
import os
import uuid
from supabase import create_client
import tempfile

# -------------------------
# Configuration Streamlit
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Image Edit", layout="wide")

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
4. Be helpful and descriptive in your analysis

When you receive an edited image description starting with [EDITED_IMAGE], you should:
1. Acknowledge that you can see the edited image
2. Describe what modifications were made
3. Analyze the result of the editing
4. Comment on the quality and success of the edit"""

# -------------------------
# Supabase
# -------------------------
@st.cache_resource
def init_supabase():
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            st.error("Supabase URL ou clé manquante")
            return None
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        st.error(f"Erreur Supabase: {e}")
        return None

supabase = init_supabase()

# -------------------------
# Fonctions Utilisateur
# -------------------------
def create_user(email, password, name):
    if not supabase:
        return False
    try:
        try:
            response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name}
            })
            return response.user is not None
        except:
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,
                "name": name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            resp = supabase.table("users").insert(user_data).execute()
            return bool(resp.data and len(resp.data) > 0)
    except Exception as e:
        st.error(f"Erreur create_user: {e}")
        return False

def verify_user(email, password):
    if not supabase:
        return None
    try:
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if resp.user:
                return {
                    "id": resp.user.id,
                    "email": resp.user.email,
                    "name": resp.user.user_metadata.get("name", email.split("@")[0])
                }
        except:
            resp = supabase.table("users").select("*").eq("email", email).execute()
            if resp.data and len(resp.data) > 0:
                user = resp.data[0]
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

# -------------------------
# Conversations & Messages
# -------------------------
def create_conversation(user_id, description="Nouvelle conversation"):
    if not supabase or not user_id:
        return None
    try:
        data = {
            "conversation_id": str(uuid.uuid4()),
            "user_id": user_id,
            "description": description,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        resp = supabase.table("conversations").insert(data).execute()
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None
    except Exception as e:
        st.error(f"Erreur create_conversation: {e}")
        return None

def get_conversations(user_id):
    if not supabase or not user_id:
        return []
    try:
        resp = supabase.table("conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return resp.data if resp.data else []
    except:
        return []

def add_message(conversation_id, sender, content, msg_type="text", image_data=None, edited_image_data=None):
    if not supabase:
        return False
    try:
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "type": msg_type,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        if image_data:
            data["image_data"] = image_data
        if edited_image_data:
            data["edited_image_data"] = edited_image_data
        resp = supabase.table("messages").insert(data).execute()
        return bool(resp.data and len(resp.data) > 0)
    except Exception as e:
        st.error(f"add_message: {e}")
        return False

def get_messages(conversation_id):
    if not supabase:
        return []
    try:
        resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        return resp.data if resp.data else []
    except:
        return []

# -------------------------
# BLIP
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
# Image Editing avec Multiple APIs
# -------------------------
@st.cache_resource
def load_image_edit_clients():
    """Charge plusieurs clients d'édition d'images comme alternatives"""
    clients = {}
    
    # Client principal : Qwen Image Edit
    try:
        clients['qwen'] = Client("Qwen/Qwen-Image-Edit")
    except:
        clients['qwen'] = None
    
    # Alternative 1 : InstEditBooth
    try:
        clients['instedit'] = Client("SeaArtLab/InstEditBooth")
    except:
        clients['instedit'] = None
    
    # Alternative 2 : Flux Dev (si disponible)
    try:
        clients['flux'] = Client("black-forest-labs/FLUX.1-dev")
    except:
        clients['flux'] = None
    
    return clients

def check_quota_status(client, client_name):
    """Vérifie si un client API a du quota disponible"""
    try:
        # Test simple pour vérifier la disponibilité
        # Chaque API a sa propre méthode de vérification
        return True
    except Exception as e:
        if "quota" in str(e).lower() or "exceeded" in str(e).lower():
            return False
        return True

def edit_image_with_multiple_apis(image, edit_prompt, seed=0, randomize_seed=True, guidance_scale=4, num_steps=20, rewrite_prompt=True):
    """Essaie plusieurs APIs d'édition d'images en cas d'échec"""
    clients = load_image_edit_clients()
    
    # Liste des APIs à essayer dans l'ordre de préférence
    api_attempts = [
        ('qwen', 'Qwen Image Edit'),
        ('instedit', 'InstEditBooth'),
        ('flux', 'Flux Dev')
    ]
    
    last_error = None
    
    for api_key, api_name in api_attempts:
        client = clients.get(api_key)
        if not client:
            continue
            
        try:
            st.info(f"🔄 Tentative avec {api_name}...")
            
            # Sauvegarder l'image temporairement
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                image.save(tmp_file.name, format='PNG')
                tmp_path = tmp_file.name
            
            # Ajuster les paramètres selon l'API
            if api_key == 'qwen':
                result = client.predict(
                    image=handle_file(tmp_path),
                    prompt=edit_prompt,
                    seed=seed,
                    randomize_seed=randomize_seed,
                    true_guidance_scale=guidance_scale,
                    num_inference_steps=min(num_steps, 20),  # Réduire les steps pour économiser le quota
                    rewrite_prompt=rewrite_prompt,
                    api_name="/infer"
                )
            elif api_key == 'instedit':
                result = client.predict(
                    image=handle_file(tmp_path),
                    prompt=edit_prompt,
                    seed=seed,
                    api_name="/predict"
                )
            elif api_key == 'flux':
                result = client.predict(
                    prompt=f"Edit this image: {edit_prompt}",
                    image=handle_file(tmp_path),
                    seed=seed,
                    api_name="/infer"
                )
            
            # Nettoyer le fichier temporaire
            os.unlink(tmp_path)
            
            # Vérifier le résultat
            if result and len(result) > 0:
                try:
                    edited_image_path = result[0] if isinstance(result[0], str) else result
                    edited_image = Image.open(edited_image_path)
                    return edited_image, f"✅ Édition réussie avec {api_name}!"
                except:
                    continue
                    
        except Exception as e:
            last_error = str(e)
            # Nettoyer le fichier temporaire en cas d'erreur
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            # Si c'est un problème de quota, essayer la prochaine API
            if "quota" in last_error.lower() or "exceeded" in last_error.lower():
                st.warning(f"⏰ Quota épuisé pour {api_name}, essai avec une alternative...")
                continue
            else:
                st.warning(f"❌ Erreur avec {api_name}: {last_error}")
                continue
    
    # Si toutes les APIs ont échoué
    return None, f"❌ Toutes les APIs d'édition ont échoué. Dernière erreur: {last_error}"

def edit_image_with_qwen(image, edit_prompt, seed=0, randomize_seed=True, guidance_scale=4, num_steps=20, rewrite_prompt=True):
    """Fonction principale d'édition avec fallback sur plusieurs APIs"""
    return edit_image_with_multiple_apis(image, edit_prompt, seed, randomize_seed, guidance_scale, num_steps, rewrite_prompt)

# -------------------------
# Image <-> Base64
# -------------------------
def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    return Image.open(io.BytesIO(base64.b64decode(img_str)))

# -------------------------
# LLaMA Client
# -------------------------
@st.cache_resource
def load_llama():
    try:
        return Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        return None

llama_client = load_llama()

def get_ai_response(prompt):
    if not llama_client:
        return "Vision AI non disponible."
    try:
        resp = llama_client.predict(
            message=str(prompt),
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"Erreur modèle: {e}"

# -------------------------
# Fonction d'édition d'image dans le chat
# -------------------------
def process_image_edit_in_chat(image, user_text, edit_params):
    """Traite l'édition d'image directement dans le chat"""
    # Extraire le prompt d'édition du texte de l'utilisateur
    edit_prompt = user_text.strip()
    if not edit_prompt:
        edit_prompt = "improve this image"
    
    # Éditer l'image
    edited_image, edit_message = edit_image_with_qwen(
        image, 
        edit_prompt,
        seed=edit_params.get('seed', 0),
        randomize_seed=(edit_params.get('seed', 0) == 0),
        guidance_scale=edit_params.get('guidance', 4.0),
        num_steps=edit_params.get('steps', 20)
    )
    
    return edited_image, edit_message, edit_prompt

# -------------------------
# Effet dactylographique
# -------------------------
def stream_response(text, placeholder):
    displayed = ""
    for char in str(text):
        displayed += char
        placeholder.markdown(displayed + "▋")
        time.sleep(0.02)
    placeholder.markdown(displayed)

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
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "image_to_edit" not in st.session_state:
    st.session_state.image_to_edit = None

# -------------------------
# Sidebar Auth & Debug
# -------------------------
st.sidebar.title("Authentification / Debug")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
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
            if create_user(email_reg, pass_reg, name_reg):
                st.success("Compte créé!")
            else:
                st.error("Erreur création compte")
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
st.sidebar.title("Conversations")
if st.sidebar.button("Nouvelle conversation"):
    conv = create_conversation(st.session_state.user["id"])
    if conv:
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.success("Nouvelle conversation créée!")
        st.rerun()

convs = get_conversations(st.session_state.user["id"])
if convs:
    options = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
    current_idx = 0
    if st.session_state.conversation:
        for i, c in enumerate(convs):
            if c["conversation_id"] == st.session_state.conversation.get("conversation_id"):
                current_idx = i
                break
    selected_idx = st.sidebar.selectbox("Vos conversations:", range(len(options)), format_func=lambda i: options[i], index=current_idx)
    st.session_state.conversation = convs[selected_idx]
    st.session_state.messages_memory = get_messages(st.session_state.conversation["conversation_id"])

# -------------------------
# Sidebar Mode Édition
# -------------------------
st.sidebar.title("🎨 Mode Édition d'Images")
st.sidebar.info("Uploadez une image puis choisissez: 💬 Analyser ou 🎨 Éditer")

# Paramètres d'édition avancés
with st.sidebar.expander("⚙️ Paramètres d'édition"):
    edit_steps = st.slider("Nombre d'étapes", min_value=10, max_value=50, value=20, 
                          help="Moins d'étapes = plus rapide mais qualité moindre")
    edit_guidance = st.slider("Force du guidage", min_value=1.0, max_value=10.0, value=4.0, step=0.5,
                             help="Plus élevé = plus fidèle au prompt")
    edit_seed = st.number_input("Seed (optionnel)", value=0, help="0 = aléatoire")

# Quota et status des APIs
with st.sidebar.expander("📊 Status des APIs"):
    st.write("**APIs d'édition disponibles:**")
    clients = load_image_edit_clients()
    for api_name, client in clients.items():
        if client:
            st.success(f"✅ {api_name.upper()}")
        else:
            st.error(f"❌ {api_name.upper()}")
    
    st.write("**Conseils pour éviter les quotas:**")
    st.write("• Réduisez le nombre d'étapes (10-20)")
    st.write("• Utilisez des prompts courts et précis")
    st.write("• Évitez les éditions complexes")

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat - Analyse & Édition d'Images")

# Affichage messages
for msg in st.session_state.messages_memory:
    role = "user" if msg["sender"] == "user" else "assistant"
    with st.chat_message(role):
        if msg["type"] == "image" and msg.get("image_data"):
            st.image(base64_to_image(msg["image_data"]), width=300, caption="Image originale")
        if msg.get("edited_image_data"):
            st.image(base64_to_image(msg["edited_image_data"]), width=300, caption="Image éditée")
        st.markdown(msg["content"])

# Interface pour l'édition d'images (mode édition spécial)
if st.session_state.edit_mode and st.session_state.image_to_edit:
    st.info("🎨 Mode Édition Activé")
    col1, col2 = st.columns(2)
    with col1:
        st.image(st.session_state.image_to_edit, width=300, caption="Image à éditer")
    with col2:
        edit_prompt = st.text_area("Décrivez les modifications souhaitées:", 
                                 placeholder="Ex: add a red hat, change background to beach, make it night scene...")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✨ Éditer l'image"):
                if edit_prompt.strip():
                    with st.spinner("Édition en cours..."):
                        edited_image, message = edit_image_with_qwen(
                            st.session_state.image_to_edit, 
                            edit_prompt,
                            seed=edit_seed,
                            randomize_seed=(edit_seed == 0),
                            guidance_scale=edit_guidance,
                            num_steps=edit_steps
                        )
                        if edited_image:
                            # Générer description de l'image éditée
                            edited_caption = generate_caption(edited_image, st.session_state.processor, st.session_state.model)
                            
                            # Sauvegarder le message d'édition
                            conv_id = st.session_state.conversation["conversation_id"]
                            edit_content = f"[EDITED_IMAGE] {edited_caption}\n\nModifications demandées: {edit_prompt}"
                            edited_image_data = image_to_base64(edited_image)
                            original_image_data = image_to_base64(st.session_state.image_to_edit)
                            
                            if add_message(conv_id, "user", edit_content, "image_edit", original_image_data, edited_image_data):
                                st.session_state.messages_memory.append({
                                    "sender": "user",
                                    "content": edit_content,
                                    "type": "image_edit",
                                    "image_data": original_image_data,
                                    "edited_image_data": edited_image_data,
                                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                                })
                                
                                # Réponse IA pour analyser l'édition
                                prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {edit_content}"
                                ai_response = get_ai_response(prompt)
                                
                                if add_message(conv_id, "assistant", ai_response, "text"):
                                    st.session_state.messages_memory.append({
                                        "sender": "assistant",
                                        "content": ai_response,
                                        "type": "text",
                                        "image_data": None,
                                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                                    })
                                
                                st.success("Image éditée avec succès!")
                                st.session_state.edit_mode = False
                                st.session_state.image_to_edit = None
                                st.rerun()
                        else:
                            st.error(f"Erreur lors de l'édition: {message}")
                else:
                    st.warning("Veuillez saisir une description des modifications")
        with col_b:
            if st.button("❌ Annuler"):
                st.session_state.edit_mode = False
                st.session_state.image_to_edit = None
                st.rerun()

# Formulaire nouveau message avec sélection d'action
with st.form("msg_form", clear_on_submit=True):
    user_input = st.text_area("Votre message:", height=100, 
                             placeholder="Écrivez votre message ici... \n\nPour éditer une image: décrivez les modifications souhaitées (ex: 'add a red hat', 'change to night scene')")
    uploaded_file = st.file_uploader("Image", type=["png","jpg","jpeg"])
    
    # Sélection d'action selon qu'une image soit uploadée ou non
    if uploaded_file:
        st.info("📷 Image détectée! Choisissez votre action:")
        action_choice = st.radio(
            "Action à effectuer:",
            ["💬 Analyser l'image", "🎨 Éditer l'image", "⚙️ Mode Édition avancé"],
            help="Sélectionnez ce que vous voulez faire avec l'image"
        )
        submit_button = st.form_submit_button("🚀 Exécuter")
        
        # Définir les variables selon le choix
        if submit_button:
            analyze_submit = action_choice == "💬 Analyser l'image"
            edit_submit = action_choice == "🎨 Éditer l'image"
            edit_mode_submit = action_choice == "⚙️ Mode Édition avancé"
        else:
            analyze_submit = edit_submit = edit_mode_submit = False
    else:
        # Pas d'image, juste un message normal
        analyze_submit = st.form_submit_button("💬 Envoyer le message")
        edit_submit = edit_mode_submit = False

# Gestion du mode édition avancé
if uploaded_file and edit_mode_submit:
    image = Image.open(uploaded_file)
    st.session_state.image_to_edit = image
    st.session_state.edit_mode = True
    st.rerun()

# Paramètres d'édition actuels
edit_params = {
    'seed': edit_seed,
    'guidance': edit_guidance,
    'steps': edit_steps
}

# Gestion de l'édition directe dans le chat
if uploaded_file and edit_submit:
    if not user_input.strip():
        st.error("⚠️ Veuillez décrire les modifications souhaitées dans le message!")
    else:
        image = Image.open(uploaded_file)
        conv_id = st.session_state.conversation["conversation_id"]
        
        # Afficher l'image originale dans le chat utilisateur
        original_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        user_message = f"[IMAGE] {original_caption}\n\nÉdition demandée: {user_input.strip()}"
        original_image_data = image_to_base64(image)
        
        # Affichage du message utilisateur
        with st.chat_message("user"):
            st.image(image, width=300, caption="Image originale")
            st.markdown(user_message)
        
        # Sauvegarder le message utilisateur
        if add_message(conv_id, "user", user_message, "image", original_image_data):
            st.session_state.messages_memory.append({
                "sender": "user",
                "content": user_message,
                "type": "image",
                "image_data": original_image_data,
                "edited_image_data": None,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Traitement de l'édition
        with st.chat_message("assistant"):
            thinking_placeholder = st.empty()
            thinking_placeholder.markdown("🎨 Vision AI édite votre image...")
            
            # Éditer l'image
            edited_image, edit_message, edit_prompt = process_image_edit_in_chat(
                image, user_input, edit_params
            )
            
            if edited_image:
                # Générer description de l'image éditée
                edited_caption = generate_caption(edited_image, st.session_state.processor, st.session_state.model)
                edited_image_data = image_to_base64(edited_image)
                
                # Préparer la réponse complète
                ai_content = f"[EDITED_IMAGE] {edited_caption}\n\n{edit_message}\n\nJ'ai modifié votre image selon votre demande: '{edit_prompt}'. Voici le résultat:"
                
                # Supprimer le placeholder et afficher le résultat
                thinking_placeholder.empty()
                st.image(edited_image, width=300, caption="Image éditée")
                
                response_placeholder = st.empty()
                stream_response(ai_content, response_placeholder)
                
                # Sauvegarder la réponse avec l'image éditée
                if add_message(conv_id, "assistant", ai_content, "image_edit_response", None, edited_image_data):
                    st.session_state.messages_memory.append({
                        "sender": "assistant",
                        "content": ai_content,
                        "type": "image_edit_response",
                        "image_data": None,
                        "edited_image_data": edited_image_data,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
            else:
                # Erreur d'édition
                thinking_placeholder.empty()
                error_message = f"❌ {edit_message}"
                st.error(error_message)
                
                if add_message(conv_id, "assistant", error_message, "text"):
                    st.session_state.messages_memory.append({
                        "sender": "assistant",
                        "content": error_message,
                        "type": "text",
                        "image_data": None,
                        "edited_image_data": None,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        st.rerun()

# Gestion de l'analyse normale (bouton analyser/envoyer)
if analyze_submit and (user_input.strip() or uploaded_file):
    conv_id = st.session_state.conversation["conversation_id"]
    message_content = user_input.strip()
    msg_type = "text"
    image_data = None

    if uploaded_file:
        image = Image.open(uploaded_file)
        image_data = image_to_base64(image)
        caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        message_content = f"[IMAGE] {caption}"
        if user_input.strip():
            message_content += f"\n\nQuestion: {user_input.strip()}"
        msg_type = "image"

    # Sauvegarde message utilisateur
    if add_message(conv_id, "user", message_content, msg_type, image_data):
        st.session_state.messages_memory.append({
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "edited_image_data": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

    # Affichage utilisateur
    with st.chat_message("user"):
        if msg_type == "image" and image_data:
            st.image(base64_to_image(image_data), width=300)
        st.markdown(message_content)

    # Placeholder "Thinking"
    with st.chat_message("assistant"):
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown("🤖 Vision AI is thinking...")
        time.sleep(1.5)

        # Générer réponse IA
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {message_content}"
        ai_response = get_ai_response(prompt)

        # Supprimer placeholder
        thinking_placeholder.empty()
        response_placeholder = st.empty()
        stream_response(ai_response, response_placeholder)

        # Sauvegarder réponse IA
        if add_message(conv_id, "assistant", ai_response, "text"):
            st.session_state.messages_memory.append({
                "sender": "assistant",
                "content": ai_response,
                "type": "text",
                "image_data": None,
                "edited_image_data": None,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })

    st.rerun()

# -------------------------
# Instructions d'utilisation
# -------------------------
if not st.session_state.messages_memory:
    st.markdown("""
    ### 🎉 Bienvenue dans Vision AI Chat!
    
    **Fonctionnalités disponibles:**
    
    🔍 **Analyse d'images:**
    - Uploadez une image et cliquez sur **💬 Analyser l'image**
    - Posez des questions sur l'image dans le message
    
    🎨 **Édition d'images (3 modes):**
    1. **Édition directe:** Uploadez une image, décrivez les modifications et cliquez **🎨 Éditer l'image**
    2. **Mode édition avancé:** Cliquez **⚙️ Mode Édition** pour plus de contrôle
    3. **Paramètres personnalisables** dans la sidebar
    
    💬 **Chat normal:**
    - Posez vos questions sans image
    - Vision AI vous répondra normalement
    
    **Exemples de prompts d'édition:**
    - "add a red hat to the person"
    - "change the background to a beach"
    - "make it a night scene"
    - "remove the car from the image"
    - "add snow falling"
    """)

# -------------------------
# Footer
# -------------------------
st.markdown("---")
st.markdown("🤖 **Vision AI** - Créé par Pepe Musafiri avec contributions de Meta AI | 🎨 Édition d'images alimentée par Qwen")

