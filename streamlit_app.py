import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # tuo modulo DB

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
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(img_str):
    img_bytes = base64.b64decode(img_str)
    return Image.open(io.BytesIO(img_bytes))

def load_user_last_conversation(user_id):
    convs = db.get_conversations(user_id)
    return convs[0] if convs else None

def save_active_conversation(user_id, conv_id):
    pass  # placeholder

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
    full_text = ""
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "**█**")
        time.sleep(0.01 if char == ' ' else 0.03)
    placeholder.markdown(full_text + " ✅")

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
# Debug sessione
# -------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 🐞 Debug Sessione")
st.sidebar.text(f"user: {st.session_state.get('user')}")
st.sidebar.text(f"conversation actuelle: {st.session_state.get('conversation')}")
if st.session_state.get('conversation'):
    st.sidebar.text(f"conversation_id: {st.session_state.conversation.get('conversation_id')}")
st.sidebar.text(f"messages_memory: {len(st.session_state.get('messages_memory', []))} messages")

# Debug détaillé des messages
if st.session_state.messages_memory:
    st.sidebar.markdown("**Messages en mémoire:**")
    for i, msg in enumerate(st.session_state.messages_memory[:3]):
        sender = msg.get('sender', 'unknown')
        content_preview = msg.get('content', '')[:30] + "..." if len(msg.get('content', '')) > 30 else msg.get('content', '')
        st.sidebar.text(f"{i+1}. {sender}: {content_preview}")

if st.session_state.user["id"] != "guest":
    try:
        convs = db.get_conversations(st.session_state.user["id"]) or []
        st.sidebar.text(f"Conversations totales DB: {len(convs)}")
        for i, c in enumerate(convs):
            is_current = st.session_state.conversation and c['conversation_id'] == st.session_state.conversation.get('conversation_id')
            marker = " ← ACTUELLE" if is_current else ""
            st.sidebar.text(f"{i+1}: {c['description']} ({c['conversation_id'][:8]}) - {c['created_at'][:16]}{marker}")
    except Exception as e:
        st.sidebar.text(f"Erreur chargement DB conversations: {e}")
