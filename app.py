import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import xml.etree.ElementTree as ET
import time
import json
import io
import unicodedata
import gc # Garbage collector pro čištění paměti

# --- KONFIGURACE ---
st.set_page_config(page_title="Plastic Planet AI", layout="centered", page_icon="🧩")

# URL feedu a Model
FEED_URL = "https://raw.githubusercontent.com/radim-contexto/xmlfeed/refs/heads/main/universal.xml"
MODEL_NAME = "models/gemini-2.5-pro"
BATCH_SIZE = 50  # Pevná velikost dávky (neměnit, 50 je ideál pro stabilitu)

# --- CSS STYLING ---
st.markdown("""
    <style>
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
    
    /* Progress bar - Tyrkysová */
    .stProgress > div > div > div > div {
        background-color: rgb(0, 232, 190);
    }
    
    div[data-testid="stDataFrame"] {
        border: 1px solid #eee;
        border-radius: 10px;
        overflow: hidden;
    }
    
    .stTextInput input {
        text-align: center;
    }

    /* Červené tlačítko v sidebaru pro záchranu */
    [data-testid="stSidebar"] button {
        background-color: #ff4b4b !important;
        color: white !important;
        border: 1px solid #ff4b4b !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- POMOCNÉ FUNKCE ---

def remove_accents(input_str):
    if not isinstance(input_str, str):
        return str(input_str)
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def create_excel_bytes(data_list):
    """Vytvoří Excel soubor v paměti."""
    if not data_list:
        return None
    df = pd.DataFrame(data_list)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Produkty')
    output.seek(0)
    return output

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
            
            prod = {
                "CODE": get_text("CODE"),
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
    """Generování s Retry logikou (3 pokusy)."""
    genai.configure(api_key=api_key)
    config = {"temperature": 0.4, "response_mime_type": "application/json"}
    
    max_retries = 3
    for attempt in range(max_retries):
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
            if attempt == max_retries - 1: # Poslední pokus selhal
                return {
                    "shortDescription": f"<p>Chyba AI: {str(e)}</p>",
                    "longDescription": "",
                    "metaTitle": product.get("PRODUCT", ""),
                    "metaDescription": ""
                }
            time.sleep(2) # Počkat před dalším pokusem

# --- MAIN UI ---

def main():
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

    # --- SIDEBAR: ZÁCHRANNÝ SYSTÉM ---
    with st.sidebar:
        st.markdown("### 🚑 Záchrana dat")
        st.info("Pokud se generování zasekne, zde si můžete stáhnout to, co už je hotové.")
        
        if 'processed_data' in st.session_state and len(st.session_state['processed_data']) > 0:
            st.markdown(f"**Hotovo:** {len(st.session_state['processed_data'])} položek")
            
            excel_data = create_excel_bytes(st.session_state['processed_data'])
            if excel_data:
                # Název souboru
                cat_name = st.session_state.get('target_cat', 'neznamo')
                safe_name = remove_accents(cat_name).replace(" ", "_")[:20]
                
                st.download_button(
                    label="💾 STÁHNOUT ČÁSTEČNÝ EXCEL",
                    data=excel_data,
                    file_name=f"ZACHRANA_{safe_name}_{len(st.session_state['processed_data'])}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="sidebar_download"
                )
        else:
            st.markdown("*(Zatím prázdno)*")

    # NAČTENÍ DAT
    with st.spinner("⏳ Načítám feed..."):
        all_products = load_data_from_xml(FEED_URL)

    if not all_products:
        return

    df = pd.DataFrame(all_products)
    categories_df = df['CATEGORYTEXT'].value_counts().reset_index()
    categories_df.columns = ['Kategorie', 'Počet produktů']
    categories_df = categories_df.sort_values(by="Kategorie")

    # Inicializace session state
    if 'processing_active' not in st.session_state:
        st.session_state['processing_active'] = False

    # --- 1. VÝBĚR KATEGORIE (Pokud neběží proces) ---
    if not st.session_state['processing_active']:
        st.markdown("### 📂 Vyberte kategorii")
        selection = st.dataframe(
            categories_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            height=350
        )
        
        if selection.selection.rows:
            idx = selection.selection.rows[0]
            selected_cat = categories_df.iloc[idx]["Kategorie"]
            total_count = int(categories_df.iloc[idx]["Počet produktů"])
            
            st.markdown("---")
            st.markdown(f"<h3 style='text-align: center'>Vybráno: {selected_cat}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; color: #666'>Celkem produktů: <b>{total_count}</b></p>", unsafe_allow_html=True)
            st.info(f"ℹ️ Automatický režim: Produkty budou zpracovány po dávkách {BATCH_SIZE} ks.")

            st.markdown("<br>", unsafe_allow_html=True)
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
            with btn_col2:
                if st.button("🚀 SPUSTIT AUTOMAT"):
                    st.session_state['processing_active'] = True
                    st.session_state['target_cat'] = selected_cat
                    st.session_state['processed_data'] = []
                    st.session_state['current_offset'] = 0
                    st.session_state['total_count'] = total_count
                    st.rerun()

    # --- 2. AUTOMATICKÉ ZPRACOVÁNÍ ---
    else:
        cat = st.session_state['target_cat']
        offset = st.session_state['current_offset']
        total = st.session_state['total_count']
        
        st.markdown(f"<h3 style='text-align: center'>Zpracovávám: {cat}</h3>", unsafe_allow_html=True)
        
        # Progress bar
        prog_val = min(len(st.session_state['processed_data']) / total, 1.0)
        st.progress(prog_val)
        st.markdown(f"<p style='text-align: center'>Hotovo: <b>{len(st.session_state['processed_data'])}</b> / {total}</p>", unsafe_allow_html=True)
        
        # Příprava dávky
        cat_products = df[df['CATEGORYTEXT'] == cat]
        batch = cat_products.iloc[offset : offset + BATCH_SIZE].to_dict('records')
        
        if batch:
            status_text = st.empty()
            
            for i, item in enumerate(batch):
                status_text.text(f"🤖 AI pracuje ({offset + i + 1}/{total}): {item.get('PRODUCT')}")
                
                ai_data = generate_descriptions(item, api_key)
                final_row = {**item, **ai_data}
                
                # Ukládáme výsledky
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
                st.session_state['processed_data'].append(clean_row)
                time.sleep(0.05) 
            
            # Úklid paměti
            gc.collect()
            
            # Posun na další dávku
            st.session_state['current_offset'] += BATCH_SIZE
            
            # Pokud není konec -> RERUN
            if st.session_state['current_offset'] < total:
                time.sleep(0.5)
                st.rerun()
            else:
                # KONEC
                st.success("✅ Kompletně hotovo!")
                
                excel_data = create_excel_bytes(st.session_state['processed_data'])
                safe_name = remove_accents(cat).replace(" ", "_")[:30]
                
                dwn_col1, dwn_col2, dwn_col3 = st.columns([1, 1, 1])
                with dwn_col2:
                    st.download_button(
                        label="📥 STÁHNOUT FINÁLNÍ EXCEL",
                        data=excel_data,
                        file_name=f"export_{safe_name}_FULL.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                if st.button("Zpracovat jinou kategorii"):
                    st.session_state['processing_active'] = False
                    st.session_state['processed_data'] = []
                    st.rerun()
        else:
            # Fallback kdyby offset přeskočil
            st.session_state['processing_active'] = False
            st.rerun()

if __name__ == "__main__":
    main()
