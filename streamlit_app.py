def get_messages(conversation_id):
    """Version debug de get_messages pour identifier le problème"""
    print(f"🔍 DEBUG: get_messages appelée avec conversation_id = {conversation_id}")
    print(f"🔍 DEBUG: type(conversation_id) = {type(conversation_id)}")
    
    try:
        # Vérifier si la connection existe
        if not hasattr(db, 'conn') or db.conn is None:
            print("❌ DEBUG: Pas de connection DB!")
            return []
        
        cursor = db.conn.cursor()
        
        # Query de debug - compter d'abord
        count_query = "SELECT COUNT(*) FROM messages WHERE conversation_id = %s"
        print(f"🔍 DEBUG: Exécution query count: {count_query}")
        print(f"🔍 DEBUG: Avec paramètre: {conversation_id}")
        
        cursor.execute(count_query, (conversation_id,))
        count_result = cursor.fetchone()
        print(f"🔍 DEBUG: Count result: {count_result}")
        
        if count_result and count_result[0] > 0:
            print(f"✅ DEBUG: {count_result[0]} messages trouvés en DB!")
            
            # Query principale
            main_query = """
                SELECT sender, content, type, image_data, created_at 
                FROM messages 
                WHERE conversation_id = %s 
                ORDER BY created_at ASC
            """
            print(f"🔍 DEBUG: Exécution query principale: {main_query}")
            
            cursor.execute(main_query, (conversation_id,))
            results = cursor.fetchall()
            print(f"🔍 DEBUG: Results fetchall: {len(results)} lignes")
            
            messages = []
            for i, row in enumerate(results):
                print(f"🔍 DEBUG: Row {i}: {row}")
                message = {
                    'sender': row[0],
                    'content': row[1],
                    'type': row[2] or 'text',
                    'image_data': row[3],
                    'created_at': row[4]
                }
                messages.append(message)
                print(f"🔍 DEBUG: Message {i} ajouté: {message['sender']}")
            
            cursor.close()
            print(f"✅ DEBUG: Retourne {len(messages)} messages")
            return messages
        else:
            print("❌ DEBUG: Aucun message trouvé avec ce conversation_id")
            
            # Test de debug: voir tous les conversation_id disponibles
            debug_query = "SELECT DISTINCT conversation_id FROM messages LIMIT 5"
            cursor.execute(debug_query)
            existing_convs = cursor.fetchall()
            print(f"🔍 DEBUG: Conversation_ids existants en DB: {existing_convs}")
            
            cursor.close()
            return []
            
    except Exception as e:
        print(f"❌ DEBUG: Erreur dans get_messages: {e}")
        print(f"❌ DEBUG: Type d'erreur: {type(e).__name__}")
        import traceback
        print(f"❌ DEBUG: Traceback complet:")
        traceback.print_exc()
        return []


# ALTERNATIVE: Si vous utilisez SQLite, la syntaxe peut être différente
def get_messages_sqlite_version(conversation_id):
    """Version pour SQLite si c'est votre DB"""
    try:
        cursor = db.conn.cursor()
        
        # Pour SQLite, utilisez ? au lieu de %s
        cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (conversation_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            cursor.execute("""
                SELECT sender, content, type, image_data, created_at 
                FROM messages 
                WHERE conversation_id = ? 
                ORDER BY created_at ASC
            """, (conversation_id,))
            
            results = cursor.fetchall()
            messages = []
            for row in results:
                messages.append({
                    'sender': row[0],
                    'content': row[1],
                    'type': row[2] or 'text',
                    'image_data': row[3],
                    'created_at': row[4]
                })
            return messages
        return []
        
    except Exception as e:
        print(f"Erreur SQLite get_messages: {e}")
        return []


# TEST MANUEL DIRECT
def test_db_manually():
    """Fonction pour tester manuellement la DB"""
    test_conversation_id = "8ad43b63-97fd-4244-ad9a-7ac148428d79"  # Votre conversation actuelle
    
    print("=== TEST MANUEL DB ===")
    
    try:
        cursor = db.conn.cursor()
        
        # 1. Vérifier la structure de la table
        print("1. Structure de la table messages:")
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'")
        columns = cursor.fetchall()
        print(f"Colonnes: {columns}")
        
        # 2. Compter tous les messages
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        print(f"2. Total messages en DB: {total_messages}")
        
        # 3. Voir quelques messages d'exemple
        cursor.execute("SELECT conversation_id, sender, content FROM messages LIMIT 3")
        sample_messages = cursor.fetchall()
        print(f"3. Échantillon messages: {sample_messages}")
        
        # 4. Chercher spécifiquement cette conversation
        cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s", (test_conversation_id,))
        specific_count = cursor.fetchone()[0]
        print(f"4. Messages pour conversation {test_conversation_id}: {specific_count}")
        
        cursor.close()
        
    except Exception as e:
        print(f"Erreur test manuel: {e}")

# Pour exécuter le test manuel, ajoutez ceci dans votre code Streamlit:
if st.sidebar.button("🧪 Test Manuel DB"):
    test_db_manually()
