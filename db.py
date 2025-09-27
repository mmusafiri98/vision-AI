import os
import uuid
import re
from datetime import datetime
from dateutil import parser
import streamlit as st
from supabase import create_client
from streamlit_extras.switch_page_button import switch_page

# ===================================================
# CONFIGURATION SUPABASE
# ===================================================

def get_supabase_client():
    """Initialise et retourne le client Supabase avec gestion d'erreur améliorée"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url:
            raise Exception("Variable SUPABASE_URL manquante")
        if not supabase_service_key:
            raise Exception("Variable SUPABASE_SERVICE_KEY manquante")

        if not supabase_url.startswith(('http://', 'https://')):
            raise Exception(f"SUPABASE_URL invalide: {supabase_url}")

        client = create_client(supabase_url, supabase_service_key)

        # Test rapide
        try:
            client.table("users").select("*").limit(1).execute()
            print("✅ Connexion Supabase réussie")
        except Exception as test_e:
            print(f"⚠️ Connexion Supabase mais test échoué: {test_e}")

        return client
    except Exception as e:
        st.error(f"❌ Erreur connexion Supabase: {e}")
        return None

# Initialiser le client global
supabase = get_supabase_client()

# ===================================================
# FONCTIONS UTILITAIRES
# ===================================================

def clean_message_content(content):
    if not content:
        return ""
    content = str(content).replace("\x00", "")
    content = content.replace("\\", "\\\\").replace("'", "''").replace('"', '""')
    if len(content) > 10000:
        content = content[:9950] + "... [contenu tronqué]"
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()

def safe_parse_datetime(date_str):
    try:
        if not date_str or date_str == "NULL":
            return datetime.now()
        return parser.isoparse(date_str)
    except Exception:
        return datetime.now()

def validate_uuid(uuid_string):
    try:
        uuid.UUID(str(uuid_string))
        return True
    except (ValueError, TypeError):
        return False

# ===================================================
# USERS
# ===================================================

def verify_user(email, password):
    """Vérifie les identifiants utilisateur et redirige si admin"""
    try:
        if not supabase:
            return None
        if not email or not password:
            return None

        # Auth via Supabase
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if auth_response.user:
                # Récupérer aussi le rôle dans la table users
                table_response = supabase.table("users").select("*").eq("email", email).execute()
                role = "user"
                if table_response.data and len(table_response.data) > 0:
                    role = table_response.data[0].get("role", "user")

                user_data = {
                    "id": auth_response.user.id,
                    "email": auth_response.user.email,
                    "name": auth_response.user.user_metadata.get("name", email.split("@")[0]),
                    "role": role
                }

                # ✅ Si admin → redirection admin
                if user_data["role"] == "admin":
                    st.success("Connexion réussie ! Redirection vers la page admin...")
                    switch_page("streamlit_admin")

                return user_data
        except Exception as auth_e:
            print(f"⚠️ verify_user: Auth échoué {auth_e}")

        # Fallback : vérification directe table
        try:
            table_response = supabase.table("users").select("*").eq("email", email).execute()
            if table_response.data and len(table_response.data) > 0:
                user = table_response.data[0]
                if user.get("password") == password:
                    return {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name", email.split("@")[0]),
                        "role": user.get("role", "user")
                    }
        except Exception as table_e:
            print(f"❌ verify_user: Erreur table: {table_e}")

        return None
    except Exception as e:
        print(f"❌ verify_user: Exception {e}")
        return None

def create_user(email, password, name=None, role="user"):
    """Création d’utilisateur avec rôle"""
    try:
        if not supabase:
            return False
        if not email or not password:
            return False

        try:
            auth_response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"name": name or email.split("@")[0], "role": role}
            })
            if auth_response.user:
                # On insère aussi dans la table "users" avec rôle
                user_data = {
                    "id": str(auth_response.user.id),
                    "email": email,
                    "password": password,
                    "name": name or email.split("@")[0],
                    "role": role,
                    "created_at": datetime.now().isoformat()
                }
                supabase.table("users").insert(user_data).execute()
                return True
        except Exception as auth_e:
            print(f"⚠️ create_user: Auth échoué {auth_e}")

        # fallback insertion manuelle
        try:
            user_data = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": password,
                "name": name or email.split("@")[0],
                "role": role,
                "created_at": datetime.now().isoformat()
            }
            supabase.table("users").insert(user_data).execute()
            return True
        except Exception as table_e:
            print(f"❌ create_user: Erreur table: {table_e}")
        return False
    except Exception as e:
        print(f"❌ create_user: Exception {e}")
        return False

# ===================================================
# STREAMLIT LOGIN UI
# ===================================================

st.set_page_config(page_title="Login", page_icon="🔑", layout="centered")

st.title("🔑 Connexion")

email = st.text_input("Email")
password = st.text_input("Mot de passe", type="password")

if st.button("Se connecter"):
    user = verify_user(email, password)
    if not user:
        st.error("❌ Identifiants incorrects")
    else:
        if user["role"] != "admin":
            st.success(f"Bienvenue {user['name']} 👋")


