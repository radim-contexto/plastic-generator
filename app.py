import streamlit as st
import requests
import json

st.set_page_config(page_title="Gemini Diagnostika", layout="wide")
st.title("🕵️ Diagnostika API Klíče")

# Načtení klíče
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("Nastavení")
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")

if st.button("🔍 ZJISTIT DOSTUPNÉ MODELY"):
    if not api_key:
        st.error("Chybí klíč!")
        st.stop()
        
    # Čistý HTTP dotaz na seznam modelů
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    st.write(f"Dotazuji se na URL: `.../models?key=***`")
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            st.success("✅ Spojení s Google API je v pořádku (200 OK)!")
            
            # Máme nějaké modely?
            if "models" in data:
                found_models = []
                for m in data["models"]:
                    # Zajímá nás jen generování obsahu
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        found_models.append(m["name"])
                
                if found_models:
                    st.write("### 🎉 HURÁ! Tvůj klíč vidí tyto modely:")
                    for m in found_models:
                        st.code(m)
                    st.info("Zkopíruj jeden z těchto názvů (např. 'models/gemini-pro') a pošli mi ho.")
                else:
                    st.error("⚠️ Klíč je platný, ale seznam 'generateContent' modelů je PRÁZDNÝ.")
                    st.write("To znamená, že nemáš povolené API v Google Cloud Console.")
            else:
                st.error("❌ Odpověď neobsahuje seznam modelů.")
                st.json(data)
        else:
            st.error(f"❌ Chyba {response.status_code}:")
            st.code(json.dumps(data, indent=2))
            st.write("Podívej se na 'message' v JSONu výše, tam je důvod.")
            
    except Exception as e:
        st.error(f"❌ Chyba sítě: {e}")
