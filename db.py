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
    
    # ÉTAPE 1: Essayer admin.create_user (recommandé)
    try:
        st.info("🔄 Création avec admin.create_user...")
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
            st.success("✅ Utilisateur créé avec admin.create_user")
            return response.user
    
    except Exception as e:
        st.warning(f"⚠️ admin.create_user échoué: {e}")
    
    # ÉTAPE 2: Fallback avec sign_up normal
    try:
        st.info("🔄 Tentative avec sign_up normal...")
        response = admin.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "name": name or "",
                    "full_name": full_name or ""
                }
            }
        })
        
        if response.user:
            st.success("✅ Utilisateur créé avec sign_up")
            st.info("💡 Si vous avez l'erreur 'Email not confirmed', désactivez la confirmation d'email dans Authentication > Settings")
            return response.user
    
    except Exception as e:
        st.error(f"❌ sign_up échoué: {e}")
    
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
    
    # Message d'aide
    with st.expander("❓ Problème de connexion ?"):
        st.markdown("""
        **Si vous avez l'erreur "Email not confirmed" :**
        1. Allez dans votre Dashboard Supabase
        2. Authentication > Settings
        3. Désactivez "Enable email confirmations"
        4. Ou configurez un provider SMTP
        """)
    
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
                st.success(f"✅ Connexion réussie ! Bienvenue {user.email}")
                st.session_state.logged_in = True
                st.session_state.user = user
                
                # Afficher infos utilisateur
                st.json({
                    "user_id": user.id,
                    "email": user.email,
                    "créé_le": str(user.created_at) if user.created_at else "N/A"
                })
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
    
    st.info("💡 L'application essaiera deux méthodes de création pour assurer le succès.")
    
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
                    st.success(f"✅ Compte créé pour {new_email}!")
                    st.balloons()
                    
                    # Auto-redirect après 3 secondes
                    import time
                    st.info("⏳ Redirection vers le login dans 3 secondes...")
                    time.sleep(1)
                    if st.button("Aller au login maintenant"):
                        st.session_state.page = "login"
                        st.rerun()
                else:
                    st.error("❌ Erreur lors de la création du compte")
    
    if st.button("Retour au login", on_click=go_to_login):
        pass
