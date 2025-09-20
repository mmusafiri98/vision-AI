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
# Debug sessione AVANCÉ
# -------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 🐞 Debug Sessione")
st.sidebar.text(f"user: {st.session_state.get('user')}")
st.sidebar.text(f"conversation actuelle: {st.session_state.get('conversation')}")
if st.session_state.get('conversation'):
    current_conv_id = st.session_state.conversation.get('conversation_id')
    st.sidebar.text(f"conversation_id: {current_conv_id}")
    
    # DEBUG CRITIQUE: Test direct de la fonction get_messages
    st.sidebar.markdown("**🔍 Test Direct DB:**")
    try:
        # Test direct de la fonction db.get_messages
        direct_messages = db.get_messages(current_conv_id)
        st.sidebar.text(f"db.get_messages() retourne: {type(direct_messages)}")
        
        if direct_messages is None:
            st.sidebar.error("❌ db.get_messages() retourne None")
        elif direct_messages == []:
            st.sidebar.warning("⚠️ db.get_messages() retourne liste vide []")
        else:
            st.sidebar.success(f"✅ db.get_messages() retourne {len(direct_messages)} messages")
            
            # Afficher les détails des premiers messages
            for i, msg in enumerate(direct_messages[:2]):
                st.sidebar.text(f"Msg {i+1}: {msg}")
                
        # Test de requête SQL directe si possible
        st.sidebar.markdown("**🔧 Test SQL Direct:**")
        
        # Afficher la structure probable de votre table messages
        st.sidebar.text("Structure attendue table 'messages':")
        st.sidebar.text("- conversation_id (FK)")
        st.sidebar.text("- sender")
        st.sidebar.text("- content")
        st.sidebar.text("- type")
        st.sidebar.text("- created_at")
        
    except Exception as e:
        st.sidebar.error(f"❌ Erreur test DB: {e}")
        st.sidebar.text(f"Erreur détaillée: {str(e)}")

st.sidebar.text(f"messages_memory: {len(st.session_state.get('messages_memory', []))} messages")

# Debug détaillé des messages en mémoire
if st.session_state.messages_memory:
    st.sidebar.markdown("**Messages en mémoire:**")
    for i, msg in enumerate(st.session_state.messages_memory[:3]):
        sender = msg.get('sender', 'unknown')
        content_preview = msg.get('content', '')[:30] + "..." if len(msg.get('content', '')) > 30 else msg.get('content', '')
        st.sidebar.text(f"{i+1}. {sender}: {content_preview}")
