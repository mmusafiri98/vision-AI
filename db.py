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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJodHB4Y2twemhzZ3N0eWNqaXdiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc4Nzg2MDMsImV4cCI6MjA3MzQ1NDYwM30.RmqgQdoMNAt-TtGaqWkSz4YOhZSLXUcVfbK6e784ewM"  # ⚠️ Utiliser Service Role pour créer des utilisateurs
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --------------------------
# Fonctions utilisateurs
# --------------------------
def create_users_table():
    """
    ⚠️ L'API Supabase ne permet pas de créer des tables via HTTPS.
    Crée la table "users" directement dans le Dashboard Supabase.
    Colonnes recommandées : id, name, email, password_hash, full_name, created_at
    """
    logger.info("📋 Assurez-vous que la table 'users' existe déjà dans Supabase.")


def create_user(email: str, password: str, name: str = None):
    """
    Crée un utilisateur via Supabase Auth et ajoute infos dans la table users.
    """
    try:
        # Créer l'utilisateur via Supabase Auth
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        user = response.user
        if not user:
            raise Exception(f"❌ Impossible de créer l'utilisateur: {response.data}")

        # Ajouter infos supplémentaires dans la table users
        user_data = {"email": email}
        if name:
            user_data["name"] = name

        supabase.table("users").insert(user_data).execute()
        logger.info(f"👤 Utilisateur créé: {user}")
        return user
    except Exception as e:
        logger.error(f"❌ Erreur create_user: {e}")
        raise e


def verify_user(email: str, password: str):
    """
    Connexion utilisateur via Supabase Auth
    """
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if response.user:
            logger.info(f"👀 Utilisateur connecté: {response.user}")
            return response.user
        else:
            raise Exception("❌ Email ou mot de passe incorrect")
    except Exception as e:
        logger.error(f"❌ Erreur verify_user: {e}")
        raise e


def get_user_by_email(email: str):
    """
    Récupère un utilisateur dans la table users par email
    """
    response = supabase.table("users").select("*").eq("email", email).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None


def list_users():
    """
    Liste tous les utilisateurs via la table users
    """
    response = supabase.table("users").select("*").execute()
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
        logger.error(f"❌ Test de connexion échoué: {e}")
        return False


# --------------------------
# Exemple d'utilisation
# --------------------------
if __name__ == "__main__":
    print("🔄 Test de connexion à Supabase via API...")

    if test_connection():
        create_users_table()

        # Créer un utilisateur de test
        try:
            new_user = create_user(
                email="test@example.com",
                password="password123",
                name="Test User"
            )
            print("✅ Utilisateur créé:", new_user)
        except Exception as e:
            print("❌ Erreur:", e)

        # Vérifier un utilisateur
        try:
            user = verify_user("test@example.com", "password123")
            print("👀 Utilisateur connecté:", user)
        except Exception as e:
            print("❌ Erreur:", e)

        # Lister tous les utilisateurs
        users = list_users()
        print(f"\n📋 Tous les utilisateurs: {users}")

