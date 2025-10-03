---\n"
        else:
            results_text += "\n❌ Aucune vidéo trouvée.\n"
    
    elif search_type == "wikipedia":
        results = search_wikipedia(query)
        
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"\n📚 ARTICLE WIKIPEDIA #{i} ({result.get('language', 'FR')}):\n"
                results_text += f"   Titre: {result['title']}\n"
                results_text += f"   URL: {result['url']}\n"
                results_text += f"   Extrait: {result['snippet']}\n"
                
                # Scraper le contenu complet de Wikipedia
                page_content = scrape_page_content(result['url'], max_chars=2000)
                if page_content:
                    results_text += f"   📖 Contenu: {page_content}...\n"
                
                results_text += f"   ---\n"
        else:
            results_text += "\n❌ Aucun article trouvé.\n"
    
    elif search_type == "news":
        results = search_news(query)
        
        if results:
            for i, result in enumerate(results, 1):
                results_text += f"\n📰 ACTUALITÉ #{i}:\n"
                results_text += f"   Titre: {result['title']}\n"
                results_text += f"   Date: {result['date']}\n"
                results_text += f"   URL: {result['url']}\n"
                
                if i <= 3:
                    page_content = scrape_page_content(result['url'], max_chars=1500)
                    if page_content:
                        results_text += f"   📄 Article: {page_content}...\n"
                
                results_text += f"   ---\n"
        else:
            results_text += "\n❌ Aucune actualité trouvée.\n"
    
    results_text += """
==========================================
⚠️ RAPPEL CRITIQUE:
- Ces résultats couvrent TOUTES LES ANNÉES disponibles sur Internet
- Vous DEVEZ utiliser ces informations dans votre réponse
- Citez les sources et dates mentionnées
- Si aucun résultat n'est trouvé, dites-le clairement
=========================================="""
    
    return results_text

def detect_search_intent(user_message):
    """Détecte le type de recherche nécessaire"""
    message_lower = user_message.lower()
    
    # Mots-clés par catégorie
    search_keywords = [
        'recherche', 'cherche', 'trouve', 'informations sur', 'info sur',
        'actualité', 'news', 'dernières nouvelles', 'quoi de neuf',
        'what is', 'who is', 'définition', 'expliquer', 'c\'est quoi',
        'météo', 'weather', 'actualités sur', 'information récente',
        'video', 'vidéo', 'youtube', 'regarder', 'montre', 'voir',
        'dernières infos', 'parle moi de', 'dis moi sur', 'connais tu'
    ]
    
    news_keywords = [
        'actualité', 'news', 'nouvelles', 'dernières nouvelles',
        'quoi de neuf', 'info du jour', 'breaking', 'flash', 'aujourd\'hui'
    ]
    
    wiki_keywords = [
        'définition', 'c\'est quoi', 'qui est', 'what is', 'who is',
        'expliquer', 'wikipedia', 'définir', 'qu\'est-ce que'
    ]
    
    youtube_keywords = [
        'video', 'vidéo', 'youtube', 'regarde', 'montre moi', 
        'voir video', 'regarder', 'visionner', 'film', 'clip'
    ]
    
    # Vérifier si une recherche est nécessaire
    needs_search = any(keyword in message_lower for keyword in search_keywords)
    
    if not needs_search:
        # Recherche intelligente: si la question semble nécessiter des infos récentes
        recent_indicators = ['2024', '2025', 'récent', 'dernier', 'nouveau', 'latest']
        if any(indicator in message_lower for indicator in recent_indicators):
            needs_search = True
    
    if not needs_search:
        return None, None
    
    # Priorité: YouTube → News → Wiki → Google
    if any(keyword in message_lower for keyword in youtube_keywords):
        return "youtube", user_message
    elif any(keyword in message_lower for keyword in news_keywords):
        return "news", user_message
    elif any(keyword in message_lower for keyword in wiki_keywords):
        return "wikipedia", user_message
    else:
        return "google", user_message

