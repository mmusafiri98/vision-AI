import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Charger les variables d'environnement (dotenv optionnel)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv n'est pas installé, on continue sans
    pass

# Configuration de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnection:
    def __init__(self):
        """
        Initialise la connexion à la base de données Supabase
        """
        # URL de connexion Supabase (remplacez par votre vraie URL avec mot de passe)
        self.database_url = os.getenv('DATABASE_URL') or \
                           "postgresql://postgres:8A%/pB7^Kt2@db.bhtpxckpzhsgstycjiwb.supabase.co:5432/postgres?sslmode=require"
        
        # Paramètres de connexion alternatifs (si vous préférez séparer les paramètres)
        self.db_config = {
            'host': os.getenv('DB_HOST', 'db.bhtpxckpzhsgstycjiwb.supabase.co'),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '8A%/pB7^Kt2'),
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

# ========== FONCTIONS POUR GESTION DES UTILISATEURS ==========

def create_users_table():
    """
    Crée la table users si elle n'existe pas
    """
    try:
        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.execute_insert(query)
        logger.info("✅ Table 'users' créée ou vérifiée")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création de la table users: {e}")
        return False

def create_user(username, email, password, full_name=None):
    """
    Crée un nouvel utilisateur dans la base de données
    
    Args:
        username (str): Nom d'utilisateur unique
        email (str): Email de l'utilisateur
        password (str): Mot de passe (vous devriez le hasher)
        full_name (str): Nom complet (optionnel)
    
    Returns:
        dict: Informations de l'utilisateur créé ou None si erreur
    """
    try:
        query = """
        INSERT INTO users (username, email, password, full_name, created_at) 
        VALUES (%s, %s, %s, %s, NOW()) 
        RETURNING id, username, email, full_name, created_at;
        """
        
        result = db.execute_query(query, (username, email, password, full_name))
        
        if result:
            logger.info(f"✅ Utilisateur créé: {username}")
            return dict(result[0])  # Convertir en dictionnaire
        return None
        
    except psycopg2.IntegrityError as e:
        if "unique constraint" in str(e).lower():
            logger.error(f"❌ Utilisateur ou email déjà existant: {username}")
            raise ValueError("Nom d'utilisateur ou email déjà utilisé")
        raise e
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création de l'utilisateur: {e}")
        raise e

def get_user_by_email(email):
    """
    Récupère un utilisateur par son email
    
    Args:
        email (str): Email de l'utilisateur
    
    Returns:
        dict: Informations utilisateur ou None
    """
    try:
        query = "SELECT id, username, email, full_name, created_at FROM users WHERE email = %s;"
        result = db.execute_query(query, (email,))
        return dict(result[0]) if result else None
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération de l'utilisateur: {e}")
        return None

def get_user_by_username(username):
    """
    Récupère un utilisateur par son nom d'utilisateur
    
    Args:
        username (str): Nom d'utilisateur
    
    Returns:
        dict: Informations utilisateur ou None
    """
    try:
        query = "SELECT id, username, email, full_name, created_at FROM users WHERE username = %s;"
        result = db.execute_query(query, (username,))
        return dict(result[0]) if result else None
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération de l'utilisateur: {e}")
        return None

def authenticate_user(username_or_email, password):
    """
    Authentifie un utilisateur
    
    Args:
        username_or_email (str): Nom d'utilisateur ou email
        password (str): Mot de passe
    
    Returns:
        dict: Informations utilisateur si authentification réussie, None sinon
    """
    try:
        query = """
        SELECT id, username, email, full_name, created_at 
        FROM users 
        WHERE (username = %s OR email = %s) AND password = %s;
        """
        result = db.execute_query(query, (username_or_email, username_or_email, password))
        return dict(result[0]) if result else None
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'authentification: {e}")
        return None

def update_user(user_id, **kwargs):
    """
    Met à jour les informations d'un utilisateur
    
    Args:
        user_id (int): ID de l'utilisateur
        **kwargs: Champs à mettre à jour (username, email, full_name, etc.)
    
    Returns:
        dict: Informations utilisateur mises à jour ou None
    """
    try:
        # Construire la requête dynamiquement
        fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in ['username', 'email', 'full_name', 'password']:
                fields.append(f"{field} = %s")
                values.append(value)
        
        if not fields:
            raise ValueError("Aucun champ valide à mettre à jour")
        
        values.append(user_id)  # Pour la clause WHERE
        
        query = f"""
        UPDATE users 
        SET {', '.join(fields)}, updated_at = NOW() 
        WHERE id = %s 
        RETURNING id, username, email, full_name, updated_at;
        """
        
        result = db.execute_query(query, tuple(values))
        return dict(result[0]) if result else None
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour de l'utilisateur: {e}")
        raise e

def delete_user(user_id):
    """
    Supprime un utilisateur
    
    Args:
        user_id (int): ID de l'utilisateur
    
    Returns:
        bool: True si suppression réussie, False sinon
    """
    try:
        query = "DELETE FROM users WHERE id = %s;"
        rows_affected = db.execute_insert(query, (user_id,))
        return rows_affected > 0
    except Exception as e:
        logger.error(f"❌ Erreur lors de la suppression de l'utilisateur: {e}")
        return False

def get_all_users():
    """
    Récupère tous les utilisateurs
    
    Returns:
        list: Liste des utilisateurs
    """
    try:
        query = "SELECT id, username, email, full_name, created_at FROM users ORDER BY created_at DESC;"
        result = db.execute_query(query)
        return [dict(row) for row in result] if result else []
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des utilisateurs: {e}")
        return []

# ========== EXEMPLE D'UTILISATION ==========
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
