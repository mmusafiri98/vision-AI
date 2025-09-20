import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import time
import pandas as pd
import io
import base64
import db  # ton module DB Supabase corrigé

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Vision AI Chat - Debug", layout="wide")

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
# DEBUG: Vérification Supabase au démarrage
# -------------------------
@st.cache_resource
def check_supabase_connection():
    """Test initial de Supabase"""
    if hasattr(db, 'supabase') and db.supabase:
        try:
            # Test simple
            response = db.supabase.table("users").select("*").limit(1).execute()
            return True, "Connexion Supabase OK"
        except Exception as e:
            return False, f"Erreur test Supabase: {e}"
    else:
        return False, "Client Supabase non initialisé"

# Test de connexion au démarrage
supabase_ok, supabase_msg = check_supabase_connection()
if not supabase_ok:
    st.error(f"🔴 PROBLEME SUPABASE: {supabase_msg}")
else:
    st.success(f"🟢 {supabase_msg}")

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

def load_last_conversation(user_id):
    """Charge la dernière conversation avec debug"""
    st.info(f"🔍 load_last_conversation: Recherche pour user_id = {user_id}")
    
    if user_id == "guest":
        st.info("👤 Mode invité - pas de conversation à charger")
        return None
    
    try:
        convs = db.get_conversations(user_id)
        st.info(f"📊 get_conversations retourné: {len(convs) if convs else 0} conversations")
        
        if convs:
            last_conv = convs[0]
            st.success(f"✅ Dernière conversation trouvée: {last_conv.get('description', 'Sans titre')}")
            return last_conv
        else:
            st.warning("⚠️ Aucune conversation trouvée pour cet utilisateur")
            return None
            
    except Exception as e:
        st.error(f"❌ Erreur load_last_conversation: {e}")
        return None

def load_conversation_messages(conversation):
    """Charge les messages d'une conversation avec debug détaillé"""
    if not conversation:
        st.warning("⚠️ load_conversation_messages: Pas de conversation fournie")
        return []
    
    conv_id = conversation.get("conversation_id") or conversation.get("id")
    st.info(f"🔍 load_conversation_messages: conversation_id = {conv_id}")
    
    if not conv_id:
        st.error("❌ load_conversation_messages: conversation_id manquant dans l'objet conversation")
        st.write("🔍 Clés disponibles dans conversation:", list(conversation.keys()))
        return []
    
    try:
        # Test direct de la fonction get_messages
        st.info("🔄 Appel de db.get_messages()...")
        messages = db.get_messages(conv_id)
        
        st.info(f"📨 db.get_messages() a retourné: {type(messages)} avec {len(messages) if messages else 0} éléments")
        
        if messages:
            st.success(f"✅ {len(messages)} messages chargés avec succès")
            
            # Afficher un aperçu des messages
            st.info("👀 Aperçu des messages chargés:")
            for i, msg in enumerate(messages[:3]):
                sender = msg.get('sender', 'unknown')
                content = msg.get('content', '')
                preview = content[:50] + "..." if len(content) > 50 else content
                st.write(f"  {i+1}. {sender}: {preview}")
                
            return messages
        else:
            st.warning(f"⚠️ Aucun message trouvé pour conversation_id: {conv_id}")
            
            # Test de debug Supabase direct
            if hasattr(db, 'supabase') and db.supabase:
                try:
                    st.info("🔍 Test Supabase direct...")
                    direct_response = db.supabase.table("messages").select("*").eq("conversation_id", conv_id).execute()
                    direct_count = len(direct_response.data) if direct_response.data else 0
                    
                    if direct_count > 0:
                        st.error(f"🚨 PROBLEME DETECTE: {direct_count} messages existent en DB mais get_messages() retourne vide!")
                        st.write("Premiers messages en DB:")
                        for msg in direct_response.data[:2]:
                            st.write(f"- {msg.get('sender')}: {msg.get('content', '')[:50]}...")
                    else:
                        st.info("ℹ️ Confirmé: Aucun message en DB pour cette conversation")
                        
                except Exception as direct_e:
                    st.error(f"❌ Test Supabase direct échoué: {direct_e}")
            
            return []
        
    except Exception as e:
        st.error(f"❌ Erreur load_conversation_messages: {e}")
        import traceback
        st.code(traceback.format_exc(), language="python")
        return []

def save_active_conversation(user_id, conv_id):
    """Placeholder si besoin de stocker active conv"""
    pass

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
# Initialisation session avec debug
# -------------------------
st.sidebar.markdown("### 🐞 Debug Session State")

