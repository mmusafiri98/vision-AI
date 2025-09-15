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
            return None
            
    except Exception as e:
        st.error(f"❌ Erreur création compte: {e}")
        return None

# --------------------------
# Gestion des pages via session_state
# --------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

# Fonctions de navigation
def go_to_register():
    st.session_state.page = "register"

def go_to_login():
    st.session_state.page = "login"

def logout_user():
    """Déconnecte l'utilisateur"""
    if "logged_in" in st.session_state:
        del st.session_state.logged_in
    if "user" in st.session_state:
        del st.session_state.user
    st.session_state.page = "login"

# --------------------------
# SIDEBAR - Informations utilisateur
# --------------------------
if "logged_in" in st.session_state and st.session_state.logged_in:
    try:
        # ✅ CORRECTION: Utiliser .email au lieu de ['email']
        st.sidebar.success(f"Connecté en tant que {st.session_state.user.email}")
        
        # Informations utilisateur
        st.sidebar.write(f"**ID:** {st.session_state.user.id[:8]}...")
        st.sidebar.write(f"**Créé:** {str(st.session_state.user.created_at)[:10]}")
        
        # Métadonnées si disponibles
        if hasattr(st.session_state.user, 'user_metadata') and st.session_state.user.user_metadata:
            metadata = st.session_state.user.user_metadata
            if metadata.get('name'):
                st.sidebar.write(f"**Nom:** {metadata['name']}")
            if metadata.get('full_name'):
                st.sidebar.write(f"**Nom complet:** {metadata['full_name']}")
        
        # Bouton de déconnexion
        st.sidebar.markdown("---")
        if st.sidebar.button("🚪 Se déconnecter"):
            logout_user()
            st.rerun()
            
    except AttributeError as e:
        st.sidebar.error("Erreur: Données utilisateur corrompues")
        logout_user()
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erreur sidebar: {e}")
else:
    st.sidebar.info("👤 Non connecté")

# --------------------------
# PAGE LOGIN
# --------------------------
if st.session_state.page == "login":
    st.title("🔑 Connexion Utilisateur")
    
    with st.form("login_form"):
        email = st.text_input("📧 Email")
        password = st.text_input("🔒 Mot de passe", type="password")
        login_submitted = st.form_submit_button("Se connecter")
    
    if login_submitted:
        if not email or not password:
            st.warning("Merci d'entrer email et mot de passe.")
        else:
            with st.spinner("Connexion en cours..."):
                user = verify_user(email, password)
                
                if user:
                    # ✅ CORRECTION: .email au lieu de ['email']
                    st.success(f"✅ Bienvenue {user.email} !")
                    
                    # Sauvegarder dans la session
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    
                    # Afficher les infos utilisateur
                    st.write(f"**ID:** {user.id}")
                    st.write(f"**Email:** {user.email}")
                    st.write(f"**Créé le:** {user.created_at}")
                    
                    # Métadonnées
                    if hasattr(user, 'user_metadata') and user.user_metadata:
                        st.write(f"**Métadonnées:** {user.user_metadata}")
                    
                    # Redirection automatique
                    st.info("Redirection en cours...")
                    st.balloons()
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
        else:
            with st.spinner("Création du compte en cours..."):
                user = create_user(new_email, new_password, new_name, new_fullname)
                
                if user:
                    # ✅ CORRECTION: .email au lieu de ['email']
                    st.success(f"✅ Compte créé pour {user.email}!")
                    st.balloons()
                    
                    # Afficher les infos du compte créé
                    st.write(f"**ID:** {user.id}")
                    st.write(f"**Email:** {user.email}")
                    st.write(f"**Créé le:** {user.created_at}")
                    
                    st.success("🎉 Vous pouvez maintenant vous connecter!")
                    
                    # Bouton pour aller au login
                    if st.button("Aller au login"):
                        go_to_login()
                        st.rerun()
                else:
                    st.error("❌ Erreur lors de la création du compte")
    
    if st.button("Retour au login", on_click=go_to_login):
        pass

# --------------------------
# SECTION DASHBOARD (si connecté)
# --------------------------
if "logged_in" in st.session_state and st.session_state.logged_in:
    st.markdown("---")
    st.header("🏠 Dashboard")
    
    # ✅ CORRECTION: .email au lieu de ['email']
    st.write(f"Bienvenue sur votre dashboard, {st.session_state.user.email}!")
    
    # Colonnes pour organiser le contenu
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Profil")
        # ✅ CORRECTIONS: Tous les attributs utilisent . au lieu de []
        st.write(f"**Email:** {st.session_state.user.email}")
        st.write(f"**ID:** {st.session_state.user.id}")
        st.write(f"**Créé:** {st.session_state.user.created_at}")
        
        # Métadonnées
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
            st.rerun()
    
    # Contenu additionnel du dashboard
    st.subheader("📊 Contenu principal")
    
    # Exemple de contenu
    tab1, tab2, tab3 = st.tabs(["Données", "Statistiques", "Paramètres"])
    
    with tab1:
        st.write("Ici vous pouvez afficher des données spécifiques à l'utilisateur.")
        # ✅ CORRECTION: .email au lieu de ['email']
        st.info(f"Données pour: {st.session_state.user.email}")
    
    with tab2:
        st.write("Graphiques et statistiques basées sur votre profil.")
        # ✅ CORRECTION: .id au lieu de ['id']
        st.info(f"Utilisateur ID: {st.session_state.user.id}")
    
    with tab3:
        st.write("Paramètres de compte et préférences.")
        if st.button("Modifier le profil"):
            st.info("Fonctionnalité de modification du profil à implémenter.")

# --------------------------
# FOOTER
# --------------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 12px;'>
    🔒 Application sécurisée avec Supabase • Authentification complète
    </div>
    """, 
    unsafe_allow_html=True
)
