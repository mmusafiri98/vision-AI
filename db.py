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
    """Vérifie les identifiants utilisateur"""
    try:
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response.user
    except Exception as e:
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            st.error("❌ Email non confirmé. Contactez l'administrateur.")
        elif "Invalid login credentials" in error_msg:
            st.error("❌ Email ou mot de passe incorrect.")
        else:
            st.error(f"❌ Erreur lors de la connexion: {error_msg}")
        return None

def create_user(email, password, name=None, full_name=None):
    """Crée un nouveau utilisateur"""
    try:
        if not email or "@" not in email or "." not in email:
            st.error("❌ Format d'email invalide")
            return None

        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "name": name or "",
                "full_name": full_name or ""
            }
        })

        if response.user:
            return response.user
        else:
            st.error("❌ Erreur: Aucun utilisateur créé")
            return None

    except Exception as e:
        error_msg = str(e)
        if "invalid format" in error_msg.lower():
            st.error("❌ Format d'email invalide. Veuillez entrer une adresse email valide.")
        elif "already registered" in error_msg.lower():
            st.error("❌ Cette adresse email est déjà utilisée.")
        else:
            st.error(f"❌ Erreur création compte: {error_msg}")
        return None

# --------------------------
# Gestion des pages via session_state
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
    if "logged_in" in st.session_state:
        del st.session_state.logged_in
    if "user" in st.session_state:
        del st.session_state.user
    if "temp_email" in st.session_state:
        del st.session_state.temp_email
    if "temp_password" in st.session_state:
        del st.session_state.temp_password
    st.session_state.page = "login"
    st.rerun()

# --------------------------
# SIDEBAR - Informations utilisateur
# --------------------------
if "logged_in" in st.session_state and st.session_state.logged_in and "user" in st.session_state and st.session_state.user:
    try:
        st.sidebar.success(f"Connecté en tant que {st.session_state.user.email}")
        
        st.sidebar.write(f"**ID:** {st.session_state.user.id[:8]}...")
        st.sidebar.write(f"**Créé:** {str(st.session_state.user.created_at)[:10]}")

        if hasattr(st.session_state.user, 'user_metadata') and st.session_state.user.user_metadata:
            metadata = st.session_state.user.user_metadata
            if metadata.get('name'):
                st.sidebar.write(f"**Nom:** {metadata['name']}")
            if metadata.get('full_name'):
                st.sidebar.write(f"**Nom complet:** {metadata['full_name']}")

        st.sidebar.markdown("---")
        st.sidebar.subheader("🧭 Navigation")

        if st.sidebar.button("🏠 Dashboard"):
            go_to_dashboard()
            st.rerun()

        if st.sidebar.button("🚪 Se déconnecter"):
            logout_user()

    except AttributeError:
        st.sidebar.error("Erreur: Données utilisateur corrompues")
        logout_user()
    except Exception as e:
        st.sidebar.error(f"Erreur sidebar: {e}")

# --------------------------
# PAGE LOGIN
# --------------------------
if st.session_state.page == "login":
    col_empty1, col_form, col_empty2 = st.columns([1, 2, 1])

    with col_form:
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
                            # CORRECTION: user.email
                            st.success(f"✅ Bienvenue {user.email} !")

                            st.session_state.logged_in = True
                            st.session_state.user = user

                            if "temp_email" in st.session_state:
                                del st.session_state.temp_email
                            if "temp_password" in st.session_state:
                                del st.session_state.temp_password

                            st.info("Redirection vers le dashboard...")
                            st.balloons()
                            go_to_dashboard()
                            st.rerun()
                        else:
                            st.error("❌ Connexion échouée")

        st.markdown("---")
        st.write("Pas encore de compte ?")
        if st.button("📝 Créer un compte"):
            go_to_register()
            st.rerun()

# --------------------------
# PAGE CREATION COMPTE
# --------------------------
elif st.session_state.page == "register":
    col_empty1, col_form, col_empty2 = st.columns([1, 2, 1])
    with col_form:
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
                    st.warning("Email et mot de passe sont obligatoires.")
                elif len(new_password) < 6:
                    st.warning("Le mot de passe doit contenir au moins 6 caractères.")
                elif not "@" in new_email or not "." in new_email:
                    st.warning("Veuillez entrer une adresse email valide.")
                else:
                    with st.spinner("Création du compte en cours..."):
                        user = create_user(new_email, new_password, new_name, new_fullname)

                        if user:
                            st.success(f"✅ Compte créé pour {user.email}!")
                            st.balloons()

                            st.session_state.temp_email = new_email
                            st.session_state.temp_password = new_password

                            st.success("🎉 Redirection automatique vers la page de connexion...")
                            go_to_login()
                            st.rerun()

        st.markdown("---")
        st.write("Déjà un compte ?")
        if st.button("🔑 Retour au login"):
            go_to_login()
            st.rerun()

# --------------------------
# PAGE DASHBOARD
# --------------------------
elif st.session_state.page == "dashboard":
    if "logged_in" not in st.session_state or not st.session_state.logged_in or "user" not in st.session_state or not st.session_state.user:
        st.warning("⚠️ Vous devez être connecté pour accéder au dashboard.")
        go_to_login()
        st.rerun()
    else:
        st.title("🏠 Dashboard")
        # CORRECTION: user.email
        st.write(f"Bienvenue sur votre dashboard, {st.session_state.user.email}!")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("👤 Profil")
            # CORRECTION: user.email
            st.write(f"**Email:** {st.session_state.user.email}")
            st.write(f"**ID:** {st.session_state.user.id}")
            st.write(f"**Créé:** {st.session_state.user.created_at}")

            if hasattr(st.session_state.user, 'user_metadata') and st.session_state.user.user_metadata:
                metadata = st.session_state.user.user_metadata
                st.write("**Métadonnées:**")
                if metadata.get('name'):
                    st.write(f"- Nom: {metadata['name']}")
                if metadata.get('full_name'):
                    st.write(f"- Nom complet: {metadata['full_name']}")

        with col2:
            st.subheader("🛠️ Actions")

            if st.button("🔄 Actualiser", use_container_width=True):
                st.rerun()

            if st.button("🚪 Se déconnecter", use_container_width=True):
                logout_user()

        st.subheader("📊 Contenu principal")

        tab1, tab2, tab3 = st.tabs(["Données", "Statistiques", "Paramètres"])

        with tab1:
            st.write("Ici vous pouvez afficher des données spécifiques à l'utilisateur.")
            st.info(f"Données pour: {st.session_state.user.email}")

        with tab2:
            st.write("Graphiques et statistiques basées sur votre profil.")
            st.info(f"Utilisateur ID: {st.session_state.user.id}")

        with tab3:
            st.write("Paramètres de compte et préférences.")
            if st.button("Modifier le profil"):
                st.info("Fonctionnalité de modification du profil à implémenter.")

# --------------------------
# PAGE PAR DÉFAUT
# --------------------------
else:
    st.error("❌ Page inconnue. Redirection vers la page de connexion.")
    go_to_login()
    st.rerun()

# --------------------------
# FOOTER
# --------------------------
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: gray; font-size: 12px;'>
    🔒 Application sécurisée avec Supabase • Page actuelle: {st.session_state.page}
    </div>
    """,
    unsafe_allow_html=True
)