# Initialisation des variables de session
if "user" not in st.session_state:
    st.session_state.messages_memory.append(ai_message)
    st.info("✅ Réponse IA ajoutée à la mémoire de session")
    
    # Test de vérification - recharger les messages depuis la DB
    st.info("🔍 Vérification: rechargement messages depuis DB...")
    
    try:
        verification_messages = db.get_messages(conv_id)
        db_count = len(verification_messages) if verification_messages else 0
        session_count = len(st.session_state.messages_memory)
        
        st.info(f"📊 Messages en DB: {db_count}, Messages en session: {session_count}")
        
        if db_count != session_count:
            st.warning(f"⚠️ DÉSYNCHRONISATION DÉTECTÉE: DB={db_count}, Session={session_count}")
            
            # Option de synchronisation
            if st.button("🔄 Forcer synchronisation DB → Session"):
                st.session_state.messages_memory = verification_messages
                st.success("✅ Synchronisation forcée")
                st.rerun()
        else:
            st.success("✅ DB et session synchronisées")
            
    except Exception as verif_e:
        st.error(f"❌ Erreur vérification: {verif_e}")
    
    # Attendre un peu pour voir les messages de debug
    time.sleep(2)
    st.rerun()

# -------------------------
# Export et outils debug
# -------------------------
if st.session_state.messages_memory:
    st.markdown("---")
    
    with st.expander("📊 Export & Debug Tools"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💾 Export")
            
            # Préparer les données pour l'export
            export_data = []
            for i, msg in enumerate(st.session_state.messages_memory):
                export_data.append({
                    "index": i + 1,
                    "sender": msg.get("sender", "unknown"),
                    "content": msg.get("content", ""),
                    "type": msg.get("type", "text"),
                    "has_image": "Oui" if msg.get("image_data") else "Non",
                    "created_at": msg.get("created_at", "")
                })
            
            if export_data:
                df = pd.DataFrame(export_data)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                
                conv_name = st.session_state.conversation.get("description", "conversation") if st.session_state.conversation else "messages"
                filename = f"{conv_name}_debug_{int(time.time())}.csv"
                
                st.download_button(
                    "📥 Télécharger CSV",
                    csv_buffer.getvalue(),
                    file_name=filename,
                    mime="text/csv"
                )
                
                st.info(f"📊 {len(export_data)} messages prêts à exporter")
        
        with col2:
            st.subheader("🔧 Debug Actions")
            
            # Bouton force reload messages
            if st.button("🔄 Force Reload Messages"):
                if st.session_state.conversation:
                    conv_id = st.session_state.conversation.get("conversation_id") or st.session_state.conversation.get("id")
                    try:
                        fresh_messages = db.get_messages(conv_id)
                        st.session_state.messages_memory = fresh_messages or []
                        st.success(f"✅ {len(st.session_state.messages_memory)} messages rechargés")
                        st.rerun()
                    except Exception as reload_e:
                        st.error(f"❌ Erreur rechargement: {reload_e}")
                else:
                    st.warning("⚠️ Aucune conversation active")
            
            # Bouton clear session
            if st.button("🗑️ Clear Session"):
                st.session_state.messages_memory = []
                st.session_state.conversation = None
                st.session_state.conversation_loaded = False
                st.success("✅ Session nettoyée")
                st.rerun()
            
            # Bouton test complet DB
            if st.button("🧪 Test Complet DB"):
                try:
                    st.write("🔍 Test connexion Supabase...")
                    
                    if hasattr(db, 'supabase') and db.supabase:
                        # Test tables
                        tables = ["users", "conversations", "messages"]
                        for table in tables:
                            try:
                                response = db.supabase.table(table).select("*").limit(1).execute()
                                st.write(f"✅ Table {table}: OK")
                            except Exception as t_e:
                                st.write(f"❌ Table {table}: {t_e}")
                        
                        # Test données utilisateur
                        user_id = st.session_state.user.get("id")
                        if user_id != "guest":
                            user_convs = db.supabase.table("conversations").select("*").eq("user_id", user_id).execute()
                            st.write(f"📊 Conversations utilisateur: {len(user_convs.data)}")
                            
                            if st.session_state.conversation:
                                conv_id = st.session_state.conversation.get("conversation_id") or st.session_state.conversation.get("id")
                                conv_messages = db.supabase.table("messages").select("*").eq("conversation_id", conv_id).execute()
                                st.write(f"📨 Messages conversation actuelle: {len(conv_messages.data)}")
                    else:
                        st.error("❌ Client Supabase non disponible")
                        
                except Exception as test_e:
                    st.error(f"❌ Erreur test: {test_e}")

# -------------------------
# Informations système en footer
# -------------------------
st.markdown("---")
st.markdown("### 🔧 Informations Système")

info_col1, info_col2, info_col3 = st.columns(3)

with info_col1:
    st.markdown("**Base de Données**")
    supabase_status = "🟢 Connecté" if supabase_ok else "🔴 Déconnecté"
    st.write(f"Supabase: {supabase_status}")
    
    if hasattr(db, 'supabase') and db.supabase:
        st.write("Client: ✅ Disponible")
    else:
        st.write("Client: ❌ Non disponible")

with info_col2:
    st.markdown("**Session Utilisateur**")
    st.write(f"ID: {st.session_state.user.get('id', 'N/A')}")
    st.write(f"Email: {st.session_state.user.get('email', 'N/A')}")
    st.write(f"Connecté: {'✅' if st.session_state.user.get('id') != 'guest' else '❌'}")

with info_col3:
    st.markdown("**État Application**")
    st.write(f"Conversation: {'✅' if st.session_state.conversation else '❌'}")
    st.write(f"Messages: {len(st.session_state.messages_memory)}")
    st.write(f"BLIP: {'✅' if st.session_state.get('processor') else '❌'}")
    st.write(f"LLaMA: {'✅' if st.session_state.get('llama_client') else '❌'}")

# Debug final - log dans la console
print(f"\n=== DEBUG FINAL SESSION ===")
print(f"User ID: {st.session_state.user.get('id')}")
print(f"Conversation: {st.session_state.conversation.get('description') if st.session_state.conversation else None}")
print(f"Messages count: {len(st.session_state.messages_memory)}")
print(f"Conversation loaded: {st.session_state.conversation_loaded}")
print(f"Supabase OK: {supabase_ok}")
print("=" * 30)user = {"id": "guest", "email": "Invité"}
    st.sidebar.info("🔄 user initialisé")

if "conversation" not in st.session_state:
    st.session_state.conversation = None
    st.sidebar.info("🔄 conversation initialisée")

if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
    st.sidebar.info("🔄 messages_memory initialisé")

if "conversation_loaded" not in st.session_state:
    st.session_state.conversation_loaded = False
    st.sidebar.info("🔄 conversation_loaded initialisé")

# Affichage debug état actuel
st.sidebar.write(f"👤 User: {st.session_state.user.get('email', 'N/A')}")
st.sidebar.write(f"💬 Conversation: {st.session_state.conversation.get('description') if st.session_state.conversation else 'None'}")
st.sidebar.write(f"📨 Messages en mémoire: {len(st.session_state.messages_memory)}")
st.sidebar.write(f"🔄 Conversation chargée: {st.session_state.conversation_loaded}")

# BLIP et LLaMA
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
    st.sidebar.info("🔄 BLIP chargé")

if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
        st.sidebar.success("✅ LLaMA connecté")
    except Exception as e:
        st.session_state.llama_client = None
        st.sidebar.error(f"❌ LLaMA non connecté: {e}")

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
    thinking_msgs = ["🤔 Vision AI réfléchit", "💭 Vision AI analyse", "✨ Vision AI génère une réponse"]
    for msg in thinking_msgs:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.2)
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "**█**")
        time.sleep(0.01 if char==' ' else 0.03)
    placeholder.markdown(full_text + " ✅")

