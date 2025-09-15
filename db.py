import streamlit as st
from supabase import create_client
import os

# --------------------------
# Configuration Supabase
# --------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)   # Login
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)  # Création utilisateurs

# --------------------------
# Configuration page
# --------------------------
st.set_page_config(
    page_title="Login / Création compte",
    page_icon="🔑",
    layout="centered"
)

# --------------------------
# Gestion des pages via session_state
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

# --------------------------
# Fonctions de navigation
# --------------------------
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
        login_email = st.text_input("Email")
        login_password = st.text_input("Mot de passe", type="password")
        login_submitted = st.form_submit_button("Se connecter")
    
    if login_submitted:
        if not login_email or not login_password:
            st.warning("Merci d'entrer email et mot de passe.")
        else:
            try:
                response = supabase_client.auth.sign_in_with_password({
                    "email": login_email,
                    "password": login_password
                })
                if response.user:
                    st.success(f"✅ Connexion réussie ! Bienvenue {response.user.email}")
                    # Ici vous pouvez rediriger vers une autre page ou stocker l'état de connexion
                    # st.session_state.logged_in = True
                    # st.session_state.user = response.user
                else:
                    st.error("❌ Email ou mot de passe incorrect")
            except Exception as e:
                st.error(f"❌ Erreur lors de la connexion: {e}")
    
    st.markdown("---")
    
    # Utilisation d'un callback pour éviter le rerun immédiat
    if st.button("Créer un compte", on_click=go_to_register):
        pass  # Le callback s'occupe du changement de page

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
            try:
                # Création utilisateur via Admin
                response = supabase_admin.auth.sign_up({
                    "email": new_email,
                    "password": new_password
                })
                user = response.user
                if user:
                    # Confirmer automatiquement
                    supabase_admin.auth.admin.update_user_by_id(
                        uid=user.id,
                        attributes={"email_confirmed_at": "now()"}
                    )
                    # Ajouter dans la table users (optionnel)
                    user_data = {"email": new_email}
                    if new_name:
                        user_data["name"] = new_name
                    if new_fullname:
                        user_data["full_name"] = new_fullname
                    
                    supabase_admin.table("users").insert(user_data).execute()
                    st.success(f"✅ Compte créé pour {new_email}. Vous pouvez maintenant vous connecter !")
                    
                    # Optionnel : retourner automatiquement au login après création
                    # st.session_state.page = "login"
                    # st.rerun()
                else:
                    st.error("❌ Erreur lors de la création de l'utilisateur")
            except Exception as e:
                st.error(f"❌ Erreur création compte: {e}")
    
    # Utilisation d'un callback pour le bouton retour
    if st.button("Retour au login", on_click=go_to_login):
        pass  # Le callback s'occupe du changement de page
