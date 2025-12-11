import streamlit as st
import requests
import pandas as pd
import time

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
        
        /* Tlačítko */
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
    st.title("Contexto AI Generator v4.0")
    st.markdown("<div style='margin-top: -20px; color: rgb(0, 232, 190);'>POWERED BY CONTEXTO ENGINE</div>", unsafe_allow_html=True)

st.markdown("---")

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Nastavení")
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    st.info("API Klíč aktivní (System Protected)")

# === FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_map():
    """Stáhne kategorie a vytvoří mapu: 'Název (X ks)' -> 'cesta'"""
    try:
        # Stahujeme kategorie
        r = requests.get(worker_url, params={"fn": "categories", "limit": 2000})
        r.encoding = 'utf-8'
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            
            # Vytvoříme slovník pro roletku
            # Klíč = To co vidí uživatel (Název + počet)
            # Hodnota = Skutečná cesta pro API
            cat_map = {}
            for item in items:
                path = item.get("path", "")
                count = item.get("count", 0) # Pokud feed obsahuje count
                
                # Pokud feed neposílá count přímo, zkusíme 'productCount' nebo prostě 0
                if count == 0 and "productCount" in item:
                    count = item["productCount"]
                
                display_name = f"{path} ({count} ks)"
                cat_map[display_name] = path
                
            # Seřadíme podle abecedy
            sorted_keys = sorted(cat_map.keys())
            return {k: cat_map[k] for k in sorted_keys}
            
        return {}
    except:
        return {}

def get_products(cat_path):
    params = {"fn": "products", "path": cat_path, "limit": 5000, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except: return []

def ask_ai(product, max_retries=3):
    """Generuje texty s opakováním při chybě"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={FIXED_API_KEY}"
    
    prompt = f"""
    Jsi senior copywriter.
    Vytvoř 4 pole pro CSV (oddělovač středník ;).
    
    PRODUKT: {product.get('PRODUCT')}
    VÝROBCE: {product.get('MANUFACTURER')}
    MĚŘÍTKO: {product.get('scale')}
    MODEL: {product.get('modelClean')}
    
    VÝSTUP (jeden řádek):
    shortDescription;longDescription;metaTitle;metaDescription
    
    PRAVIDLA:
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): Struktura <h3>, <h4>. Historická fakta.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    
    DŮLEŽITÉ: 
    - Žádný markdown. 
    - Odstraň odřádkování.
    - Oddělovač je středník (;).
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
    
    # Retry logika (zkusí to 3x, když Google hodí chybu)
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            
            # Pokud je server busy (503) nebo limit (429), čekáme
            if response.status_code in [429, 503]:
                time.sleep(2)
                continue
                
            if response.status_code == 200:
                result = response.json()
                try:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
                except:
                    return "CHYBA PARSINGU;CHYBA;CHYBA;CHYBA"
            else:
                # Pokud je to jiná chyba, nečekáme a vrátíme chybu
                if attempt == max_retries - 1:
                    return f"CHYBA HTTP {response.status_code};CHYBA;CHYBA;CHYBA"
                
        except Exception:
            time.sleep(1)
            continue
            
    return "CHYBA SÍTĚ;CHYBA;CHYBA;CHYBA"

# === HLAVNÍ LOGIKA ===

with st.spinner("Načítám kategorie..."):
    cat_map = get_categories_map()

if not cat_map:
    st.error("Nepodařilo se načíst seznam kategorií. Zkontrolujte Worker URL.")
    # Fallback input
    selected_path = st.text_input("Zadejte cestu kategorie ručně", "Modely + | Letadla a vrtulníky | 1:72")
else:
    # Roletka ukazuje Názvy s počty (klíče mapy)
    selected_display_name = st.selectbox("Vyberte kategorii", options=list(cat_map.keys()))
    # Podle výběru získáme čistou cestu (hodnota mapy)
    selected_path = cat_map[selected_display_name]

if st.button("SPUSTIT GENERÁTOR", type="primary"):
    
    with st.status("🚀 Contexto AI pracuje...", expanded=True) as status:
        st.write(f"Stahuji produkty: {selected_path}...")
        products = get_products(selected_path)
        
        if not products:
            status.update(label="Kategorie je prázdná.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"Nalezeno {total} produktů. Aplikuji AI modely...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji ({i+1}/{total}): **{p.get('PRODUCT')}**")
            
            csv_line = ask_ai(p)
            
            parts = csv_line.split(";")
            if len(parts) < 4: parts = [csv_line, "Chyba", "Chyba", "Chyba"]
            
            p["shortDescription"] = parts[0]
            p["longDescription"] = parts[1]
            p["metaTitle"] = parts[2]
            p["metaDescription"] = parts[3]
            results.append(p)
            
            my_bar.progress((i + 1) / total)
            # Bezpečnější pauza
            time.sleep(1.0) 
            
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
