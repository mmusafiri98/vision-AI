import os
import streamlit as st
from supabase import create_client

# --------------------------
# Initialisation de Supabase
# --------------------------
@st.cache_resource
def init_supabase():
    """Initialise le client Supabase et l'admin client."""
    try:
        supabase_url = os.environ["SUPABASE_URL"]
        supabase_anon_key = os.environ["SUPABASE_ANON_KEY"]
        supabase_service_key = os.environ["SUPABASE_SERVICE_KEY"]

        client = create_client(supabase_url, supabase_anon_key)
        admin = create_client(supabase_url, supabase_service_key)
        return client, admin
    except KeyError as e:
        st.error(f"Erreur de configuration: la variable d'environnement {e} est manquante.")
        st.stop()

client, admin = init_supabase()

# --------------------------
# Fonctions d'authentification
# --------------------------
def verify_user(email, password):
    """Vérifie les identifiants de l'utilisateur et renvoie l'objet utilisateur."""
    try:
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response.user
    except Exception as e:
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            st.error("❌ Email non confirmé.")
        elif "Invalid login credentials" in error_msg:
            st.error("❌ Email ou mot de passe incorrect.")
        else:
            st.error(f"❌ Erreur lors de la connexion: {error_msg}")
        return None

def create_user(email, password, name=None):
    """Crée un nouvel utilisateur avec confirmation automatique de l'email."""
    try:
        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "name": name or ""
            }
        })
        if response.user:
            return response.user
        else:
            raise Exception("Aucun utilisateur n'a été créé.")
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg:
            st.error("❌ Cette adresse email est déjà utilisée.")
        else:
            st.error(f"❌ Erreur de création de compte: {error_msg}")
        return None

# --------------------------
# Fonctions de gestion des conversations et messages
# --------------------------
def create_conversation(user_id, title):
    """Crée une nouvelle conversation pour l'utilisateur."""
    response = client.table('conversations').insert({
        "user_id": user_id,
        "title": title
    }).execute()
    return response.data[0]

def get_conversations(user_id):
    """Récupère toutes les conversations d'un utilisateur."""
    response = client.table('conversations').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
    return response.data

def add_message(conversation_id, sender, content):
    """Ajoute un message à une conversation."""
    response = client.table('messages').insert({
        "conversation_id": conversation_id,
        "sender": sender,
        "content": content
    }).execute()
    return response.data[0]

def get_messages(conversation_id):
    """Récupère tous les messages d'une conversation."""
    response = client.table('messages').select('*').eq('conversation_id', conversation_id).order('created_at', desc=False).execute()
    return response.data
