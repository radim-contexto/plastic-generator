import streamlit as st
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import time

# === 1. NASTAVENÍ STRÁNKY ===
st.set_page_config(page_title="Plastic Planet AI", layout="wide")
st.title("🤖 Plastic Planet: Generátor popisů")

# === 2. NAČTENÍ KLÍČE ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    # Pokud není klíč v secrets, vezmi ho z inputu
    if not api_key:
        api_key_input = st.text_input("Vlož Gemini API Key", type="password")
        if api_key_input:
            api_key = api_key_input
    
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")

    st.markdown("---")
    # TLAČÍTKO PRO RYCHLÝ TEST
    if st.button("🛠 Otestovat API Klíč"):
        if not api_key:
            st.error("Chybí klíč!")
        else:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                res = model.generate_content("Ahoj, funguješ?")
                st.success(f"✅ Funguje! Odpověď AI: {res.text}")
            except Exception as e:
                st.error(f"❌ Chyba spojení: {e}")

# === 3. FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_list():
    try:
        r = requests.get(worker_url, params={"fn": "categories", "limit": 1000})
        r.encoding = 'utf-8'
        if r.status_code == 200:
            data = r.json()
            cats = [item["path"] for item in data.get("items", [])]
            return sorted(list(set(cats)))
        return []
    except:
        return []

def get_products(cat_path, limit):
    params = {
        "fn": "products",
        "path": cat_path,
        "limit": limit,
        "mode": "view"
    }
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba Workeru: {e}")
        return []

def ask_ai(product, model):
    """Generuje popisky s vypnutou cenzurou"""
    
    prompt = f"""
    Jsi expertní copywriter. Vytvoř 4 pole pro CSV (oddělovač středník ;).
    
    VSTUP:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Název: {product.get('modelClean')}
    
    VÝSTUP (jeden řádek):
    shortDescription;longDescription;metaTitle;metaDescription
    
    PRAVIDLA:
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): Struktura <h3>, <h4>. Dohledej fakta o předloze.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    
    DŮLEŽITÉ: Nepoužívej Markdown. Odstraň nové řádky.
    """
    
    # NASTAVENÍ BEZPEČNOSTI - Vypínáme blokování, aby prošly tanky a válka
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        return response.text.strip()
    except Exception as e:
        # Vracíme text chyby, abychom viděli PROČ to nejde
        return f"CHYBA API: {str(e)};CHYBA;CHYBA;CHYBA"

# === 4. APLIKACE ===

with st.spinner("Načítám seznam kategorií..."):
    all_categories = get_categories_list()

col1, col2 = st.columns([3, 1])
with col1:
    if all_categories:
        selected_cat = st.selectbox("📂 Vyber kategorii", all_categories)
    else:
        selected_cat = st.text_input("Kategorie (ručně)", "Letadla 1:72")
with col2:
    limit_input = st.number_input("Počet produktů", min_value=1, max_value=5000, value=5)

if st.button("🚀 Spustit generování", type="primary"):
    if not api_key:
        st.error("⛔️ CHYBÍ API KLÍČ! Zadej ho vlevo v menu.")
        st.stop()
        
    # Inicializace modelu
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    with st.status("Pracuji...", expanded=True) as status:
        st.write(f"Stahuji data: {selected_cat}...")
        products = get_products(selected_cat, limit_input)
        
        if not products:
            status.update(label="Žádné produkty nenalezeny", state="error")
            st.stop()
            
        st.write(f"Nalezeno {len(products)} položek. Generuji...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji ({i+1}/{len(products)}): {p.get('PRODUCT')}")
            
            # Volání AI
            ai_text = ask_ai(p, model)
            
            # Zpracování odpovědi
