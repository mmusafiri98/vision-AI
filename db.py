import streamlit as st
from supabase import create_client
import os

# --------------------------
# Configurazione Supabase
# --------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)   # per login
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)  # per creare utenti

# --------------------------
# Interfaccia centrata
# --------------------------
st.set_page_config(page_title="Login / Registrazione", page_icon="🔑", layout="centered")

st.title("🔑 Area Utente")

with st.container():
    st.subheader("Login")
    login_email = st.text_input("Email Login")
    login_password = st.text_input("Password Login", type="password")
    
    if st.button("Login"):
        if not login_email or not login_password:
            st.warning("Inserisci email e password per il login.")
        else:
            try:
                response = supabase_client.auth.sign_in_with_password({
                    "email": login_email,
                    "password": login_password
                })
                if response.user:
                    st.success(f"✅ Login riuscito! Benvenuto {response.user.email}")
                else:
                    st.error("❌ Email o password errata")
            except Exception as e:
                st.error(f"❌ Errore login: {e}")

    st.markdown("---")
    st.subheader("Crea un nuovo account")
    new_email = st.text_input("Email Nuovo Account")
    new_password = st.text_input("Password Nuovo Account", type="password")
    new_name = st.text_input("Nome (opzionale)")
    new_fullname = st.text_input("Nome completo (opzionale)")

    if st.button("Crea Account"):
        if not new_email or not new_password:
            st.warning("Inserisci email e password per creare l'account.")
        else:
            try:
                # Creazione account via Admin
                response = supabase_admin.auth.sign_up({
                    "email": new_email,
                    "password": new_password
                })
                user = response.user
                if user:
                    # Conferma automatica
                    supabase_admin.auth.admin.update_user_by_id(
                        uid=user.id,
                        attributes={"email_confirmed_at": "now()"}
                    )
                    # Inserimento nella tabella users (opzionale)
                    user_data = {"email": new_email}
                    if new_name:
                        user_data["name"] = new_name
                    if new_fullname:
                        user_data["full_name"] = new_fullname
                    supabase_admin.table("users").insert(user_data).execute()

                    st.success(f"✅ Utente creato: {new_email}. Salva i tuoi dati!")
                else:
                    st.error("❌ Errore nella creazione dell'utente")
            except Exception as e:
                st.error(f"❌ Errore creazione account: {e}")