st.sidebar.markdown("---")

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
                    last_conv = load_user_last_conversation(user_result["id"])
                    st.session_state.conversation = last_conv
                    if last_conv:
                        conv_id = last_conv.get("conversation_id")
                        try:
                            messages = db.get_messages(conv_id)
                            st.session_state.messages_memory = messages or []
                            st.success(f"Connexion réussie! {len(st.session_state.messages_memory)} messages chargés.")
                        except Exception as e:
                            st.error(f"Erreur chargement messages: {e}")
                            st.session_state.messages_memory = []
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
    if st.sidebar.button("🚪 Se déconnecter"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Sidebar Conversations - VERSION CORRIGÉE
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    
    # Bouton nouvelle conversation
    if st.sidebar.button("➕ Nouvelle conversation"):
        try:
            conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
            if conv:
                st.session_state.conversation = conv
                st.session_state.messages_memory = []
                st.success("Nouvelle conversation créée!")
                st.rerun()
            else:
                st.error("Impossible de créer une nouvelle conversation")
        except Exception as e:
            st.error(f"Erreur création conversation: {e}")
    
    try:
        # Charger toutes les conversations
        convs = db.get_conversations(st.session_state.user["id"]) or []
        
        if convs:
            # Créer le mapping conversation -> texte d'affichage
            conv_mapping = {}
            options = []
            
            # Trier les conversations par date de création (plus récente en premier)
            convs_sorted = sorted(convs, key=lambda x: x.get('created_at', ''), reverse=True)
            
            for conv in convs_sorted:
                # Créer le texte d'affichage
                description = conv.get('description', 'Sans titre')
                created_at = conv.get('created_at', '')[:16]  # Prendre seulement date et heure
                display_text = f"{description} - {created_at}"
                
                options.append(display_text)
                conv_mapping[display_text] = conv
            
            # Trouver l'index de la conversation actuelle
            current_index = 0
            if st.session_state.conversation:
                current_conv_id = st.session_state.conversation.get("conversation_id")
                for i, conv in enumerate(convs_sorted):
                    if conv.get("conversation_id") == current_conv_id:
                        current_index = i
                        break
            
            # Selectbox avec les conversations
            selected_display = st.sidebar.selectbox(
                "📋 Choisir une conversation:",
                options,
                index=current_index,
                key="conv_selector"
            )
            
            # Charger la conversation sélectionnée
            if selected_display and selected_display in conv_mapping:
                selected_conv = conv_mapping[selected_display]
                selected_conv_id = selected_conv.get("conversation_id")
                
                # Vérifier si on a changé de conversation
                current_conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
                
                if selected_conv_id != current_conv_id:
                    st.sidebar.info(f"🔄 Changement vers: {selected_conv.get('description', 'Sans titre')}")
                    
                    # Mettre à jour la conversation
                    st.session_state.conversation = selected_conv
                    
                    # Charger les messages de cette conversation
                    try:
                        messages = db.get_messages(selected_conv_id)
                        st.session_state.messages_memory = messages or []
                        
                        # Message de confirmation
                        msg_count = len(st.session_state.messages_memory)
                        st.sidebar.success(f"✅ {msg_count} messages chargés")
                        
                        # Debug des messages chargés
                        if messages:
                            st.sidebar.markdown("**Messages chargés:**")
                            for i, msg in enumerate(messages[:2]):
                                sender = msg.get('sender', 'unknown')
                                content = msg.get('content', '')[:25] + "..." if len(msg.get('content', '')) > 25 else msg.get('content', '')
                                st.sidebar.text(f"• {sender}: {content}")
                        
                        st.rerun()
                        
                    except Exception as e:
                        st.sidebar.error(f"❌ Erreur chargement messages: {e}")
                        st.session_state.messages_memory = []
        
        else:
            st.sidebar.info("Aucune conversation trouvée. Créez-en une nouvelle!")
            
    except Exception as e:
        st.sidebar.error(f"❌ Erreur chargement conversations: {e}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description', 'Conversation sans titre')
    conv_id_short = st.session_state.conversation.get('conversation_id', '')[:8]
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title} ({conv_id_short})</p>", unsafe_allow_html=True)

# -------------------------
# Affichage messages
# -------------------------
st.markdown("---")

# Afficher le nombre de messages
if st.session_state.messages_memory:
    st.markdown(f"**💬 {len(st.session_state.messages_memory)} messages dans cette conversation**")
else:
    st.markdown("**💭 Aucun message dans cette conversation. Commencez à écrire!**")

# Afficher les messages
display_msgs = st.session_state.messages_memory.copy() if st.session_state.messages_memory else []

for i, m in enumerate(display_msgs):
    role = "user" if m["sender"] in ["user", "user_api_request"] else "assistant"
    
    with st.chat_message(role):
        # Afficher l'image si présente
        if m.get("type") == "image" and m.get("image_data"):
            try:
                img = base64_to_image(m["image_data"])
                if img:
                    st.image(img, width=300, caption=f"Image du message {i+1}")
            except Exception as e:
                st.error(f"Erreur affichage image: {e}")
        
        # Afficher le contenu du message
        content = m.get("content", "")
        if content:
            st.markdown(content)
        else:
            st.markdown("*[Message vide]*")

# -------------------------
# Nouveau message
# -------------------------
st.markdown("---")
message_container = st.container()

with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_area(
            "💭 Tapez votre message...", 
            key="user_message", 
            placeholder="Posez votre question ou décrivez ce que vous voulez que j'analyse dans l'image...",
            height=100
        )
    
    with col2:
        uploaded_file = st.file_uploader(
            "📷 Image", 
            type=["png", "jpg", "jpeg"], 
            key="image_upload"
        )
    
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

# Traitement du message
if submit_button and (user_input.strip() or uploaded_file):
    # Vérifier qu'on a une conversation active
    if not st.session_state.conversation:
        st.error("❌ Aucune conversation active. Créez ou sélectionnez une conversation.")
        st.stop()
    
    conv_id = st.session_state.conversation.get("conversation_id")
    full_message = ""
    image_base64 = None
    image_caption = ""

    # Traitement de l'image
    if uploaded_file:
        try:
            image = Image.open(uploaded_file)
            image_base64 = image_to_base64(image)
            
            # Afficher l'image uploadée
            with message_container:
                with st.chat_message("user"):
                    st.image(image, caption="Image uploadée pour analyse", width=300)
            
            # Générer la description de l'image
            image_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            full_message = f"[IMAGE] {image_caption}"
            
            if user_input.strip():
                full_message += f"\n\nQuestion: {user_input.strip()}"
                
        except Exception as e:
            st.error(f"❌ Erreur traitement image: {e}")
            st.stop()
    else:
        full_message = user_input.strip()

    if full_message:
        try:
            # Sauvegarder le message utilisateur
            if conv_id:
                db.add_message(conv_id, "user", full_message, "image" if image_base64 else "text", image_data=image_base64)
            
            # Ajouter à la mémoire de session
            st.session_state.messages_memory.append({
                "sender": "user",
                "content": full_message,
                "type": "image" if image_base64 else "text",
                "image_data": image_base64
            })

            # Générer la réponse IA
            prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
            
            with message_container:
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    response_placeholder.write("🤔 Vision AI réfléchit...")
                    
                    try:
                        resp = get_ai_response(prompt)
                        stream_response(resp, response_placeholder)
                        
                        # Sauvegarder la réponse
                        if conv_id:
                            db.add_message(conv_id, "assistant", resp, "text")
                        
                        # Ajouter à la mémoire de session
                        st.session_state.messages_memory.append({
                            "sender": "assistant",
                            "content": resp,
                            "type": "text",
                            "image_data": None
                        })
                        
                    except Exception as e:
                        error_msg = f"❌ Erreur génération réponse: {e}"
                        response_placeholder.write(error_msg)
                        
                        # Sauvegarder l'erreur
                        if conv_id:
                            db.add_message(conv_id, "assistant", error_msg, "text")
                        
                        st.session_state.messages_memory.append({
                            "sender": "assistant",
                            "content": error_msg,
                            "type": "text",
                            "image_data": None
                        })
            
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Erreur traitement message: {e}")

# -------------------------
# Export CSV
# -------------------------
if display_msgs:
    st.markdown("---")
    with st.expander("📂 Exporter la conversation"):
        export_msgs = []
        for i, m in enumerate(display_msgs):
            export_msgs.append({
                "index": i+1,
                "sender": m.get("sender", "unknown"),
                "content": m.get("content", ""),
                "type": m.get("type", "text"),
                "has_image": "Oui" if m.get("image_data") else "Non",
                "timestamp": m.get("created_at", "")
            })
        
        df = pd.DataFrame(export_msgs)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        
        conv_id_for_file = st.session_state.conversation.get("conversation_id", "invite")[:8]
        conv_name = st.session_state.conversation.get("description", "conversation") if st.session_state.conversation else "invite"
        filename = f"{conv_name}_{conv_id_for_file}.csv"
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "💾 Télécharger (CSV)",
                csv_buffer.getvalue(),
                file_name=filename,
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            st.info(f"📊 {len(export_msgs)} messages à exporter")
