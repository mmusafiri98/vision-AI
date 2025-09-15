import streamlit as st


# === SESSION INIT ===
if "user" not in st.session_state:
    st.session_state.user = None
if "show_signup" not in st.session_state:
    st.session_state.show_signup = False

# === FONCTIONS ===
def login_user(email, password):
    user = db.verify_user(email, password)
    if user:
        # Si user est un tuple, convertir en dict
        if isinstance(user, tuple):
            user = {"id": user[0], "email": user[1], "name": user[2]}
        st.session_state.user = user
        st.success(f"Bienvenue {user['email']} !")
        st.session_state.show_signup = False
    else:
        st.error("Email ou mot de passe invalide")

def create_account(email, name, password):
    try:
        user = db.create_user(email, password, name)
        st.success("Compte créé ! Vous pouvez maintenant vous connecter.")
        st.session_state.show_signup = False
    except Exception as e:
        st.error(f"Erreur création compte : {e}")

# === INTERFACE AUTHENTIFICATION ===
st.title("Vision AI Chat")

if st.session_state.user is None:
    if st.session_state.show_signup:
        st.subheader("Créer un compte")
        name_reg = st.text_input("Nom")
        email_reg = st.text_input("Email")
        pass_reg = st.text_input("Mot de passe", type="password")
        if st.button("Créer mon compte"):
            create_account(email_reg, name_reg, pass_reg)
        if st.button("← Retour à la connexion"):
            st.session_state.show_signup = False
    else:
        st.subheader("Se connecter")
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Connexion"):
            login_user(email, password)
        st.markdown("Vous n'avez pas de compte ?")
        if st.button("Créer un compte"):
            st.session_state.show_signup = True

    st.stop()  # Stoppe le reste tant que l'utilisateur n'est pas connecté
else:
    st.success(f"Connecté en tant que {st.session_state.user['email']}")
    if st.button("Se déconnecter"):
        st.session_state.user = None
        st.experimental_rerun()

# === CHAT ===
st.write("Ici démarre votre chat Vision AI…")
# Votre code pour afficher le chat et gérer les conversations

