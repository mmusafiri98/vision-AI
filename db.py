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
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            st.error("❌ Email non confirmé. Essayez de recréer votre compte ou contactez l'administrateur.")
        elif "Invalid login credentials" in error_msg:
            st.error("❌ Email ou mot de passe incorrect.")
        else:
            st.error(f"❌ Erreur lors de la connexion: {error_msg}")
        return None

def create_user(email, password, name=None, full_name=None):
    """Crée un nouveau utilisateur confirmé automatiquement"""
    try:
        # Méthode principale: admin.create_user
        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Confirme automatiquement l'email
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
        
        # Méthode alternative si la première échoue
        try:
            st.info("🔄 Tentative avec méthode alternative...")
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
                # Confirmer manuellement l'email
                admin.auth.admin.update_user_by_id(
                    uid=response.user.id,
                    attributes={"email_confirmed_at": "2024-01-01T00:00:00Z"}
                )
                st.info("✅ Email confirmé automatiquement")
                return response.user
        except Exception as e2:
            st.error(f"❌ Méthode alternative échouée: {e2}")
        
        return None

def logout_user():
    """Déconnecte l'utilisateur"""
    try:
        client.auth.sign_out()
    except:
        pass  # Ignorer les erreurs de déconnexion
    
    # Nettoyer la session Streamlit
    if "logged_in" in st.session_state:
        del st.session_state.logged_in
    if "user" in st.session_state:
        del st.session_state.user
    st.session_state.page = "login"

def debug_user_object(user):
    """Affiche les propriétés de l'objet user pour debug"""
    with st.expander("🔍 Debug - Informations utilisateur"):
        try:
            st.write(f"**ID:** {user.id}")
            st.write(f"**Email:** {user.email}")
            st.write(f"**Créé le:** {user.created_at}")
            
            if hasattr(user, 'email_confirmed_at'):
                st.write(f"**Email confirmé:** {user.email_confirmed_at}")
            
            if hasattr(user, 'user_metadata') and user.user_metadata:
                st.write(f"**Métadonnées:** {user.user_metadata}")
                
        except Exception as e:
            st.write(f"❌ Erreur debug: {e}")

# --------------------------
# Configuration page
# --------------------------
st.set_page_config(
    page_title="Authentification Supabase",
    page_icon="🔑",
    layout="centered"
)

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

def go_to_dashboard():
    st.session_state.page = "dashboard"

# --------------------------
# SIDEBAR - Informations utilisateur
# --------------------------
if "logged_in" in st.session_state and st.session_state.logged_in:
    # ✅ CORRECTION: Utiliser user.email au lieu de user['email']
    st.sidebar.success(f"Connecté en tant que {st.session_state.user.email}")
    
    # Informations utilisateur dans la sidebar
    st.sidebar.write(f"**ID:** {st.session_state.user.id[:8]}...")
    st.sidebar.write(f"**Créé le:** {str(st.session_state.user.created_at)[:10]}")
    
    # Métadonnées si disponibles
    if hasattr(st.session_state.user, 'user_metadata') and st.session_state.user.user_metadata:
        metadata = st.session_state.user.user_metadata
        if metadata.get('name'):
            st.sidebar.write(f"**Nom:** {metadata['name']}")
        if metadata.get('full_name'):
            st.sidebar.write(f"**Nom complet:** {metadata['full_name']}")
    
    # Navigation
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 Dashboard"):
        go_to_dashboard()
        st.rerun()
        
    if st.sidebar.button("🚪 Se déconnecter"):
        logout_user()
        st.rerun()
else:
    st.sidebar.info("👤 Non connecté")
    st.sidebar.write("Connectez-vous pour accéder à toutes les fonctionnalités.")

# --------------------------
# PAGE LOGIN
# --------------------------
if st.session_state.page == "login":
    st.title("🔑 Connexion")
    
    # Message d'information
    st.info("💡 Entrez vos identifiants pour vous connecter à votre compte.")
    
    with st.form("login_form"):
        email = st.text_input("📧 Email", placeholder="votre@email.com")
        password = st.text_input("🔒 Mot de passe", type="password", placeholder="Votre mot de passe")
        login_submitted = st.form_submit_button("🔐 Se connecter", use_container_width=True)
    
    if login_submitted:
        if not email or not password:
            st.warning("⚠️ Merci d'entrer votre email et mot de passe.")
        else:
            with st.spinner("🔄 Connexion en cours..."):
                user = verify_user(email, password)
                
                if user:
                    # ✅ CORRECTION: Utiliser user.email au lieu de user['email']
                    st.success(f"✅ Bienvenue {user.email} !")
                    
                    # Stocker dans la session
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.session_state.page = "dashboard"
                    
                    # Debug optionnel
                    debug_user_object(user)
                    
                    # Redirection automatique
                    st.rerun()
                else:
                    st.error("❌ Connexion échouée. Vérifiez vos identifiants.")
    
    # Lien vers création de compte
    st.markdown("---")
    st.write("Pas encore de compte ?")
    if st.button("📝 Créer un compte", use_container_width=True):
        go_to_register()
        st.rerun()

