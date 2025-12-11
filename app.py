import streamlit as st
import requests
import pandas as pd
import time
import json

# === KONFIGURACE ===
FIXED_API_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"
MODEL_NAME = "models/gemini-2.5-flash"  # Rychlý a moderní model

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === CONTEXTO BRANDING (CSS) ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        
        .stApp { background-color: #0e1117; font-family: 'Poppins', sans-serif; }
        h1, h2, h3, h4 { color: #ffffff !important; font-weight: 600; }
        
        /* Tlačítka */
        div.stButton > button:first-child {
            background-color: rgb(0, 232, 190) !important;
            color: #000000 !important;
            border: none; padding: 12px 24px; border-radius: 6px;
            font-size: 16px; font-weight: 600; text-transform: uppercase;
            box-shadow: 0 4px 15px rgba(0, 232, 190, 0.2);
            width: 100%; transition: all 0.3s ease;
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 232, 190, 0.4);
        }
        
        /* Inputy */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #0d1117; color: white; border: 1px solid #30363d;
        }
        
        /* Skrytí patiček */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* Tabs (Záložky) */
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #0e1117; border-radius: 4px; color: #fff; }
        .stTabs [aria-selected="true"] { background-color: #161b22; border-bottom: 2px solid rgb(0, 232, 190); color: rgb(0, 232, 190); }
    </style>
""", unsafe_allow_html=True)

# === HLAVIČKA ===
col1, col2 = st.columns([1, 6])
with col1: st.markdown("## ⚡") 
with col2:
    st.title("Contexto AI Generator v3.0")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190); font-size: 14px;'>POWERED BY CONTEXTO ENGINE</div>", unsafe_allow_html=True)

st.markdown("---")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Konfigurace")
    worker_url = st.text_input("Zdroj dat (Worker)", value="https://plastic-planet.radim-81e.workers.dev/")
    st.info("ℹ️ API Klíč aktivní (System Protected)")
    st.markdown("---")
    st.caption("Verze 3.0 (Smart JSON + Retries)")

# === FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_list():
    try:
        r = requests.get(worker_url, params={"fn": "categories", "limit": 2000})
        r.encoding = 'utf-8'
        if r.status_code == 200:
            data = r.json()
            cats = [item["path"] for item in data.get("items", [])]
            return sorted(list(set(cats)))
        return []
    except: return []

def get_products(cat_filter, mode="exact"):
    """
    mode='exact': hledá přesnou cestu (pro Katalog)
    mode='search': hledá fulltextově v názvu kategorie (pro Filtr)
    """
    params = {"fn": "products", "limit": 5000, "mode": "view"}
    
    if mode == "exact":
        params["path"] = cat_filter
    else:
        params["cat"] = cat_filter # Worker parametr 'cat' umí fulltext v cestě
        
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba spojení: {e}")
        return []

def ask_ai_robust(product, max_retries=3):
    """Generuje data s opakováním při chybě (Retry Logic) a JSON parsingem"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={FIXED_API_KEY}"
    
    # Prompt nutící JSON výstup - mnohem bezpečnější než CSV string
    prompt = f"""
    Jsi senior copywriter. Zpracuj produkt a vrať validní JSON.
    
    PRODUKT:
    Název: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Model: {product.get('modelClean')}
    
    POŽADOVANÝ VÝSTUP (JSON format):
    {{
        "shortDescription": "2-3 úderné HTML věty.",
        "longDescription": "HTML struktura <h3>, <h4>. Fakta o předloze.",
        "metaTitle": "Max 60 znaků | Plasticplanet.cz",
        "metaDescription": "Max 160 znaků SEO."
    }}
    
    Pravidla: Žádný markdown, jen čistý JSON.
    """

    payload = {
        "contents": [{ "parts": [{"text": prompt}] }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": { "temperature": 0.4, "responseMimeType": "application/json" }
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            
            # Pokud je server přetížený (503) nebo limit (429), počkáme
            if response.status_code in [429, 503]:
                time.sleep(2 * (attempt + 1)) # Exponenciální čekání: 2s, 4s, 6s
                continue
                
            if response.status_code == 200:
                result = response.json()
                try:
                    text_json = result['candidates'][0]['content']['parts'][0]['text']
                    return json.loads(text_json) # Bezpečný parsing JSONu
                except:
                    return None # Chyba struktury
            else:
                return None # Jiná chyba HTTP
                
        except Exception:
            time.sleep(1)
            continue
            
    return None # Všechny pokusy selhaly

# === HLAVNÍ LOGIKA ===

# Záložky pro výběr režimu
tab1, tab2 = st.tabs(["📂 Katalog kategorií", "🔍 Chytrý filtr / Vyhledávání"])

selected_products = []
search_info = ""

with tab1:
    with st.spinner("Načítám strom kategorií..."):
        all_cats = get_categories_list()
    
    if all_cats:
        cat_exact = st.selectbox("Vyberte konkrétní kategorii", all_cats, key="cat_select")
        if cat_exact:
            # Tady zatím nic nestahujeme, až po kliku na tlačítko, nebo pro info?
            # Pro sjednocení logiky stáhneme data až při generování, 
            # ale uživatel chce vidět počty. Takže musíme udělat "pre-fetch" nebo věřit odhadu.
            # Zde nastavíme parametry pro pozdější stahování.
            mode = "exact"
            query = cat_exact

with tab2:
    st.markdown("Zadejte klíčové slovo (např. **'Civilní'**, **'Tanky'**, **'1:72'**). Spojí všechny odpovídající kategorie.")
    cat_search = st.text_input("Hledat napříč kategoriemi", placeholder="Např. civilní vozidla")
    if cat_search:
        mode = "search"
        query = cat_search
    else:
        # Fallback aby aplikace nespadla
        mode = "none"
        query = None

# === TLAČÍTKO A PROCES ===

st.markdown("---")

if st.button("SPUSTIT GENERÁTOR", type="primary"):
    if mode == "none":
        st.warning("⚠️ Vyberte kategorii nebo zadejte hledaný výraz.")
        st.stop()

    with st.status("🚀 Contexto AI startuje...", expanded=True) as status:
        
        # 1. Stažení dat
        st.write(f"Získávám data (Režim: {mode}, Dotaz: {query})...")
        products = get_products(query, mode=mode)
        
        if not products:
            status.update(label="❌ Žádné produkty nenalezeny.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"✅ **Nalezeno {total} produktů** k zpracování.")
        time.sleep(1) # Čas na přečtení počtu
        
        # 2. Generování
        st.write("Aplikuji AI modely (s ochranou proti výpadkům)...")
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji ({i+1}/{total}): **{p.get('PRODUCT')}**")
            
            # Volání AI s retry logikou
            ai_data = ask_ai_robust(p)
            
            if ai_data:
                p["shortDescription"] = ai_data.get("shortDescription", "")
                p["longDescription"] = ai_data.get("longDescription", "")
                p["metaTitle"] = ai_data.get("metaTitle", "")
                p["metaDescription"] = ai_data.get("metaDescription", "")
            else:
                p["shortDescription"] = "CHYBA GENEROWÁNÍ"
                p["longDescription"] = "Zkuste znovu později"
                p["metaTitle"] = "CHYBA"
                p["metaDescription"] = "CHYBA"
            
            results.append(p)
            my_bar.progress((i + 1) / total)
            
            # Pauza proti přetížení (API limituje cca 15 requestů/min u Free tieru, tak zpomalíme)
            time.sleep(1.5) 
            
        status.update(label="Hotovo! Export připraven.", state="complete")
        
    # 3. Výsledek
    df = pd.DataFrame(results)
    st.success(f"✅ Zpracováno {len(df)} položek.")
    
    # Náhled
    st.dataframe(df[["PRODUCT", "shortDescription", "metaTitle"]])
    
    # Export
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="📥 STÁHNOUT CSV EXPORT",
        data=csv,
        file_name=f"export_{query.replace(' ', '_')}.csv",
        mime="text/csv"
    )
