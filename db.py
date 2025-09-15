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
        # Utiliser admin.create_user pour créer un utilisateur confirmé
        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Confirme automatiquement
            "user_metadata": {
                "name": name or "",
                "full_name": full_name or ""
            }
        })
        
        if response.user:
            st.success("✅ Utilisateur créé avec succès!")
            return response.user
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
            user = verify_user(email, password)
            
            if user:
                # CORRECTION: Utiliser user.email au lieu de user['email']
                st.success(f"Bienvenue {user.email} !")
                st.session_state.logged_in = True
                st.session_state.user = user
                
                # Afficher les informations utilisateur (optionnel)
                with st.expander("ℹ️ Informations utilisateur"):
                    st.write(f"**ID:** {user.id}")
                    st.write(f"**Email:** {user.email}")
                    st.write(f"**Créé le:** {user.created_at}")
                    
                    # Métadonnées si elles existent
                    if hasattr(user, 'user_metadata') and user.user_metadata:
                        st.write(f"**Nom:** {user.user_metadata.get('name', 'Non défini')}")
                        st.write(f"**Nom complet:** {user.user_metadata.get('full_name', 'Non défini')}")
            else:
                st.error("❌ Connexion échouée")
    
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
            with st.spinner("Création du compte en cours..."):
                user = create_user(new_email, new_password, new_name, new_fullname)
                
                if user:
                    # CORRECTION: Utiliser user.email au lieu de user['email']
                    st.success(f"✅ Compte créé pour {user.email}!")
                    st.success("🎉 Vous pouvez maintenant vous connecter!")
                else:
                    st.error("❌ Erreur lors de la création du compte")
    
    if st.button("Retour au login", on_click=go_to_login):
        pass
