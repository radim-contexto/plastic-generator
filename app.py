import streamlit as st
import requests
import pandas as pd
import time
import json

# === KONFIGURACE (HARDCODED) ===
# Klíč je napevno v kódu, uživatel ho nevidí a nemůže smazat.
FIXED_API_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"
MODEL_NAME = "models/gemini-2.5-flash"

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === CONTEXTO BRANDING (CSS) ===
st.markdown("""
    <style>
        /* Import Fontu (Poppins) */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

        /* Tmavé pozadí celé aplikace */
        .stApp {
            background-color: #0e1117;
            font-family: 'Poppins', sans-serif;
        }

        /* Nadpisy bílé */
        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
            font-weight: 600;
        }

        /* Sidebar - tmavší šedá */
        section[data-testid="stSidebar"] {
            background-color: #161b22;
            border-right: 1px solid #30363d;
        }

        /* === TLAČÍTKA CONTEXTO STYLE === */
        /* Hlavní tlačítko (Primary) */
        div.stButton > button:first-child {
            background-color: rgb(0, 232, 190) !important; /* Contexto Green */
            color: #000000 !important; /* Černý text pro kontrast */
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            width: 100%;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 4px 15px rgba(0, 232, 190, 0.2);
        }

        /* Hover efekt (po najetí myší) */
        div.stButton > button:first-child:hover {
            background-color: rgb(0, 200, 160) !important; /* O trochu tmavší při najetí */
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 232, 190, 0.4);
            color: #000000 !important;
        }
        
        /* Inputy (Textová pole) */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #0d1117;
            color: white;
            border: 1px solid #30363d;
            border-radius: 4px;
        }
        
        /* Skrytí Streamlit brandingu */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Status bar */
        .stStatus {
            background-color: #161b22;
            border: 1px solid rgb(0, 232, 190); /* Zelený rámeček */
        }
    </style>
""", unsafe_allow_html=True)

# === HLAVIČKA APLIKACE ===
col1, col2 = st.columns([1, 6])
with col1:
    # Zde můžeš dát URL na logo Contexto, pokud ho máš online
    st.markdown("## ⚡") 
with col2:
    st.title("Contexto AI Generator")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190); font-size: 14px;'>POWERED BY CONTEXTO ENGINE</div>", unsafe_allow_html=True)

st.markdown("---")

# === SIDEBAR (Jen to nejnutnější) ===
with st.sidebar:
    st.header("⚙️ Konfigurace")
    
    # URL Workeru necháme editovatelnou, kdyby se změnila, ale default je nastaven
    worker_url = st.text_input("Zdroj dat (Worker)", value="https://plastic-planet.radim-81e.workers.dev/")
    
    st.info("ℹ️ API Klíč je bezpečně uložen v systému.")
    
    st.markdown("---")
    st.caption("Verze 2.5 (Contexto Stable)")

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
    except:
        return []

def get_products(cat_path):
    params = {"fn": "products", "path": cat_path, "limit": 5000, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba spojení: {e}")
        return []

def ask_ai(product):
    """Generuje texty pomocí hardcoded API klíče"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={FIXED_API_KEY}"
    
    prompt = f"""
    Jsi senior copywriter pro Contexto.cz.
    Píšeš expertní popisky pro specializovaný e-shop (modely).
    
    DATA O PRODUKTU:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Název: {product.get('modelClean')}
    
    VÝSTUPNÍ FORMÁT (CSV řádek, oddělovač ;):
    shortDescription;longDescription;metaTitle;metaDescription
    
    INSTRUKCE:
    1. shortDescription (HTML): 2-3 úderné věty. Neutrální tón.
    2. longDescription (HTML): Použij tagy <h3>, <h4>. Čerpej fakta z historie předlohy.
    3. metaTitle: "Název | Plasticplanet.cz" (Max 60 znaků)
    4. metaDescription: Max 160 znaků. SEO optimalizované.
    
    TECHNICKÉ POKYNY:
    - Žádný Markdown.
    - Celý výstup na JEDEN řádek.
    - Oddělovač sloupců je středník (;).
    - Uvnitř textu středníky nahraď čárkou.
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
    
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            result = response.json()
            try:
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
            except:
                return "CHYBA PARSINGU;CHYBA;CHYBA;CHYBA"
        else:
            return f"CHYBA HTTP {response.status_code};CHYBA;CHYBA;CHYBA"
    except Exception as e:
        return f"CHYBA SÍTĚ;CHYBA;CHYBA;CHYBA"

# === HLAVNÍ LOGIKA ===

with st.spinner("Synchronizace katalogu..."):
    all_cats = get_categories_list()

if not all_cats:
    selected_cat = st.text_input("Zadejte kategorii ručně", "Modely + | Letadla a vrtulníky | 1:72")
else:
    selected_cat = st.selectbox("Vyberte kategorii", all_cats)

# TLAČÍTKO V BARVĚ CONTEXTO
if st.button("SPUSTIT GENERÁTOR", type="primary"):
    
    with st.status("🚀 Contexto AI pracuje...", expanded=True) as status:
        st.write(f"Načítám produkty: {selected_cat}...")
        products = get_products(selected_cat)
        
        if not products:
            status.update(label="Kategorie je prázdná.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"Nalezeno {total} produktů. Aplikuji jazykové modely...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji: **{p.get('PRODUCT')}** ({i+1}/{total})")
            
            # Voláme AI (klíč už je uvnitř funkce)
            csv_line = ask_ai(p)
            
            parts = csv_line.split(";")
            if len(parts) < 4: parts = [csv_line, "Chyba", "Chyba", "Chyba"]
            
            p["shortDescription"] = parts[0]
            p["longDescription"] = parts[1]
            p["metaTitle"] = parts[2]
            p["metaDescription"] = parts[3]
            results.append(p)
            
            my_bar.progress((i + 1) / total)
            # Pauza, aby nás Google neblokl
            time.sleep(0.05)
            
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
