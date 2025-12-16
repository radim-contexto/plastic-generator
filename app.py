import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import time
import json
import os

# --- KONFIGURACE ---
st.set_page_config(
    page_title="Generátor Popisků",
    page_icon="📝",
    layout="centered" # Vše na střed
)

# Fixní nastavení (skryté před uživatelem)
WORKER_URL = "https://plastic-planet.radim-81e.workers.dev"
MODEL_NAME = "models/gemini-2.5-pro" 

# --- CSS ÚPRAVY (Minimalismus) ---
st.markdown("""
    <style>
    /* Skrytí menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Zvětšení hlavního nadpisu */
    h1 {
        text-align: center;
        font-weight: 700;
        padding-bottom: 20px;
    }
    
    /* Zarovnání tlačítek na střed */
    div.stButton > button {
        width: 100%;
        background-color: #000000;
        color: white;
        font-weight: bold;
        padding: 12px;
    }
    div.stButton > button:hover {
        background-color: #333333;
        color: white;
        border-color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKCE ---

def get_categories_safe(worker_url):
    """Načte kategorie a ošetří různé formáty dat."""
    try:
        resp = requests.get(worker_url, params={"fn": "categories"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("payload", data)
        
        # Pokud je payload slovník (chyba API), převedeme na list
        if isinstance(payload, dict):
            payload = [payload]
            
        return payload
    except Exception as e:
        st.error(f"Chyba načítání dat: {e}")
        return []

def get_products_recursive(worker_url, category_path):
    """Stáhne všechny produkty."""
    products = []
    limit = 50 
    offset = 0
    
    status_cont = st.empty()
    
    while True:
        status_cont.info(f"⏳ Stahuji položky... ({len(products)} načteno)")
        try:
            params = {
                "fn": "products",
                "path": category_path,
                "limit": limit,
                "offset": offset
            }
            resp = requests.get(worker_url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            
            batch = data.get("payload", [])
            if not batch:
                break
            products.extend(batch)
            
            next_offset = data.get("nextOffset")
            if not next_offset or next_offset == 0:
                break
            offset = next_offset
            time.sleep(0.1) 
        except Exception as e:
            st.error(f"Chyba stahování: {e}")
            break
            
    status_cont.empty()
    return products

def generate_descriptions(product, api_key):
    """Generuje popisky."""
    genai.configure(api_key=api_key)
    generation_config = {"temperature": 0.4, "response_mime_type": "application/json"}

    try:
        # Fallback na 1.5-pro kdyby 2.5 dělal problémy s názvem
        try:
            model = genai.GenerativeModel(model_name=MODEL_NAME, generation_config=generation_config)
        except:
            model = genai.GenerativeModel(model_name="models/gemini-1.5-pro", generation_config=generation_config)

        name = product.get("PRODUCT", "")
        manufacturer = product.get("MANUFACTURER", "")
        scale = product.get("scale", "")
        cat_text = product.get("CATEGORYTEXT", "")

        prompt = f"""
        ÚKOL: Vytvoř strukturovaná produktová data pro e-shop (modelářství).
        
        PRODUKT:
        Název: {name}
        Výrobce: {manufacturer}
        Měřítko: {scale}
        Kategorie: {cat_text}

        VÝSTUP (JSON):
        {{
            "shortDescription": "HTML (2-3 věty, neutrální, pro koho to je)",
            "longDescription": "HTML (struktura: <h3>Detailní popis</h3>, <h4>O výrobci</h4>, <h4>O měřítku</h4>, <h4>O modelu - historie předlohy</h4>). Pokud chybí fakta, sekci vynech.",
            "metaTitle": "String (max 60 znaků)",
            "metaDescription": "String (max 160 znaků)"
        }}

        Jazyk: Čeština.
        """

        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        return {
            "shortDescription": "<p>Popis se nepodařilo vygenerovat.</p>",
            "longDescription": "",
            "metaTitle": f"{name}",
            "metaDescription": ""
        }

# --- MAIN UI ---

def main():
    st.title("Generátor Popisků")

    # 1. API Klíč (Schovaný v expanderu)
    with st.expander("🔐 Nastavení přístupu", expanded=False):
        default_key = st.secrets.get("GOOGLE_API_KEY", "")
        api_key = st.text_input("Google API Key", value=default_key, type="password")

    # 2. Načtení kategorií
    if 'categories' not in st.session_state:
        # Automaticky zkusit načíst při startu
        st.session_state['categories'] = get_categories_safe(WORKER_URL)

    if not st.session_state['categories']:
        if st.button("🔄 Načíst kategorie"):
            st.session_state['categories'] = get_categories_safe(WORKER_URL)
            st.rerun()

    # 3. Výběr kategorie (Tabulka)
    if st.session_state['categories']:
        cats_data = []
        
        # --- ZDE BÝVALA CHYBA: Ošetření formátu dat ---
        for c in st.session_state['categories']:
            if isinstance(c, dict):
                # Standardní objekt
                name = c.get('name', 'Neznámá kategorie')
                path = c.get('path', c.get('id', name)) # Fallback pro ID
                count = c.get('count', '')
            else:
                # Pokud worker vrací jen stringy ["Kat1", "Kat2"]
                name = str(c)
                path = str(c)
                count = ''
            
            cats_data.append({
                "Kategorie": name,
                "ID": path,
                "Položek": count
            })
        # -----------------------------------------------

        df_cats = pd.DataFrame(cats_data)
        
        st.write("### 1. Vyberte kategorii")
        
        selection = st.dataframe(
            df_cats,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if selection.selection.rows:
            idx = selection.selection.rows[0]
            selected_row = df_cats.iloc[idx]
            cat_name = selected_row["Kategorie"]
            cat_path = selected_row["ID"]
            
            st.success(f"Vybráno: **{cat_name}**")
            
            st.write("### 2. Akce")
            if st.button(f"🚀 SPUSTIT GENEROVÁNÍ"):
                if not api_key:
                    st.error("Chybí API klíč. Zadejte ho v nastavení nahoře.")
                    return
                
                # A. Stažení
                products = get_products_recursive(WORKER_URL, cat_path)
                
                if not products:
                    st.warning("Tato kategorie neobsahuje žádné produkty.")
                else:
                    # B. Generování
                    st.info(f"Nalezeno {len(products)} produktů. Začínám pracovat...")
                    
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, prod in enumerate(products):
                        p_name = prod.get('PRODUCT', 'Produkt')
                        status_text.text(f"Zpracovávám ({i+1}/{len(products)}): {p_name}")
                        
                        ai_data = generate_descriptions(prod, api_key)
                        
                        full_row = {**prod, **ai_data}
                        
                        # Export pouze relevantních sloupců
                        export_row = {
                            "PRODUCT": full_row.get("PRODUCT"),
                            "MANUFACTURER": full_row.get("MANUFACTURER"),
                            "modelClean": full_row.get("modelClean"),
                            "scale": full_row.get("scale"),
                            "PRICE_VAT": full_row.get("PRICE_VAT"),
                            "URL": full_row.get("URL"),
                            "EAN": full_row.get("EAN"),
                            "CATEGORYTEXT": full_row.get("CATEGORYTEXT"),
                            "shortDescription": full_row.get("shortDescription"),
                            "longDescription": full_row.get("longDescription"),
                            "metaTitle": full_row.get("metaTitle"),
                            "metaDescription": full_row.get("metaDescription"),
                        }
                        results.append(export_row)
                        
                        progress_bar.progress((i+1)/len(products))
                        time.sleep(0.1) 

                    status_text.success("✅ Hotovo!")
                    
                    # C. Export
                    df_result = pd.DataFrame(results)
                    csv = df_result.to_csv(sep=";", index=False, encoding="utf-8-sig")
                    
                    st.download_button(
                        label="📥 STÁHNOUT VÝSLEDEK (CSV)",
                        data=csv,
                        file_name=f"export_{cat_path}.csv",
                        mime="text/csv"
                    )

if __name__ == "__main__":
    main()
