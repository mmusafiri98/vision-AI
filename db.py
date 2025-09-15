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

# CSS pour le style moderne inspiré de l'image
st.markdown("""
<style>
    /* Cache le sidebar */
    .css-1d391kg {display: none}
    .css-1rs6os {display: none}
    .css-17ziqus {display: none}
    [data-testid="stSidebar"] {display: none}
    .css-1lcbmhc {display: none}
    
    /* Cache le header Streamlit */
    header[data-testid="stHeader"] {display: none}
    
    /* Style général */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }
    
    /* Container principal */
    .main-container {
        background: white;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        max-width: 400px;
        margin: 2rem auto;
    }
    
    /* Logo/Titre */
    .logo {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .logo h1 {
        color: #333;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
    }
    
    .logo p {
        color: #666;
        font-size: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Inputs personnalisés */
    .stTextInput > div > div > input {
        border: 2px solid #f1f1f1;
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 14px;
        background: #fafafa;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #ff6b35;
        box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
        background: white;
    }
    
    /* Boutons personnalisés */
    .stButton > button {
        background: linear-gradient(135deg, #ff6b35 0%, #ff8c42 100%);
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        color: white;
        font-weight: 600;
        font-size: 16px;
        width: 100%;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(255, 107, 53, 0.3);
    }
    
    /* Bouton secondaire */
    .secondary-btn {
        background: transparent !important;
        border: 2px solid #ff6b35 !important;
        color: #ff6b35 !important;
    }
    
    .secondary-btn:hover {
        background: #ff6b35 !important;
        color: white !important;
    }
    
    /* Messages */
    .stSuccess {
        background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
        border-radius: 12px;
        border: none;
    }
    
    .stError {
        background: linear-gradient(135deg, #f44336 0%, #ef5350 100%);
        border-radius: 12px;
        border: none;
    }
    
    .stWarning {
        background: linear-gradient(135deg, #ff9800 0%, #ffb74d 100%);
        border-radius: 12px;
        border: none;
    }
    
    /* Séparateur */
    .separator {
        text-align: center;
        margin: 2rem 0;
        position: relative;
    }
    
    .separator::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 0;
        right: 0;
        height: 1px;
        background: #e0e0e0;
    }
    
    .separator span {
        background: white;
        padding: 0 1rem;
        color: #666;
        font-size: 14px;
    }
    
    /* Dashboard */
    .dashboard-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 20px;
        margin: 1rem 0;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
    }
    
    .profile-info {
        background: rgba(255,255,255,0.1);
        padding: 1rem;
        border-radius: 12px;
        margin: 1rem 0;
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
# LOGIQUE PRINCIPALE
# --------------------------

# Vérifier si l'utilisateur est déjà connecté
if "logged_in" in st.session_state and st.session_state.logged_in:
    # DASHBOARD - Utilisateur connecté
    st.markdown("""
    <div class="dashboard-card">
        <div class="logo">
            <h1>🏠 Dashboard</h1>
            <p>Bienvenue dans votre espace personnel</p>
        </div>
        <div class="profile-info">
            <h3>👤 Profil</h3>
            <p><strong>Email:</strong> {}</p>
            <p><strong>ID:</strong> {}</p>
        </div>
    </div>
    """.format(st.session_state.user.email, st.session_state.user.id), unsafe_allow_html=True)

    metadata = getattr(st.session_state.user, "user_metadata", {})
    if metadata and (metadata.get("name") or metadata.get("full_name")):
        st.markdown("""
        <div class="profile-info">
            <h4>Informations supplémentaires:</h4>
        </div>
        """, unsafe_allow_html=True)
        if metadata.get("name"): 
            st.write(f"**Nom:** {metadata['name']}")
        if metadata.get("full_name"): 
            st.write(f"**Nom complet:** {metadata['full_name']}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🚪 Déconnexion", use_container_width=True):
            # Nettoyer la session
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

else:
    # PAGE DE CONNEXION/INSCRIPTION avec design moderne
    st.markdown("""
    <div class="main-container">
        <div class="logo">
            <h1>🟠 MonApp</h1>
            <p>Bon de vous revoir !</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Variables pour gérer l'affichage
    if "show_register" not in st.session_state:
        st.session_state.show_register = False
    
    if not st.session_state.show_register:
        # --------------------------
        # FORMULAIRE DE CONNEXION
        # --------------------------
        with st.form("login_form"):
            login_email = st.text_input("Email", placeholder="votre@email.com")
            login_password = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            login_submitted = st.form_submit_button("Se connecter")

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

        st.markdown("""
        <div class="separator">
            <span>ou</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Créer un nouveau compte", use_container_width=True):
            st.session_state.show_register = True
            st.rerun()
    
    else:
        # --------------------------
        # FORMULAIRE D'INSCRIPTION
        # --------------------------
        st.markdown("<p style='text-align: center; color: #666; margin-bottom: 1rem;'>Créer votre compte</p>", unsafe_allow_html=True)
        
        with st.form("register_form"):
            reg_email = st.text_input("Email", placeholder="votre@email.com")
            reg_password = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            reg_name = st.text_input("Nom (optionnel)", placeholder="Votre nom")
            reg_fullname = st.text_input("Nom complet (optionnel)", placeholder="Nom et prénom")
            register_submitted = st.form_submit_button("Créer le compte")

            if register_submitted:
                if not reg_email or not reg_password:
                    st.warning("Email et mot de passe obligatoires.")
                elif len(reg_password) < 6:
                    st.warning("Le mot de passe doit contenir au moins 6 caractères.")
                else:
                    with st.spinner("Création du compte en cours..."):
                        user = create_user(reg_email, reg_password, reg_name, reg_fullname)
                        if user:
                            st.success(f"✅ Compte créé pour {user.email}!")
                            st.balloons()
                            st.info("Vous pouvez maintenant vous connecter.")
                            st.session_state.show_register = False

        st.markdown("""
        <div class="separator">
            <span>ou</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Retour à la connexion", use_container_width=True):
            st.session_state.show_register = False
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
