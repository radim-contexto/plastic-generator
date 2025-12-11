import streamlit as st
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import time

st.set_page_config(page_title="Plastic Planet AI", layout="wide")
st.title("🤖 Plastic Planet: Generátor")

# === NASTAVENÍ ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")
    
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    
    st.info("Tip: Pokud to hází chybu 404, znamená to starou verzi knihovny. Zkontroluj requirements.txt.")

# === FUNKCE ===
def get_products(cat_path, limit):
    params = {"fn": "products", "path": cat_path, "limit": limit, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8' # <--- TOTO OPRAVUJE ROZSYPANÉ EAN KÓDY
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba Workeru: {e}")
        return []

def ask_ai(product, model):
    prompt = f"""
    Jsi expertní copywriter. Vytvoř 4 pole pro CSV (oddělovač středník ;).
    
    VSTUP:
    Produkt: {product.get('PRODUCT')}
    Výrobce: {product.get('MANUFACTURER')}
    Měřítko: {product.get('scale')}
    Název: {product.get('modelClean')}
    
    VÝSTUP (jeden řádek):
    shortDescription;longDescription;metaTitle;metaDescription
    
    PRAVIDLA:
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): <h3>...</h3>. Fakta z historie.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    
    Nepoužívej Markdown. Žádné odřádkování.
    """
    
    # Vypnutí cenzury (aby prošly tanky/válka)
    safety = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        response = model.generate_content(prompt, safety_settings=safety)
        return response.text.strip()
    except Exception as e:
        return f"CHYBA AI: {str(e)};CHYBA;CHYBA;CHYBA"

# === APLIKACE ===
col1, col2 = st.columns([3, 1])
with col1:
    cat_input = st.text_input("Kategorie (přesná cesta)", "Modely + | Letadla a vrtulníky | 1:72")
with col2:
    limit_input = st.number_input("Počet", 1, 1000, 3)

if st.button("🚀 Spustit", type="primary"):
    if not api_key:
        st.error("Chybí klíč!")
        st.stop()
        
    # Inicializace AI
    genai.configure(api_key=api_key)
    # Zkusíme Flash, kdyby nešel, spadlo by to do chyby, ale update requirements to vyřeší
    model = genai.GenerativeModel('gemini-1.5-flash')

    with st.status("Pracuji...", expanded=True) as status:
        st.write("Stahuji data...")
        products = get_products(cat_input, limit_input)
        
        if not products:
            status.update(label="Nic nenalezeno", state="error")
            st.stop()
            
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji: {p.get('PRODUCT')}")
            csv_line = ask_ai(p, model)
            
            parts = csv_line.split(";")
            if len(parts) < 4: parts = [csv_line, "Chyba", "Chyba", "Chyba"]
            
            p["shortDescription"] = parts[0]
            p["longDescription"] = parts[1]
            p["metaTitle"] = parts[2]
            p["metaDescription"] = parts[3]
            results.append(p)
            my_bar.progress((i + 1) / len(products))
            
        status.update(label="Hotovo!", state="complete")
        
    df = pd.DataFrame(results)
    st.dataframe(df)
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("Stáhnout CSV", csv, "export.csv", "text/csv")
