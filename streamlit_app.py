import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
from gradio_client import Client
import json
import os
import uuid

# === CONFIG ===
st.set_page_config(page_title="Vision AI Chat", layout="wide")

CHAT_DIR = "chats"
os.makedirs(CHAT_DIR, exist_ok=True)

# === UTILS ===
def save_chat_history(history, chat_id):
    with open(os.path.join(CHAT_DIR, f"{chat_id}.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_chat_history(chat_id):
    file_path = os.path.join(CHAT_DIR, f"{chat_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# === BLIP MODEL ===
@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

def generate_caption(image, processor, model):
    inputs = processor(image, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        model = model.to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50, num_beams=5)
    return processor.decode(out[0], skip_special_tokens=True)

# === SESSION INIT ===
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = load_chat_history(st.session_state.chat_id)
if "mode" not in st.session_state:
    st.session_state.mode = "describe"
if "processor" not in st.session_state or "model" not in st.session_state:
    processor, model = load_blip()
    st.session_state.processor = processor
    st.session_state.model = model
if "llama_client" not in st.session_state:
    try:
        st.session_state.llama_client = Client("muryshev/LLaMA-3.1-70b-it-NeMo")
    except:
        st.session_state.llama_client = None

# === SIDEBAR ===
mode_radio = st.sidebar.radio("Choisir le mode:", ["Description", "Édition"],
                              index=0 if st.session_state.mode == "describe" else 1)
# Fixer le mode **uniquement ici**, pas dans le submit
st.session_state.mode = "describe" if mode_radio == "Description" else "edit"

# === DISPLAY CHAT ===
st.markdown("<h1 style='text-align:center'>Vision AI Chat</h1>", unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    badge = msg.get("type", "text")
    if msg["role"] == "user":
        st.markdown(f"Vous ({badge}): {msg['content']}")
        if msg.get("image") and os.path.exists(msg["image"]):
            st.image(msg["image"], width=300)
    elif msg["role"] == "assistant":
        st.markdown(f"Vision AI ({badge}): {msg['content']}")
        if msg.get("edited_image") and os.path.exists(msg["edited_image"]):
            st.image(msg["edited_image"], width=300)

# === FORM ===
with st.form("chat_form", clear_on_submit=False):
    uploaded_file = st.file_uploader("Upload image", type=["jpg", "jpeg", "png"])
    if st.session_state.mode == "describe":
        user_message = st.text_input("Question sur l'image (optionnel)")
        submit = st.form_submit_button("Analyser")
    else:
        user_message = st.text_input("Instruction d'édition", placeholder="ex: rendre le ciel bleu")
        submit = st.form_submit_button("Éditer")

# === LLaMA PREDICT ===
def llama_predict(query):
    if st.session_state.llama_client is None:
        return "Erreur : modèle non disponible"
    return st.session_state.llama_client.predict(
        message=query,
        max_tokens=512,
        temperature=0.7,
        top_p=0.95,
        api_name="/chat"
    )

# === SUBMIT LOGIC ===
if submit:
    # **On fixe le msg_type ici pour garantir la cohérence**
    msg_type = "describe" if st.session_state.mode == "describe" else "edit"

    if uploaded_file:
        image = Image.open(uploaded_file).convert("RGB")
        image_path = os.path.join(CHAT_DIR, f"{uuid.uuid4().hex}.png")
        image.save(image_path)

        if msg_type == "describe":
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            query = f"Description image: {caption}. {user_message}" if user_message else f"Description image: {caption}"
            response = llama_predict(query)
        else:
            response = "Mode Édition actif, mais l'édition n'est pas encore implémentée."

        st.session_state.chat_history.append({
            "role": "user",
            "content": user_message or "Image envoyée",
            "image": image_path,
            "type": msg_type
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response,
            "type": msg_type
        })
        save_chat_history(st.session_state.chat_history, st.session_state.chat_id)

    elif user_message:
        response = llama_predict(user_message)
        st.session_state.chat_history.append({"role": "user", "content": user_message, "type": "text"})
        st.session_state.chat_history.append({"role": "assistant", "content": response, "type": "text"})
        save_chat_history(st.session_state.chat_history, st.session_state.chat_id)
