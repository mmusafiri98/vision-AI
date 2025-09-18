import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat", layout="wide")
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
# Utility functions
# -------------------------
def image_to_base64(image):
    """Convertir une image PIL en base64 pour la stockage"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return img_str
    except:
        return None

def base64_to_image(img_str):
    """Convertir base64 en image PIL"""
    try:
        img_bytes = base64.b64decode(img_str)
        return Image.open(io.BytesIO(img_bytes))
    except:
        return None

# -------------------------
# BLIP loader
# -------------------------
@st.cache_resource
def load_blip():
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return processor, model
    except Exception as e:
        st.error(f"Erreur BLIP: {e}")
        return None, None

def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Description indisponible"
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"Erreur génération: {e}"

# -------------------------
# Session init
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossible de connecter LLaMA.")

# -------------------------
# AI functions
# -------------------------
def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return "❌ Vision AI non disponible."
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
        return f"❌ Erreur modèle: {e}"

def stream_response(text, placeholder):
    """Animation de frappe pour afficher le texte caractère par caractère"""
    full_text = ""
    text_str = str(text)
    
    # Phases d'animation
    # 1. Afficher "En train d'écrire..."
    thinking_messages = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_messages:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.3)
    
    # 2. Animation de frappe caractère par caractère
    for i, char in enumerate(text_str):
        full_text += char
        # Afficher avec curseur clignotant stylisé
        display_text = full_text + "**█**"
        placeholder.markdown(display_text)
        
        # Vitesse variable : plus rapide pour les espaces, plus lent pour la ponctuation
        if char == ' ':
            time.sleep(0.01)
        elif char in '.,!?;:':
            time.sleep(0.1)
        else:
            time.sleep(0.03)
    
    # 3. Afficher le texte final proprement
    placeholder.markdown(full_text)
    
    # 4. Petit effet de fin
    time.sleep(0.2)
    placeholder.markdown(full_text + " ✅")
    time.sleep(0.5)
    placeholder.markdown(full_text)

# -------------------------
# Auth
# -------------------------
st.sidebar.title("🔐 Authentification")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    with tab1:
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Se connecter"):
                user_result = db.verify_user(email, password)
                if user_result:
                    st.session_state.user = user_result
                    st.session_state.conversation = None
                    st.session_state.messages_memory = []
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Email ou mot de passe invalide")
        with col2:
            if st.button("👤 Mode invité"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.session_state.conversation = None
                st.session_state.messages_memory = []
                st.rerun()
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        if st.button("✨ Créer mon compte"):
            if email_reg and name_reg and pass_reg:
                ok = db.create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Compte créé, connecte-toi.")
                else:
                    st.error("Erreur création compte")
    st.stop()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    
    # Bouton déconnexion
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    if st.sidebar.button("➕ Nouvelle conversation"):
        conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.rerun()

    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            options = ["Choisir une conversation..."] + [f"{c['description']} - {c['created_at']}" for c in convs]
            sel = st.sidebar.selectbox("📋 Vos conversations:", options)
            if sel != "Choisir une conversation...":
                idx = options.index(sel) - 1
                selected_conv = convs[idx]
                if st.session_state.conversation != selected_conv:
                    st.session_state.conversation = selected_conv
                    st.session_state.messages_memory = []
                    st.rerun()
        else:
            st.sidebar.info("Aucune conversation. Créez-en une.")
    except Exception as e:
        st.sidebar.error(f"Erreur chargement conversations: {e}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Créé par <b>Pepe Musafiri</b> (Ingénieur IA) avec la contribution de <b>Meta AI</b></p>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

# -------------------------
# Afficher les messages existants
# -------------------------
display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    try:
        db_msgs = db.get_messages(conv_id)
        for m in db_msgs:
            display_msgs.append({
                "sender": m["sender"], 
                "content": m["content"], 
                "created_at": m["created_at"], 
                "type": m.get("type", "text"),
                "image_data": m.get("image_data", None)
            })
    except Exception as e:
        st.error(f"Erreur chargement messages: {e}")
else:
    display_msgs = st.session_state.messages_memory.copy()

# Afficher l'historique des messages
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        # Si c'est un message avec image
        if m.get("type") == "image":
            # Afficher l'image si elle existe
            if m.get("image_data"):
                try:
                    # Reconstituer l'image depuis base64
                    img = base64_to_image(m["image_data"])
                    if img:
                        st.image(img, caption="Image analysée", width=300)
                    else:
                        st.write("📷 Image (non disponible)")
                except:
                    st.write("📷 Image (erreur d'affichage)")
            else:
                st.write("📷 Image uploadée")
            
            # Afficher la description si elle existe dans le contenu
            if "[IMAGE]" in m["content"]:
                description = m["content"].replace("[IMAGE] ", "").split("\n\nQuestion/Demande")[0]
                st.write(f"*Description automatique: {description}*")
                
                # Afficher la question utilisateur si elle existe
                if "Question/Demande de l'utilisateur:" in m["content"]:
                    user_question = m["content"].split("Question/Demande de l'utilisateur: ")[1]
                    st.write(f"**Question:** {user_question}")
        else:
            # Message texte normal
            st.markdown(m["content"])

# -------------------------
# Conteneur pour les nouveaux messages
# -------------------------
message_container = st.container()

# -------------------------
# Formulaire de saisie unifié
# -------------------------
with st.form(key="chat_form", clear_on_submit=True):
    # Upload d'image (optionnel)
    uploaded_file = st.file_uploader("📷 Ajouter une image (optionnel)", type=["png","jpg","jpeg"], key="image_upload")
    
    # Champ de texte principal
    user_input = st.text_area(
        "💭 Tapez votre message...", 
        key="user_message", 
        placeholder="Posez votre question ou décrivez ce que vous voulez que j'analyse dans l'image...",
        height=80
    )
    
    # Bouton d'envoi unique
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

# -------------------------
# Traitement unifié
# -------------------------
if submit_button and (user_input or uploaded_file is not None):
    
    # Variables pour construire le message complet
    full_message = ""
    image_caption = ""
    image_base64 = None
    
    # Traitement de l'image si présente
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            
            # Convertir l'image en base64 pour stockage
            image_base64 = image_to_base64(image)
            
            # Afficher l'image uploadée dans le chat
            with message_container:
                with st.chat_message("user"):
                    st.image(image, caption="Image uploadée pour analyse", width=300)
            
            # Générer la description de l'image
            with st.spinner("Analyse de l'image en cours..."):
                image_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            
            # Construire le message avec image
            full_message = f"[IMAGE] {image_caption}"
            if user_input.strip():
                full_message += f"\n\nQuestion/Demande de l'utilisateur: {user_input}"
                # Afficher aussi la question dans le chat
                with message_container:
                    with st.chat_message("user"):
                        st.write(f"**Question:** {user_input}")
            
            # Sauvegarder le message image avec texte
            conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
            if conv_id:
                # Supposons que votre fonction db.add_message accepte un paramètre image_data
                # Si ce n'est pas le cas, vous devrez modifier votre base de données
                try:
                    db.add_message(conv_id, "user", full_message, "image", image_data=image_base64)
                except:
                    # Fallback si la DB ne supporte pas image_data
                    db.add_message(conv_id, "user", full_message, "image")
            else:
                st.session_state.messages_memory.append({
                    "sender": "user", 
                    "content": full_message, 
                    "created_at": None,
                    "type": "image",
                    "image_data": image_base64
                })
                
        except Exception as e:
            st.error(f"Erreur lors du traitement de l'image: {e}")
            full_message = user_input if user_input else ""
    
    # Si pas d'image, juste le texte
    elif user_input.strip():
        full_message = user_input
        
        # Afficher le message utilisateur
        with message_container:
            with st.chat_message("user"):
                st.markdown(user_input)
        
        # Sauvegarder le message texte
        conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
        if conv_id:
            db.add_message(conv_id, "user", user_input, "text")
        else:
            st.session_state.messages_memory.append({
                "sender": "user", 
                "content": user_input, 
                "created_at": None,
                "type": "text"
            })

    # Générer la réponse AI si on a un message
    if full_message:
        prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
        
        with message_container:
            with st.chat_message("assistant"):
                # Créer un placeholder pour l'animation
                response_placeholder = st.empty()
                response_placeholder.write("Vision AI réfléchit... 🤔")
                
                # Obtenir la réponse
                resp = get_ai_response(prompt)
                
                # Animer la réponse caractère par caractère
                stream_response(resp, response_placeholder)

        # Sauvegarder la réponse
        conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
        if conv_id:
            db.add_message(conv_id, "assistant", resp, "text")
        else:
            st.session_state.messages_memory.append({
                "sender": "assistant", 
                "content": resp, 
                "created_at": None,
                "type": "text"
            })
        
        st.rerun()

# Message d'aide
st.markdown("---")
st.info("💡 **Comment utiliser Vision AI:**\n"
        "• **Texte seul:** Posez vos questions normalement\n"
        "• **Image seule:** Uploadez une image, elle sera analysée automatiquement\n"
        "• **Image + Texte:** Uploadez une image ET écrivez votre question pour une analyse ciblée")

# -------------------------
# Export CSV
# -------------------------
if display_msgs:
    st.markdown("---")
    with st.expander("📂 Exporter la conversation"):
        # Créer une version propre pour l'export (sans les données image base64)
        export_msgs = []
        for m in display_msgs:
            export_msg = {
                "sender": m["sender"],
                "content": m["content"],
                "created_at": m["created_at"],
                "type": m.get("type", "text"),
                "has_image": "Oui" if m.get("image_data") else "Non"
            }
            export_msgs.append(export_msg)
        
        df = pd.DataFrame(export_msgs)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        conv_id_for_file = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else "invite"
        st.download_button(
            "💾 Télécharger la conversation (CSV)",
            csv_buffer.getvalue(),
            file_name=f"conversation_{conv_id_for_file}.csv",
            mime="text/csv",
            use_container_width=True
        )
