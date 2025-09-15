import os
import logging
from supabase import create_client, Client

# --------------------------
# Configuration logging
# --------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------
# Configuration Supabase via Secrets
# --------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

# Clients Supabase
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# --------------------------
# Fonctions utilisateurs
# --------------------------

def create_users_table():
    """
    ⚠️ Créez la table "users" directement dans le Dashboard Supabase.
    Colonnes recommandées :
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password_hash TEXT,
        full_name TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    """
    logger.info("📋 Assurez-vous que la table 'users' existe déjà dans Supabase.")

def create_user(email: str, password: str, name: str = None, full_name: str = None):
    """
    Crée un utilisateur via Supabase Auth et ajoute infos dans la table users
    Retourne un dict avec message et identifiants à afficher à l'utilisateur
    """
    try:
        # Création dans Supabase Auth
        response = supabase_admin.auth.sign_up({
            "email": email,
            "password": password
        })
        user = response.user
        if not user:
            raise Exception(f"Impossible de créer l'utilisateur: {response.data}")

        # Confirmer l'utilisateur automatiquement
        supabase_admin.auth.api.update_user(user.id, {"email_confirmed_at": "now()"})

        # Ajouter infos dans la table users
        user_data = {"email": email}
        if name:
            user_data["name"] = name
        if full_name:
            user_data["full_name"] = full_name

        supabase_admin.table("users").insert(user_data).execute()
        logger.info(f"Utilisateur créé: {user}")

        # Retourner message pour interface
        return {
            "message": "Utilisateur créé avec succès ! Merci de sauvegarder vos identifiants.",
            "email": email,
            "password": password
        }

    except Exception as e:
        logger.error(f"Erreur create_user: {e}")
        raise e

def verify_user(email: str, password: str):
    """
    Connexion utilisateur via Supabase Auth (clé anon)
    """
    try:
        response = supabase_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if response.user:
            logger.info(f"Utilisateur connecté: {response.user}")
            return response.user
        else:
            raise Exception("Email ou mot de passe incorrect")
    except Exception as e:
        logger.error(f"Erreur verify_user: {e}")
        raise e

def get_user_by_email(email: str):
    """
    Récupère un utilisateur dans la table users par email
    """
    response = supabase_admin.table("users").select("*").eq("email", email).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def list_users():
    """
    Liste tous les utilisateurs via la table users
    """
    response = supabase_admin.table("users").select("*").execute()
    if response.data:
        return response.data
    return []

def test_connection():
    """
    Test basique pour vérifier que l'API Supabase répond
    """
    try:
        users = list_users()
        logger.info(f"🎉 Test réussi ! {len(users)} utilisateur(s) récupéré(s).")
        return True
    except Exception as e:
        logger.error(f"Test de connexion échoué: {e}")
        return False

