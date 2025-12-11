import streamlit as st
import requests
import pandas as pd
import time
import json

# === KONFIGURACE ===
DEFAULT_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"

st.set_page_config(page_title="Contexto Diagnostic", layout="wide", page_icon="🛠")

# === DESIGN ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        .stApp { background-color: #0e1117; font-family: 'Poppins', sans-serif; }
        h1, h2, h3, h4 { color: #ffffff !important; }
        .stButton > button { background-color: rgb(0, 232, 190) !important; color: black !important; font-weight: bold; }
        .success-box { padding: 10px; background-color: rgba(0, 255, 0, 0.1); border: 1px solid green; border-radius: 5px; color: #fff; margin-bottom: 5px; }
        .error-box { padding: 10px; background-color: rgba(255, 0, 0, 0.1); border: 1px solid red; border-radius: 5px; color: #fff; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("🛠 Contexto: Diagnostika & Generátor")
st.markdown("---")

# === SIDEBAR (NASTAVENÍ) ===
with st.sidebar:
    st.header("⚙️ Nastavení API")
    api_key = st.text_input("API Key", value=DEFAULT_KEY, type="password")
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    st.info("Zde nastavte klíč. Vpravo spusťte test.")

# === FUNKCE DIAGNOSTIKY ===
def test_single_model(model_name, key):
    """Zkusí vygenerovat 'Hello' s daným modelem."""
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={key}"
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": "Hello"}]}]}, headers={'Content-Type': 'application/json'})
        if resp.status_code == 200:
            return True, "OK"
        else:
            return False, f"Chyba {resp.status_code}"
    except Exception as e:
        return False, str(e)

def get_google_models(key):
    """Stáhne seznam všech modelů dostupných pro klíč."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            # Filtrujeme jen ty, co umí generateContent
            return [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        return []
    except:
        return []

# === ČÁST 1: DIAGNOSTIKA ===
st.subheader("1. Krok: Otestovat modely")
st.write("Klikni na tlačítko. Aplikace zkusí spojení s Googlem a zjistí, který model pro tebe funguje.")

if "working_models" not in st.session_state:
    st.session_state.working_models = []

col_test, col_res = st.columns([1, 3])

with col_test:
    if st.button("🔍 SPUSTIT TEST MODELŮ"):
        st.session_state.working_models = []
        with st.status("Testuji modely...", expanded=True) as status:
            # 1. Stáhnout seznam
            st.write("Stahuji seznam modelů...")
            all_models = get_google_models(api_key)
            
            if not all_models:
                # Fallback, když nejde stáhnout seznam, zkusíme tyhle základní
                st.warning("Nelze stáhnout seznam. Testuji základní sadu.")
                all_models = ["models/gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-pro"]
            
            # 2. Testovat každý zvlášť
            for m in all_models:
                st.write(f"Testuji: {m}...")
                is_ok, msg = test_single_model(m, api_key)
                if is_ok:
                    st.session_state.working_models.append(m)
                    st.markdown(f":white_check_mark: **{m}** funguje!", unsafe_allow_html=True)
                else:
                    st.markdown(f":x: {m} - {msg}", unsafe_allow_html=True)
                time.sleep(0.2)
            
            status.update(label="Test hotov!", state="complete")

# === ČÁST 2: GENERÁTOR ===
st.markdown("---")
st.subheader("2. Krok: Generování")

if not st.session_state.working_models:
    st.warning("⚠️ Nejdřív spusťte test výše, nebo se nenašel žádný funkční model.")
    chosen_model = st.text_input("Zadejte model ručně (pokud test selhal)", "models/gemini-1.5-flash")
else:
    # Uživatel si vybere jen z těch, co svítily zeleně
    chosen_model = st.selectbox("✅ Vyberte funkční model:", st.session_state.working_models)

# Logika generátoru (Standardní)
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
    Jsi expert na modely.
    VSTUP: {product.get('PRODUCT')}, {product.get('MANUFACTURER')}, {product.get('scale')}, {product.get('CATEGORYTEXT')}
    POKYN: Najdi měřítko, pokud chybí. Vytvoř texty oddělené "###".
    VÝSTUP: shortDescription###longDescription###metaTitle###metaDescription
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): Struktura <h3>, <h4>. Historie.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    DŮLEŽITÉ: Vše na jeden řádek.
    """
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
        if r.status_code == 200: return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        elif r.status_code == 429: time.sleep(2); return ask_ai(product, key, model) # Jednoduchý retry
        else: return f"CHYBA API {r.status_code}###Chyba###Chyba###Chyba"
    except Exception as e: return f"CHYBA SÍTĚ###{str(e)}###Chyba###Chyba"

# UI Generátoru
with st.spinner("Načítám kategorie..."):
    cat_map = get_categories()

if cat_map:
    cat_name = st.selectbox("Vyberte kategorii", list(cat_map.keys()))
    cat_path = cat_map[cat_name]
    
    if st.button("🚀 SPUSTIT GENERÁTOR"):
        if not api_key: st.error("Chybí klíč"); st.stop()
        
        with st.status("Pracuji...", expanded=True) as status:
            prods = get_products(cat_path)
            if not prods: st.error("Prázdná kategorie"); st.stop()
            
            total = len(prods)
            my_bar = st.progress(0)
            res = []
            
            for i, p in enumerate(prods):
                status.update(label=f"Zpracovávám: {p.get('PRODUCT')}")
                raw = ask_ai(p, api_key, chosen_model)
                parts = raw.split("###")
                
                if len(parts) >= 4:
                    p["shortDescription"] = parts[0]; p["longDescription"] = parts[1]
                    p["metaTitle"] = parts[2]; p["metaDescription"] = parts[3]
                else:
                    p["shortDescription"] = f"CHYBA: {raw}"
                
                res.append(p)
                my_bar.progress((i+1)/total)
                time.sleep(1.0)
            status.update(label="Hotovo!", state="complete")
            
        df = pd.DataFrame(res)
        st.dataframe(df[["PRODUCT", "shortDescription"]])
        csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("STÁHNOUT CSV", csv, "export.csv", "text/csv")
