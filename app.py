import streamlit as st
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import time

# === 1. NASTAVENÍ STRÁNKY ===
st.set_page_config(page_title="Plastic Planet AI", layout="wide")
st.title("🤖 Plastic Planet: Generátor (Full Category)")

# === 2. SIDEBAR A NASTAVENÍ ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")
    
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    
    st.markdown("---")
    # TLAČÍTKO TESTU SPOJENÍ
    if st.button("🛠 Otestovat API Klíč"):
        if not api_key:
            st.error("Chybí klíč!")
        else:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                res = model.generate_content("Ahoj")
                st.success(f"✅ Spojení funguje! AI odpověděla: {res.text}")
            except Exception as e:
                st.error(f"❌ Chyba: {e}")

# === 3. FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_list():
    """Stáhne všechny dostupné kategorie pro výběr"""
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

def get_all_products_in_category(cat_path):
    """Stáhne 'vše' z kategorie (limit 5000 je maximum workeru)"""
    params = {
        "fn": "products",
        "path": cat_path,
        "limit": 5000,
        "mode": "view"
    }
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8' # Oprava EAN kódování
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba při stahování produktů: {e}")
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
    2. longDescription (HTML): Struktura <h3>, <h4>. Dohledej fakta o předloze.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    
    Nepoužívej Markdown. Odstraň nové řádky.
    """
    
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

# === 4. HLAVNÍ APLIKACE ===

with st.spinner("Načítám seznam kategorií..."):
    all_cats = get_categories_list()

if not all_cats:
    st.error("Nepodařilo se načíst seznam kategorií. Zkontroluj URL Workeru.")
    # Pokud selže načtení, dovolíme alespoň ruční zadání jako zálohu
    selected_cat = st.text_input("Zadej kategorii ručně (když selhal seznam)", "Modely + | Letadla a vrtulníky | 1:72")
else:
    selected_cat = st.selectbox("📂 Vyber kategorii ze seznamu", all_cats)

if st.button("🚀 Vygenerovat celou kategorii", type="primary"):
    if not api_key:
        st.error("Chybí API klíč! (Zadej vlevo)")
        st.stop()
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    with st.status("Pracuji...", expanded=True) as status:
        st.write(f"Stahuji všechny produkty z: {selected_cat}...")
        
        products = get_all_products_in_category(selected_cat)
        
        if not products:
            status.update(label="V této kategorii nejsou žádné produkty.", state="error")
            st.stop()
            
        total_items = len(products)
        st.write(f"Nalezeno {total_items} produktů. Začínám generovat...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji ({i+1}/{total_items}): {p.get('PRODUCT')}")
            
            csv_line = ask_ai(p, model)
            
            parts = csv_line.split(";")
            if len(parts) < 4: parts = [csv_line, "Chyba", "Chyba", "Chyba"]
            
            p["shortDescription"] = parts[0]
            p["longDescription"] = parts[1]
            p["metaTitle"] = parts[2]
            p["metaDescription"] = parts[3]
            results.append(p)
            
            my_bar.progress((i + 1) / total_items)
            time.sleep(0.1)
            
        status.update(label="Hotovo! 🎉", state="complete")
        
    df = pd.DataFrame(results)
    
    st.success(f"Úspěšně zpracováno {len(df)} položek.")
    st.dataframe(df[["PRODUCT", "shortDescription", "EAN"]])
    
    csv_data = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="📥 Stáhnout kompletní CSV", 
        data=csv_data, 
        file_name=f"export_full.csv", 
        mime="text/csv"
    )