# -------------------------
# Authentification avec debug
# -------------------------
st.sidebar.title("🔐 Authentification")

def login_ui():
    tab1, tab2 = st.sidebar.tabs(["Connexion", "Inscription"])
    
    with tab1:
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Se connecter"):
                st.info(f"🔍 Tentative de connexion pour: {email}")
                
                if not email or not password:
                    st.error("⚠️ Email et mot de passe requis")
                else:
                    try:
                        with st.spinner("🔄 Vérification des identifiants..."):
                            user_result = db.verify_user(email, password)
                        
                        st.info(f"🔍 verify_user() résultat: {user_result}")
                        
                        if user_result:
                            # Mise à jour de la session
                            st.session_state.user = user_result
                            st.session_state.conversation_loaded = False
                            
                            st.success(f"✅ Connexion réussie pour {user_result.get('name', email)}")
                            st.info("🔄 Rechargement de l'application...")
                            
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Email ou mot de passe invalide")
                            
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la connexion: {e}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")
        
        with col2:
            if st.button("👤 Mode invité"):
                st.info("🔄 Passage en mode invité")
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.session_state.conversation = None
                st.session_state.messages_memory = []
                st.session_state.conversation_loaded = False
                st.rerun()
    
    with tab2:
        email_reg = st.text_input("📧 Email", key="reg_email")
        name_reg = st.text_input("👤 Nom complet", key="reg_name")
        pass_reg = st.text_input("🔒 Mot de passe", type="password", key="reg_password")
        
        if st.button("✨ Créer mon compte"):
            if email_reg and name_reg and pass_reg:
                st.info(f"🔍 Création compte pour: {email_reg}")
                
                try:
                    with st.spinner("🔄 Création du compte..."):
                        ok = db.create_user(email_reg, pass_reg, name_reg)
                    
                    st.info(f"🔍 create_user() résultat: {ok}")
                    
                    if ok:
                        st.success("✅ Compte créé avec succès! Vous pouvez vous connecter.")
                    else:
                        st.error("❌ Erreur lors de la création du compte")
                        
                except Exception as e:
                    st.error(f"❌ Exception création compte: {e}")
                    import traceback
                    st.code(traceback.format_exc(), language="python")
            else:
                st.warning("⚠️ Tous les champs sont requis")
    
    st.stop()

