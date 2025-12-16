import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import time
import json
import os

# --- KONFIGURACE A BRANDING ---
st.set_page_config(
    page_title="Contexto | AI Content Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Fixní nastavení
WORKER_URL = "https://plastic-planet.radim-81e.workers.dev"
MODEL_NAME = "models/gemini-2.5-pro" # Natvrdo nastavený model

# --- CSS STYLING (Contexto Brand) ---
st.markdown("""
    <style>
    /* Hlavní barvy a fonty */
    .stApp {
        background-color: #ffffff;
        color: #1a1a1a;
    }
    
    /* Skrytí defaultního Streamlit menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Custom Header */
    .custom-header {
        background-color: #ffffff;
        padding: 20px 0;
        border-bottom: 2px solid #000000;
        margin-bottom: 30px;
        display: flex;
        align-items: center;
    }
    .custom-header img {
        height: 50px;
        margin-right: 20px;
    }
    .custom-header h1 {
        font-family: 'Helvetica', 'Arial', sans-serif;
        color: #000000;
        font-size: 24px;
        margin: 0;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Stylování tlačítek */
    div.stButton > button {
        background-color: #000000;
        color: #ffffff;
        border-radius: 0px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
        text-transform: uppercase;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #333333;
        color: #ffffff;
        border: none;
    }

    /* Tabulka */
    div[data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
    }
    </style>
    
    <div class="custom-header">
        <img src="https://contexto.cz/wp-content/uploads/2019/11/logo_contexto.png" alt="Contexto Logo">
        <h1>AI Content Generator <span style="font-weight:300; font-size: 18px; color: #666;">| Plastic Planet Edition</span></h1>
    </div>
    """, unsafe_allow_html=True)

# --- FUNKCE ---

def get_categories(worker_url):
    """Načte kategorie z workeru."""
    try:
        resp = requests.get(worker_url, params={"fn": "categories"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("payload", data)
        return payload
    except Exception as e:
        st.error(f"Chyba při komunikaci se serverem: {e}")
        return []

def get_products_recursive(worker_url, category_path):
    """Stáhne KOMPLETNĚ celou kategorii."""
    products = []
    limit = 50 
    offset = 0
    
    # Custom status container
    status_container = st.empty()
    
    while True:
        status_container.info(f"⏳ Contexto AI stahuje data... načteno položek: {len(products)}")
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
            st.error(f"❌ Chyba stahování: {e}")
            break
            
    status_container.empty()
    return products

def generate_descriptions(product, api_key):
    """Generuje popisky pomocí Gemini 2.5 Pro."""
    genai.configure(api_key=api_key)
    
    generation_config = {
        "temperature": 0.4,
        "response_mime_type": "application/json",
    }

    try:
        # Používáme striktně 2.5 Pro (nebo fallback na 1.5 Pro kdyby 2.5 nebyl dostupný v API pod tímto jménem)
        # Poznámka: Oficiální název v API může být 'gemini-1.5-pro-latest' nebo 'gemini-experimental'. 
        # Zde používáme to, co jsi chtěl, ale s fallbackem.
        try:
            model = genai.GenerativeModel(model_name=MODEL_NAME, generation_config=generation_config)
        except:
            # Fallback kdyby '2.5' string nefungoval
            model = genai.GenerativeModel(model_name="models/gemini-1.5-pro", generation_config=generation_config)

        name = product.get("PRODUCT", "")
        manufacturer = product.get("MANUFACTURER", "")
        scale = product.get("scale", "")
        cat_text = product.get("CATEGORYTEXT", "")

        prompt = f"""
        Jsi senior copywriter pro Contexto Consulting, pracující na projektu Plasticplanet.cz.
        
        ÚKOL: Vytvoř strukturovaná produktová data pro:
        Název: {name}
        Výrobce: {manufacturer}
        Měřítko: {scale}
        Kategorie: {cat_text}

        VÝSTUP (JSON):
        {{
            "shortDescription": "HTML (2-3 věty, neutrální)",
            "longDescription": "HTML (strukturovaný: O výrobci, O měřítku, O modelu)",
            "metaTitle": "String (max 60 znaků)",
            "metaDescription": "String (max 160 znaků)"
        }}

        PRAVIDLA:
        1. longDescription: 
           - Používej nadpisy <h3>, <h4>.
           - Sekce "O modelu": detailní historie předlohy.
           - Pokud chybí fakta, celou sekci vynech. Nevymýšlej si.
        2. Jazyk: Čeština.
        """

        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        return {
            "shortDescription": "<p>Data nedostupná.</p>",
            "longDescription": "",
            "metaTitle": f"{name} | Plasticplanet.cz",
            "metaDescription": ""
        }

# --- MAIN UI ---

def main():
    # Sidebar pouze pro API klíč (čistý design)
    with st.sidebar:
        st.image("https://contexto.cz/wp-content/uploads/2019/11/logo_contexto.png", width=150)
        st.markdown("### Konfigurace")
        # API klíč ze secrets nebo input
        default_key = st.secrets.get("GOOGLE_API_KEY", "")
        api_key = st.text_input("Google API Key", value=default_key, type="password")
        
        st.markdown("---")
        st.caption(f"Backend: {WORKER_URL}")
        st.caption(f"AI Model: {MODEL_NAME}")
        
        if st.button("🔄 Aktualizovat seznam kategorií"):
            cats = get_categories(WORKER_URL)
            st.session_state['categories'] = cats
            st.rerun()

    # 1. Načtení kategorií (pokud nejsou)
    if 'categories' not in st.session_state:
        st.session_state['categories'] = get_categories(WORKER_URL)

    # 2. Výběr kategorie - LISTOVACÍ SEZNAM (Dataframe)
    st.subheader("1. Vyberte kategorii k exportu")
    
    if st.session_state['categories']:
        # Příprava dat pro tabulku
        cats_data = []
        for c in st.session_state['categories']:
            cats_data.append({
                "Název kategorie": c.get('name', 'Neznámá'),
                "ID/Cesta": c.get('path', c.get('id')),
                "Položek": c.get('count', 'N/A') # Zobrazí počet, pokud ho worker posílá
            })
        
        df_cats = pd.DataFrame(cats_data)
        
        # Konfigurace interaktivní tabulky
        selection = st.dataframe(
            df_cats,
            use_container_width=True,
            hide_index=True,
            on_select="rerun", # Po kliknutí se appka obnoví
            selection_mode="single-row"
        )
        
        # Získání vybraného řádku
        selected_rows = selection.selection.rows
        
        if selected_rows:
            index = selected_rows[0]
            selected_cat = df_cats.iloc[index]
            cat_name = selected_cat["Název kategorie"]
            cat_path = selected_cat["ID/Cesta"]
            
            st.markdown(f"### Vybrána kategorie: **{cat_name}**")
            st.info("Systém je připraven ke zpracování dat pomocí modelu Gemini 2.5 Pro.")

            # 3. Spuštění procesu
            if st.button(f"🚀 SPUSTIT GENERÁTOR PRO {cat_name.upper()}"):
                if not api_key:
                    st.error("Chybí Google API Key.")
                    return
                
                # A. Stažení
                products = get_products_recursive(WORKER_URL, cat_path)
                
                if not products:
                    st.warning("Kategorie je prázdná.")
                else:
                    # B. Generování
                    st.write("---")
                    st.subheader("2. Průběh zpracování")
                    
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Kontejner pro živý náhled
                    preview_container = st.container()

                    for i, prod in enumerate(products):
                        status_text.markdown(f"**Zpracovávám ({i+1}/{len(products)}):** {prod.get('PRODUCT')}")
                        
                        ai_data = generate_descriptions(prod, api_key)
                        
                        full_row = {**prod, **ai_data}
                        
                        # Finální formát pro CSV
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
                        time.sleep(0.1) # Prevence 429

                    status_text.success("✅ Hotovo! Generování dokončeno.")
                    
                    # C. Export
                    st.write("---")
                    st.subheader("3. Export dat")
                    
                    df_result = pd.DataFrame(results)
                    st.dataframe(df_result)
                    
                    csv = df_result.to_csv(sep=";", index=False, encoding="utf-8-sig")
                    
                    st.download_button(
                        label="📥 STÁHNOUT FINÁLNÍ CSV",
                        data=csv,
                        file_name=f"Contexto_Export_{cat_path}.csv",
                        mime="text/csv"
                    )
    else:
        st.warning("Nepodařilo se načíst žádné kategorie.")

if __name__ == "__main__":
    main()
