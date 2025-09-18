# Importazioni (già presenti nel tuo codice)
import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch
import pandas as pd
import io
import db  # Module per la base di dati (non fornito, supposto esistente)
import time

# ... (altre importazioni)

# Configurazione della pagina Streamlit
st.set_page_config(page_title="Vision AI Chat", layout="wide")

# Prompt sistema per me (Vision AI)
SYSTEM_PROMPT = """You are Vision AI.
You were created by Pepe Musafiri, an Artificial Intelligence Engineer,
with contributions from Meta AI.
Your role is to help users with any task they need, from image analysis
and editing to answering questions clearly and helpfully.
Always answer naturally as Vision AI.

When you receive an image description starting with [IMAGE], you should:
1. Acknowledge that you can see and analyze the image
2. Provide detailed analysis of what you observe
3. Answer any specific questions about the image
4. Be helpful and descriptive in your analysis"""

# Caricamento del modello BLIP per l'analisi delle immagini
@st.cache_resource
def load_blip():
    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return processor, model
    except Exception as e:
        st.error(f"Errore BLIP: {e}")
        return None, None

# Generazione di didascalie per le immagini
def generate_caption(image, processor, model):
    if processor is None or model is None:
        return "Descrizione indisponibile"
    try:
        inputs = processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
            model = model.to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return f"Errore generazione: {e}"

# Inizializzazione della sessione
if "user" not in st.session_state:
    st.session_state.user = {"id": "guest", "email": "Invité"}
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages_memory" not in st.session_state:
    st.session_state.messages_memory = []
if "processor" not in st.session_state or "model" not in st.session_state:
    st.session_state.processor, st.session_state.model = load_blip()
if "llama_client" not in st.session_state:
    try:
        # Nota: il client LLaMA non è stato configurato in questo esempio
        # st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
        st.session_state.llama_client = None
        st.warning("Impossibile connettersi a LLaMA.")
    except Exception:
        st.session_state.llama_client = None
        st.warning("Impossibile connettersi a LLaMA.")

# Funzioni per interagire con il modello di linguaggio
def get_ai_response(query: str) -> str:
    if not st.session_state.llama_client:
        return " Vision AI non disponibile."
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
        return f" Errore modello: {e}"

def stream_response(text, placeholder):
    """Animazione di digitazione per visualizzare il testo carattere per carattere"""
    full_text = ""
    text_str = str(text)

    # Fasi di animazione
    # 1. Visualizza "Sto scrivendo..."
    thinking_messages = [" Vision AI sta riflettendo", " Vision AI sta analizzando", " Vision AI sta generando una risposta"]
    for msg in thinking_messages:
        placeholder.markdown(f"*{msg}...*")
        time.sleep(0.3)

    # 2. Animazione di digitazione carattere per carattere
    for i, char in enumerate(text_str):
        full_text += char
        # Visualizza con cursore lampeggiante stilizzato
        display_text = full_text + "**█**"
        placeholder.markdown(display_text)

        # Velocità variabile: più rapida per gli spazi, più lenta per la punteggiatura
        if char == ' ':
            time.sleep(0.01)
        elif char in '.,!?;:':
            time.sleep(0.1)
        else:
            time.sleep(0.03)

    # 3. Visualizza il testo finale in modo pulito
    placeholder.markdown(full_text)

    # 4. Piccolo effetto finale
    time.sleep(0.2)
    placeholder.markdown(full_text + " ")
    time.sleep(0.5)
    placeholder.markdown(full_text)

# Autenticazione
st.sidebar.title("")
if st.session_state.user["id"] == "guest":
    tab1, tab2 = st.sidebar.tabs(["Connessione", "Iscriviti"])
    with tab1:
        email = st.text_input(" Email")
        password = st.text_input(" Password", type="password")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button(" Entra"):
                user_result = db.verify_user(email, password)
                if user_result:
                    st.session_state.user = user_result
                    st.session_state.conversation = None
                    st.session_state.messages_memory = []
                    st.success("Connessione riuscita!")
                    st.experimental_rerun()
                else:
                    st.error("Email o password non validi")
        with col2:
            if st.button(" Modalità Ospite"):
                st.session_state.user = {"id": "guest", "email": "Invité"}
                st.session_state.conversation = None
                st.session_state.messages_memory = []
                st.experimental_rerun()
    with tab2:
        email_reg = st.text_input(" Email", key="reg_email")
        name_reg = st.text_input(" Nome completo", key="reg_name")
        pass_reg = st.text_input(" Password", type="password", key="reg_password")
        if st.button(" Crea il tuo account"):
            if email_reg and name_reg and pass_reg:
                ok = db.create_user(email_reg, pass_reg, name_reg)
                if ok:
                    st.success("Account creato, accedi.")
                else:
                    st.error("Errore creazione account")
    st.stop()
