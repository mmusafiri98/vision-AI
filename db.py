import os
from supabase import create_client
from datetime import datetime

# Configuration Supabase
def get_supabase_client():
    """Initialise et retourne le client Supabase"""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
        supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_service_key:
            raise Exception("Variables d'environnement Supabase manquantes")
            
        # Utiliser la clé service pour avoir tous les droits
        client = create_client(supabase_url, supabase_service_key)
        return client
    except Exception as e:
        print(f"Erreur connexion Supabase: {e}")
        return None

# Instance globale du client
supabase = get_supabase_client()

# ===== FONCTIONS UTILISATEUR =====

def verify_user(email, password):
    """
    Vérifie les identifiants utilisateur
    Retourne: dict avec {id, email, name} ou None si échec
    """
    try:
        if not supabase:
            return None
            
        # Authentification avec Supabase
        response = supabase.auth.sign_in_with_password({
            "email": email, 
            "password": password
        })
        
        if response.user:
            user_data = {
                'id': response.user.id,
                'email': response.user.email,
                'name': response.user.user_metadata.get('name', email.split('@')[0])
            }
            return user_data
        return None
        
    except Exception as e:
        print(f"Erreur verify_user: {e}")
        return None

def create_user(email, password, name=None):
    """
    Crée un nouvel utilisateur
    Retourne: True si succès, False sinon
    """
    try:
        if not supabase:
            return False
            
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name or email.split('@')[0]}
        })
        
        return response.user is not None
        
    except Exception as e:
        print(f"Erreur create_user: {e}")
        return False

# ===== FONCTIONS CONVERSATIONS =====

def create_conversation(user_id, title):
    """
    Crée une nouvelle conversation
    Retourne: dict avec {id, title, created_at, user_id} ou None
    """
    try:
        if not supabase:
            return None
            
        data = {
            "user_id": user_id,
            "title": title,
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase.table('conversations').insert(data).execute()
        
        if response.data and len(response.data) > 0:
            conv = response.data[0]
            return {
                'id': conv['id'],
                'title': conv['title'],
                'created_at': datetime.fromisoformat(conv['created_at']),
                'user_id': conv['user_id']
            }
        return None
        
    except Exception as e:
        print(f"Erreur create_conversation: {e}")
        return None

def get_conversations(user_id):
    """
    Récupère toutes les conversations d'un utilisateur
    Retourne: liste de conversations ou []
    """
    try:
        if not supabase:
            return []
            
        response = supabase.table('conversations')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .execute()
        
        conversations = []
        for conv in response.data:
            conversations.append({
                'id': conv['id'],
                'title': conv['title'],
                'created_at': datetime.fromisoformat(conv['created_at']),
                'user_id': conv['user_id']
            })
        
        return conversations
        
    except Exception as e:
        print(f"Erreur get_conversations: {e}")
        return []

# ===== FONCTIONS MESSAGES =====

def add_message(conversation_id, sender, content):
    """
    Ajoute un message à une conversation
    sender: 'user' ou 'assistant'
    Retourne: True si succès, False sinon
    """
    try:
        if not supabase:
            return False
            
        data = {
            "conversation_id": conversation_id,
            "sender": sender,
            "content": content,
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase.table('messages').insert(data).execute()
        return len(response.data) > 0
        
    except Exception as e:
        print(f"Erreur add_message: {e}")
        return False

def get_messages(conversation_id):
    """
    Récupère tous les messages d'une conversation
    Retourne: liste de messages [{sender, content, created_at}] ou []
    """
    try:
        if not supabase:
            return []
            
        response = supabase.table('messages')\
            .select('*')\
            .eq('conversation_id', conversation_id)\
            .order('created_at', desc=False)\
            .execute()
        
        messages = []
        for msg in response.data:
            messages.append({
                'sender': msg['sender'],
                'content': msg['content'],
                'created_at': datetime.fromisoformat(msg['created_at'])
            })
        
        return messages
        
    except Exception as e:
        print(f"Erreur get_messages: {e}")
        return []

# ===== FONCTIONS DE TEST =====

def test_connection():
    """Test la connexion à Supabase"""
    try:
        if not supabase:
            return False, "Client Supabase non initialisé"
            
        # Test simple avec une requête
        response = supabase.table('conversations').select('id').limit(1).execute()
        return True, "Connexion OK"
        
    except Exception as e:
        return False, f"Erreur connexion: {e}"

# ===== INITIALISATION DES TABLES (optionnel) =====

def init_tables():
    """
    Crée les tables si elles n'existent pas
    Note: Normalement fait dans l'interface Supabase
    """
    print("⚠️ Créez ces tables dans votre dashboard Supabase :")
    print("""
    -- Table conversations
    CREATE TABLE conversations (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );

    -- Table messages  
    CREATE TABLE messages (
        id SERIAL PRIMARY KEY,
        conversation_id INTEGER REFERENCES conversations(id),
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

if __name__ == "__main__":
    # Test du module
    print("🧪 Test du module db.py...")
    
    success, message = test_connection()
    print(f"Connexion Supabase: {'✅' if success else '❌'} {message}")
    
    if not success:
        print("\n📋 Vérifiez vos variables d'environnement :")
        print("- SUPABASE_URL")
        print("- SUPABASE_SERVICE_KEY") 
        
        init_tables()
