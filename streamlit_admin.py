import streamlit as st
import pandas as pd
import io
from supabase import create_client

st.set_page_config(page_title="Vision AI Admin", layout="wide")
ADMIN_EMAIL = "essice34@gmail,com"
ADMIN_PASSWORD = "4Us,T}17!"

if "admin_logged" not in st.session_state:
    st.session_state.admin_logged = False

# -------------------------
# Login
# -------------------------
if not st.session_state.admin_logged:
    st.title("🔐 Admin Login")
    email = st.text_input("Email")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            st.session_state.admin_logged = True
            st.experimental_rerun()
        else:
            st.error("Email ou mot de passe incorrect")
    st.stop()

# -------------------------
# Dashboard
# -------------------------
st.title("🛠️ Admin Dashboard")
st.sidebar.success("Connecté en tant qu'admin")

# Utilisateurs
st.header("👥 Utilisateurs")
try:
    users = db.supabase.table("users").select("*").execute().data
    if users:
        df_users = pd.DataFrame(users)
        st.dataframe(df_users)
        csv_buffer = io.StringIO()
        df_users.to_csv(csv_buffer, index=False)
        st.download_button("💾 Télécharger les utilisateurs (CSV)", csv_buffer.getvalue(), "users.csv", "text/csv")
except Exception as e:
    st.error(f"Erreur récupération utilisateurs: {e}")

# Conversations
st.header("💬 Conversations")
try:
    convs = db.supabase.table("messager").select("*").order("created_at").execute().data
    if convs:
        df_conv = pd.DataFrame(convs)
        st.dataframe(df_conv)
        csv_buffer = io.StringIO()
        df_conv.to_csv(csv_buffer, index=False)
        st.download_button("💾 Télécharger toutes les conversations (CSV)", csv_buffer.getvalue(), "all_conversations.csv", "text/csv")

        for cid in df_conv["conversation_id"].unique():
            df_c = df_conv[df_conv["conversation_id"] == cid]
            csv_buffer = io.StringIO()
            df_c.to_csv(csv_buffer, index=False)
            st.download_button(f"💾 Télécharger CSV conversation {cid}", csv_buffer.getvalue(), f"conversation_{cid}.csv", "text/csv")
except Exception as e:
    st.error(f"Erreur récupération conversations: {e}")
