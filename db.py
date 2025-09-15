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
    page_title="Connexion",
    page_icon="🟠",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# CSS amélioré et simplifié
st.markdown("""
<style>
    /* Cache le sidebar et header */
    .css-1d391kg, .css-1rs6os, .css-17ziqus, [data-testid="stSidebar"], .css-1lcbmhc {display: none}
    header[data-testid="stHeader"] {display: none}
    
    /* Background */
    .stApp {
        background: white !important;
        min-height: 100vh;
    }
    
    /* Container principal */
    .main > div {
        background: white;
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        max-width: 400px;
        margin: 2rem auto;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        padding: 14px 16px !important;
        font-size: 14px !important;
        background: #fafafa !important;
        margin-bottom: 8px !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #007bff !important;
        box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.1) !important;
        background: white !important;
    }
    
    /* Cache les labels */
    .stTextInput > label {
        display: none !important;
    }
    
    /* Boutons */
    .stButton > button {
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        color: white !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        width: 100% !important;
        transition: all 0.3s ease !important;
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 16px rgba(40, 167, 69, 0.3) !important;
    }
    
    /* Tous les boutons sont maintenant verts */
    .create-account-btn button,
    .login-btn button {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
    }
    
    .create-account-btn button:hover,
    .login-btn button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 16px rgba(40, 167, 69, 0.3) !important;
    }
    
    /* Bouton secondaire */
    .secondary-btn button {
        background: transparent !important;
        border: 2px solid #666 !important;
        color: #666 !important;
    }
    
    /* Titre */
    .page-title {
        color: #333;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 2rem;
        text-align: left;
    }
    
    /* Messages */
    .stSuccess, .stError, .stWarning {
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

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

def create_user(email, password, name=None):
    try:
        response = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or "", "full_name": name or ""}
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
# LOGIQUE PRINCIPALE
# --------------------------

# Initialiser l'état de la page
if "show_register" not in st.session_state:
    st.session_state.show_register = False

# Vérifier si l'utilisateur est déjà connecté
if "logged_in" in st.session_state and st.session_state.logged_in:
    # DASHBOARD
    st.markdown('<h1 class="page-title">🏠 Dashboard</h1>', unsafe_allow_html=True)
    st.write(f"Bienvenue, {st.session_state.user.email}!")
    
    st.subheader("👤 Profil")
    st.write(f"**Email:** {st.session_state.user.email}")
    st.write(f"**ID:** {st.session_state.user.id}")
    
    metadata = getattr(st.session_state.user, "user_metadata", {})
    if metadata and metadata.get("name"):
        st.write(f"**Nom:** {metadata['name']}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🚪 Déconnexion", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

else:
    # PAGE UNIQUE - LOGIN + CRÉATION DE COMPTE
    
    # SECTION LOGIN
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #333; font-size: 1.8rem; font-weight: 600; margin: 0;">Login</h1>
        <p style="color: #666; font-size: 1rem; margin: 0.5rem 0;">Bon de vous revoir !</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        login_email = st.text_input("Email", placeholder="votre@email.com")
        login_password = st.text_input("Password", type="password", placeholder="••••••••")
        
        st.markdown('<div class="login-btn">', unsafe_allow_html=True)
        login_submitted = st.form_submit_button("Se connecter", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if login_submitted:
            if not login_email or not login_password:
                st.warning("Merci d'entrer email et mot de passe.")
            else:
                with st.spinner("Connexion en cours..."):
                    user = verify_user(login_email, login_password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.success("✅ Connexion réussie!")
                        st.rerun()

    # SÉPARATEUR
    st.markdown("""
    <div style="text-align: center; margin: 2rem 0; position: relative;">
        <div style="position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: #e0e0e0;"></div>
        <span style="background: white; padding: 0 1rem; color: #666; font-size: 14px;">ou</span>
    </div>
    """, unsafe_allow_html=True)
    
    # SECTION CREATE ACCOUNT
    st.markdown('<h2 class="page-title" style="text-align: left;">Create Account</h2>', unsafe_allow_html=True)
    
    with st.form("register_form"):
        reg_email = st.text_input("Email", placeholder="Email", label_visibility="collapsed", key="reg_email")
        reg_password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed", key="reg_password")
        reg_name = st.text_input("Full Name", placeholder="Full Name", label_visibility="collapsed", key="reg_name")
        
        st.markdown('<div class="create-account-btn">', unsafe_allow_html=True)
        register_submitted = st.form_submit_button("Create Account", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if register_submitted:
            if not reg_email or not reg_password:
                st.warning("Email et mot de passe obligatoires.")
            elif len(reg_password) < 6:
                st.warning("Le mot de passe doit contenir au moins 6 caractères.")
            else:
                with st.spinner("Création du compte en cours..."):
                    user = create_user(reg_email, reg_password, reg_name)
                    if user:
                        st.success(f"✅ Compte créé pour {user.email}!")
                        st.balloons()
                        st.info("Vous pouvez maintenant vous connecter avec vos identifiants ci-dessus.")
                        # Optionnel : connecter automatiquement l'utilisateur
                        # st.session_state.logged_in = True
                        # st.session_state.user = user
                        # st.rerun()
