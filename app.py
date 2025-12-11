import streamlit as st
import requests
import pandas as pd
import time

# === KONFIGURACE ===
DEFAULT_API_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === DESIGN (Contexto Style) ===
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
        .stTextInput > div > div > input { background-color: #0d1117; color: white; border: 1px solid #30363d; }
        
        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# === HLAVIČKA ===
col1, col2 = st.columns([1, 6])
with col1: st.markdown("## ⚡") 
with col2:
    st.title("Contexto AI Generator")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190);'>ADMIN CONSOLE</div>", unsafe_allow_html=True)
st.markdown("---")

# === SIDEBAR (VRÁCENÝ OVLÁDACÍ PANEL) ===
with st.sidebar:
    st.header("⚙️ Konfigurace")
    
    # 1. API Klíč (Editovatelný!)
    api_key = st.text_input("API Key", value=DEFAULT_API_KEY, type="password")
    
    # 2. Worker URL
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    
    # 3. Výběr modelu (Záchrana při chybě 404/403)
    model_name = st.selectbox("Model AI", [
        "models/gemini-2.5-flash",    # Tvůj nový
        "models/gemini-1.5-flash",    # Starší, stabilní
        "models/gemini-2.0-flash",    # Alternativa
        "models/gemini-pro"           # Záloha
    ])
    
    st.markdown("---")
    
    # Rychlý test, abys nemusel generovat celou tabulku pro zjištění chyby
    if st.button("🛠 TEST SPOJENÍ"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
            resp = requests.post(url, json={"contents": [{"parts": [{"text": "TEST"}]}]}, headers={'Content-Type': 'application/json'})
            if resp.status_code == 200:
                st.success("✅ Spojení OK!")
            else:
                st.error(f"❌ Chyba {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Chyba sítě: {e}")

# === FUNKCE ===

@st.cache_data(ttl=600)
def get_categories():
    try:
        r = requests.get(worker_url, params={"fn": "categories", "limit": 2000})
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

def get_products(path):
    try:
        r = requests.get(worker_url, params={"fn": "products", "path": path, "limit": 5000, "mode": "view"})
        return r.json().get("items", [])
    except: return []

def ask_ai(product, key, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={key}"
    
    prompt = f"""
    Jsi expert na modely. Napiš unikátní popis produktu.
    
    VSTUP:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Kategorie: {product.get('CATEGORYTEXT')}
    
    POKYN: Pokud chybí měřítko, zjisti ho z kategorie.
    Vytvoř 4 části textu oddělené znaky "###".
    
    VÝSTUPNÍ FORMÁT:
    shortDescription###longDescription###metaTitle###metaDescription
    
    OBSAH:
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): Nadpisy <h3>, <h4>. Historie předlohy.
    3. metaTitle: "Název | Plasticplanet.cz"
    4. metaDescription: SEO popis.
    
    DŮLEŽITÉ: Celý výstup na JEDEN řádek.
    """

    payload = {
        "contents": [{ "parts": [{"text": prompt}] }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": { "temperature": 0.6 }
    }
    
    try:
        resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        
        if resp.status_code == 429: # Limit
            time.sleep(2)
            resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})

        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            return f"CHYBA API {resp.status_code}###Chyba###Chyba###Chyba"
    except Exception as e:
        return f"CHYBA SITE###{str(e)}###Chyba###Chyba"

# === APLIKACE ===

with st.spinner("Načítám kategorie..."):
    cat_map = get_categories()

if not cat_map:
    st.error("Chyba načítání kategorií.")
    sel_path = st.text_input("Ruční zadání kategorie")
else:
    name = st.selectbox("Vyberte kategorii", list(cat_map.keys()))
    sel_path = cat_map[name]

if st.button("SPUSTIT GENERÁTOR", type="primary"):
    if not api_key:
        st.error("Chybí klíč!")
        st.stop()

    with st.status("Pracuji...", expanded=True) as status:
        st.write("Stahuji data...")
        prods = get_products(sel_path)
        
        if not prods:
            st.error("Žádné produkty.")
            st.stop()
            
        total = len(prods)
        st.write(f"Mám {total} produktů. Startuji AI.")
        
        bar = st.progress(0)
        res = []
        
        for i, p in enumerate(prods):
            status.update(label=f"Generuji: {p.get('PRODUCT')} ({i+1}/{total})")
            
            # Předáváme klíč a model z lišty
            raw = ask_ai(p, api_key, model_name)
            parts = raw.split("###")
            
            if len(parts) >= 4:
                p["shortDescription"] = parts[0]
                p["longDescription"] = parts[1]
                p["metaTitle"] = parts[2]
                p["metaDescription"] = parts[3]
            else:
                p["shortDescription"] = f"CHYBA: {raw}"
                p["longDescription"] = raw
            
            res.append(p)
            bar.progress((i+1)/total)
            time.sleep(1.0) 
            
        status.update(label="Hotovo!", state="complete")
        
    df = pd.DataFrame(res)
    st.success(f"Hotovo {len(df)} ks.")
    st.dataframe(df[["PRODUCT", "shortDescription"]])
    
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("STÁHNOUT CSV", csv, "export.csv", "text/csv")
