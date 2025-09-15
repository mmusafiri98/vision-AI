import streamlit as st
from supabase import create_client
import os

# --------------------------
# Configurazione Supabase
# --------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# --------------------------
# Interfaccia Login
# --------------------------
st.title("🔑 Login utente")

email = st.text_input("Email")
password = st.text_input("Password", type="password")

if st.button("Login"):
    if not email or not password:
        st.error("Per favore inserisci email e password")
    else:
        try:
            # Tentativo di login
            response = supabase_client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if response.user:
                st.success(f"✅ Login riuscito! Benvenuto {response.user.email}")
            else:
                st.error("❌ Email o password errata")
        except Exception as e:
            st.error(f"❌ Errore login: {e}")