# --------------------------
# PAGE CREATION COMPTE
# --------------------------
elif st.session_state.page == "register":
    st.title("📝 Créer un compte")
    
    st.info("🎯 Créez votre compte en quelques secondes. Aucune confirmation par email requise !")
    
    with st.form("register_form"):
        new_email = st.text_input("📧 Email", placeholder="votre@email.com")
        new_password = st.text_input("🔒 Mot de passe", type="password", placeholder="Minimum 6 caractères")
        new_name = st.text_input("👤 Nom (optionnel)", placeholder="Votre nom")
        new_fullname = st.text_input("📝 Nom complet (optionnel)", placeholder="Votre nom complet")
        
        register_submitted = st.form_submit_button("🚀 Créer le compte", use_container_width=True)
    
    if register_submitted:
        if not new_email or not new_password:
            st.warning("⚠️ Email et mot de passe sont obligatoires.")
        elif len(new_password) < 6:
            st.warning("⚠️ Le mot de passe doit contenir au moins 6 caractères.")
        else:
            with st.spinner("🔄 Création du compte en cours..."):
                user = create_user(new_email, new_password, new_name, new_fullname)
                
                if user:
                    # ✅ CORRECTION: Utiliser user.email au lieu de user['email']
                    st.success(f"✅ Compte créé avec succès pour {user.email} !")
                    st.balloons()
                    
                    st.info("🎉 Votre compte est prêt ! Vous pouvez maintenant vous connecter.")
                    
                    # Debug optionnel
                    debug_user_object(user)
                    
                    # Bouton pour aller au login
                    if st.button("🔐 Aller au login", use_container_width=True):
                        go_to_login()
                        st.rerun()
                else:
                    st.error("❌ Erreur lors de la création du compte. Veuillez réessayer.")
    
    # Lien retour login
    st.markdown("---")
    st.write("Déjà un compte ?")
    if st.button("🔑 Retour au login", use_container_width=True):
        go_to_login()
        st.rerun()

# --------------------------
# PAGE DASHBOARD (après connexion)
# --------------------------
elif st.session_state.page == "dashboard":
    # Vérifier si l'utilisateur est connecté
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.error("❌ Accès non autorisé. Veuillez vous connecter.")
        go_to_login()
        st.rerun()
    
    # ✅ CORRECTION: Utiliser user.email au lieu de user['email']
    st.title(f"🏠 Tableau de bord - {st.session_state.user.email}")
    
    # Message de bienvenue
    st.success("🎉 Vous êtes maintenant connecté !")
    
    # Informations utilisateur
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Profil utilisateur")
        # ✅ CORRECTION: Utiliser les attributs au lieu de clés de dictionnaire
        st.write(f"**Email:** {st.session_state.user.email}")
        st.write(f"**ID:** {st.session_state.user.id}")
        st.write(f"**Compte créé:** {str(st.session_state.user.created_at)[:19]}")
        
        # Métadonnées utilisateur
        if hasattr(st.session_state.user, 'user_metadata') and st.session_state.user.user_metadata:
            metadata = st.session_state.user.user_metadata
            if metadata.get('name'):
                st.write(f"**Nom:** {metadata['name']}")
            if metadata.get('full_name'):
                st.write(f"**Nom complet:** {metadata['full_name']}")
    
    with col2:
        st.subheader("🛠️ Actions")
        
        if st.button("🔄 Actualiser les informations", use_container_width=True):
            st.rerun()
        
        if st.button("🔧 Mode debug", use_container_width=True):
            debug_user_object(st.session_state.user)
        
        if st.button("🚪 Se déconnecter", use_container_width=True, type="secondary"):
            logout_user()
            st.rerun()
    
    # Contenu principal du dashboard
    st.markdown("---")
    st.subheader("📊 Contenu principal")
    
    # Exemple de contenu
    tab1, tab2, tab3 = st.tabs(["📈 Statistiques", "📋 Données", "⚙️ Paramètres"])
    
    with tab1:
        st.write("Ici vous pouvez afficher des graphiques et statistiques.")
        st.info("Contenu personnalisé basé sur votre profil utilisateur.")
    
    with tab2:
        st.write("Ici vous pouvez afficher des données spécifiques à l'utilisateur.")
        st.info("Tables, listes, ou autres contenus dynamiques.")
    
    with tab3:
        st.write("Paramètres du compte et préférences.")
        st.info("Formulaires de mise à jour du profil, etc.")

# --------------------------
# FOOTER
# --------------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.8em;'>
    🔒 Application sécurisée avec Supabase Authentication
    </div>
    """, 
    unsafe_allow_html=True
)
