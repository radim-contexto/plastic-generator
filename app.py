import streamlit as st
import requests
import pandas as pd
import time
import json

# === KONFIGURACE APLIKACE ===
MODEL_NAME = "models/gemini-2.5-flash"
st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === CUSTOM CSS (CONTEXTO BRANDING) ===
st.markdown("""
    <style>
        /* Import Fontu (Poppins - moderní, čistý) */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

        /* Hlavní pozadí */
        .stApp {
            background-color: #0e1117; /* Tmavé pozadí */
            font-family: 'Poppins', sans-serif;
        }

        /* Nadpisy */
        h1, h2, h3 {
            color: #ffffff !important;
            font-weight: 600;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #161b22;
            border-right: 1px solid #30363d;
        }

        /* Tlačítka (Primary) - Contexto Style */
        div.stButton > button:first-child {
            background: linear-gradient(90deg, #4f46e5 0%, #3b82f6 100%); /* Modro-fialový gradient */
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            width: 100%;
            box-shadow: 0 4px 14px 0 rgba(0,118,255,0.39);
        }

        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,118,255,0.23);
            background: linear-gradient(90deg, #4338ca 0%, #2563eb 100%);
        }

        /* Inputy a Selectboxy */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #0d1117;
            color: white;
            border: 1px solid #30363d;
            border-radius: 6px;
        }
        
        /* Skrytí Streamlit elementů (Patička, Hamburger menu) */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Custom Alert boxy */
        .stAlert {
            background-color: #161b22;
            border: 1px solid #30363d;
            color: #c9d1d9;
        }
    </style>
""", unsafe_allow_html=True)

# === LOGO A HLAVIČKA ===
col1, col2 = st.columns([1, 5])
with col1:
    # Místo pro logo - pokud máš URL na logo Contexto, vlož ho sem místo odkazu na placeholder
    st.image("https://cdn-icons-png.flaticon.com/512/1698/1698535.png", width=60) 
with col2:
    st.title("Contexto AI Generator")
    st.markdown("<div style='margin-top: -20px; color: #8b949e;'>Automated Product Description Tool</div>", unsafe_allow_html=True)

st.markdown("---")

# === LOGIKA APLIKACE ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Konfigurace")
    
    if not api_key:
        api_key = st.text_input("API Klíč", type="password")
    
    worker_url = st.text_input("Worker Endpoint", value="https://plastic-planet.radim-81e.workers.dev/")
    
    st.markdown("---")
    st.caption("Powered by Contexto.cz Dev Team")

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

def ask_ai(product, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={api_key}"
    
    prompt = f"""
    Jsi senior copywriter pro Contexto.cz.
    Tvým úkolem je napsat prodejní texty pro modelářský e-shop.
    
    VSTUP:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Název: {product.get('modelClean')}
    
    VÝSTUP (CSV řádek, oddělovač ;):
    shortDescription;longDescription;metaTitle;metaDescription
    
    INSTRUKCE:
    1. shortDescription (HTML): 2-3 úderné věty.
    2. longDescription (HTML): Struktura <h3>, <h4>. Fakticky správné info o předloze (historie, technika).
    3. metaTitle: Max 60 znaků. "Název | Plasticplanet.cz"
    4. metaDescription: Max 160 znaků, lákavé pro kliknutí.
    
    DŮLEŽITÉ: Žádný Markdown, vše na jeden řádek, oddělovač středník.
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

# === HLAVNÍ APLIKACE ===

with st.spinner("Synchronizace dat..."):
    all_cats = get_categories_list()

if not all_cats:
    selected_cat = st.text_input("Zadejte kategorii ručně", "Modely + | Letadla a vrtulníky | 1:72")
else:
    selected_cat = st.selectbox("Vyberte kategorii k exportu", all_cats)

# Moderní velké tlačítko
if st.button("Generovat Export", type="primary"):
    if not api_key:
        st.warning("⚠️ Chybí API klíč")
        st.stop()
        
    with st.status("🚀 Contexto AI pracuje...", expanded=True) as status:
        st.write(f"Načítám feed: {selected_cat}...")
        products = get_products(selected_cat)
        
        if not products:
            status.update(label="Kategorie je prázdná.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"Nalezeno {total} produktů. Aplikuji AI modely...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            # Custom status text
            status.update(label=f"Zpracovávám: **{p.get('PRODUCT')}** ({i+1}/{total})")
            
            csv_line = ask_ai(p, api_key)
            
            parts = csv_line.split(";")
            if len(parts) < 4: parts = [csv_line, "Chyba", "Chyba", "Chyba"]
            
            p["shortDescription"] = parts[0]
            p["longDescription"] = parts[1]
            p["metaTitle"] = parts[2]
            p["metaDescription"] = parts[3]
            results.append(p)
            
            my_bar.progress((i + 1) / total)
            time.sleep(0.05)
            
        status.update(label="Hotovo! Export připraven.", state="complete")
        
    df = pd.DataFrame(results)
    st.success(f"✅ Úspěšně vygenerováno {len(df)} produktů.")
    
    st.dataframe(df[["PRODUCT", "shortDescription"]])
    
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="📥 Stáhnout CSV Export",
        data=csv,
        file_name="contexto_export.csv",
        mime="text/csv"
    )
