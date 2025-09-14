import psycopg2
import psycopg2.extras
import bcrypt
import os

# Connexion à PostgreSQL (Streamlit Cloud utilise les secrets)
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "user_vision_ai"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "password"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

# === UTILISATEURS ===
def create_user(email, password, name):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s) RETURNING id, email, name",
                (email, hashed, name))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(user)

def verify_user(email, password):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return dict(user)
    return None

# === CONVERSATIONS ===
def create_conversation(user_id, title="Nouvelle conversation"):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING *", (user_id, title))
    conv = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(conv)

def get_conversations(user_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM conversations WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
    convs = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(c) for c in convs]

# === MESSAGES ===
def add_message(conversation_id, sender, content):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("INSERT INTO messages (conversation_id, sender, content) VALUES (%s, %s, %s) RETURNING *",
                (conversation_id, sender, content))
    msg = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(msg)

def get_messages(conversation_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM messages WHERE conversation_id=%s ORDER BY created_at ASC", (conversation_id,))
    msgs = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(m) for m in msgs]