if st.session_state.user["id"] == "guest":
    login_ui()
else:
    st.sidebar.success(f"✅ Connecté: {st.session_state.user.get('email')}")
    
    # Bouton déconnexion
    if st.sidebar.button("🚪 Se déconnecter"):
        st.info("🔄 Déconnexion en cours...")
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.session_state.conversation_loaded = False
        st.rerun()

# -------------------------
# DEBUG: Boutons de test
# -------------------------
st.sidebar.markdown("### 🧪 Tests Debug")

if st.sidebar.button("🔍 Test DB Connection"):
    if hasattr(db, 'test_connection'):
        result = db.test_connection()
        st.sidebar.write(f"Test connexion: {result}")
    else:
        st.sidebar.error("Fonction test_connection non disponible")

if st.sidebar.button("📊 Stats DB"):
    if hasattr(db, 'get_database_stats'):
        db.get_database_stats()
    else:
        st.sidebar.error("Fonction get_database_stats non disponible")

if st.session_state.conversation and st.sidebar.button("🔬 Debug Conversation"):
    conv_id = st.session_state.conversation.get("conversation_id") or st.session_state.conversation.get("id")
    if hasattr(db, 'debug_conversation_messages'):
        db.debug_conversation_messages(conv_id)
    else:
        st.sidebar.error("Fonction debug_conversation_messages non disponible")

# Bouton reset Supabase
if st.sidebar.button("🔄 Reset Supabase"):
    if hasattr(db, 'reset_supabase_client'):
        result = db.reset_supabase_client()
        st.sidebar.write(f"Reset Supabase: {result}")
    else:
        st.sidebar.error("Fonction reset_supabase_client non disponible")

# -------------------------
# Chargement dernière conversation et messages avec debug
# -------------------------
if st.session_state.user["id"] != "guest" and not st.session_state.conversation_loaded:
    st.info("🔄 Chargement automatique de la dernière conversation...")
    
    # Charger la dernière conversation
    last_conv = load_last_conversation(st.session_state.user["id"])
    
    if last_conv:
        st.session_state.conversation = last_conv
        
        # Charger les messages avec debug détaillé
        st.info("🔄 Chargement des messages de la conversation...")
        messages = load_conversation_messages(last_conv)
        st.session_state.messages_memory = messages
        
        # Confirmation
        st.success(f"✅ Conversation chargée: {len(st.session_state.messages_memory)} messages")
    else:
        st.info("ℹ️ Aucune conversation précédente - interface prête pour nouvelle conversation")
    
    st.session_state.conversation_loaded = True
    
    # Pause pour voir les messages de debug
    time.sleep(2)
    st.rerun()

