import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import time
import json

# --- KONFIGURACE UI ---
st.set_page_config(page_title="Generátor", layout="centered")

# Skrytí menu a patičky pro čistý vzhled
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    h1 {text-align: center; padding-bottom: 20px;}
    .stButton button {width: 100%; background: #000; color: #fff; font-weight: bold;}
    .stButton button:hover {background: #333; color: #fff; border-color: #333;}
    </style>
""", unsafe_allow_html=True)

# --- KONSTANTY ---
WORKER_URL = "https://plastic-planet.radim-81e.workers.dev"
MODEL_NAME = "models/gemini-2.5-pro"

# --- FUNKCE ---

def get_categories_safe(worker_url):
    """Bezpečné načtení kategorií - poradí si s objekty i prostým textem."""
    try:
        resp = requests.get(worker_url, params={"fn": "categories"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Worker může vracet data přímo nebo v 'payload'
        payload = data.get("payload", data)
        
        # Pojistka: pokud to není seznam, uděláme z toho seznam
        if not isinstance(payload, list):
            return [payload] if payload else []
            
        return payload
    except Exception as e:
        st.error(f"Chyba načítání feedu: {e}")
        return []

def get_products_recursive(worker_url, category_path):
    """Stáhne všechny produkty z vybrané kategorie."""
    products = []
    limit = 50 
    offset = 0
    status = st.empty()
    
    while True:
        status.info(f"⏳ Stahuji položky... ({len(products)} načteno)")
        try:
            params = {"fn": "products", "path": category_path, "limit": limit, "offset": offset}
            resp = requests.get(worker_url, params=params, timeout=20)
            data = resp.json()
            
            batch = data.get("payload", [])
            if not batch: break
            products.extend(batch)
            
            next_offset = data.get("nextOffset")
            if not next_offset or next_offset == 0: break
            offset = next_offset
            time.sleep(0.1)
        except: break
            
    status.empty()
    return products

def generate_descriptions(product, api_key):
    """Generování textů přes Gemini 2.5 Pro."""
    genai.configure(api_key=api_key)
    # Zkusíme 2.5, když nepůjde, fallback na 1.5-pro
    try:
        model = genai.GenerativeModel(MODEL_NAME, generation_config={"response_mime_type": "application/json"})
    except:
        model = genai.GenerativeModel("models/gemini-1.5-pro", generation_config={"response_mime_type": "application/json"})

    prompt = f"""
    PRODUKT: {product.get('PRODUCT')} | {product.get('MANUFACTURER')} | {product.get('scale')}
    ÚKOL: Vytvoř JSON s popisky pro e-shop.
    JAZYK: Čeština.
    STRUKTURA JSON:
    {{
        "shortDescription": "HTML (2-3 věty)",
        "longDescription": "HTML (strukturovaný text s nadpisy h3, h4. Sekce: O výrobci, O měřítku, O modelu. Pokud chybí fakta, sekci vynech.)",
        "metaTitle": "SEO Titulek (max 60 znaků)",
        "metaDescription": "SEO Popis (max 160 znaků)"
    }}
    """
    try:
        resp = model.generate_content(prompt)
        return json.loads(resp.text)
    except:
        return {"shortDescription": "<p>Chyba.</p>", "longDescription": "", "metaTitle": "", "metaDescription": ""}

# --- HLAVNÍ UI ---

def main():
    st.title("Generátor Popisků")

    # API Klíč (schovaný)
    with st.expander("🔐 Nastavení"):
        api_key = st.text_input("Google API Key", value=st.secrets.get("GOOGLE_API_KEY", ""), type="password")

    # 1. Načtení kategorií (automaticky)
    if 'categories' not in st.session_state:
        st.session_state['categories'] = get_categories_safe(WORKER_URL)

    cats_raw = st.session_state['categories']
    
    if cats_raw:
        # PŘÍPRAVA DAT PRO TABULKU (OPRAVA CHYBY Z MINULA)
        table_data = []
        for c in cats_raw:
            # Pokud je kategorie jen text (str), použijeme ho jako název i ID
            if isinstance(c, str):
                table_data.append({"Kategorie": c, "ID": c})
            # Pokud je to objekt (dict), vytáhneme data
            elif isinstance(c, dict):
                table_data.append({
                    "Kategorie": c.get('name', 'Bez názvu'), 
                    "ID": c.get('path', c.get('id', c.get('name')))
                })

        df = pd.DataFrame(table_data)

        # 2. VYKRESLENÍ ROLOVACÍHO SEZNAMU
        st.write("### Vyberte kategorii ze seznamu:")
        
        selection = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            height=400  # Výška pro rolování
        )

        # 3. AKCE PO KLIKNUTÍ
        if selection.selection.rows:
            idx = selection.selection.rows[0]
            selected_row = df.iloc[idx]
            cat_name = selected_row["Kategorie"]
            cat_id = selected_row["ID"]

            st.success(f"Vybráno: **{cat_name}**")
            
            if st.button("🚀 SPUSTIT GENEROVÁNÍ"):
                if not api_key:
                    st.error("Chybí API klíč!")
                    return

                # Stahování
                items = get_products_recursive(WORKER_URL, cat_id)
                if not items:
                    st.warning("Kategorie je prázdná.")
                    return
                
                # Generování
                results = []
                bar = st.progress(0)
                info = st.empty()
                
                for i, item in enumerate(items):
                    info.text(f"Zpracovávám: {item.get('PRODUCT')}")
                    ai_data = generate_descriptions(item, api_key)
                    
                    # Sloučení dat
                    final = item.copy()
                    final.update(ai_data)
                    
                    # Úklid pro CSV
                    clean_row = {k: final.get(k, "") for k in [
                        "PRODUCT", "MANUFACTURER", "modelClean", "scale", 
                        "PRICE_VAT", "URL", "EAN", "CATEGORYTEXT", 
                        "shortDescription", "longDescription", "metaTitle", "metaDescription"
                    ]}
                    results.append(clean_row)
                    bar.progress((i+1)/len(items))
                    time.sleep(0.1)
                
                info.success("Hotovo!")
                
                # Export
                csv = pd.DataFrame(results).to_csv(sep=";", index=False, encoding="utf-8-sig")
                st.download_button("📥 Stáhnout CSV", csv, f"export_{cat_id}.csv", "text/csv")
    
    else:
        st.warning("Nepodařilo se načíst feed kategorií. Zkontrolujte Worker URL.")
        if st.button("Zkusit znovu"):
            st.session_state.pop('categories', None)
            st.rerun()

if __name__ == "__main__":
    main()