def detect_datetime_intent(user_message):
    """Détecte si l'utilisateur demande la date/heure"""
    datetime_keywords = [
        'quelle heure', 'quel jour', 'quelle date', 'aujourd\'hui',
        'maintenant', 'heure actuelle', 'date actuelle', 'quel mois',
        'quelle année', 'what time', 'what date', 'current time',
        'current date', 'today', 'now', 'heure', 'date', 'jour',
        'sommes-nous', 'est-il', 'c\'est quel jour', 'on est quel jour',
        'quelle est la date', 'quelle est l\'heure', 'il est quelle heure'
    ]
    
    message_lower = user_message.lower()
    return any(keyword in message_lower for keyword in datetime_keywords)

# -------------------------
# AI functions avec Vision AI thinking
# -------------------------
def get_ai_response(query):
    if not st.session_state.get('llama_client'):
        return "Vision AI non disponible."
    
    try:
        resp = st.session_state.llama_client.predict(
            message=query,
            max_tokens=8192,
            temperature=0.7,
            top_p=0.95,
            api_name="/chat"
        )
        return str(resp)
    except Exception as e:
        return f"Erreur modèle: {e}"

def show_vision_ai_thinking(placeholder):
    """Affiche l'animation Vision AI thinking..."""
    thinking_frames = [
        "Vision AI thinking",
        "Vision AI thinking.",
        "Vision AI thinking..",
        "Vision AI thinking..."
    ]
    
    for _ in range(2):
        for frame in thinking_frames:
            placeholder.markdown(f"**{frame}**")
            time.sleep(0.3)

def stream_response_with_thinking(text, placeholder):
    """Affiche Vision AI thinking puis stream la réponse"""
    show_vision_ai_thinking(placeholder)
    time.sleep(0.5)
    
    full_text = ""
    for char in str(text):
        full_text += char
        placeholder.markdown(full_text + "▋")
        time.sleep(0.02)
    placeholder.markdown(full_text)

# -------------------------
# Edition d'image avec Qwen
# -------------------------
def edit_image_with_qwen(image: Image.Image, edit_instruction: str = ""):
    client = st.session_state.get("qwen_client")
    if not client:
        return None, "Client Qwen non disponible."
    
    try:
        temp_path = os.path.join(TMP_DIR, f"input_{uuid.uuid4().hex}.png")
        image.save(temp_path)
        
        prompt_message = edit_instruction if edit_instruction.strip() else "enhance and improve the image"
        
        result = client.predict(
            input_image=handle_file(temp_path),
            prompt=prompt_message,
            api_name="/global_edit"
        )
        
        if result and isinstance(result, (list, tuple)) and len(result) >= 2:
            result_path = result[0]
            status_message = result[1]
            
            if isinstance(result_path, str) and os.path.exists(result_path):
                edited_img = Image.open(result_path).convert("RGBA")
                
                final_path = os.path.join(EDITED_IMAGES_DIR, f"edited_{uuid.uuid4().hex}.png")
                edited_img.save(final_path)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
                edit_msg = f"Image éditée avec succès - {status_message}"
                if edit_instruction:
                    edit_msg += f" (instruction: {edit_instruction})"
                    
                return edited_img, edit_msg
        
        return None, "Erreur traitement image"
    except Exception as e:
        return None, str(e)

