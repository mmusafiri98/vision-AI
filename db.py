import streamlit as st
import os
import db # Assurez-vous que votre fichier db.py est bien dans le même dossier

# === STYLE CSS ===
# J'ai créé un style qui imite les designs de connexion modernes et épurés
# que vous avez fournis en images.
st.markdown(
    """
    <style>
    body {
        background: linear-gradient(135deg, #1f4287, #2159c4);
        color: white;
        font-family: Arial, sans-serif;
    }
    .stApp {
        background: linear-gradient(135deg, #1f4287, #2159c4);
        background-attachment: fixed;
    }
    .main-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        width: 100%;
    }
    .login-form-container {
        background-color: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 40px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.18);
        width: 100%;
        max-width: 400px;
        text-align: center;
    }
    h1, h2 {
        color: #FFFFFF;
        text-align: center;
    }
    .stTextInput label, .stMarkdown, .stButton button, .stCheckbox label {
        color: #FFFFFF;
    }
    .stTextInput input {
        background-color: rgba(255, 255, 255, 0.2);
        border: none;
        color: white;
    }
    .stButton button {
        background-color: #4A90E2;
        border: none;
        color: white;
        font-weight: bold;
        padding: 10px 20px;
        border-radius: 10px;
    }
    .stButton button:hover {
        background-color: #357ABD;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# === GESTION DES PAGES ===
if "page" not in st.session_state:
    st.session_state.page = "login"

def go_to_register():
    st.session_state.page = "register"

def go_to_login():
    st.session_state.page = "login"

def go_to_dashboard():
    st.session_state.page = "dashboard"

def logout_user():
    if "user" in st.session_state:
        del st.session_state.user
    st.session_state.page = "login"
    st.rerun()

# === PAGE DE CONNEXION ===
if st.session_state.page == "login":
    st.markdown("<div class='main-container'>", unsafe_allow_html=True)
    st.markdown("<div class='login-form-container'>", unsafe_allow_html=True)
    st.header("Login")

    email = st.text_input("Username", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("LOGIN", use_container_width=True):
        user = db.verify_user(email, password)
        if user:
            st.session_state.user = user
            st.success("Connexion réussie!")
            go_to_dashboard()
            st.rerun()
        else:
            st.error("Email ou mot de passe incorrect.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Forgot your password?</p>", unsafe_allow_html=True)
    st.markdown("---", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>New here? <a href='#' style='color: white; text-decoration: none; font-weight: bold;'>Sign Up</a></p>", unsafe_allow_html=True)
    if st.button("Sign Up", key="signup_button"):
        go_to_register()
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# === PAGE D'INSCRIPTION ===
elif st.session_state.page == "register":
    st.markdown("<div class='main-container'>", unsafe_allow_html=True)
    st.markdown("<div class='login-form-container'>", unsafe_allow_html=True)
    st.header("Sign Up")

    email_reg = st.text_input("Email", key="reg_email")
    name_reg = st.text_input("Username", key="reg_name")
    pass_reg = st.text_input("Password", type="password", key="reg_pass")

    if st.button("CREATE ACCOUNT", use_container_width=True):
        if not email_reg or not pass_reg:
            st.error("Veuillez remplir tous les champs obligatoires.")
        else:
            user = db.create_user(email_reg, pass_reg, name_reg)
            if user:
                st.success("Compte créé avec succès! Vous pouvez maintenant vous connecter.")
                go_to_login()
                st.rerun()
            else:
                st.error("La création du compte a échoué.")

    st.markdown("---", unsafe_allow_html=True)
    if st.button("Go to Login"):
        go_to_login()
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# === PAGE DU DASHBOARD (EXEMPLE) ===
elif st.session_state.page == "dashboard":
    if "user" not in st.session_state or st.session_state.user is None:
        st.warning("Veuillez vous connecter pour accéder à cette page.")
        go_to_login()
        st.rerun()
    else:
        st.title("Bienvenue sur votre Dashboard!")
        st.write(f"Connecté en tant que: **{st.session_state.user.email}**")
        if st.button("Se déconnecter"):
            logout_user()

# === PIED DE PAGE ===
st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        color: gray;
        text-align: center;
        padding: 10px;
    }
    </style>
    <div class="footer">
        © 2024 Vision AI. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True
)
