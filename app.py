import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import xml.etree.ElementTree as ET
import time
import json
import io
import unicodedata
import gc 

# --- KONFIGURACE ---
st.set_page_config(page_title="Plastic Planet AI", layout="centered", page_icon="🧩")

# URL feedu a Model
FEED_URL = "https://raw.githubusercontent.com/radim-contexto/xmlfeed/refs/heads/main/universal.xml"
MODEL_NAME = "models/gemini-2.5-pro"
BATCH_SIZE = 50       # Velikost jedné malé dávky pro AI
SAFETY_LIMIT = 200    # Po kolika kusech se má systém zastavit a donutit uložit data

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
    
    .stProgress > div > div > div > div {
        background-color: rgb(0, 232, 190);
    }
    
    div[data-testid="stDataFrame"] {
        border: 1px solid #eee;
        border-radius: 10px;
        overflow: hidden;
    }
    
    .stTextInput input, .stNumberInput input {
        text-align: center;
    }
    
    /* Styl pro záchranné tlačítko v sidebaru */
    [data-testid="stSidebar"] button {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: white !important;
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
            ZADÁNÍ: Jsi copywriter pro e-shop Plasticplanet.cz.
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
            if attempt == max_retries - 1:
                return {
                    "shortDescription": f"<p>Chyba AI: {str(e)}</p>",
                    "longDescription": "",
                    "metaTitle": product.get("PRODUCT", ""),
                    "metaDescription": ""
                }
            time.sleep(2)

# --- MAIN UI ---

def main():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.image("https://cdn.myshoptet.com/usr/www.plasticplanet.cz/user/logos/plasticplanet_new_rgb.png", use_container_width=True)
    
    st.markdown("<h1>Generátor popisků</h1>", unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Powered by Contexto Engine v2.0</div>', unsafe_allow_html=True)

    default_key = st.secrets.get("GOOGLE_API_KEY", "")
    api_key = st.text_input("Vložte Google API Key", value=default_key, type="password")

    if not api_key:
        st.warning("⚠️ Zadejte API klíč.")
        return

    # ZÁCHRANA DAT V SIDEBARU
    with st.sidebar:
        st.markdown("### 🚑 Záchrana dat")
        if 'processed_data' in st.session_state and len(st.session_state['processed_data']) > 0:
            st.info(f"V paměti je {len(st.session_state['processed_data'])} nezajištěných položek.")
            excel_data = create_excel_bytes(st.session_state['processed_data'])
            if excel_data:
                st.download_button(
                    label="💾 STÁHNOUT NYNÍ",
                    data=excel_data,
                    file_name="ZACHRANA_EMERGENCY.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="emergency_btn"
                )

    with st.spinner("⏳ Načítám feed..."):
        all_products = load_data_from_xml(FEED_URL)

    if not all_products:
        return

    df = pd.DataFrame(all_products)
    categories_df = df['CATEGORYTEXT'].value_counts().reset_index()
    categories_df.columns = ['Kategorie', 'Počet produktů']
    categories_df = categories_df.sort_values(by="Kategorie")

    if 'processing_active' not in st.session_state:
        st.session_state['processing_active'] = False

    # 1. VÝBĚR KATEGORIE
    if not st.session_state['processing_active']:
        st.markdown("### 📂 Vyberte kategorii")
        selection = st.dataframe(categories_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", height=350)
        
        if selection.selection.rows:
            idx = selection.selection.rows[0]
            selected_cat = categories_df.iloc[idx]["Kategorie"]
            total_count = int(categories_df.iloc[idx]["Počet produktů"])
            
            st.markdown("---")
            st.markdown(f"<h3 style='text-align: center'>Vybráno: {selected_cat}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; color: #666'>Celkem: {total_count} položek</p>", unsafe_allow_html=True)
            
            st.info(f"🛡️ BEZPEČNÝ REŽIM: Data se ukládají po částech ({SAFETY_LIMIT} ks).")

            # --- NOVINKA: MOŽNOST RUČNÍHO STARTU ---
            st.markdown("<br>", unsafe_allow_html=True)
            col_inp, col_btn = st.columns([1, 1])
            with col_inp:
                # Uživatel může zadat, kde začít (default = 1)
                start_from = st.number_input("Začít od produktu číslo:", min_value=1, max_value=total_count, value=1, step=50)
            
            with col_btn:
                # Zarovnání tlačítka dolů k inputu
                st.write("") 
                st.write("")
                if st.button("🚀 SPUSTIT GENEROVÁNÍ"):
                    st.session_state['processing_active'] = True
                    st.session_state['target_cat'] = selected_cat
                    st.session_state['processed_data'] = []
                    # Nastavíme startovní offset (uživatel vidí 1, python počítá od 0)
                    st.session_state['current_offset'] = start_from - 1 
                    st.session_state['total_count'] = total_count
                    st.session_state['part_number'] = 1 
                    st.rerun()

    # 2. PROCES GENEROVÁNÍ
    else:
        cat = st.session_state['target_cat']
        offset = st.session_state['current_offset']
        total = st.session_state['total_count']
        
        # KONTROLA BEZPEČNOSTNÍHO LIMITU (MEZISKLAD)
        if len(st.session_state['processed_data']) >= SAFETY_LIMIT:
            st.success(f"✅ **Část {st.session_state['part_number']} hotova!** ({len(st.session_state['processed_data'])} položek)")
            st.warning("🛑 **Pauza:** Stáhněte data, paměť se musí vyčistit.")
            
            excel_data = create_excel_bytes(st.session_state['processed_data'])
            safe_name = remove_accents(cat).replace(" ", "_")[:20]
            # Do názvu souboru dáme i rozsah (odkud kam)
            end_processed = offset
            start_processed = end_processed - len(st.session_state['processed_data']) + 1
            file_name = f"export_{safe_name}_OD_{start_processed}_DO_{end_processed}.xlsx"
            
            dwn_c1, dwn_c2, dwn_c3 = st.columns([1, 1, 1])
            with dwn_c2:
                st.download_button(
                    label=f"📥 STÁHNOUT ČÁST {st.session_state['part_number']}",
                    data=excel_data,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            st.markdown("---")
            st.markdown(f"Zbývá: **{total - offset}** položek.")
            
            cont_c1, cont_c2, cont_c3 = st.columns([1, 1, 1])
            with cont_c2:
                if st.button("➡️ POKRAČOVAT"):
                    st.session_state['processed_data'] = [] 
                    st.session_state['part_number'] += 1    
                    gc.collect()                            
                    st.rerun()
            st.stop()

        # --- SMYČKA ---
        st.markdown(f"<h3 style='text-align: center'>{cat}</h3>", unsafe_allow_html=True)
        st.caption(f"Zpracovávám položku {offset + 1} až {min(offset + BATCH_SIZE, total)} z {total}")
        
        prog_val = min(offset / total, 1.0)
        st.progress(prog_val)
        
        cat_products = df[df['CATEGORYTEXT'] == cat]
        batch = cat_products.iloc[offset : offset + BATCH_SIZE].to_dict('records')
        
        if batch:
            status_text = st.empty()
            
            for i, item in enumerate(batch):
                real_index = offset + i + 1
                status_text.text(f"Zpracovávám ({real_index}/{total}): {item.get('PRODUCT')}")
                
                ai_data = generate_descriptions(item, api_key)
                final_row = {**item, **ai_data}
                
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
            
            st.session_state['current_offset'] += BATCH_SIZE
            
            if st.session_state['current_offset'] < total:
                time.sleep(0.5)
                st.rerun()
            else:
                st.success("🎉 HOTOVO!")
                
                if len(st.session_state['processed_data']) > 0:
                    excel_data = create_excel_bytes(st.session_state['processed_data'])
                    safe_name = remove_accents(cat).replace(" ", "_")[:20]
                    # Dynamický název souboru podle toho, kde jsme skončili
                    start_processed = offset - len(st.session_state['processed_data']) + 1
                    file_name = f"export_{safe_name}_OD_{start_processed}_DO_KONCE.xlsx"
                    
                    dwn_c1, dwn_c2, dwn_c3 = st.columns([1, 1, 1])
                    with dwn_c2:
                        st.download_button(
                            label="📥 STÁHNOUT ZBYTEK",
                            data=excel_data,
                            file_name=file_name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                
                if st.button("Zpracovat jinou kategorii"):
                    st.session_state['processing_active'] = False
                    st.session_state['processed_data'] = []
                    st.rerun()
        else:
            st.session_state['processing_active'] = False
            st.rerun()

if __name__ == "__main__":
    main()
