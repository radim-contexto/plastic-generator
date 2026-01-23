import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import xml.etree.ElementTree as ET
import time
import json
import io
import unicodedata

# --- KONFIGURACE ---
st.set_page_config(page_title="Plastic Planet AI", layout="centered", page_icon="🧩")

# URL feedu a Model
FEED_URL = "https://raw.githubusercontent.com/radim-contexto/xmlfeed/refs/heads/main/universal.xml"
MODEL_NAME = "models/gemini-2.5-pro"

# --- CSS STYLING (BRANDING) ---
st.markdown("""
    <style>
    /* PŘEPSÁNÍ HLAVNÍ BARVY TÉMATU */
    :root {
        --primary-color: rgb(0, 232, 190) !important;
        --background-color: #ffffff;
        --secondary-background-color: #f0f2f6;
        --text-color: #000000;
        --font: sans-serif;
    }

    #MainMenu, footer, header {visibility: hidden;}
    
    h1 {
        text-align: center;
        font-family: 'Helvetica', sans-serif;
        font-weight: 800;
        color: #000;
        margin-bottom: 0px;
        padding-bottom: 5px;
    }
    
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 30px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    div.stButton > button {
        width: 100% !important; 
        background-color: rgb(0, 232, 190) !important;
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 16px !important;
        padding: 16px 24px !important; 
        border-radius: 50px !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(0, 232, 190, 0.4);
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
        white-space: nowrap !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0, 232, 190, 0.6);
        background-color: rgb(50, 255, 220) !important;
    }
    
    div[data-testid="stAlert"] {
        background-color: rgba(0, 232, 190, 0.1);
        border: 1px solid rgb(0, 232, 190);
        color: #005f50;
        border-radius: 10px;
    }
    div[data-testid="stAlert"] svg {
        fill: rgb(0, 232, 190) !important;
    }
    
    .stTextInput input {
        border-radius: 10px;
        border: 1px solid #ddd;
        text-align: center;
    }
    .stTextInput input:focus {
        border-color: rgb(0, 232, 190) !important;
        box-shadow: 0 0 5px rgba(0, 232, 190, 0.5) !important;
    }
    div[data-testid="stWidgetLabel"] {
        justify-content: center;
        display: flex;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #eee;
        border-radius: 10px;
        overflow: hidden;
    }
    </style>
""", unsafe_allow_html=True)

# --- POMOCNÉ FUNKCE ---

def remove_accents(input_str):
    """Odstraní diakritiku z textu pro bezpečný název souboru."""
    if not isinstance(input_str, str):
        return str(input_str)
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

# --- LOGIKA APLIKACE ---

@st.cache_data(ttl=3600)
def load_data_from_xml(url):
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        products = []
        for item in root.findall(".//SHOPITEM"):
            def get_text(tag_name):
                node = item.find(tag_name)
                return node.text if node is not None else ""
            
            # Zde načítáme data z XML. Přidán CODE.
            prod = {
                "CODE": get_text("CODE"), # Kód produktu
                "PRODUCT": get_text("PRODUCT"),
                "MANUFACTURER": get_text("MANUFACTURER"),
                "modelClean": get_text("modelClean"),
                "scale": get_text("scale"),
                "PRICE_VAT": get_text("PRICE_VAT"),
                "URL": get_text("URL"),
                "EAN": get_text("EAN"),
                "CATEGORYTEXT": get_text("CATEGORYTEXT")
            }
            if prod["PRODUCT"] and prod["CATEGORYTEXT"]:
                products.append(prod)
        return products
    except Exception as e:
        st.error(f"Chyba při načítání XML: {e}")
        return []

