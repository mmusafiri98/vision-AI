# streamlit_app.py

import streamlit as st
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch

# --- Chargement du modèle BLIP ---
@st.cache_resource
def load_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

processor, model = load_model()

# --- Interface Streamlit ---
st.set_page_config(page_title="BLIP Image Captioning", page_icon="🖼️")

st.title("🖼️ BLIP - Image Captioning")
st.write("Charge une image et laisse le modèle **BLIP** générer une légende automatique.")

# Upload image
uploaded_file = st.file_uploader("Choisis une image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Image chargée", use_column_width=True)

    # Bouton pour générer la légende
    if st.button("Générer la légende"):
        inputs = processor(image, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=30)
        caption = processor.decode(out[0], skip_special_tokens=True)

        st.subheader("📜 Légende générée :")
        st.success(caption)
