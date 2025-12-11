import streamlit as st
import requests
import pandas as pd
import time
import re

# === KONFIGURACE ===
FIXED_API_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"
MODEL_NAME = "models/gemini-2.5-flash"

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === CONTEXTO DESIGN ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        .stApp { background-color: #0e1117; font-family: 'Poppins', sans-serif; }
        h1, h2, h3, h4 { color: #ffffff !important; }
        div.stButton > button:first-child {
            background-color: rgb(0, 232, 190) !important; color: #000000 !important;
            border: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; text-transform: uppercase; width: 100%;
        }
        div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0, 232, 190, 0.4); }
        .stSelectbox > div > div > div { background-color: #0d1117; color: white; border: 1px solid #30363d; }
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# === HLAVIČKA ===
col1, col2 = st.columns([1, 6])
with col1: st.markdown("## ⚡") 
with col2:
    st.title("Contexto AI Generator v6.0")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190);'>POWERED BY CONTEXTO ENGINE (Creative Mode)</div>", unsafe_allow_html=True)
st.markdown("---")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Nastavení")
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    st.info("API Klíč aktivní")

# === FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_map():
    try:
        r = requests.get(worker_url, params={"fn": "categories", "limit": 2000})
        r.encoding = 'utf-8'
        if r.status_code == 200:
            data = r.json()
            cat_map = {}
            for item in data.get("items", []):
                path = item.get("path", "")
                count = item.get("count", 0)
                if count == 0 and "productCount" in item: count = item["productCount"]
                cat_map[f"{path} ({count} ks)"] = path
            return {k: cat_map[k] for k in sorted(cat_map.keys())}
        return {}
    except: return {}

def get_products(cat_path):
    try:
        r = requests.get(worker_url, params={"fn": "products", "path": cat_path, "limit": 5000, "mode": "view"})
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except: return []

def ask_ai_creative(product, max_retries=3):
    """Generuje unikátní texty (Creative Mode)"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={FIXED_API_KEY}"
    
    # Do promptu posíláme i CATEGORYTEXT, aby AI našla měřítko, když chybí ve scale
    prompt = f"""
    Jsi zkušený modelář a copywriter. Napiš čtivý a unikátní popis produktu.
    
    DATA:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko (Scale): {product.get('scale')} (Pokud chybí, odvoď z názvu nebo kategorie)
    Kategorie: {product.get('CATEGORYTEXT')}
    
    ÚKOL:
    Vytvoř 4 textová pole oddělená přesně sekvencí "###".
    
    FORMÁT VÝSTUPU:
    shortDescription###longDescription###metaTitle###metaDescription
    
    OBSAH:
    1. shortDescription (HTML): 2-3 lákavé věty. Co to je, pro koho.
    2. longDescription (HTML): 
       - Struktura: <h3>Popis modelu</h3>, <h4>O předloze</h4> (zde napiš fakta o skutečném stroji/objektu).
       - Pokud neznáš fakta o předloze, napiš obecně o typu stroje, ale nevymýšlej si nesmysly.
    3. metaTitle: "Název | Plasticplanet.cz" (max 60 znaků)
    4. metaDescription: Max 160 znaků.
    
    DŮLEŽITÉ: 
    - Nepoužívej Markdown.
    - Celý výstup musí být na JEDEN dlouhý řádek.
    - Nepoužívej enter.
    """

    payload = {
        "contents": [{ "parts": [{"text": prompt}] }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": { "temperature": 0.6 } # Vyšší teplota = více kreativity
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            
            if response.status_code in [429, 503]:
                time.sleep(2)
                continue
                
            if response.status_code == 200:
                result = response.json()
                try:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
                except:
                    pass
        except:
            time.sleep(1)
            continue
            
    # Pokud AI selže, vrátíme prázdný string, aby to v tabulce bylo vidět jako chyba
    return "CHYBA_AI###CHYBA_AI###CHYBA_AI###CHYBA_AI"

# === HLAVNÍ APLIKACE ===

with st.spinner("Načítám kategorie..."):
    cat_map = get_categories_map()

if not cat_map:
    selected_path = st.text_input("Zadejte cestu ručně", "Modely + | Letadla a vrtulníky | 1:72")
else:
    display_name = st.selectbox("Vyberte kategorii", options=list(cat_map.keys()))
    selected_path = cat_map[display_name]

if st.button("SPUSTIT GENERÁTOR", type="primary"):
    
    with st.status("🚀 Contexto AI pracuje...", expanded=True) as status:
        st.write(f"Stahuji data...")
        products = get_products(selected_path)
        
        if not products:
            status.update(label="Kategorie je prázdná.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"Nalezeno {total} produktů. Generuji texty...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Zpracovávám: **{p.get('PRODUCT')}** ({i+1}/{total})")
            
            # Volání AI
            raw_text = ask_ai_creative(p)
            
            # Rozdělení podle našeho speciálního oddělovače ###
            parts = raw_text.split("###")
            
            if len(parts) >= 4:
                p["shortDescription"] = parts[0].strip()
                p["longDescription"] = parts[1].strip()
                p["metaTitle"] = parts[2].strip()
                p["metaDescription"] = parts[3].strip()
            else:
                # Fallback jen pokud se formát úplně rozpadne
                p["shortDescription"] = "Chyba formátu"
                p["longDescription"] = raw_text
                p["metaTitle"] = ""
                p["metaDescription"] = ""
            
            results.append(p)
            my_bar.progress((i + 1) / total)
            time.sleep(1.0) 
            
        status.update(label="Hotovo! Export připraven.", state="complete")
        
    df = pd.DataFrame(results)
    st.success(f"✅ Zpracováno {len(df)} položek.")
    st.dataframe(df[["PRODUCT", "shortDescription"]])
    
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 STÁHNOUT CSV EXPORT", csv, "contexto_export.csv", "text/csv")
