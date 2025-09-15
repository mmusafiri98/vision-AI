import streamlit as st
from supabase import create_client
import os

# --------------------------
# Initialisation Supabase
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

st.set_page_config(page_title="Login / Création compte", page_icon="🔑", layout="centered")

# --------------------------
# Navigation
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

def go_to(page):
    st.session_state.page = page

# --------------------------
# Fonctions
# --------------------------
def verify_user(email, password):
    try:
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response.user
    except Exception:
        st.error("❌ Identifiants incorrects ou problème de connexion")
        return None

def create_user(email, password, name=None, full_name=None):
    try:
        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or "", "full_name": full_name or ""}
        })
        return response.user
    except Exception:
        st.error("❌ Erreur création compte (email déjà utilisé ?)")
        return None

def logout():
    for key in ["logged_in", "user", "temp_email", "temp_password"]:
        st.session_state.pop(key, None)
    go_to("login")

# --------------------------
# Sidebar
# --------------------------
if st.session_state.get("logged_in"):
    st.sidebar.success(f"Connecté: {st.session_state.user.email}")
    if st.sidebar.button("🏠 Dashboard"):
        go_to("dashboard")
    if st.sidebar.button("🚪 Déconnexion"):
        logout()
else:
    st.sidebar.info("👤 Non connecté")

# --------------------------
# Pages
# --------------------------
if st.session_state.page == "login":
    st.title("🔑 Connexion")
    email = st.text_input("📧 Email", value=st.session_state.get("temp_email", ""))
    password = st.text_input("🔒 Mot de passe", type="password", value=st.session_state.get("temp_password", ""))
    if st.button("Se connecter"):
        user = verify_user(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            go_to("dashboard")

    st.markdown("---")
    if st.button("📝 Créer un compte"):
        go_to("register")

elif st.session_state.page == "register":
    st.title("📝 Créer un compte")
    email = st.text_input("📧 Email")
    password = st.text_input("🔒 Mot de passe", type="password")
    name = st.text_input("👤 Nom (optionnel)")
    fullname = st.text_input("📝 Nom complet (optionnel)")
    if st.button("Créer le compte"):
        if email and password:
            user = create_user(email, password, name, fullname)
            if user:
                st.success("✅ Compte créé, connectez-vous maintenant.")
                st.session_state.temp_email = email
                st.session_state.temp_password = password
                go_to("login")

    st.markdown("---")
    if st.button("🔑 Retour au login"):
        go_to("login")

elif st.session_state.page == "dashboard":
    if not st.session_state.get("logged_in"):
        st.warning("⚠️ Vous devez être connecté.")
        go_to("login")
    else:
        st.title("🏠 Dashboard")
        st.write(f"Bienvenue {st.session_state.user.email}")
        if st.button("🚪 Déconnexion"):
            logout()

