import logging
from supabase import create_client, Client

# --------------------------
# Configuration logging
# --------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------
# Configuration Supabase API
# --------------------------
SUPABASE_URL = "https://bhtpxckpzhsgstycjiwb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJodHB4Y2twemhzZ3N0eWNqaXdiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc4Nzg2MDMsImV4cCI6MjA3MzQ1NDYwM30.RmqgQdoMNAt-TtGaqWkSz4YOhZSLXUcVfbK6e784ewM"  # ⚠️ Remplace par ta clé anon (frontend) ou service_role (backend)

# Création du client Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --------------------------
# Fonctions utilisateurs
# --------------------------
def create_users_table():
    """
    ⚠️ L'API Supabase ne permet pas de créer des tables via HTTPS.
    Crée la table "users" directement dans le Dashboard Supabase.
    Colonnes recommandées : id, username, email, password, full_name, created_at
    """
    logger.info("📋 Assurez-vous que la table 'users' existe déjà dans Supabase.")


def create_user(username: str, email: str, password: str, full_name: str = None):
    """
    Crée un nouvel utilisateur via l'API Supabase
    """
    # Vérifier si l'utilisateur existe déjà
    existing_user = get_user_by_email(email)
    if existing_user:
        raise ValueError(f"Un utilisateur avec l'email '{email}' existe déjà.")

    response = supabase.table("users").insert({
        "username": username,
        "email": email,
        "password": password,  # ⚠️ Hasher le mot de passe en production
        "full_name": full_name
    }).execute()

    if response.error:
        logger.error(f"❌ Erreur lors de la création de l'utilisateur: {response.error}")
        raise Exception(response.error)
    
    logger.info(f"👤 Utilisateur créé: {response.data}")
    return response.data


def get_user_by_email(email: str):
    """
    Récupère un utilisateur par email via l'API Supabase
    """
    response = supabase.table("users").select("*").eq("email", email).execute()
    if response.error:
        logger.error(f"❌ Erreur lors de la récupération de l'utilisateur: {response.error}")
        raise Exception(response.error)
    return response.data[0] if response.data else None


def list_users():
    """
    Liste tous les utilisateurs via l'API Supabase
    """
    response = supabase.table("users").select("*").execute()
    if response.error:
        logger.error(f"❌ Erreur lors de la récupération des utilisateurs: {response.error}")
        raise Exception(response.error)
    return response.data


def test_connection():
    """
    Test basique pour vérifier que l'API Supabase répond
    """
    try:
        users = list_users()
        logger.info(f"🎉 Test réussi ! {len(users)} utilisateur(s) récupéré(s).")
        return True
    except Exception as e:
        logger.error(f"❌ Test de connexion échoué: {e}")
        return False


# --------------------------
# Exemple d'utilisation
# --------------------------
if __name__ == "__main__":
    print("🔄 Test de connexion à Supabase via API...")

    if test_connection():
        create_users_table()  # Juste pour info

        # Créer un utilisateur de test
        try:
            print("\n👤 Création d'un utilisateur de test...")
            new_user = create_user(
                username="test_user",
                email="test@example.com",
                password="password123",
                full_name="Utilisateur Test"
            )
            print("✅ Utilisateur créé:", new_user)
        except ValueError as ve:
            print("ℹ️", ve)
        except Exception as e:
            print("❌ Erreur:", e)

        # Récupérer un utilisateur
        try:
            user = get_user_by_email("test@example.com")
            print("👀 Utilisateur récupéré:", user)
        except Exception as e:
            print("❌ Erreur:", e)

        # Lister tous les utilisateurs
        try:
            users = list_users()
            print(f"\n📋 Tous les utilisateurs: {users}")
        except Exception as e:
            print("❌ Erreur:", e)

