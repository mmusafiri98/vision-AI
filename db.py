import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

# Charger les variables d'environnement (.env)
load_dotenv()

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self):
        """
        Initialise la connexion à la base de données Supabase
        """
        self.db_config = {
            "host": os.getenv("DB_HOST", "db.bhtpxckpzhsgstycjiwb.supabase.co"),
            "database": os.getenv("DB_NAME", "postgres"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),  # ⚠️ Mets ton mot de passe dans .env
            "port": os.getenv("DB_PORT", "5432"),
            "sslmode": "require",
        }
        self.connection = None

    def connect(self):
        """Établit la connexion"""
        try:
            self.connection = psycopg2.connect(
                **self.db_config,
                cursor_factory=RealDictCursor
            )
            logger.info("✅ Connexion à Supabase établie avec succès")
            return self.connection
        except psycopg2.Error as e:
            logger.error(f"❌ Erreur de connexion: {e}")
            raise e

    def disconnect(self):
        """Ferme la connexion"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("🔌 Connexion fermée")

    def get_cursor(self):
        """Retourne un curseur actif"""
        if not self.connection:
            self.connect()
        return self.connection.cursor()

    def execute_query(self, query, params=None):
        """Exécute une requête SELECT"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except psycopg2.Error as e:
            logger.error(f"Erreur SQL (SELECT): {e}")
            raise e

    def execute_insert(self, query, params=None):
        """Exécute une requête INSERT/UPDATE/DELETE"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return cursor.rowcount
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Erreur SQL (INSERT/UPDATE/DELETE): {e}")
            raise e


# Instance globale
db = DatabaseConnection()

# --------------------------
# Fonctions utilitaires
# --------------------------
def get_connection():
    return db.connect()

def close_connection():
    db.disconnect()

def test_connection():
    """Teste la connexion"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"🎉 Test réussi ! Version PostgreSQL: {version['version']}")
            return True
    except Exception as e:
        logger.error(f"❌ Test de connexion échoué: {e}")
        return False
    finally:
        close_connection()

# --------------------------
# Fonctions spécifiques "users"
# --------------------------
def create_users_table():
    """Crée la table users si elle n'existe pas"""
    query = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(200) NOT NULL,
        full_name VARCHAR(100),
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    db.execute_insert(query)
    logger.info("📋 Table 'users' prête.")

def create_user(username, email, password, full_name=None):
    """Crée un nouvel utilisateur"""
    if get_user_by_email(email):
        raise ValueError("Un utilisateur avec cet email existe déjà.")
    query = """
    INSERT INTO users (username, email, password, full_name)
    VALUES (%s, %s, %s, %s)
    RETURNING *;
    """
    result = db.execute_query(query, (username, email, password, full_name))
    return result[0] if result else None

def get_user_by_email(email):
    """Récupère un utilisateur par email"""
    query = "SELECT * FROM users WHERE email = %s;"
    result = db.execute_query(query, (email,))
    return result[0] if result else None

# --------------------------
# Exemple d'utilisation
# --------------------------
if __name__ == "__main__":
    print("🔄 Test de connexion à Supabase...")
    if test_connection():
        # Créer la table users
        create_users_table()

        # Créer un utilisateur
        try:
            print("\n👤 Création d'un utilisateur de test...")
            new_user = create_user(
                username="test_user",
                email="test@example.com",
                password="password123",  # ⚠️ A hasher en prod
                full_name="Utilisateur Test"
            )
            print(f"✅ Utilisateur créé: {new_user}")
        except ValueError as e:
            print(f"ℹ️ {e}")

        # Récupérer un utilisateur
        user = get_user_by_email("test@example.com")
        print(f"👀 Utilisateur récupéré: {user}")

        # Lister les tables
        tables = db.execute_query("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public';
        """)
        print(f"\n📋 Tables disponibles: {[t['table_name'] for t in tables]}")

        close_connection()

