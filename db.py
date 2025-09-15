import streamlit as st
from supabase import create_client
import os

# --------------------------
# Configuration Supabase
# --------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)   # pour login
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)  # pour créer utilisateurs

# --------------------------
# Gestion simple des "pages"
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

# --------------------------
# Page Login
# --------------------------
if st.session_state.page == "login":
    st.set_page_config(page_title="Login", page_icon="🔑", layout="centered")
    st.title("🔑 Connexion Utilisateur")

    login_email = st.text_input("Email")
    login_password = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if not login_email or not login_password:
            st.warning("Merci d’entrer email et mot de passe.")
        else:
            try:
                response = supabase_client.auth.sign_in_with_password({
                    "email": login_email,
                    "password": login_password
                })
                if response.user:
                    st.success(f"✅ Connexion réussie ! Bienvenue {response.user.email}")
                else:
                    st.error("❌ Email ou mot de passe incorrect")
            except Exception as e:
                st.error(f"❌ Erreur lors de la connexion: {e}")

    st.markdown("---")
    if st.button("Créer un compte"):
        st.session_state.page = "register"
        st.experimental_rerun()  # Recharge la page pour aller vers l'inscription

# --------------------------
# Page Création compte
# --------------------------
elif st.session_state.page == "register":
    st.set_page_config(page_title="Créer un compte", page_icon="📝", layout="centered")
    st.title("📝 Créer un nouveau compte")

    new_email = st.text_input("Email")
    new_password = st.text_input("Mot de passe", type="password")
    new_name = st.text_input("Nom (optionnel)")
    new_fullname = st.text_input("Nom complet (optionnel)")

    if st.button("Créer le compte"):
        if not new_email or not new_password:
            st.warning("Merci d’entrer email et mot de passe.")
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
                else:
                    st.error("❌ Erreur lors de la création de l'utilisateur")
            except Exception as e:
                st.error(f"❌ Erreur création compte: {e}")

    if st.button("Retour au login"):
        st.session_state.page = "login"
        st.experimental_rerun()