def generate_descriptions(product, api_key):
    genai.configure(api_key=api_key)
    config = {"temperature": 0.4, "response_mime_type": "application/json"}
    try:
        try:
            model = genai.GenerativeModel(MODEL_NAME, generation_config=config)
        except:
            model = genai.GenerativeModel("models/gemini-1.5-pro", generation_config=config)

        prompt = f"""
        ZADÁNÍ: Jsi copywriter pro modelářský e-shop Plasticplanet.cz.
        PRODUKT: {product.get("PRODUCT")}
        VÝROBCE: {product.get("MANUFACTURER")}
        MĚŘÍTKO: {product.get("scale")}
        KATEGORIE: {product.get("CATEGORYTEXT")}

        VÝSTUP (JSON):
        {{
            "shortDescription": "HTML (2-3 věty, neutrální)",
            "longDescription": "HTML (Strukturovaný text s nadpisy h3, h4. Sekce: O výrobci, O měřítku, O modelu. Pokud chybí fakta, sekci vynech.)",
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

# --- MAIN UI ---

def main():
    # LOGO
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.image("https://cdn.myshoptet.com/usr/www.plasticplanet.cz/user/logos/plasticplanet_new_rgb.png", use_container_width=True)
    
    st.markdown("<h1>Generátor popisků</h1>", unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Powered by Contexto Engine v2.0</div>', unsafe_allow_html=True)

    # API KLÍČ
    default_key = st.secrets.get("GOOGLE_API_KEY", "")
    api_key = st.text_input("Vložte Google API Key", value=default_key, type="password", help="Klíč je nutný pro spuštění AI.")

    if not api_key:
        st.warning("⚠️ Pro pokračování zadejte API klíč.")
        return

    # NAČTENÍ DAT
    with st.spinner("⏳ Načítám feed..."):
        all_products = load_data_from_xml(FEED_URL)

    if not all_products:
        return

    # TABULKA
    df = pd.DataFrame(all_products)
    categories_df = df['CATEGORYTEXT'].value_counts().reset_index()
    categories_df.columns = ['Kategorie', 'Počet produktů']
    categories_df = categories_df.sort_values(by="Kategorie")

    st.markdown("### 📂 Vyberte kategorii")
    
    selection = st.dataframe(
        categories_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=350
    )

    # AKCE
    if selection.selection.rows:
        idx = selection.selection.rows[0]
        selected_cat = categories_df.iloc[idx]["Kategorie"]
        count = categories_df.iloc[idx]["Počet produktů"]
        
        st.markdown("---")
        st.markdown(f"<h3 style='text-align: center'>Vybráno: {selected_cat}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #666'>Počet položek ke zpracování: {count}</p>", unsafe_allow_html=True)
        
        # TLAČÍTKO
        st.markdown("<br>", unsafe_allow_html=True)
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
        
        with btn_col2:
            start_button = st.button("🚀 SPUSTIT GENERÁTOR")
        
        if start_button:
            target_products = df[df['CATEGORYTEXT'] == selected_cat].to_dict('records')
            
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, item in enumerate(target_products):
                status_text.text(f"Zpracovávám ({i+1}/{count}): {item.get('PRODUCT')}")
                
                ai_data = generate_descriptions(item, api_key)
                final_row = {**item, **ai_data}
                
                # PŘÍPRAVA SLOUPCŮ PRO EXPORT
                # Přidán sloupec 'kód' (mapuje se na CODE z feedu)
                clean_row = {
                    "kód": final_row.get("CODE", ""),
                    "PRODUCT": final_row.get("PRODUCT", ""),
                    "MANUFACTURER": final_row.get("MANUFACTURER", ""),
                    "modelClean": final_row.get("modelClean", ""),
                    "scale": final_row.get("scale", ""),
                    "PRICE_VAT": final_row.get("PRICE_VAT", ""),
                    "URL": final_row.get("URL", ""),
                    "EAN": final_row.get("EAN", ""),
                    "CATEGORYTEXT": final_row.get("CATEGORYTEXT", ""),
                    "shortDescription": final_row.get("shortDescription", ""),
                    "longDescription": final_row.get("longDescription", ""),
                    "metaTitle": final_row.get("metaTitle", ""),
                    "metaDescription": final_row.get("metaDescription", "")
                }
                results.append(clean_row)
                
                progress_bar.progress((i + 1) / count)
                time.sleep(0.1) 
            
            status_text.empty()
            st.success("✅ Hotovo! Data jsou připravena.")
            
            # --- EXPORT DO EXCELU (.xlsx) ---
            result_df = pd.DataFrame(results)
            
            # Vytvoření binárního streamu pro Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # index=False zajistí, že se nevypisuje číslo řádku
                # Pandas defaultně formátuje hlavičku tučně, ale data jsou bez formátování
                result_df.to_excel(writer, index=False, sheet_name='Produkty')
            
            output.seek(0)
            
            # Příprava bezpečného názvu souboru (bez diakritiky)
            safe_cat_name = remove_accents(selected_cat).replace(" ", "_")
            file_name = f"export_{safe_cat_name}.xlsx"
            
            dwn_col1, dwn_col2, dwn_col3 = st.columns([1, 1, 1])
            with dwn_col2:
                st.download_button(
                    label="📥 STÁHNOUT EXCEL (.xlsx)",
                    data=output,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()
