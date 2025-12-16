import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import xml.etree.ElementTree as ET
import time
import json

# --- KONFIGURACE ---
st.set_page_config(page_title="Generátor (XML)", layout="centered")

# URL tvého feedu
FEED_URL = "https://raw.githubusercontent.com/radim-contexto/xmlfeed/refs/heads/main/universal.xml"
MODEL_NAME = "models/gemini-2.5-pro"

# --- CSS PRO ČISTÝ DESIGN ---
st.markdown("""
    <style>
    /* Skrytí zbytečností */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Nadpis */
    h1 {
        text-align: center;
        font-family: 'Helvetica', sans-serif;
        font-weight: 700;
        padding-bottom: 30px;
    }
    
    /* Tlačítka */
    div.stButton > button {
        width: 100%;
        background-color: #000000;
        color: #ffffff;
        font-weight: bold;
        padding: 12px;
        border-radius: 4px;
        border: none;
    }
    div.stButton > button:hover {
        background-color: #333333;
        color: #ffffff;
    }
    
    /* Tabulka */
    div[data-testid="stDataFrame"] {
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- NAČÍTÁNÍ DAT ---

@st.cache_data(ttl=3600)
def load_data_from_xml(url):
    """Stáhne XML a převede ho na seznam produktů."""
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        
        # Parsování XML
        root = ET.fromstring(resp.content)
        products = []
        
        for item in root.findall(".//SHOPITEM"):
            # Pomocná funkce pro bezpečné vytažení textu
            def get_text(tag_name):
                node = item.find(tag_name)
                return node.text if node is not None else ""

            # Extrahuje data. Pokud se tagy ve feedu jmenují jinak, uprav to zde.
            prod = {
                "PRODUCT": get_text("PRODUCT"),
                "MANUFACTURER": get_text("MANUFACTURER"),
                "modelClean": get_text("modelClean"), # Předpokládám, že tento tag v XML existuje
                "scale": get_text("scale"),           # Předpokládám, že tento tag v XML existuje
                "PRICE_VAT": get_text("PRICE_VAT"),
                "URL": get_text("URL"),
                "EAN": get_text("EAN"),
                "CATEGORYTEXT": get_text("CATEGORYTEXT")
            }
            
            # Zahodíme produkty bez názvu nebo kategorie
            if prod["PRODUCT"] and prod["CATEGORYTEXT"]:
                products.append(prod)
                
        return products

    except Exception as e:
        st.error(f"❌ Chyba při načítání XML: {e}")
        return []

# --- AI GENERÁTOR ---

def generate_descriptions(product, api_key):
    """Generování textů pomocí Gemini."""
    genai.configure(api_key=api_key)
    
    config = {"temperature": 0.4, "response_mime_type": "application/json"}
    
    try:
        # Primárně zkoušíme 2.5 Pro
        try:
            model = genai.GenerativeModel(MODEL_NAME, generation_config=config)
        except:
            # Fallback na 1.5 Pro, kdyby 2.5 nebyl dostupný
            model = genai.GenerativeModel("models/gemini-1.5-pro", generation_config=config)

        # Data produktu
        p_name = product.get("PRODUCT", "")
        p_manuf = product.get("MANUFACTURER", "")
        p_scale = product.get("scale", "")
        p_cat = product.get("CATEGORYTEXT", "")

        prompt = f"""
        ZADÁNÍ: Jsi copywriter pro modelářský e-shop. Napiš texty pro tento produkt:
        
        NÁZEV: {p_name}
        VÝROBCE: {p_manuf}
        MĚŘÍTKO: {p_scale}
        KATEGORIE: {p_cat}

        VÝSTUP (JSON):
        {{
            "shortDescription": "HTML (2-3 věty, neutrální, o čem model je)",
            "longDescription": "HTML (Strukturovaný text s nadpisy <h3> a <h4>. Sekce: 'O výrobci', 'O měřítku', 'O modelu' - historie předlohy. Pokud chybí fakta, sekci vynech. Nevymýšlej si.)",
            "metaTitle": "SEO Titulek (max 60 znaků)",
            "metaDescription": "SEO Popisek (max 160 znaků)"
        }}
        
        JAZYK: Čeština.
        """
        
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        return {
            "shortDescription": "<p>Chyba při generování.</p>",
            "longDescription": "",
            "metaTitle": product.get("PRODUCT", ""),
            "metaDescription": ""
        }

# --- HLAVNÍ UI ---

def main():
    st.title("Generátor Popisků")

    # 1. API Klíč (Schovaný)
    with st.expander("🔐 Nastavení API", expanded=False):
        api_key = st.text_input("Google API Key", value=st.secrets.get("GOOGLE_API_KEY", ""), type="password")

    # 2. Načtení dat
    with st.spinner("Stahuji data z feedu..."):
        all_products = load_data_from_xml(FEED_URL)

    if not all_products:
        st.warning("Nepodařilo se načíst feed nebo je prázdný.")
        return

    # Převedení na DataFrame
    df = pd.DataFrame(all_products)

    # 3. Příprava seznamu kategorií
    # Seskupíme podle kategorie a spočítáme počet produktů
    categories_df = df['CATEGORYTEXT'].value_counts().reset_index()
    categories_df.columns = ['Kategorie', 'Počet produktů']
    categories_df = categories_df.sort_values(by="Kategorie")

    # 4. Výběr kategorie (Rolovací tabulka)
    st.markdown("### 1. Vyberte kategorii ze seznamu")
    
    selection = st.dataframe(
        categories_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=400 # Fixní výška pro rolování
    )

    # 5. Akce po výběru
    if selection.selection.rows:
        idx = selection.selection.rows[0]
        selected_cat = categories_df.iloc[idx]["Kategorie"]
        count = categories_df.iloc[idx]["Počet produktů"]
        
        st.info(f"Vybráno: **{selected_cat}** ({count} položek)")
        
        if st.button("🚀 SPUSTIT GENEROVÁNÍ"):
            if not api_key:
                st.error("Chybí API Klíč!")
                return
            
            # Filtrace produktů jen pro vybranou kategorii
            target_products = df[df['CATEGORYTEXT'] == selected_cat].to_dict('records')
            
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, item in enumerate(target_products):
                status_text.text(f"Zpracovávám ({i+1}/{count}): {item.get('PRODUCT')}")
                
                # AI Generování
                ai_data = generate_descriptions(item, api_key)
                
                # Spojení dat
                final_row = {**item, **ai_data}
                
                # Úklid sloupců pro CSV (jen ty co chceme)
                export_cols = [
                    "PRODUCT", "MANUFACTURER", "modelClean", "scale", 
                    "PRICE_VAT", "URL", "EAN", "CATEGORYTEXT", 
                    "shortDescription", "longDescription", "metaTitle", "metaDescription"
                ]
                # Vytvoříme řádek jen s existujícími sloupci
                clean_row = {k: final_row.get(k, "") for k in export_cols}
                
                results.append(clean_row)
                
                # Aktualizace baru
                progress_bar.progress((i + 1) / count)
                time.sleep(0.1) 
            
            status_text.success("✅ Hotovo!")
            
            # Export do CSV
            result_df = pd.DataFrame(results)
            csv_data = result_df.to_csv(sep=";", index=False, encoding="utf-8-sig")
            
            st.download_button(
                label="📥 STÁHNOUT CSV",
                data=csv_data,
                file_name=f"export_popisky.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
