import streamlit as st
import requests
import pandas as pd
import time
import json
import re

# === KONFIGURACE ===
FIXED_API_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"
MODEL_NAME = "models/gemini-2.5-flash"

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === CONTEXTO DESIGN (CSS) ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        .stApp { background-color: #0e1117; font-family: 'Poppins', sans-serif; }
        h1, h2, h3, h4 { color: #ffffff !important; }
        
        /* Tlačítka */
        div.stButton > button:first-child {
            background-color: rgb(0, 232, 190) !important;
            color: #000000 !important;
            border: none; padding: 12px 24px; border-radius: 6px;
            font-weight: 600; text-transform: uppercase; width: 100%;
            transition: all 0.3s ease;
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 232, 190, 0.4);
        }
        
        /* Inputy */
        .stSelectbox > div > div > div {
            background-color: #0d1117; color: white; border: 1px solid #30363d;
        }
        
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# === HLAVIČKA ===
col1, col2 = st.columns([1, 6])
with col1: st.markdown("## ⚡") 
with col2:
    st.title("Contexto AI Generator v5.0")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190);'>POWERED BY CONTEXTO ENGINE (Anti-Fail Mode)</div>", unsafe_allow_html=True)

st.markdown("---")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Nastavení")
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    st.info("API Klíč aktivní (System Protected)")

# === POMOCNÉ FUNKCE PRO STABILITU ===

def clean_json_string(text):
    """Odstraní Markdown balast (```json ... ```) z odpovědi AI"""
    text = text.strip()
    # Odstranění code blocků
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text)
        text = re.sub(r"```$", "", text)
    return text.strip()

def generate_fallback(product):
    """Vytvoří základní popis, když AI selže (aby nebylo v CSV prázdno)"""
    name = product.get('PRODUCT', '')
    manuf = product.get('MANUFACTURER', '')
    scale = product.get('scale', '')
    
    return {
        "shortDescription": f"<p>Plastikový model <strong>{name}</strong> od výrobce <strong>{manuf}</strong>. Měřítko {scale}. Stavebnice neobsahuje lepidlo ani barvy.</p>",
        "longDescription": f"<h3>Popis produktu</h3><p>Detailně provedený model {name}. Vhodné pro modeláře. Balení obsahuje plastové výlisky a návod.</p><h4>Parametry</h4><ul><li>Výrobce: {manuf}</li><li>Měřítko: {scale}</li></ul>",
        "metaTitle": f"{name} {scale} {manuf} | Plasticplanet.cz",
        "metaDescription": f"Kupte si model {name} v měřítku {scale} od {manuf}. Skvělá cena a rychlé dodání na Plasticplanet.cz."
    }

# === API FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_map():
    try:
        r = requests.get(worker_url, params={"fn": "categories", "limit": 2000})
        r.encoding = 'utf-8'
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            cat_map = {}
            for item in items:
                path = item.get("path", "")
                count = item.get("count", 0)
                if count == 0 and "productCount" in item: count = item["productCount"]
                
                display_name = f"{path} ({count} ks)"
                cat_map[display_name] = path
            
            sorted_keys = sorted(cat_map.keys())
            return {k: cat_map[k] for k in sorted_keys}
        return {}
    except: return {}

def get_products(cat_path):
    params = {"fn": "products", "path": cat_path, "limit": 5000, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except: return []

def ask_ai_robust(product, max_retries=3):
    """Generuje data a vrací slovník (dict). Pokud AI selže, vrátí Fallback."""
    
    url = f"[https://generativelanguage.googleapis.com/v1beta/](https://generativelanguage.googleapis.com/v1beta/){MODEL_NAME}:generateContent?key={FIXED_API_KEY}"
    
    # Prompt žádající JSON
    prompt = f"""
    Jsi senior copywriter. Zpracuj produkt a vrať POUZE validní JSON objekt.
    
    PRODUKT: {product.get('PRODUCT')}
    VÝROBCE: {product.get('MANUFACTURER')}
    MĚŘÍTKO: {product.get('scale')}
    MODEL: {product.get('modelClean')}
    
    VÝSTUPNÍ JSON STRUKTURA:
    {{
        "shortDescription": "HTML text (2-3 věty)",
        "longDescription": "HTML text (struktura <h3>, <h4>, fakta)",
        "metaTitle": "SEO titulek (max 60 znaků)",
        "metaDescription": "SEO popis (max 160 znaků)"
    }}
    """

    payload = {
        "contents": [{ "parts": [{"text": prompt}] }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": { "temperature": 0.4 }
    }
    
    # 1. Pokusy o získání AI dat
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            
            # Backoff při přetížení
            if response.status_code in [429, 503]:
                time.sleep(2 * (attempt + 1))
                continue
                
            if response.status_code == 200:
                result = response.json()
                try:
                    raw_text = result['candidates'][0]['content']['parts'][0]['text']
                    clean_text = clean_json_string(raw_text)
                    # Parsování JSONu
                    data = json.loads(clean_text)
                    
                    # Kontrola, zda máme všechny klíče
                    if all(k in data for k in ["shortDescription", "longDescription"]):
                        return data # ÚSPĚCH
                except:
                    pass # Chyba parsování, zkusíme další pokus
        except:
            time.sleep(1)
            continue
    
    # 2. Pokud vše selže -> FALLBACK (Záchrana)
    # Místo chyby vrátíme automaticky vygenerovaný text
    return generate_fallback(product)

# === HLAVNÍ LOGIKA ===

with st.spinner("Načítám kategorie..."):
    cat_map = get_categories_map()

if not cat_map:
    st.error("Nepodařilo se načíst seznam kategorií.")
    selected_path = st.text_input("Zadejte cestu kategorie ručně", "Modely + | Letadla a vrtulníky | 1:72")
else:
    selected_display_name = st.selectbox("Vyberte kategorii", options=list(cat_map.keys()))
    selected_path = cat_map[selected_display_name]

if st.button("SPUSTIT GENERÁTOR", type="primary"):
    
    with st.status("🚀 Contexto AI pracuje...", expanded=True) as status:
        st.write(f"Stahuji produkty: {selected_path}...")
        products = get_products(selected_path)
        
        if not products:
            status.update(label="Kategorie je prázdná.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"Nalezeno {total} produktů. Startuji generování...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji ({i+1}/{total}): **{p.get('PRODUCT')}**")
            
            # Získání dat (buď AI, nebo Fallback)
            ai_data = ask_ai_robust(p)
            
            # Doplnění do produktu
            p["shortDescription"] = ai_data.get("shortDescription", "")
            p["longDescription"] = ai_data.get("longDescription", "")
            p["metaTitle"] = ai_data.get("metaTitle", "")
            p["metaDescription"] = ai_data.get("metaDescription", "")
            
            results.append(p)
            my_bar.progress((i + 1) / total)
            
            # Čekání 1.5s je ideální kompromis pro stabilitu
            time.sleep(1.5) 
            
        status.update(label="Hotovo! Export připraven.", state="complete")
        
    df = pd.DataFrame(results)
    st.success(f"✅ Zpracováno {len(df)} položek.")
    
    st.dataframe(df[["PRODUCT", "shortDescription"]])
    
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="📥 STÁHNOUT CSV EXPORT",
        data=csv,
        file_name="contexto_export.csv",
        mime="text/csv"
    )
