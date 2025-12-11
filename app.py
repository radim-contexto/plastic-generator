import streamlit as st
import requests
import pandas as pd
import time

# === KONFIGURACE (HARDCODED) ===
# Klíč je napevno, uživatel ho nevidí a nemůže změnit.
FIXED_API_KEY = "AIzaSyBZXa2nnvwxlfd2lPuqytatB_P0H5SWKQg"
MODEL_NAME = "models/gemini-2.5-flash"

st.set_page_config(page_title="Contexto AI Generator", layout="wide", page_icon="⚡")

# === CONTEXTO BRANDING (CSS) ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        
        .stApp { background-color: #0e1117; font-family: 'Poppins', sans-serif; }
        h1, h2, h3, h4 { color: #ffffff !important; }
        
        /* Tlačítka Contexto (Tyrkysová + Černý text) */
        div.stButton > button:first-child {
            background-color: rgb(0, 232, 190) !important;
            color: #000000 !important;
            border: none; padding: 12px 24px; border-radius: 6px;
            font-weight: 600; text-transform: uppercase; width: 100%;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 232, 190, 0.2);
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 232, 190, 0.4);
            background-color: rgb(0, 200, 160) !important;
        }
        
        /* Inputy */
        .stSelectbox > div > div > div {
            background-color: #0d1117; color: white; border: 1px solid #30363d;
        }
        
        /* Skrytí patiček */
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
    st.success("API Klíč aktivní (System Protected)")

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
    """
    Kreativní režim:
    - Používá oddělovač ### (aby se nerozbil CSV formát)
    - Čte i CATEGORYTEXT pro doplnění měřítka
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={FIXED_API_KEY}"
    
    # Prompt posíláme s více daty, aby si AI domyslela chybějící měřítko
    prompt = f"""
    Jsi zkušený modelář a copywriter pro e-shop.
    Napiš unikátní, čtivý a prodejní text. Žádné šablony.
    
    DATA O PRODUKTU:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko (Scale): {product.get('scale')} (POKUD ZDE NENÍ HODNOTA, ODVOĎ JI Z NÁZVU KATEGORIE!)
    Kategorie: {product.get('CATEGORYTEXT')}
    
    ÚKOL:
    Vytvoř 4 textová pole. Odděl je PŘESNĚ sekvencí tří křížků: ###
    
    POŽADOVANÝ VÝSTUP:
    shortDescription###longDescription###metaTitle###metaDescription
    
    OBSAH POLÍ:
    1. shortDescription (HTML): 2-3 lákavé věty. O čem model je a pro koho je vhodný.
    2. longDescription (HTML): 
       - Struktura: <h3>Popis modelu</h3>, <h4>O předloze</h4>.
       - Zde se rozepiš o historii skutečného stroje (tank, letadlo, loď...). Ukaž, že tomu rozumíš.
       - Pokud nemáš fakta, popiš obecně daný typ techniky.
    3. metaTitle: "Název | Plasticplanet.cz" (max 60 znaků)
    4. metaDescription: Max 160 znaků. SEO optimalizované.
    
    TECHNICKÉ POKYNY:
    - Žádný Markdown.
    - Celý výstup na JEDEN řádek.
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
        "generationConfig": { "temperature": 0.65 } # Vyšší teplota = Větší kreativita (méně generické)
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            
            # Pokud je server přetížený, počkáme
            if response.status_code in [429, 503]:
                time.sleep(2)
                continue
                
            if response.status_code == 200:
                result = response.json()
                try:
                    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    # Pokud AI vrátila text, je to OK.
                    return text
                except:
                    pass
        except:
            time.sleep(1)
            continue
            
    # Pokud to selže 3x, vrátíme chybu (lepší než generický nesmysl, aspoň víš, že to máš zkusit znova)
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
            
            # Rozdělení podle ### (bezpečnější než středník)
            parts = raw_text.split("###")
            
            if len(parts) >= 4:
                p["shortDescription"] = parts[0].strip()
                p["longDescription"] = parts[1].strip()
                p["metaTitle"] = parts[2].strip()
                p["metaDescription"] = parts[3].strip()
            else:
                # Pokud se formát rozpadne, zapíšeme původní text do prvního sloupce pro kontrolu
                p["shortDescription"] = f"CHYBA FORMÁTU: {raw_text[:50]}..."
                p["longDescription"] = raw_text
                p["metaTitle"] = "CHYBA"
                p["metaDescription"] = "CHYBA"
            
            results.append(p)
            my_bar.progress((i + 1) / total)
            time.sleep(1.2) # Pauza pro stabilitu
            
        status.update(label="Hotovo! Export připraven.", state="complete")
        
    df = pd.DataFrame(results)
    st.success(f"✅ Zpracováno {len(df)} položek.")
    st.dataframe(df[["PRODUCT", "shortDescription"]])
    
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 STÁHNOUT CSV EXPORT", csv, "contexto_export.csv", "text/csv")
