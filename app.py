import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import time
import json
import os

# --- KONFIGURACE ---
# Tvoje URL workeru
DEFAULT_WORKER_URL = "https://plastic-planet.radim-81e.workers.dev"

st.set_page_config(page_title="PlasticPlanet AI Generator", layout="wide")

# --- FUNKCE: Worker ---

def get_categories(worker_url):
    """Načte kategorie."""
    try:
        # Volání bez parametrů nebo s fn=categories, podle toho jak to máš nastavené
        resp = requests.get(worker_url, params={"fn": "categories"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("payload", data) 
    except Exception as e:
        st.error(f"Chyba při načítání kategorií: {e}")
        return []

def get_products_recursive(worker_url, category_path):
    """Stáhne KOMPLETNĚ celou kategorii (všechny stránky)."""
    products = []
    limit = 50 
    offset = 0
    
    status_box = st.empty()
    
    while True:
        status_box.info(f"⏳ Stahuji produkty... zatím mám: {len(products)}")
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
            
            # Kontrola další stránky
            next_offset = data.get("nextOffset")
            if not next_offset or next_offset == 0:
                break
            
            offset = next_offset
            time.sleep(0.1) 
            
        except Exception as e:
            st.error(f"❌ Chyba při stahování: {e}")
            break
            
    status_box.empty()
    return products

# --- FUNKCE: AI Generátor ---

def generate_descriptions(product, api_key, model_name):
    """Generuje popisky."""
    genai.configure(api_key=api_key)
    
    # Konfigurace pro JSON výstup
    generation_config = {
        "temperature": 0.4,
        "response_mime_type": "application/json",
    }

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
        )

        name = product.get("PRODUCT", "")
        manufacturer = product.get("MANUFACTURER", "")
        scale = product.get("scale", "")
        cat_text = product.get("CATEGORYTEXT", "")

        # Prompt
        prompt = f"""
        Jsi expert na plastikové modelářství (Plasticplanet.cz).
        Vytvoř strukturovaná data pro produkt:
        
        Název: {name}
        Výrobce: {manufacturer}
        Měřítko: {scale}
        Kategorie: {cat_text}

        Vrať JSON:
        {{
            "shortDescription": "HTML string (2-3 věty, neutrální)",
            "longDescription": "HTML string (strukturovaný: O výrobci, O měřítku, O modelu)",
            "metaTitle": "String (max 60 znaků)",
            "metaDescription": "String (max 160 znaků)"
        }}

        PRAVIDLA:
        1. longDescription: 
           - Používej nadpisy <h3>, <h4>.
           - Sekce "O modelu": detailní historie předlohy. 
           - Pokud nemáš fakta, celou sekci vynech. Nevymýšlej si!
        2. Jazyk: Čeština.
        """

        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        return {
            "shortDescription": "<p>Chyba generování.</p>",
            "longDescription": "",
            "metaTitle": f"{name} | Plasticplanet.cz",
            "metaDescription": ""
        }

# --- HLAVNÍ APLIKACE ---

def main():
    st.title("🤖 PlasticPlanet AI Popiskovač")

    # Sidebar
    with st.sidebar:
        st.header("Nastavení")
        
        # API klíč se bere ze Secrets (pokud je nastaven), jinak text input
        default_key = st.secrets.get("GOOGLE_API_KEY", "")
        api_key = st.text_input("Google API Key", value=default_key, type="password")
        
        # Worker URL (už předvyplněná tvoje)
        worker_url = st.text_input("Worker URL", value=DEFAULT_WORKER_URL)
        
        # Výběr modelu
        model_choice = st.selectbox(
            "Model", 
            ["models/gemini-2.0-flash", "models/gemini-1.5-pro", "models/gemini-1.5-flash"]
        )
        
        st.divider()
        if st.button("🔄 Načíst kategorie"):
            cats = get_categories(worker_url)
            st.session_state['categories'] = cats
            if cats:
                st.success(f"Načteno {len(cats)} kategorií.")

    # Hlavní okno
    if 'categories' in st.session_state and st.session_state['categories']:
        # Selectbox
        cats_dict = {c['name']: c['path'] for c in st.session_state['categories'] if 'name' in c}
        selected_name = st.selectbox("Vyber kategorii:", list(cats_dict.keys()))
        
        if st.button(f"🚀 SPUSTIT pro: {selected_name}"):
            if not api_key:
                st.error("Chybí API klíč!")
                return
            
            selected_path = cats_dict[selected_name]
            
            # 1. Stáhnout data
            products = get_products_recursive(worker_url, selected_path)
            
            if not products:
                st.warning("Žádné produkty.")
                return
            
            st.info(f"Mám {len(products)} produktů. Generuji...")
            
            # 2. Generovat
            results = []
            bar = st.progress(0)
            status = st.empty()
            
            for i, prod in enumerate(products):
                status.text(f"Zpracovávám: {prod.get('PRODUCT')}")
                
                ai_data = generate_descriptions(prod, api_key, model_choice)
                
                # Spojení dat
                full_row = {**prod, **ai_data} # Spojí původní data z feedu + nová z AI
                
                # Filtrace sloupců pro CSV export (aby tam nebylo smetí z workeru)
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
                bar.progress((i+1)/len(products))
                time.sleep(0.2) # Ochrana proti limitům
            
            # 3. Export
            status.success("Hotovo!")
            df = pd.DataFrame(results)
            st.dataframe(df.head())
            
            st.download_button(
                "📥 Stáhnout CSV",
                df.to_csv(sep=";", index=False, encoding="utf-8-sig"),
                f"export_{selected_path}.csv",
                "text/csv"
            )

if __name__ == "__main__":
    main()
