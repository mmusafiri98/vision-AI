# streamlit_app.py

import streamlit as st
from transformers import (
    AutoModelForCausalLM, AutoTokenizer,
    BlipProcessor, BlipForConditionalGeneration
)
from PIL import Image
import torch

# -----------------------
# Chargement des modèles
# -----------------------
@st.cache_resource
def load_llm():
    name = "Qwen/Qwen1.5-0.5B-Chat"  # modèle Qwen léger pour démo
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        name,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
        trust_remote_code=True
    )
    return tok, model

@st.cache_resource
def load_blip():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

tok, llm = load_llm()
blip_processor, blip_model = load_blip()

# -----------------------
# Fonctions utilitaires
# -----------------------
def blip_caption(image: Image.Image) -> str:
    """Génère une description avec BLIP."""
    inputs = blip_processor(image, return_tensors="pt").to(blip_model.device)
    with torch.no_grad():
        out = blip_model.generate(**inputs, max_new_tokens=30)
    return blip_processor.decode(out[0], skip_special_tokens=True)

def chat_llm(history, user_message):
    """Dialogue avec Qwen et ajoute contexte historique."""
    history.append({"role": "user", "content": user_message})
    prompt = ""
    for m in history:
        if m["role"] == "user":
            prompt += f"User: {m['content']}\n"
        else:
            prompt += f"Assistant: {m['content']}\n"
    prompt += "Assistant:"

    inputs = tok(prompt, return_tensors="pt").to(llm.device)
    with torch.no_grad():
        out_ids = llm.generate(
            **inputs,
            max_new_tokens=200,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tok.eos_token_id
        )
    text = tok.decode(out_ids[0], skip_special_tokens=True)
    answer = text.split("Assistant:")[-1].strip()
    history.append({"role": "assistant", "content": answer})
    return answer, history

# -----------------------
# Interface Streamlit
# -----------------------
st.set_page_config(page_title="Chat Qwen + BLIP", page_icon="🤖")

st.title("🤖 Chatbot Qwen + 🖼️ BLIP")
st.write("Dialogue avec **Qwen**. Si tu charges une image et demandes de la décrire, "
         "le modèle utilisera **BLIP** pour générer une légende.")

# Stocker l’historique de conversation
if "history" not in st.session_state:
    st.session_state.history = []

# Upload image
uploaded_file = st.file_uploader("📂 Charge une image (facultatif)", type=["jpg", "jpeg", "png"])
image = None
if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Image chargée", use_column_width=True)

# Zone de chat
user_msg = st.chat_input("💬 Pose une question ou demande 'Décris l'image'")
if user_msg:
    # Si l'utilisateur demande une description et une image est chargée
    if image is not None and ("décris" in user_msg.lower() or "decrire" in user_msg.lower()):
        caption = blip_caption(image)
        bot_answer = f"D'accord ! Voici la description de l'image : {caption}"
        st.session_state.history.append({"role": "assistant", "content": bot_answer})
    else:
        bot_answer, st.session_state.history = chat_llm(st.session_state.history, user_msg)

# Afficher l’historique dans style chat
for msg in st.session_state.history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])
