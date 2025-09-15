import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

# Charger les variables d'environnement
load_dotenv()

# Configuration de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnection:
    def __init__(self):
        """
        Initialise la connexion à la base de données Supabase
        """
        # URL de connexion Supabase
        self.database_url = os.getenv('DATABASE_URL') or \
                           "postgresql://postgres:[8A%/pB7^Kt2@db.bhtpxckpzhsgstycjiwb.supabase.co:5432/postgres?sslmode=require"
        
        # Paramètres de connexion alternatifs (si vous préférez séparer les paramètres)
        self.db_config = {
            'host': os.getenv('DB_HOST', 'db.bhtpxckpzhsgstycjiwb.supabase.co'),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'VOTRE_MOT_DE_PASSE'),
            'port': os.getenv('DB_PORT', '5432'),
            'sslmode': 'require'
        }
        
        self.connection = None
    
    def connect(self):
        """
        Établit la connexion à la base de données
        """
        try:
            # Méthode 1: Avec l'URL complète
            self.connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor  # Pour avoir des résultats sous forme de dictionnaire
            )
            
            # Alternative - Méthode 2: Avec les paramètres séparés
            # self.connection = psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
            
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
        
        Args:
            query (str): Requête SQL
            params (tuple): Paramètres de la requête (optionnel)
        
        Returns:
            list: Résultats de la requête
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
        
        Args:
            query (str): Requête SQL
            params (tuple): Paramètres de la requête (optionnel)
        
        Returns:
            int: Nombre de lignes affectées
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

# Instance globale de la connexion
db = DatabaseConnection()

# Fonctions utilitaires pour une utilisation simple
def get_connection():
    """
    Retourne une connexion à la base de données
    """
    return db.connect()

def close_connection():
    """
    Ferme la connexion globale
    """
    db.disconnect()

def test_connection():
    """
    Test la connexion à la base de données
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"🎉 Test réussi ! Version PostgreSQL: {version[0]}")
            return True
    except Exception as e:
        logger.error(f"❌ Test de connexion échoué: {e}")
        return False
    finally:
        close_connection()

# Exemple d'utilisation
if __name__ == "__main__":
    # Test de la connexion
    print("🔄 Test de connexion à Supabase...")
    if test_connection():
        
        # Créer la table users si elle n'existe pas
        print("\n📋 Création/vérification de la table users...")
        create_users_table()
        
        # Exemple de création d'utilisateur
        try:
            print("\n👤 Test de création d'utilisateur...")
            new_user = create_user(
                username="test_user",
                email="test@example.com",
                password="password123",  # En production, hasher le mot de passe !
                full_name="Utilisateur Test"
            )
            print(f"Utilisateur créé: {new_user}")
            
            # Test de récupération
            user = get_user_by_email("test@example.com")
            print(f"Utilisateur récupéré: {user}")
            
        except ValueError as e:
            print(f"ℹ️  {e}")  # Utilisateur déjà existant
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    # Lister les tables
    try:
        # Lister les tables
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
