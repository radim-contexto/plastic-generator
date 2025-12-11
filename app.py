import streamlit as st
import requests
import json

# Tvůj klíč (jako výchozí hodnota, můžeš ho přepsat)
DEFAULT_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"

st.set_page_config(page_title="Google AI Scanner", layout="wide")

st.title("🔍 Google AI Model Scanner")
st.markdown("Tento nástroj projde všechny dostupné modely a zjistí, které **skutečně fungují** s tvým klíčem.")

# Vstup pro klíč
api_key = st.text_input("API Klíč", value=DEFAULT_KEY, type="password")

if st.button("SPUSTIT TEST VŠECH MODELŮ", type="primary"):
    if not api_key:
        st.error("Chybí klíč.")
        st.stop()

    st.write("---")
    
    # 1. Získání seznamu všech modelů
    st.info("1. Stahuji seznam modelů z Google API...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    try:
        r = requests.get(list_url)
        if r.status_code != 200:
            st.error(f"❌ Nelze ani stáhnout seznam modelů. Chyba {r.status_code}.")
            st.stop()
            
        data = r.json()
        all_models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        st.success(f"Google tvrdí, že máš přístup k {len(all_models)} modelům. Jdeme je otestovat.")
        
    except Exception as e:
        st.error(f"Chyba sítě: {e}")
        st.stop()

    # 2. Testování každého modelu
    st.write("---")
    st.write("### 2. Test funkčnosti (Generování)")
    
    working_models = []
    
    # Progress bar
    my_bar = st.progress(0)
    
    for i, model_name in enumerate(all_models):
        # URL pro generování
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
        
        # Jednoduchý payload
        payload = {"contents": [{"parts": [{"text": "Hello"}]}]}
        
        try:
            # Testovací volání
            resp = requests.post(gen_url, json=payload, headers={'Content-Type': 'application/json'})
            
            if resp.status_code == 200:
                st.success(f"✅ **{model_name}** -> FUNGUJE!")
                working_models.append(model_name)
            else:
                # Vypíšeme chybu šedě, ať to neruší
                error_msg = f"Chyba {resp.status_code}"
                if resp.status_code == 403: error_msg = "403 Forbidden (Zakázáno)"
                if resp.status_code == 404: error_msg = "404 Not Found"
                if resp.status_code == 429: error_msg = "429 Limit (Moc rychle)"
                
                st.markdown(f"<div style='color: grey;'>❌ {model_name} - {error_msg}</div>", unsafe_allow_html=True)
        
        except Exception as e:
            st.write(f"❌ {model_name} - Chyba sítě")
            
        # Aktualizace progress baru
        my_bar.progress((i + 1) / len(all_models))
    
    st.write("---")
    
    # 3. Závěr
    if working_models:
        st.header("🎉 VÍTĚZNÉ MODELY")
        st.success("Tyto modely jsou připraveny k použití. Zkopíruj si jeden z nich:")
        for wm in working_models:
            st.code(wm)
    else:
        st.error("😭 Žádný model nefungoval. Tvůj API klíč je pravděpodobně zablokovaný nebo nemá povolenou službu v Google Cloud.")
