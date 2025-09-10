import streamlit as st
from transformers import AutoProcessor, AutoModelForCausalLM
from PIL import Image
import torch
import json
import os
import uuid

# === CONFIG ===
st.set_page_config(page_title="Vision AI Chat (Local Qwen-7B)", page_icon="🎯", layout="wide")
CHAT_DIR = "chats"
EDITED_IMAGES_DIR = "edited_images"
os.makedirs(CHAT_DIR, exist_ok=True)
os.makedirs(EDITED_IMAGES_DIR, exist_ok=True)

SYSTEM_PROMPT = """
You are Vision AI.
Help users by describing images, answering questions clearly, and providing basic image editing guidance.
Always answer naturally as Vision AI.
"""

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

def list_chats():
    return sorted([f.replace(".json","") for f in os.listdir(CHAT_DIR) if f.endswith(".json")])

# === BLIP MODEL pour caption ===
@st.cache_resource
def load_blip():
    from transformers import BlipProcessor, BlipForConditionalGeneration
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
    st.session_state.processor, st.session_state.model = load_blip()

# === QWEN-7B LOCAL ===
@st.cache_resource
def load_local_qwen7b():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_name = "Qwen/Qwen-7B-Instruct"  # modèle local
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto", torch_dtype=torch.float16)
    return tokenizer, model, device

if "tokenizer" not in st.session_state:
    st.session_state.tokenizer, st.session_state.local_model, st.session_state.device = load_local_qwen7b()

# === SIDEBAR ===
st.sidebar.title("📂 Gestion des chats")
if st.sidebar.button("➕ Nouveau chat"):
    st.session_state.chat_id = str(uuid.uuid4())
    st.session_state.chat_history = []
    save_chat_history([], st.session_state.chat_id)

available_chats = list_chats()
if available_chats:
    selected = st.sidebar.selectbox(
        "Vos discussions:",
        available_chats,
        index=available_chats.index(st.session_state.chat_id) if st.session_state.chat_id in available_chats else 0
    )
    if selected != st.session_state.chat_id:
        st.session_state.chat_id = selected
        st.session_state.chat_history = load_chat_history(selected)

st.sidebar.title("🛠️ Mode")
mode = st.sidebar.radio("Choisir:", ["📝 Description", "✏️ Édition"])
st.session_state.mode = "describe" if mode=="📝 Description" else "edit"

# === DISPLAY CHAT ===
st.markdown("<h1 style='text-align:center'>🎯 Vision AI Chat (Local)</h1>", unsafe_allow_html=True)
chat_container = st.container()
with chat_container:
    for msg in st.session_state.chat_history:
        badge = "📝" if msg["type"]=="describe" else "✏️" if msg["type"]=="edit" else "💬"
        if msg["role"]=="user":
            st.markdown(f"**👤 Vous {badge}:** {msg['content']}")
            if msg.get("image") and os.path.exists(msg["image"]):
                st.image(msg["image"], width=300)
        elif msg["role"]=="assistant":
            st.markdown(f"**🤖 Vision AI {badge}:** {msg['content']}")
            if msg.get("edited_image") and os.path.exists(msg["edited_image"]):
                st.image(msg["edited_image"], width=300)

# === FORM ===
with st.form("chat_form", clear_on_submit=False):
    uploaded_file = st.file_uploader("📤 Upload image", type=["jpg","jpeg","png"])
    if st.session_state.mode=="describe":
        user_message = st.text_input("💬 Question sur l'image (optionnel)")
        submit = st.form_submit_button("🚀 Analyser")
    else:
        user_message = st.text_input("✏️ Instruction d'édition", placeholder="ex: rendre le ciel bleu")
        submit = st.form_submit_button("✏️ Éditer")

# === PROCESSING ===
def generate_response_local(prompt):
    tokenizer = st.session_state.tokenizer
    model = st.session_state.local_model
    device = st.session_state.device

    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_new_tokens=512, do_sample=True, top_p=0.95, temperature=0.7)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response

if submit:
    # --- IMAGE UPLOAD ---
    if uploaded_file:
        image = Image.open(uploaded_file).convert("RGB")
        image_path = os.path.join(CHAT_DIR, f"img_{uuid.uuid4().hex}.png")
        image.save(image_path)

        if st.session_state.mode=="describe":
            caption = generate_caption(image, st.session_state.processor, st.session_state.model)
            query = f"{SYSTEM_PROMPT}\nImage description: {caption}\nUser question: {user_message or ''}"
            response = generate_response_local(query)
            st.session_state.chat_history.append({"role":"user","content":user_message or "Image envoyée","image":image_path,"type":"describe"})
            st.session_state.chat_history.append({"role":"assistant","content":response,"type":"describe"})
        else:
            st.error("⚠️ Édition d'image non supportée en local pour Qwen-7B")
    # --- TEXTE SEUL ---
    elif user_message:
        query = f"{SYSTEM_PROMPT}\nUser: {user_message}"
        response = generate_response_local(query)
        st.session_state.chat_history.append({"role":"user","content":user_message,"type":"text"})
        st.session_state.chat_history.append({"role":"assistant","content":response,"type":"text"})

    save_chat_history(st.session_state.chat_history, st.session_state.chat_id)