# -------------------------
# Sidebar conversations avec debug
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("💬 Mes Conversations")
    
    # Nouvelle conversation
    if st.sidebar.button("➕ Nouvelle conversation"):
        st.sidebar.info("🔄 Création nouvelle conversation...")
        
        try:
            conv = db.create_conversation(st.session_state.user["id"], "Nouvelle discussion")
            st.sidebar.info(f"🔍 create_conversation() résultat: {conv}")
            
            if conv:
                st.session_state.conversation = conv
                st.session_state.messages_memory = []
                st.sidebar.success("✅ Nouvelle conversation créée")
                st.rerun()
            else:
                st.sidebar.error("❌ Échec création conversation")
                
        except Exception as e:
            st.sidebar.error(f"❌ Erreur création conversation: {e}")
    
    # Liste des conversations
    try:
        convs = db.get_conversations(st.session_state.user["id"])
        st.sidebar.info(f"📊 Conversations disponibles: {len(convs) if convs else 0}")
        
        if convs:
            # Créer la liste des options
            options = ["Choisir une conversation..."]
            for c in convs:
                desc = c.get('description', 'Sans titre')
                date = c.get('created_at', '')[:16] if c.get('created_at') else 'N/A'
                options.append(f"{desc} - {date}")
            
            # Selectbox
            sel = st.sidebar.selectbox("Vos conversations:", options)
            
            if sel != "Choisir une conversation...":
                idx = options.index(sel) - 1
                selected_conv = convs[idx]
                
                st.sidebar.info(f"🔍 Conversation sélectionnée: {selected_conv.get('description')}")
                
                # Vérifier si c'est une nouvelle sélection
                current_conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
                selected_conv_id = selected_conv.get("conversation_id") or selected_conv.get("id")
                
                if current_conv_id != selected_conv_id:
                    st.sidebar.info("🔄 Changement de conversation détecté")
                    
                    # Mettre à jour la conversation
                    st.session_state.conversation = selected_conv
                    
                    # Charger les messages avec debug
                    st.sidebar.info("🔄 Chargement messages...")
                    messages = load_conversation_messages(selected_conv)
                    st.session_state.messages_memory = messages
                    
                    st.sidebar.success(f"✅ {len(messages)} messages chargés")
                    st.rerun()
        else:
            st.sidebar.info("ℹ️ Aucune conversation existante")
            
    except Exception as e:
        st.sidebar.error(f"❌ Erreur chargement conversations: {e}")

# -------------------------
# Header
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2E8B57;'>🤖 Vision AI Chat - Mode Debug</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connecté en tant que: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

if st.session_state.conversation:
    conv_title = st.session_state.conversation.get('description','Conversation sans titre')
    conv_id_short = (st.session_state.conversation.get('conversation_id') or st.session_state.conversation.get('id') or 'N/A')[:8]
    st.markdown(f"<p style='text-align:center; color:#4CAF50; font-weight:bold;'>📝 {conv_title} ({conv_id_short})</p>", unsafe_allow_html=True)

# Afficher statistiques actuelles
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📨 Messages", len(st.session_state.messages_memory))
with col2:
    st.metric("💬 Conversation", "Active" if st.session_state.conversation else "Aucune")
with col3:
    st.metric("🔗 Supabase", "OK" if supabase_ok else "KO")

st.markdown("---")

# -------------------------
# Affichage messages
# -------------------------
if st.session_state.messages_memory:
    st.info(f"💬 Affichage de {len(st.session_state.messages_memory)} messages:")
    
    message_container = st.container()
    
    for i, m in enumerate(st.session_state.messages_memory):
        role = "user" if m.get("sender") == "user" else "assistant"
        
        with message_container:
            with st.chat_message(role):
                # Debug info message
                with st.expander(f"🔍 Debug Message {i+1}", expanded=False):
                    st.write(f"Sender: {m.get('sender')}")
                    st.write(f"Type: {m.get('type')}")
                    st.write(f"Created: {m.get('created_at')}")
                    st.write(f"Has image: {'Yes' if m.get('image_data') else 'No'}")
                
                # Affichage image si présente
                if m.get("type") == "image" and m.get("image_data"):
                    try:
                        st.image(base64_to_image(m["image_data"]), width=300)
                    except Exception as img_e:
                        st.error(f"Erreur affichage image: {img_e}")
                
                # Contenu du message
                content = m.get("content", "")
                if content:
                    st.markdown(content)
                else:
                    st.warning("Message sans contenu")
else:
    st.info("💭 Aucun message dans cette conversation. Commencez à écrire!")

# -------------------------
# Formulaire message avec debug
# -------------------------
st.markdown("---")
st.subheader("📝 Nouveau Message")

with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_area(
            "💭 Tapez votre message...", 
            height=80,
            placeholder="Posez votre question ou décrivez ce que vous voulez analyser..."
        )
    
    with col2:
        uploaded_file = st.file_uploader(
            "📷 Image", 
            type=["png","jpg","jpeg"]
        )
    
    submit_button = st.form_submit_button("📤 Envoyer", use_container_width=True)