else:
    st.sidebar.success(f" Connesso: {st.session_state.user.get('email')}")

    # Bottone di disconnessione
    if st.sidebar.button(" Disconnetti"):
        st.session_state.user = {"id": "guest", "email": "Invité"}
        st.session_state.conversation = None
        st.session_state.messages_memory = []
        st.experimental_rerun()

# Conversazioni
st.sidebar.title(" Le tue conversazioni")
if st.session_state.user["id"] != "guest":
    if st.sidebar.button(" Nuova conversazione"):
        conv = db.create_conversation(st.session_state.user["id"], "Nuova discussione")
        st.session_state.conversation = conv
        st.session_state.messages_memory = []
        st.experimental_rerun()

    try:
        convs = db.get_conversations(st.session_state.user["id"])
        if convs:
            options = ["Scegli una conversazione..."] + [f"{c['description']} - {c['created_at']}" for c in convs]
            sel = st.sidebar.selectbox(" Le tue conversazioni:", options)
            if sel != "Scegli una conversazione...":
                idx = options.index(sel) - 1
                selected_conv = convs[idx]
                if st.session_state.conversation != selected_conv:
                    st.session_state.conversation = selected_conv
                    st.session_state.messages_memory = []
                    st.experimental_rerun()
        else:
            st.sidebar.info("Nessuna conversazione. Creane una.")
    except Exception as e:
        st.sidebar.error(f"Errore caricamento conversazioni: {e}")

# Intestazione
st.markdown("<h1 style='text-align:center; color:#2E8B57;'> Vision AI Chat</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Creato da <b>Pepe Musafiri</b> (Ingegnere di Intelligenza Artificiale) con il contributo di <b>Meta AI</b></p>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#666;'>Connesso come: <b>{st.session_state.user.get('email')}</b></p>", unsafe_allow_html=True)

# Visualizza i messaggi esistenti
display_msgs = []
if st.session_state.conversation:
    conv_id = st.session_state.conversation.get("conversation_id")
    try:
        db_msgs = db.get_messages(conv_id)
        for m in db_msgs:
            display_msgs.append({"sender": m["sender"], "content": m["content"], "created_at": m["created_at"], "type": m.get("type", "text")})
    except Exception as e:
        st.error(f"Errore caricamento messaggi: {e}")
else:
    display_msgs = st.session_state.messages_memory.copy()

# Visualizza la cronologia dei messaggi
for m in display_msgs:
    role = "user" if m["sender"] in ["user","user_api_request"] else "assistant"
    with st.chat_message(role):
        # Se è un messaggio di immagine, visualizza l'immagine se esiste nel contenuto
        if m.get("type") == "image" and "[IMAGE]" in m["content"]:
            st.write("📷 Immagine caricata per analisi")
            # Visualizza la descrizione dell'immagine
            description = m["content"].replace("[IMAGE] ", "")
            st.write(f"*Descrizione automatica: {description}*")
        else:
            # Utilizza markdown per un miglior rendering dei messaggi storici
            st.markdown(m["content"])

# Contenitore per i nuovi messaggi
message_container = st.container()

# Modulo di input unificato
with st.form(key="chat_form", clear_on_submit=True):
    # Caricamento di un'immagine (opzionale)
    uploaded_file = st.file_uploader("📷 Aggiungi un'immagine (opzionale)", type=["png","jpg","jpeg"], key="image_upload")

    # Campo di testo principale
    user_input = st.text_area("💭 Inserisci il tuo messaggio...", key="user_message", placeholder="Poni la tua domanda o descrivi ciò che vuoi che io analizzi nell'immagine...", height=80)

    # Bottone di invio unico
    submit_button = st.form_submit_button("📤 Invia", use_container_width=True)

