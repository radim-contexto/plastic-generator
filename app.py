import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === NAČTENÍ KLÍČE Z TREZORU (SECRETS) ===
# Kód se podívá do nastavení serveru, jestli tam je klíč.
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    API_KEY = None

# === DESIGN ===
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
    st.title("Contexto AI Generator")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190);'>SECURE MODE</div>", unsafe_allow_html=True)
st.markdown("---")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Nastavení")
    
    # Kontrola klíče
    if API_KEY:
        st.success("✅ API Klíč načten (Secure)")
    else:
        st.error("❌ Chybí API klíč v Secrets!")
        st.info("Jdi do Settings -> Secrets a přidej GEMINI_API_KEY")
    
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    
    # Výběr modelu (pro jistotu necháváme možnost volby)
    model_choice = st.selectbox("AI Model", [
        "models/gemini-1.5-flash", # Stabilní
        "models/gemma-3-27b-it",   # Alternativa
        "models/gemini-2.0-flash"  # Nový
    ])

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
    VSTUP: {product.get('PRODUCT')}, {product.get('MANUFACTURER')}, {product.get('scale')}, {product.get('CATEGORYTEXT')}
    
    POKYN: Pokud chybí měřítko, zjisti ho z kategorie.
    Vytvoř 4 části textu oddělené znaky "###".
    
    VÝSTUP: shortDescription###longDescription###metaTitle###metaDescription
    
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
        "generationConfig": { "temperature": 0.5 }
    }
    
    try:
        resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        
        if resp.status_code == 429:
            time.sleep(2)
            resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})

        if resp.status_code == 200:
            return resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            return f"CHYBA API {resp.status_code}###Chyba###Chyba###Chyba"
    except Exception as e:
        return f"CHYBA SÍTĚ###{str(e)}###Chyba###Chyba"

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
    if not API_KEY:
        st.error("⛔️ Aplikace nemá nastavený API klíč v Secrets!")
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
            
            raw = ask_ai(p, API_KEY, model_choice)
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