def create_edit_context(original_caption, edit_instruction, edited_caption, success_info):
    return {
        "original_description": original_caption,
        "edit_instruction": edit_instruction,
        "edited_description": edited_caption,
        "edit_info": success_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def process_image_edit_request(image: Image.Image, edit_instruction: str, conv_id: str):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.info("Analyse de l'image originale...")
        progress_bar.progress(20)
        time.sleep(0.5)
        
        original_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
        
        status_text.info(f"Édition en cours: '{edit_instruction}'...")
        progress_bar.progress(40)
        
        edited_img, result_info = edit_image_with_qwen(image, edit_instruction)
        
        if edited_img:
            status_text.info("Analyse de l'image éditée...")
            progress_bar.progress(70)
            time.sleep(0.5)
            
            edited_caption = generate_caption(edited_img, st.session_state.processor, st.session_state.model)
            
            status_text.info("Sauvegarde et finalisation...")
            progress_bar.progress(90)
            
            edit_context = create_edit_context(original_caption, edit_instruction, edited_caption, result_info)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Image originale")
                st.image(image, caption="Avant", use_column_width=True)
                st.write(f"**Description:** {original_caption}")
                
            with col2:
                st.subheader("Image éditée")
                st.image(edited_img, caption=f"Après: {edit_instruction}", use_column_width=True)
                st.write(f"**Description:** {edited_caption}")
                st.write(f"**Info technique:** {result_info}")
            
            st.success("Édition terminée avec succès !")
            
            response_content = f"""**Édition d'image terminée !**

**Instruction:** {edit_instruction}

**Analyse comparative:**
- **Image originale:** {original_caption}
- **Image éditée:** {edited_caption}

**Modifications:** J'ai appliqué "{edit_instruction}". L'image montre maintenant: {edited_caption}

**Info technique:** {result_info}"""
            
            edited_b64 = image_to_base64(edited_img.convert("RGB"))
            success = add_message(conv_id, "assistant", response_content, "image", edited_b64, None)
            
            if success:
                progress_bar.progress(100)
                status_text.success("Traitement terminé!")
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()
                
                st.session_state.messages_memory.append({
                    "message_id": str(uuid.uuid4()),
                    "sender": "assistant",
                    "content": response_content,
                    "type": "image",
                    "image_data": edited_b64,
                    "edit_context": str(edit_context),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                img_buffer = io.BytesIO()
                edited_img.convert("RGB").save(img_buffer, format="PNG")
                
                st.download_button(
                    label="Télécharger PNG",
                    data=img_buffer.getvalue(),
                    file_name=f"edited_image_{int(time.time())}.png",
                    mime="image/png"
                )
                
                return True
            else:
                status_text.error("Erreur sauvegarde")
                progress_bar.empty()
                return False
        else:
            status_text.error(f"Échec édition: {result_info}")
            progress_bar.empty()
            return False
    except Exception as e:
        status_text.error(f"Erreur: {e}")
        progress_bar.empty()
        return False

def get_editing_context_from_conversation():
    context_info = []
    for msg in st.session_state.messages_memory:
        if msg.get("edit_context"):
            try:
                if isinstance(msg["edit_context"], str):
                    import ast
                    edit_ctx = ast.literal_eval(msg["edit_context"])
                else:
                    edit_ctx = msg["edit_context"]
                
                context_info.append(f"""
Édition précédente:
- Image originale: {edit_ctx.get('original_description', 'N/A')}
- Résultat: {edit_ctx.get('edited_description', 'N/A')}
- Date: {edit_ctx.get('timestamp', 'N/A')}
""")
            except:
                continue
    
    return "\n".join(context_info) if context_info else ""

# -------------------------
# Interface de récupération de mot de passe
# -------------------------
def show_password_reset():
    st.subheader("Récupération de mot de passe")
    
    if st.session_state.reset_step == "request":
        with st.form("password_reset_request"):
            reset_email = st.text_input("Adresse email")
            submit_reset = st.form_submit_button("Envoyer le code")
            
            if submit_reset and reset_email.strip() and supabase:
                try:
                    user_check = supabase.table("users").select("*").eq("email", reset_email.strip()).execute()
                    
                    if user_check.data:
                        reset_token = generate_reset_token()
                        
                        if store_reset_token(reset_email.strip(), reset_token):
                            st.session_state.reset_email = reset_email.strip()
                            st.session_state.reset_token = reset_token
                            st.session_state.reset_step = "verify"
                            
                            st.success("Code généré!")
                            st.warning(f"**Code:** {reset_token}")
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.error("Email introuvable")
                except Exception as e:
                    st.error(f"Erreur: {e}")
        
        if st.button("← Retour connexion"):
            st.session_state.reset_step = "request"
            st.rerun()
    
    elif st.session_state.reset_step == "verify":
        with st.form("password_reset_verify"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                token_input = st.text_input("Code de récupération")
                new_password = st.text_input("Nouveau mot de passe", type="password")
                confirm_password = st.text_input("Confirmer", type="password")
            
            with col2:
                st.write("**Code généré:**")
                st.code(st.session_state.reset_token)
            
            submit = st.form_submit_button("Réinitialiser")
            
            if submit:
                if not token_input.strip():
                    st.error("Entrez le code")
                elif not new_password:
                    st.error("Entrez un mot de passe")
                elif len(new_password) < 6:
                    st.error("Minimum 6 caractères")
                elif new_password != confirm_password:
                    st.error("Mots de passe différents")
                elif token_input.strip() != st.session_state.reset_token:
                    st.error("Code incorrect")
                else:
                    if reset_password(st.session_state.reset_email, token_input.strip(), new_password):
                        st.success("Mot de passe réinitialisé!")
                        st.session_state.reset_step = "request"
                        st.session_state.reset_email = ""
                        st.session_state.reset_token = ""
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Erreur réinitialisation")

# -------------------------
# Interface Admin
# -------------------------
def show_admin_page():
    st.title("Interface Administrateur")
    
    if st.button("← Retour"):
        st.session_state.page = "main"
        st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["Utilisateurs", "Conversations", "Statistiques"])
    
    with tab1:
        if supabase:
            try:
                users = supabase.table("users").select("*").order("created_at", desc=True).execute()
                if users.data:
                    for user in users.data:
                        with st.expander(f"{user.get('name')} ({user.get('email')})"):
                            st.write(f"**ID:** {user.get('id')[:8]}...")
                            st.write(f"**Rôle:** {user.get('role', 'user')}")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab2:
        if supabase:
            try:
                convs = supabase.table("conversations").select("*").limit(20).execute()
                if convs.data:
                    for conv in convs.data:
                        st.write(f"- {conv.get('description')} ({conv.get('created_at')[:10]})")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with tab3:
        if supabase:
            try:
                users_count = supabase.table("users").select("id", count="exact").execute()
                convs_count = supabase.table("conversations").select("id", count="exact").execute()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Utilisateurs", users_count.count or 0)
                with col2:
                    st.metric("Conversations", convs_count.count or 0)
            except Exception as e:
                st.error(f"Erreur: {e}")

def cleanup_temp_files():
    try:
        current_time = time.time()
        for filename in os.listdir(TMP_DIR):
            filepath = os.path.join(TMP_DIR, filename)
            if os.path.isfile(filepath) and current_time - os.path.getctime(filepath) > 3600:
                os.remove(filepath)
    except:
        pass

# -------------------------
# Session State
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}

if "conversation" not in st.session_state:
    st.session_state.conversation = None

if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []

if "processor" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()

if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        st.session_state.llama_client = None

if "qwen_client" not in st.session_state:
    try:
        st.session_state.qwen_client = Client("Selfit/ImageEditPro")
    except:
        st.session_state.qwen_client = None

if "reset_step" not in st.session_state:
    st.session_state.reset_step = "request"

if "reset_email" not in st.session_state:
    st.session_state.reset_email = ""

if "reset_token" not in st.session_state:
    st.session_state.reset_token = ""

if "page" not in st.session_state:
    st.session_state.page = "main"

# -------------------------
# Navigation
# -------------------------
if st.session_state.page == "admin":
    show_admin_page()
    st.stop()

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("Authentification")

if st.session_state.user["id"] == "guest":
    tab1, tab2, tab3 = st.sidebar.tabs(["Connexion", "Inscription", "Reset"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        
        if st.button("Se connecter", type="primary"):
            if email and password:
                with st.spinner("Connexion..."):
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.success("Connecté!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Identifiants invalides")

    with tab2:
        email_reg = st.text_input("Email", key="reg_email")
        name_reg = st.text_input("Nom", key="reg_name")
        pass_reg = st.text_input("Mot de passe", type="password", key="reg_pass")
        pass_confirm = st.text_input("Confirmer", type="password", key="reg_confirm")
        
        if st.button("Créer compte"):
            if email_reg and name_reg and pass_reg and pass_confirm:
                if pass_reg != pass_confirm:
                    st.error("Mots de passe différents")
                elif len(pass_reg) < 6:
                    st.error("Minimum 6 caractères")
                else:
                    with st.spinner("Création..."):
                        if create_user(email_reg, pass_reg, name_reg):
                            st.success("Compte créé!")
                            time.sleep(1)

    with tab3:
        show_password_reset()
    
    st.stop()
else:
    st.sidebar.success(f"Connecté: {st.session_state.user.get('email')}")
    
    if st.session_state.user.get('role') == 'admin':
        st.sidebar.markdown("**Admin**")
        if st.sidebar.button("Interface Admin"):
            st.session_state.page = "admin"
            st.rerun()
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.user = {"id": "guest", "email": "Invité", "role": "guest"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.rerun()

# -------------------------
# Gestion Conversations
# -------------------------
if st.session_state.user["id"] != "guest":
    st.sidebar.title("Conversations")
    
    if st.sidebar.button("Nouvelle conversation"):
        with st.spinner("Création..."):
            conv = create_conversation(st.session_state.user["id"], "Nouvelle discussion")
            if conv:
                st.session_state.conversation = conv
                st.session_state.messages_memory = []
                st.success("Créée!")
                time.sleep(1)
                st.rerun()
    
    convs = get_conversations(st.session_state.user["id"])
    if convs:
        options = [f"{c['description']} ({c['created_at'][:16]})" for c in convs]
        
        current_idx = 0
        if st.session_state.conversation:
            current_id = st.session_state.conversation.get("conversation_id")
            for i, c in enumerate(convs):
                if c.get("conversation_id") == current_id:
                    current_idx = i
                    break
        
        selected_idx = st.sidebar.selectbox(
            "Vos conversations:",
            range(len(options)),
            format_func=lambda i: options[i],
            index=current_idx
        )
        
        selected_conv = convs[selected_idx]
        
        if (not st.session_state.conversation or 
            st.session_state.conversation.get("conversation_id") != selected_conv.get("conversation_id")):
            
            with st.spinner("Chargement..."):
                st.session_state.conversation = selected_conv
                messages = get_messages(selected_conv.get("conversation_id"))
                st.session_state.messages_memory = messages
                time.sleep(0.5)
                st.rerun()

# -------------------------
# Interface principale
# -------------------------
st.title("Vision AI Chat - Analyse & Édition d'Images")

if st.session_state.conversation:
    st.subheader(f"Conversation: {st.session_state.conversation.get('description')}")

tab1, tab2 = st.tabs(["Chat Normal", "Mode Éditeur"])

with tab1:
    st.write("Mode chat avec analyse d'images et recherche web avancée")
    
    if st.session_state.messages_memory:
        for msg in st.session_state.messages_memory:
            role = "user" if msg.get("sender") == "user" else "assistant"
            
            with st.chat_message(role):
                if msg.get("type") == "image" and msg.get("image_data"):
                    try:
                        st.image(base64_to_image(msg["image_data"]), width=300)
                    except:
                        pass
                
                st.markdown(msg.get("content", ""))
    
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            user_input = st.text_area(
                "Votre message:",
                height=100,
                placeholder="Posez vos questions..."
            )
        
        with col2:
            uploaded_file = st.file_uploader(
                "Image",
                type=["png","jpg","jpeg"],
                key="chat_upload"
            )
        
        submit_chat = st.form_submit_button("Envoyer")

with tab2:
    st.write("Mode éditeur avec Qwen-Image-Edit")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Image à éditer")
        editor_file = st.file_uploader(
            "Image",
            type=["png", "jpg", "jpeg"],
            key="editor_upload"
        )
        
        if editor_file:
            editor_image = Image.open(editor_file).convert("RGBA")
            st.image(editor_image, caption="Original", use_column_width=True)
            
            with st.spinner("Analyse..."):
                original_desc = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                st.write(f"**Description:** {original_desc}")
    
    with col2:
        st.subheader("Instructions d'édition")
        
        example_prompts = [
            "Add a beautiful sunset background",
            "Change to black and white", 
            "Add flowers",
            "Make it look like a painting",
            "Add snow falling",
            "Cyberpunk style",
            "Remove background",
            "Add a person",
            "More colorful",
            "Add magic effects"
        ]
        
        selected_example = st.selectbox("Exemples", ["Custom..."] + example_prompts)
        
        if selected_example == "Custom...":
            edit_instruction = st.text_area(
                "Instruction (en anglais):",
                height=120,
                placeholder="ex: Add a man, change sky..."
            )
        else:
            edit_instruction = st.text_area(
                "Instruction:",
                value=selected_example,
                height=120
            )
        
        if st.button("Éditer", type="primary", disabled=not (editor_file and edit_instruction.strip())):
            if not st.session_state.conversation:
                conv = create_conversation(st.session_state.user["id"], "Édition d'images")
                if conv:
                    st.session_state.conversation = conv
            
            if st.session_state.conversation:
                original_caption = generate_caption(editor_image, st.session_state.processor, st.session_state.model)
                user_msg = f"**Édition demandée**\n\n**Image:** {original_caption}\n\n**Instruction:** {edit_instruction}"
                original_b64 = image_to_base64(editor_image.convert("RGB"))
                
                add_message(
                    st.session_state.conversation.get("conversation_id"),
                    "user",
                    user_msg,
                    "image",
                    original_b64
                )
                
                st.session_state.messages_memory.append({
                    "message_id": str(uuid.uuid4()),
                    "sender": "user",
                    "content": user_msg,
                    "type": "image",
                    "image_data": original_b64,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
                success = process_image_edit_request(
                    editor_image,
                    edit_instruction,
                    st.session_state.conversation.get("conversation_id")
                )
                
                if success:
                    st.rerun()

# -------------------------
# Traitement chat
# -------------------------
if 'submit_chat' in locals() and submit_chat and (user_input.strip() or uploaded_file):
    if not st.session_state.conversation:
        with st.spinner("Création conversation..."):
            conv = create_conversation(st.session_state.user["id"], "Discussion")
            if conv:
                st.session_state.conversation = conv
            else:
                st.error("Impossible de créer conversation")
                st.stop()
    
    conv_id = st.session_state.conversation.get("conversation_id")
    
    message_content = user_input.strip()
    image_data = None
    msg_type = "text"
    
    if uploaded_file:
        with st.spinner("Analyse de l'image..."):
            image = Image.open(uploaded_file)
            image_data = image_to_base64(image)
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            message_content = f"[IMAGE] {caption}"
            
            if user_input.strip():
                message_content += f"\n\nQuestion: {user_input.strip()}"
            msg_type = "image"
            time.sleep(0.5)
    
    if message_content:
        add_message(conv_id, "user", message_content, msg_type, image_data)
        
        user_msg = {
            "sender": "user",
            "content": message_content,
            "type": msg_type,
            "image_data": image_data,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.messages_memory.append(user_msg)
        
        lower = user_input.lower()
        if (any(k in lower for k in ["edit", "édite", "modifie"]) and uploaded_file):
            edit_instruction = user_input.strip()
            success = process_image_edit_request(
                Image.open(uploaded_file).convert("RGBA"),
                edit_instruction,
                conv_id
            )
            if success:
                st.rerun()
        else:
            edit_context = get_editing_context_from_conversation()
            
            # Construction du prompt enrichi avec TOUJOURS date/heure
            prompt = f"{SYSTEM_PROMPT}\n\n"
            
            # TOUJOURS ajouter les informations de date/heure
            datetime_info = format_datetime_for_prompt()
            prompt += f"{datetime_info}\n\n"
            
            # Détecter et effectuer une recherche web si nécessaire
            search_type, search_query = detect_search_intent(user_input)
            
            if search_type and search_query:
                with st.spinner(f"🔍 Recherche {search_type} en cours..."):
                    # Afficher un message informatif
                    search_info = st.empty()
                    search_info.info(f"Recherche de '{search_query}' sur {search_type.upper()}...")
                    
                    web_results = format_web_search_for_prompt(search_query, search_type)
                    prompt += f"{web_results}\n\n"
                    
                    search_info.success(f"✅ Recherche {search_type} terminée!")
                    time.sleep(1)
                    search_info.empty()
            
            # Ajouter le contexte d'édition si disponible
            if edit_context:
                prompt += f"[EDIT_CONTEXT] {edit_context}\n\n"
            
            # Message final
            prompt += f"""
==========================================
INSTRUCTIONS FINALES:
1. Utilisez [DATETIME] pour les questions de date/heure
2. Utilisez [WEB_SEARCH] pour les informations recherchées
3. Soyez précis et citez vos sources
4. Les recherches couvrent TOUTES les années jusqu'à 2025
==========================================

Utilisateur: {message_content}"""
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                if edit_context and any(w in user_input.lower() for w in ["edit", "image", "avant", "après"]):
                    with st.spinner("Consultation mémoire..."):
                        time.sleep(1)
                
                # Appel API avec Vision AI thinking
                response = get_ai_response(prompt)
                
                # Afficher Vision AI thinking puis la réponse
                stream_response_with_thinking(response, placeholder)
                
                add_message(conv_id, "assistant", response, "text")
                
                ai_msg = {
                    "sender": "assistant",
                    "content": response,
                    "type": "text",
                    "image_data": None,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.messages_memory.append(ai_msg)
                
                st.rerun()

# -------------------------
# Footer
# -------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.write("**Vision AI:**")
    st.write("- Analyse intelligente")
    st.write("- Édition avec Qwen")
    st.write("- Mémoire des éditions")

with col2:
    st.write("**Chat:**")
    st.write("- Conversations sauvegardées")
    st.write("- Contexte des éditions")
    st.write("- Discussion modifications")

with col3:
    st.write("**Recherche Web:**")
    st.write("- Google + DuckDuckGo")
    st.write("- YouTube avec transcriptions")
    st.write("- Wikipedia multilingue")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.write("**Fonctionnalités améliorées:**")
    st.write("- ✅ Date/heure temps réel")
    st.write("- ✅ Recherche Google (si API)")
    st.write("- ✅ DuckDuckGo (GRATUIT, sans API)")
    st.write("- ✅ YouTube + transcriptions")
    st.write("- ✅ Scraping de pages web")

with col2:
    st.write("**Sources disponibles:**")
    st.write("- Google Custom Search")
    st.write("- DuckDuckGo Search")
    st.write("- YouTube Data API v3")
    st.write("- Wikipedia FR/EN")
    st.write("- Google News RSS")

# -------------------------
# Configuration API Keys
# -------------------------
with st.expander("⚙️ Configuration APIs & Installation"):
    st.markdown("""
    ### 🔑 Configuration des API Keys (OPTIONNEL)
    
    **IMPORTANT:** L'application fonctionne maintenant SANS API keys grâce à DuckDuckGo !
    
    **Configuration dans Streamlit Cloud:**
    Settings → Secrets → Ajoutez (optionnel):
```toml
    GOOGLE_API_KEY = "votre_clé_google"
    GOOGLE_SEARCH_ENGINE_ID = "votre_search_engine_id"
    YOUTUBE_API_KEY = "votre_clé_youtube"