else:
    st.sidebar.warning("🚫 Aucun message en mémoire de session")

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
                if not email or not password:
                    st.error("⚠️ Veuillez remplir email et mot de passe")
                else:
                    with st.spinner("🔄 Connexion en cours..."):
                        user_result = db.verify_user(email, password)
                        
                        if user_result:
                            st.session_state.user = user_result
                            st.success(f"✅ Connecté en tant que {user_result.get('name', user_result.get('email'))}")
                            
                            # Debug Supabase: tester la connexion
                            try:
                                if hasattr(db, 'supabase') and db.supabase:
                                    st.info("🟢 Supabase connecté")
                                else:
                                    st.warning("🟡 Supabase potentiellement déconnecté")
                                    
                                # Charger les conversations
                                all_convs = db.get_conversations(user_result["id"])
                                st.info(f"📊 {len(all_convs) if all_convs else 0} conversations trouvées")
                                
                                if all_convs:
                                    # Prendre la première conversation (plus récente)
                                    first_conv = all_convs[0]
                                    st.session_state.conversation = first_conv
                                    conv_id = first_conv.get("conversation_id")
                                    
                                    st.info(f"🔄 Chargement conversation: {first_conv.get('description')} ({conv_id})")
                                    
                                    # Charger les messages avec debug Supabase
                                    try:
                                        messages = db.get_messages(conv_id)
                                        st.info(f"📨 get_messages() retourne {len(messages) if messages else 0} messages")
                                        
                                        if messages:
                                            st.session_state.messages_memory = messages
                                            st.success(f"✅ {len(messages)} messages chargés!")
                                            
                                            # Afficher aperçu des messages
                                            for i, msg in enumerate(messages[:2]):
                                                sender = msg.get('sender', 'unknown')
                                                content = msg.get('content', '')[:50] + "..."
                                                st.write(f"Message {i+1}: {sender} - {content}")
                                        else:
                                            st.session_state.messages_memory = []
                                            st.warning(f"⚠️ Aucun message dans cette conversation")
                                            
                                            # Test direct Supabase
                                            try:
                                                if db.supabase:
                                                    test_response = db.supabase.table("messages").select("*").eq("conversation_id", conv_id).execute()
                                                    st.info(f"🔍 Test Supabase direct: {len(test_response.data)} messages trouvés")
                                                    if test_response.data:
                                                        st.write("Premiers messages trouvés:")
                                                        for msg in test_response.data[:2]:
                                                            st.write(f"- {msg.get('sender')}: {msg.get('content', '')[:30]}...")
                                            except Exception as direct_e:
                                                st.error(f"❌ Test Supabase direct échoué: {direct_e}")
                                                
                                    except Exception as msg_e:
                                        st.error(f"❌ Erreur chargement messages: {msg_e}")
                                        st.session_state.messages_memory = []
                                else:
                                    st.session_state.conversation = None
                                    st.session_state.messages_memory = []
                                    st.info("ℹ️ Aucune conversation trouvée - créez en une nouvelle!")
                                    
                            except Exception as conv_e:
                                st.error(f"❌ Erreur chargement conversations: {conv_e}")
                                st.session_state.conversation = None
                                st.session_state.messages_memory = []
                            
                            # Attendre pour voir les messages de debug
                            time.sleep(3)
                            st.rerun()
                        else:
                            st.error("❌ Email ou mot de passe invalide")
                            st.info("💡 Vérifiez vos identifiants ou créez un nouveau compte")
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
            
            # BOUTON DE TEST MANUEL AVANCÉ
            if st.sidebar.button("🔄 Test Complet DB", help="Diagnostic complet de la base de données"):
                if st.session_state.conversation:
                    test_conv_id = st.session_state.conversation.get("conversation_id")
                    st.sidebar.info(f"🔍 Test pour conversation: {test_conv_id}")
                    
                    try:
                        # 1. Test de la fonction get_messages
                        st.sidebar.markdown("**1️⃣ Test db.get_messages():**")
                        test_messages = db.get_messages(test_conv_id)
                        st.sidebar.write(f"Type retourné: {type(test_messages)}")
                        st.sidebar.write(f"Contenu: {test_messages}")
                        
                        # 2. Test de connection DB directe (si possible)
                        st.sidebar.markdown("**2️⃣ Test Connection DB:**")
                        try:
                            # Essayons d'accéder à la connection directement
                            if hasattr(db, 'conn') or hasattr(db, 'connection'):
                                conn = getattr(db, 'conn', None) or getattr(db, 'connection', None)
                                if conn:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s", (test_conv_id,))
                                    count = cursor.fetchone()[0]
                                    st.sidebar.write(f"Messages trouvés en DB: {count}")
                                    
                                    if count > 0:
                                        cursor.execute("SELECT sender, content, created_at FROM messages WHERE conversation_id = %s LIMIT 3", (test_conv_id,))
                                        sample_messages = cursor.fetchall()
                                        st.sidebar.write("Échantillon messages:")
                                        for msg in sample_messages:
                                            st.sidebar.write(f"- {msg[0]}: {msg[1][:30]}... ({msg[2]})")
                                    cursor.close()
                                else:
                                    st.sidebar.error("Connection DB non accessible")
                            else:
                                st.sidebar.warning("Attribut connection non trouvé dans le module db")
                                
                        except Exception as conn_error:
                            st.sidebar.error(f"Erreur connection directe: {conn_error}")
                        
                        # 3. Test avec différents types de conversation_id
                        st.sidebar.markdown("**3️⃣ Test Types de Données:**")
                        st.sidebar.write(f"conversation_id type: {type(test_conv_id)}")
                        st.sidebar.write(f"conversation_id value: '{test_conv_id}'")
                        
                        # Test avec string explicite
                        try:
                            test_messages_str = db.get_messages(str(test_conv_id))
                            st.sidebar.write(f"Test avec str(): {len(test_messages_str) if test_messages_str else 0} messages")
                        except Exception as str_error:
                            st.sidebar.error(f"Erreur test string: {str_error}")
                        
                        # 4. Si on a des messages, les charger
                        if test_messages:
                            st.session_state.messages_memory = test_messages
                            st.sidebar.success(f"✅ {len(test_messages)} messages rechargés!")
                            st.rerun()
                        else:
                            st.sidebar.error("❌ Aucun message trouvé malgré le diagnostic")
                            
                    except Exception as e:
                        st.sidebar.error(f"❌ Erreur diagnostic: {e}")
                        st.sidebar.write(f"Erreur complète: {str(e)}")
                else:
                    st.sidebar.warning("⚠️ Aucune conversation sélectionnée")
            
            # Test de Connection Supabase
            if st.sidebar.button("🔌 Test Supabase", help="Teste la connexion à Supabase"):
                try:
                    if hasattr(db, 'supabase') and db.supabase:
                        st.sidebar.success("✅ Client Supabase connecté")
                        
                        # Test des tables
                        for table_name in ["users", "conversations", "messages"]:
                            try:
                                response = db.supabase.table(table_name).select("*").limit(1).execute()
                                st.sidebar.write(f"✅ Table {table_name}: OK ({len(response.data)} exemples)")
                            except Exception as table_e:
                                st.sidebar.error(f"❌ Table {table_name}: {table_e}")
                        
                        # Test avec votre conversation actuelle
                        if st.session_state.conversation:
                            conv_id = st.session_state.conversation.get("conversation_id")
                            try:
                                msg_response = db.supabase.table("messages").select("*").eq("conversation_id", conv_id).execute()
                                st.sidebar.info(f"📊 Messages pour cette conversation: {len(msg_response.data)}")
                                
                                if msg_response.data:
                                    st.sidebar.write("Premiers messages:")
                                    for i, msg in enumerate(msg_response.data[:2]):
                                        sender = msg.get('sender', 'unknown')
                                        content = msg.get('content', '')[:25] + "..."
                                        st.sidebar.write(f"{i+1}. {sender}: {content}")
                            except Exception as conv_e:
                                st.sidebar.error(f"❌ Test conversation: {conv_e}")
                    else:
                        st.sidebar.error("❌ Supabase non connecté")
                        
                        # Vérifier les variables d'environnement
                        import os
                        supabase_url = os.environ.get("SUPABASE_URL")
                        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
                        
                        st.sidebar.write(f"SUPABASE_URL: {'✅ Défini' if supabase_url else '❌ Manquant'}")
                        st.sidebar.write(f"SUPABASE_SERVICE_KEY: {'✅ Défini' if supabase_key else '❌ Manquant'}")
                        
                except Exception as e:
                    st.sidebar.error(f"❌ Erreur test Supabase: {e}")
                if st.session_state.conversation:
                    conv_id = st.session_state.conversation.get("conversation_id")
                    st.sidebar.write(f"🔍 Test pour conversation: {conv_id}")
                    
                    try:
                        # Essayer d'accéder à la connection DB
                        conn = None
                        if hasattr(db, 'conn'):
                            conn = db.conn
                        elif hasattr(db, 'connection'):
                            conn = db.connection
                        elif hasattr(db, 'get_connection'):
                            conn = db.get_connection()
                        else:
                            st.sidebar.error("❌ Impossible de trouver la connection DB dans le module 'db'")
                            st.sidebar.write("Attributs disponibles dans db:")
                            st.sidebar.write([attr for attr in dir(db) if not attr.startswith('_')])
                        
                        if conn:
                            cursor = conn.cursor()
                            
                            # Test 1: Compter TOUS les messages
                            try:
                                cursor.execute("SELECT COUNT(*) FROM messages")
                                total_count = cursor.fetchone()[0]
                                st.sidebar.write(f"📊 Total messages en DB: {total_count}")
                            except Exception as e:
                                st.sidebar.error(f"Erreur count total: {e}")
                            
                            # Test 2: Compter pour cette conversation
                            try:
                                cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s", (conv_id,))
                                conv_count = cursor.fetchone()[0]
                                st.sidebar.write(f"📊 Messages pour cette conversation: {conv_count}")
                            except Exception as e:
                                # Essayer avec SQLite syntax
                                try:
                                    cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (conv_id,))
                                    conv_count = cursor.fetchone()[0]
                                    st.sidebar.write(f"📊 Messages (SQLite syntax): {conv_count}")
                                except Exception as e2:
                                    st.sidebar.error(f"Erreur count conversation: {e} | {e2}")
                            
                            # Test 3: Voir quelques conversation_id existants
                            try:
                                cursor.execute("SELECT DISTINCT conversation_id FROM messages LIMIT 5")
                                existing_convs = cursor.fetchall()
                                st.sidebar.write("📋 Conversation IDs en DB:")
                                for conv_row in existing_convs:
                                    st.sidebar.write(f"- {conv_row[0]}")
                            except Exception as e:
                                st.sidebar.error(f"Erreur liste conversations: {e}")
                            
                            cursor.close()
                        
                    except Exception as e:
                        st.sidebar.error(f"❌ Erreur test SQL: {e}")
                        st.sidebar.write(f"Type d'erreur: {type(e).__name__}")
                else:
                    st.sidebar.warning("⚠️ Aucune conversation sélectionnée")
            
            # Bouton pour voir les attributs du module db
            if st.sidebar.button("🔍 Voir module DB", help="Affiche les attributs du module db"):
                st.sidebar.write("**Attributs du module db:**")
                db_attrs = [attr for attr in dir(db) if not attr.startswith('_')]
                for attr in db_attrs:
                    try:
                        attr_type = type(getattr(db, attr)).__name__
                        st.sidebar.write(f"- {attr}: {attr_type}")
                    except:
                        st.sidebar.write(f"- {attr}: (inaccessible)")
                
                # Essayer de voir le code de get_messages
                try:
                    import inspect
                    if hasattr(db, 'get_messages'):
                        source_code = inspect.getsource(db.get_messages)
                        st.sidebar.code(source_code[:500] + "..." if len(source_code) > 500 else source_code, language="python")
                except Exception as e:
                    st.sidebar.error(f"Code get_messages non accessible: {e}")
            
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