# Elaborazione unificata
if submit_button and (user_input or uploaded_file is not None):

    # Variabili per costruire il messaggio completo
    full_message = ""
    image_caption = ""

    # **Gestione delle Immagini che iniziano con [IMAGE]**
    if user_input and user_input.startswith("[IMAGE]"):
        st.write("📷 **Vision AI può vedere e analizzare l'immagine.**")
        # Analisi dell'immagine
        image_description = user_input.replace("[IMAGE] ", "")
        st.write(f"**Descrizione dell'immagine:** {image_description}")

        # **Analisi Dettagliata**
        # Nota: per una vera analisi, avresti bisogno di un'immagine reale caricata o di un'API di analisi delle immagini.
        # Per ora, fornirò una risposta di esempio.
        st.write("**Analisi Dettagliata dell'Immagine:**")
        st.write("L'immagine sembra essere un paesaggio naturale con alberi, un fiume e un cielo nuvoloso.")
        st.write("Gli elementi principali dell'immagine sono:")
        st.write("- **Colore Principale:** Verde")
        st.write("- **Mood:** Calmo, Sereno")
        st.write("- **Oggetti Principali:** Alberi, Fiume, Cielo Nuvoloso")

        # **Risposta al Messaggio**
        prompt = f"{SYSTEM_PROMPT}\n\nUtente: {user_input}"
        with message_container:
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response_placeholder.write("Vision AI sta riflettendo... ")
                resp = get_ai_response(prompt)
                stream_response(resp, response_placeholder)

    # Elaborazione dell'immagine se presente
    elif uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)

            # Contenitore per l'immagine
            image_container = st.container()
            with image_container:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.image(image, caption="Immagine caricata per analisi", width=250)
                with col2:
                    with st.spinner("Analisi dell'immagine in corso..."):
                        image_caption = generate_caption(image, st.session_state.processor, st.session_state.model)
                    st.write(f"**Descrizione automatica:**\n{image_caption}")

            # Costruisci il messaggio con l'immagine
            full_message = f"[IMAGE] {image_caption}"
            if user_input.strip():
                full_message += f"\n\nDomanda/Richiesta dell'utente: {user_input}"

            # Salva il messaggio di immagine con testo
            conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
            if conv_id:
                db.add_message(conv_id, "user", full_message, "image")
            else:
                st.session_state.messages_memory.append({
                    "sender": "user", 
                    "content": full_message, 
                    "created_at": None,
                    "type": "image"
                })

        except Exception as e:
            st.error(f"Errore durante l'elaborazione dell'immagine: {e}")
            full_message = user_input if user_input else ""

    # Se non c'è un'immagine, utilizza solo l'input dell'utente
    elif user_input.strip():
        full_message = user_input
        # Visualizza il messaggio dell'utente
        with message_container:
            with st.chat_message("user"):
                st.markdown(user_input)

    # Gestisci la risposta del modello
    if full_message:
        prompt = f"{SYSTEM_PROMPT}\n\nUtente: {full_message}"

        # Contenitore per la risposta del modello
        response_container = st.container()
        with response_container:
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response_placeholder.write("Vision AI sta riflettendo... ")
                resp = get_ai_response(prompt)
                stream_response(resp, response_placeholder)

        # Salva la risposta
        conv_id = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else None
        if conv_id:
            db.add_message(conv_id, "assistant", resp, "text")
        else:
            st.session_state.messages_memory.append({
                "sender": "assistant", 
                "content": resp, 
                "created_at": None,
                "type": "text"
            })

        st.experimental_rerun()

# Messaggio di aiuto
st.markdown("---")
st.info("💡 **Come utilizzare Vision AI:**\n"
        "• **Solo Testo:** Poni le tue domande normalmente\n"
        "• **Solo Immagine:** Carica un'immagine, verrà analizzata automaticamente\n"
        "• **Immagine + Testo:** Carica un'immagine e inserisci la tua domanda per un'analisi mirata")

# Esportazione CSV
if display_msgs:
    st.markdown("---")
    with st.expander("📂 Esporta la conversazione"):
        df = pd.DataFrame(display_msgs)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        conv_id_for_file = st.session_state.conversation.get("conversation_id") if st.session_state.conversation else "invite"
        st.download_button(
            "💾 Scarica la conversazione (CSV)",
            csv_buffer.getvalue(),
            file_name=f"conversazione_{conv_id_for_file}.csv",
            mime="text/csv",
            use_container_width=True
        )
