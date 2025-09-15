import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

# Charger les variables d'environnement
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
            'host': os.getenv('DB_HOST', 'db.bhtpxckpzhsgstycjiwb.supabase.co'),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '[8A%/pB7^Kt2'),  # ⚠️ Mets ton vrai mot de passe ici ou dans .env
            'port': os.getenv('DB_PORT', '5432'),
            'sslmode': 'require'
        }
        self.connection = None

    def connect(self):
        """
        Établit la connexion à la base de données
        """
        try:
            self.connection = psycopg2.connect(
                **self.db_config,
                cursor_factory=RealDictCursor
            )
            logger.info("✅ Connexion à Supabase établie avec succès")
            return self.connection
        except psycopg2.Error as e:
            logger.error(f"❌ Erreur de connexion à la base de données: {e}")
            raise e

    def disconnect(self):
        """
        Ferme la connexion à la base de données
        """
        if self.connection:
            self.connection.close()
            logger.info("🔌 Connexion fermée")

    def get_cursor(self):
        """
        Retourne un curseur pour exécuter des requêtes
        """
        if not self.connection:
            self.connect()
        return self.connection.cursor()

    def execute_query(self, query, params=None):
        """
        Exécute une requête SELECT et retourne les résultats
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return results
        except psycopg2.Error as e:
            logger.error(f"Erreur lors de l'exécution de la requête: {e}")
            raise e

    def execute_insert(self, query, params=None):
        """
        Exécute une requête INSERT/UPDATE/DELETE
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return cursor.rowcount
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Erreur lors de l'insertion: {e}")
            raise e


# Instance globale
db = DatabaseConnection()

# Fonctions utilitaires
def get_connection():
    return db.connect()

def close_connection():
    db.disconnect()

def test_connection():
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
    """
    Crée la table users si elle n'existe pas
    """
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
    """
    Crée un nouvel utilisateur
    """
    # Vérifier si l'utilisateur existe déjà
    existing = get_user_by_email(email)
    if existing:
        raise ValueError("Un utilisateur avec cet email existe déjà.")

    query = """
    INSERT INTO users (username, email, password, full_name)
    VALUES (%s, %s, %s, %s)
    RETURNING *;
    """
    results = db.execute_query(query, (username, email, password, full_name))
    return results[0] if results else None


def get_user_by_email(email):
    """
    Récupère un utilisateur par email
    """
    query = "SELECT * FROM users WHERE email = %s;"
    results = db.execute_query(query, (email,))
    return results[0] if results else None


# --------------------------
# Exemple d'utilisation
# --------------------------
if __name__ == "__main__":
    print("🔄 Test de connexion à Supabase...")
    if test_connection():
        # Création de la table users
        create_users_table()

        # Création d'un utilisateur
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

        # Récupération d'un utilisateur
        user = get_user_by_email("test@example.com")
        print(f"👀 Utilisateur récupéré: {user}")

        # Lister les tables
        tables = db.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        print(f"\n📋 Tables disponibles: {[table['table_name'] for table in tables]}")

        close_connection()
