import streamlit as st
from supabase import create_client
import os

# --------------------------
# Configuration Supabase
# --------------------------
@st.cache_resource
def init_supabase():
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
# Configuration page
# --------------------------
st.set_page_config(
    page_title="Login / Création compte",
    page_icon="🔑",
    layout="centered"
)

# --------------------------
# Fonctions utilitaires
# --------------------------
def verify_user(email, password):
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        return response.user
    except Exception as e:
        msg = str(e)
        if "Email not confirmed" in msg:
            st.error("❌ Email non confirmé.")
        elif "Invalid login credentials" in msg:
            st.error("❌ Email ou mot de passe incorrect.")
        else:
            st.error(f"❌ Erreur connexion: {msg}")
        return None

def create_user(email, password, name=None, full_name=None):
    try:
        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or "", "full_name": full_name or ""}
        })
        if response.user:
            return response.user
        st.error("❌ Aucun utilisateur créé")
        return None
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower():
            st.error("❌ Cette adresse email est déjà utilisée.")
        else:
            st.error(f"❌ Erreur création compte: {msg}")
        return None

# --------------------------
# Gestion des pages
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

def go_to_register():
    st.session_state.page = "register"

def go_to_login():
    st.session_state.page = "login"

def go_to_dashboard():
    st.session_state.page = "dashboard"

def logout_user():
    for key in ["logged_in", "user", "temp_email", "temp_password"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.page = "login"
    st.rerun()

# --------------------------
# PAGE LOGIN
# --------------------------
if st.session_state.page == "login":
    st.title("🔑 Connexion Utilisateur")
    st.markdown("---")

    default_email = st.session_state.get("temp_email", "")
    default_password = st.session_state.get("temp_password", "")

    with st.form("login_form"):
        email = st.text_input("📧 Email", value=default_email)
        password = st.text_input("🔒 Mot de passe", type="password", value=default_password)
        login_submitted = st.form_submit_button("Se connecter")

        if login_submitted:
            if not email or not password:
                st.warning("Merci d'entrer email et mot de passe.")
            else:
                with st.spinner("Connexion en cours..."):
                    user = verify_user(email, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        for key in ["temp_email", "temp_password"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        go_to_dashboard()
                        st.rerun()
                    else:
                        st.error("❌ Connexion échouée")

    st.markdown("---")
    if st.button("📝 Créer un compte"):
        go_to_register()
        st.rerun()

# --------------------------
# PAGE CREATION COMPTE
# --------------------------
elif st.session_state.page == "register":
    st.title("📝 Créer un nouveau compte")
    st.info("💡 Votre compte sera automatiquement confirmé.")

    with st.form("register_form"):
        new_email = st.text_input("📧 Email")
        new_password = st.text_input("🔒 Mot de passe", type="password")
        new_name = st.text_input("👤 Nom (optionnel)")
        new_fullname = st.text_input("📝 Nom complet (optionnel)")
        register_submitted = st.form_submit_button("Créer le compte")

        if register_submitted:
            if not new_email or not new_password:
                st.warning("Email et mot de passe obligatoires.")
            elif len(new_password) < 6:
                st.warning("Le mot de passe doit contenir au moins 6 caractères.")
            else:
                with st.spinner("Création du compte en cours..."):
                    user = create_user(new_email, new_password, new_name, new_fullname)
                    if user:
                        st.success(f"✅ Compte créé pour {user.email}!")
                        st.balloons()
                        # Sauvegarde temporaire pour login automatique
                        st.session_state.temp_email = new_email
                        st.session_state.temp_password = new_password

    st.markdown("---")
    if st.button("🔑 Retour au login"):
        go_to_login()
        st.rerun()

# --------------------------
# PAGE DASHBOARD
# --------------------------
elif st.session_state.page == "dashboard":
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.warning("⚠️ Connectez-vous d'abord.")
        go_to_login()
        st.rerun()
    else:
        st.title("🏠 Dashboard")
        st.write(f"Bienvenue, {st.session_state.user.email}!")

        st.subheader("👤 Profil")
        st.write(f"**Email:** {st.session_state.user.email}")
        st.write(f"**ID:** {st.session_state.user.id}")

        metadata = getattr(st.session_state.user, "user_metadata", {})
        if metadata:
            st.write("**Métadonnées:**")
            if metadata.get("name"): st.write(f"- Nom: {metadata['name']}")
            if metadata.get("full_name"): st.write(f"- Nom complet: {metadata['full_name']}")

        st.subheader("🛠️ Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Actualiser", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🚪 Se déconnecter", use_container_width=True):
                logout_user()

# --------------------------
# FOOTER
# --------------------------
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:gray;font-size:12px;'>🔒 Application sécurisée • Page: {st.session_state.page}</div>",
    unsafe_allow_html=True
)
