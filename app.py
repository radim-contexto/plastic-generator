import streamlit as st
import requests
import google.generativeai as genai
import pandas as pd
import time
import io

# === 1. NASTAVENÍ STRÁNKY ===
st.set_page_config(page_title="Plastic Planet AI Export", layout="wide")
st.title("🤖 Plastic Planet: Generátor popisů (Unlimited)")

# === 2. NAČTENÍ KLÍČE ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")
    
    # Tady je URL na tvůj worker napevno, ať to nepřekáží
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")

# === 3. FUNKCE ===

def get_products(cat, limit):
    params = {"fn": "products", "cat": cat, "limit": limit, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8' # Vynucení češtiny, aby se nerozsypaly EANy
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba při stahování dat z Workeru: {e}")
        return []

def ask_ai(product, model):
    prompt = f"""
    Jsi expertní copywriter. Vytvoř 4 pole pro CSV (oddělovač středník).
    
    VSTUP:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Název modelu: {product.get('modelClean')}
    
    VÝSTUP (jeden řádek, oddělovač ;):
    shortDescription;longDescription;metaTitle;metaDescription
    
    PRAVIDLA:
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): 
       - Struktura: <h3>Detailní popis</h3> <h4>O výrobci</h4>... <h4>O měřítku</h4>... <h4>O modelu</h4>...
       - DOHLEDEJ FAKTA na webu. Pokud nevíš, sekci vynech.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    
    DŮLEŽITÉ: Nepoužívej markdown. Text na jeden řádek.
    """
    
    try:
        # Tady voláme AI
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # VRÁTÍME SKUTEČNOU CHYBU, ABYCHOM VIDĚLI, CO JE ŠPATNĚ
        return f"CHYBA AI: {str(e)};CHYBA;CHYBA;CHYBA"

# === 4. APLIKACE ===

col1, col2 = st.columns([3, 1])
with col1:
    cat_input = st.text_input("🔍 Hledat kategorii", placeholder="Např. letadla 1:72")
with col2:
    # ZVÝŠENÝ LIMIT NA 2000
    limit_input = st.number_input("Počet kusů", min_value=1, max_value=2000, value=10)

if st.button("🚀 Spustit generování", type="primary"):
    if not api_key:
        st.error("CHYBÍ API KLÍČ! Zadej ho vlevo.")
        st.stop()
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Chyba při přihlášení k AI: {e}")
        st.stop()
    
    with st.spinner("Stahuji data..."):
        products = get_products(cat_input, limit_input)
        
    if not products:
        st.warning("Nic nenalezeno.")
        st.stop()
        
    st.write(f"Nalezeno {len(products)} položek. Jdeme na to.")
    
    my_bar = st.progress(0)
    results = []
    
    for i, p in enumerate(products):
        # AI Volání
        csv_line = ask_ai(p, model)
        
        parts = csv_line.split(";")
        # Pokud je tam méně sloupců, asi to spadlo do chyby
        if len(parts) < 4: 
            # Zkusíme zjistit, jestli v prvním sloupci není chybová hláška
            error_msg = parts[0] if parts else "Neznámá chyba"
            parts = [error_msg, "Chyba formátu", "Chyba", "Chyba"]
            
        p["shortDescription"] = parts[0]
        p["longDescription"] = parts[1]
        p["metaTitle"] = parts[2]
        p["metaDescription"] = parts[3]
        results.append(p)
        
        my_bar.progress((i + 1) / len(products))
        time.sleep(0.1) 
        
    # Výsledek
    df = pd.DataFrame(results)
    cols = ["PRODUCT", "MANUFACTURER", "shortDescription", "longDescription", "metaTitle", "metaDescription", "EAN", "URL"]
    
    # Jen pro jistotu, kdyby nějaký sloupec chyběl
    final_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[final_cols])
    
    csv_data = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 Stáhnout CSV", csv_data, f"export_{cat_input}.csv", "text/csv")