# Traitement du message avec debug complet
if submit_button and (user_input.strip() or uploaded_file):
    st.info("🔄 Traitement du nouveau message...")
    
    # Vérifier qu'on a une conversation
    if not st.session_state.conversation:
        st.error("❌ Aucune conversation active - création automatique...")
        
        try:
            new_conv = db.create_conversation(st.session_state.user["id"], "Discussion automatique")
            if new_conv:
                st.session_state.conversation = new_conv
                st.success(f"✅ Nouvelle conversation créée: {new_conv.get('conversation_id')}")
            else:
                st.error("❌ Impossible de créer une conversation")
                st.stop()
        except Exception as e:
            st.error(f"❌ Erreur création conversation: {e}")
            st.stop()
    
    # Récupérer l'ID de conversation
    conv_id = st.session_state.conversation.get("conversation_id") or st.session_state.conversation.get("id")
    st.info(f"🔍 Conversation ID utilisé: {conv_id}")
    
    # Préparer le message
    full_message = user_input.strip()
    image_base64 = None
    msg_type = "text"
    
    # Traitement de l'image
    if uploaded_file:
        st.info("🖼️ Traitement de l'image uploadée...")
        
        try:
            image = Image.open(uploaded_file)
            image_base64 = image_to_base64(image)
            
            # Génération caption
            with st.spinner("🤖 Analyse de l'image..."):
                caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            
            st.info(f"🔍 Caption générée: {caption}")
            
            full_message = f"[IMAGE] {caption}"
            if user_input.strip():
                full_message += f"\n\nQuestion: {user_input.strip()}"
            
            msg_type = "image"
            
        except Exception as img_e:
            st.error(f"❌ Erreur traitement image: {img_e}")
            st.stop()
    
    if not full_message.strip():
        st.warning("⚠️ Message vide - annulation")
        st.stop()
    
    st.info(f"📝 Message final: {full_message[:100]}...")
    st.info(f"🔍 Type: {msg_type}, Image: {'Oui' if image_base64 else 'Non'}")
    
    # Sauvegarder le message utilisateur en DB
    if conv_id:
        st.info("💾 Sauvegarde message utilisateur en DB...")
        
        try:
            save_success = db.add_message(conv_id, "user", full_message, msg_type, image_data=image_base64)
            st.info(f"🔍 db.add_message() résultat: {save_success}")
            
            if not save_success:
                st.error("❌ Échec sauvegarde message utilisateur")
        except Exception as save_e:
            st.error(f"❌ Erreur sauvegarde message: {save_e}")
    
    # Ajouter à la mémoire de session
    user_message = {
        "sender": "user",
        "content": full_message,
        "type": msg_type,
        "image_data": image_base64,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    st.session_state.messages_memory.append(user_message)
    st.info("✅ Message ajouté à la mémoire de session")
    
    # Affichage du message utilisateur
    with st.chat_message("user"):
        if msg_type == "image" and image_base64:
            st.image(base64_to_image(image_base64), width=300)
        st.markdown(full_message)
    
    # Génération de la réponse IA
    st.info("🤖 Génération de la réponse IA...")
    
    prompt = f"{SYSTEM_PROMPT}\n\nUtilisateur: {full_message}"
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        
        try:
            with st.spinner("🤔 Vision AI réfléchit..."):
                resp = get_ai_response(prompt)
            
            st.info(f"🔍 Réponse IA générée: {len(resp)} caractères")
            
            # Animation de la réponse
            stream_response(resp, placeholder)
            
        except Exception as ai_e:
            resp = f"❌ Erreur génération réponse: {ai_e}"
            placeholder.markdown(resp)
    
    # Sauvegarder la réponse IA en DB
    if conv_id:
        st.info("💾 Sauvegarde réponse IA en DB...")
        
        try:
            ai_save_success = db.add_message(conv_id, "assistant", resp, "text")
            st.info(f"🔍 Sauvegarde IA résultat: {ai_save_success}")
            
            if not ai_save_success:
                st.error("❌ Échec sauvegarde réponse IA")
        except Exception as ai_save_e:
            st.error(f"❌ Erreur sauvegarde réponse IA: {ai_save_e}")
    
    # Ajouter la réponse à la mémoire de session
    ai_message = {
        "sender": "assistant",
        "content": resp,
        "type": "text",
        "image_data": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    st.session_state.

