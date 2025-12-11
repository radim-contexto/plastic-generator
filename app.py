import streamlit as st
import requests
import google.generativeai as genai
import pandas as pd
import time
import io

# === 1. NASTAVENÍ STRÁNKY ===
st.set_page_config(page_title="Plastic Planet AI Export", layout="wide")
st.title("🤖 Plastic Planet: Generátor popisů")
st.markdown("Tento nástroj stáhne produkty z feedu, dohledá fakta přes AI a připraví CSV.")

# === 2. NAČTENÍ KLÍČE (SECRETS) ===
# Pokusí se načíst klíč z nastavení serveru. Pokud není, zobrazí pole pro ruční zadání.
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")
    else:
        st.success("API Klíč načten bezpečně ze systému.")
        
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")

# === 3. FUNKCE PRO KOMUNIKACI ===

def get_products(cat, limit):
    """Stáhne data z tvého Workeru"""
    params = {"fn": "products", "cat": cat, "limit": limit, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba při stahování dat: {e}")
        return []

def ask_ai(product, model):
    """Pošle produkt do Gemini a získá řádek CSV"""
    
    # Prompt - instrukce pro AI
    prompt = f"""
    Jsi expertní copywriter pro modelářský e-shop.
    Tvým úkolem je vytvořit 4 textová pole pro CSV export na základě vložených dat a externích znalostí.
    
    VSTUP:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Název modelu: {product.get('modelClean')}
    
    POŽADOVANÝ VÝSTUP (Formát CSV, oddělovač středník):
    shortDescription;longDescription;metaTitle;metaDescription
    
    PRAVIDLA:
    1. shortDescription (HTML): 2-3 věty, neutrální. <p>Model <strong>...</strong> od <strong>...</strong>...</p>.
    2. longDescription (HTML):
       - Struktura: <h3>Detailní popis produktu</h3> <h4>O výrobci</h4>... <h4>O měřítku</h4>... <h4>O modelu {product.get('modelClean')}</h4>...
       - DOHLEDEJ FAKTA (např. Wikipedia) o historii skutečné předlohy (tank, letadlo...).
       - Pokud fakta nenajdeš, sekci 'O modelu' vynech. Nevymýšlej si.
    3. metaTitle: Max 60 znaků. "Název | Plasticplanet.cz"
    4. metaDescription: Max 160 znaků.
    
    DŮLEŽITÉ:
    - Vše musí být na jednom řádku.
    - Odstraň nové řádky (entery) z textů.
    - Jako oddělovač sloupců použij středník (;).
    - Uvnitř textu středníky nepoužívej (nahraď je čárkou).
    - Nevracej žádný Markdown (žádné ```). Jen čistý text.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Chyba;Chyba;Chyba;Chyba"

# === 4. HLAVNÍ LOGIKA APLIKACE ===

col1, col2 = st.columns([3, 1])
with col1:
    cat_input = st.text_input("🔍 Hledat kategorii / produkt", placeholder="Např. letadla 1:72")
with col2:
    limit_input = st.number_input("Počet kusů", min_value=1, max_value=100, value=5)

if st.button("🚀 Spustit generování", type="primary"):
    if not api_key:
        st.warning("Chybí API klíč! Zadej ho v bočním menu nebo v nastavení aplikace.")
        st.stop()
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Stahování dat
    with st.spinner("Stahuji data z feedu..."):
        products = get_products(cat_input, limit_input)
        
    if not products:
        st.error("Nic nenalezeno.")
        st.stop()
        
    # Progress bar a status
    my_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    
    # Smyčka přes produkty
    for i, p in enumerate(products):
        status_text.text(f"Generuji popis pro: {p.get('PRODUCT')} ({i+1}/{len(products)})")
        
        # Volání AI
        csv_line = ask_ai(p, model)
        
        # Rozsekání odpovědi na sloupce
        parts = csv_line.split(";")
        if len(parts) < 4: parts = ["Chyba", "Chyba", "Chyba", "Chyba"]
        
        # Uložení
        p["shortDescription"] = parts[0]
        p["longDescription"] = parts[1]
        p["metaTitle"] = parts[2]
        p["metaDescription"] = parts[3]
        results.append(p)
        
        # Posun progress baru
        my_bar.progress((i + 1) / len(products))
        time.sleep(0.2) # Ochrana proti přetížení
        
    status_text.success("Hotovo!")
    
    # === 5. VÝSTUP A EXPORT ===
    df = pd.DataFrame(results)
    
    # Definice sloupců pro finální CSV
    cols = ["PRODUCT", "MANUFACTURER", "modelClean", "scale", "PRICE_VAT", 
            "URL", "EAN", "CATEGORYTEXT", 
            "shortDescription", "longDescription", "metaTitle", "metaDescription"]
            
    # Ošetření chybějících sloupců
    for c in cols:
        if c not in df.columns: df[c] = ""
        
    final_df = df[cols]
    
    st.dataframe(final_df.head())
    
    # Tlačítko pro stažení
    csv_data = final_df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    
    st.download_button(
        label="📥 Stáhnout CSV Export",
        data=csv_data,
        file_name=f"export_{cat_input.replace(' ', '_')}.csv",
        mime="text/csv"
    )