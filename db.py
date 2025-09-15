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
        # Paramètres de connexion séparés (pas de DATABASE_URL avec caractères spéciaux)
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
                cursor_factory=RealDictCursor  # résultats sous forme de dictionnaire
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


# Exemple d'utilisation
if __name__ == "__main__":
    print("🔄 Test de connexion à Supabase...")
    if test_connection():
        try:
            tables = db.execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            print(f"\n📋 Tables disponibles: {[table['table_name'] for table in tables]}")
        except Exception as e:
            print(f"Erreur: {e}")
        finally:
            close_connection()

