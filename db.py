from supabase import create_client

SUPABASE_URL = "https://bhtpxckpzhsgstycjiwb.supabase.co"
SUPABASE_KEY = "VOTRE_CLE_SERVICE_ROLE"  # Service Role pour pouvoir créer des users
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Créer un utilisateur via Supabase Auth
def sign_up_user(email: str, password: str, name: str = None):
    # Crée l'utilisateur dans Supabase Auth
    response = supabase.auth.sign_up({
        "email": email,
        "password": password
    })
    
    if response.user:
        # Optionnel : Ajouter des infos supplémentaires dans la table users
        user_data = {
            "name": name,
            "email": email
        }
        supabase.table("users").insert(user_data).execute()
        return response.user
    else:
        raise Exception(response.session or response.data)

# Connexion utilisateur
def sign_in_user(email: str, password: str):
    response = supabase.auth.sign_in({
        "email": email,
        "password": password
    })
    if response.user:
        return response.user
    else:
        raise Exception(response.session or response.data)
