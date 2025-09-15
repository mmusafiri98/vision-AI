import streamlit as st
from supabase import create_client
import os

# --------------------------
# Configuration Supabase
# --------------------------
@st.cache_resource
def init_supabase():
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_anon_key = os.environ["SUPABASE_ANON_KEY"]
    supabase_service_key = os.environ["SUPABASE_SERVICE_KEY"]
    
    client = create_client(supabase_url, supabase_anon_key)
    admin = create_client(supabase_url, supabase_service_key)
    
    return client, admin

client, admin = init_supabase()

# --------------------------
# Fonctions d'authentification
# --------------------------
def verify_user(email, password):
    """Vérifie les identifiants utilisateur"""
    try:
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response.user
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion: {e}")
        return None

def create_user(email, password, name=None, full_name=None):
    """Crée un nouveau utilisateur"""
    try:
        response = admin.auth.sign_up({
            "email": email,
            "password": password
        })
        user = response.user
        
        if user:
            # Confirmer automatiquement
            admin.auth.admin.update_user_by_id(
                uid=user.id,
                attributes={"email_confirmed_at": "now()"}
            )
            
            # Ajouter dans la table users (optionnel)
            user_data = {"email": email}
            if name:
                user_data["name"] = name
            if full_name:
                user_data["full_name"] = full_name
            
            admin.table("users").insert(user_data).execute()
            return user
        else:
            return None
            
    except Exception as e:
        st.error(f"❌ Erreur création compte: {e}")
        return None

# --------------------------
# Configuration page
# --------------------------
st.set_page_config(
    page_title="Login / Création compte",
    page_icon="🔑",
    layout="centered"
)

# --------------------------
# Gestion des pages
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

def go_to_register():
    st.session_state.page = "register"

def go_to_login():
    st.session_state.page = "login"

# --------------------------
# PAGE LOGIN
# --------------------------
if st.session_state.page == "login":
    st.title("🔑 Connexion Utilisateur")
    
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        login_submitted = st.form_submit_button("Se connecter")
    
    if login_submitted:
        if not email or not password:
            st.warning("Merci d'entrer email et mot de passe.")
        else:
            user = verify_user(email, password)  # Ligne équivalente à votre ligne 63
            
            if user:
                st.success(f"✅ Connexion réussie ! Bienvenue {user.email}")
                st.session_state.logged_in = True
                st.session_state.user = user
            else:
                st.error("❌ Email ou mot de passe incorrect")
    
    st.markdown("---")
    if st.button("Créer un compte", on_click=go_to_register):
        pass

# --------------------------
# PAGE CREATION COMPTE
# --------------------------
elif st.session_state.page == "register":
    st.title("📝 Créer un nouveau compte")
    
    with st.form("register_form"):
        new_email = st.text_input("Email")
        new_password = st.text_input("Mot de passe", type="password")
        new_name = st.text_input("Nom (optionnel)")
        new_fullname = st.text_input("Nom complet (optionnel)")
        register_submitted = st.form_submit_button("Créer le compte")
    
    if register_submitted:
        if not new_email or not new_password:
            st.warning("Merci d'entrer email et mot de passe.")
        else:
            user = create_user(new_email, new_password, new_name, new_fullname)
            
            if user:
                st.success(f"✅ Compte créé pour {new_email}. Vous pouvez maintenant vous connecter !")
            else:
                st.error("❌ Erreur lors de la création du compte")
    
    if st.button("Retour au login", on_click=go_to_login):
        pass
