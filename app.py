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
import base64
import streamlit.components.v1 as components

# --- KONFIGURACE ---
st.set_page_config(page_title="Plastic Planet AI", layout="centered", page_icon="🧩")

# URL feedu a Model
FEED_URL = "https://www.plasticplanet.cz/universal.xml?hash=9tggSsPcMkaJHHLXcX07ZU"
MODEL_NAME = "models/gemini-2.5-pro"
BATCH_SIZE = 10       # Menší dávky pro AI, aby se uvolňovala paměť častěji
SAFETY_LIMIT = 50     # Ukládání po 50 kusech pro maximální stabilitu bez pádu

# --- CSS STYLING ---
st.markdown("""
    <style>
    :root { --primary-color: rgb(0, 232, 190) !important; }
    #MainMenu, footer, header {visibility: hidden;}
    h1 { text-align: center; font-family: 'Helvetica', sans-serif; font-weight: 800; color: #000; }
    .subtitle { text-align: center; color: #666; font-size: 14px; margin-bottom: 30px; }
    div.stButton > button {
        width: 100% !important; background-color: rgb(0, 232, 190) !important; color: #000 !important;
        font-weight: 800 !important; padding: 16px 24px !important; border-radius: 50px !important;
        border: none !important; box-shadow: 0 4px 15px rgba(0, 232, 190, 0.4);
    }
    .stProgress > div > div > div > div { background-color: rgb(0, 232, 190); }
    [data-testid="stSidebar"] button { background-color: #ff4b4b !important; border-color: #ff4b4b !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- FUNKCE ---

def remove_accents(input_str):
    if not isinstance(input_str, str): return str(input_str)
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def auto_download_excel(data_list, filename):
    """JavaScript hack pro automatické stažení s optimalizací paměti."""
    if not data_list: return
    
    try:
        # Vytvoření Excelu
        df = pd.DataFrame(data_list)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Produkty')
        
        # Okamžitý úklid DF
        del df
        gc.collect()
        
        val = output.getvalue()
        b64 = base64.b64encode(val).decode()
        
        # Okamžitý úklid bufferu
        output.close()
        del output
        del val
        gc.collect()

        # JS Download
        js_code = f"""
            <script>
            function download() {{
                var link = document.createElement('a');
                link.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}';
                link.download = '{filename}';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}
            setTimeout(download, 1000);
            </script>
        """
        components.html(js_code, height=0)
    except Exception as e:
        st.error(f"Chyba při přípravě souboru: {e}")

@st.cache_data(ttl=3600)
def load_data_from_xml(url):
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        products = []
        for item in root.findall(".//SHOPITEM"):
            def get_text(tag): return item.find(tag).text if item.find(tag) is not None else ""
            
            # Striktně jen tag CODE
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
            if prod["PRODUCT"] and prod["CATEGORYTEXT"]: products.append(prod)
        return products
    except Exception as e:
        st.error(f"Chyba feedu: {e}"); return []

def generate_descriptions(product, api_key):
    genai.configure(api_key=api_key)
    config = {"temperature": 0.4, "response_mime_type": "application/json"}
    for attempt in range(3):
        try:
            try: model = genai.GenerativeModel(MODEL_NAME, generation_config=config)
            except: model = genai.GenerativeModel("models/gemini-1.5-pro", generation_config=config)
            
            prompt = f"""
            ZADÁNÍ: Jsi copywriter pro e-shop Plasticplanet.cz.
            PRODUKT: {product.get("PRODUCT")} | {product.get("MANUFACTURER")} | {product.get("scale")}
            VÝSTUP (JSON): {{"shortDescription": "HTML (2-3 věty)", "longDescription": "HTML (strukturovaný text)", "metaTitle": "SEO Title", "metaDescription": "SEO Desc"}}
            JAZYK: Čeština.
            """
            result = model.generate_content(prompt)
            # Okamžité uvolnění paměti modelu
            del model
            return json.loads(result.text)
        except Exception as e:
            if attempt == 2: return {"shortDescription": f"Chyba: {e}", "longDescription": "", "metaTitle": "", "metaDescription": ""}
            time.sleep(2)

# --- MAIN ---

def main():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c: st.image("https://cdn.myshoptet.com/usr/www.plasticplanet.cz/user/logos/plasticplanet_new_rgb.png", use_container_width=True)
    st.markdown("<h1>Generátor popisků</h1>", unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Powered by Contexto Engine v2.0</div>', unsafe_allow_html=True)

    default_key = st.secrets.get("GOOGLE_API_KEY", "")
    api_key = st.text_input("Google API Key", value=default_key, type="password")
    if not api_key: st.warning("⚠️ Zadejte API klíč."); return

    # Sidebar záchrana - Manuální vytvoření Excelu
    with st.sidebar:
        st.markdown("### 🚑 Záchrana dat")
        if 'processed_data' in st.session_state and len(st.session_state['processed_data']) > 0:
            st.warning(f"V paměti je {len(st.session_state['processed_data'])} nezajištěných položek.")
            if st.button("Vytvořit záchranný soubor"):
                 df_rescue = pd.DataFrame(st.session_state['processed_data'])
                 out_rescue = io.BytesIO()
                 with pd.ExcelWriter(out_rescue, engine='openpyxl') as writer:
                     df_rescue.to_excel(writer, index=False)
                 st.download_button("💾 STÁHNOUT NYNÍ", out_rescue, "ZACHRANA_CRASH.xlsx")

    with st.spinner("⏳ Načítám feed..."): all_products = load_data_from_xml(FEED_URL)
    if not all_products: return

    df = pd.DataFrame(all_products)
    cats = df['CATEGORYTEXT'].value_counts().reset_index()
    cats.columns = ['Kategorie', 'Počet']
    cats = cats.sort_values(by="Kategorie")

    if 'processing_active' not in st.session_state: st.session_state['processing_active'] = False

    # 1. VÝBĚR
    if not st.session_state['processing_active']:
        st.markdown("### 📂 Vyberte kategorii")
        sel = st.dataframe(cats, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", height=350)
        
        if sel.selection.rows:
            idx = sel.selection.rows[0]
            cat_name = cats.iloc[idx]["Kategorie"]
            count = int(cats.iloc[idx]["Počet"])
            
            st.info(f"Vybráno: **{cat_name}** ({count} ks). Stabilní režim: automatické ukládání po {SAFETY_LIMIT} kusech.")
            
            c1, c2 = st.columns(2)
            start = c1.number_input("Začít od:", min_value=1, max_value=count, value=1, step=50)
            c2.write(""); c2.write("")
            if c2.button("🚀 SPUSTIT AUTOPILOTA"):
                st.session_state.update({
                    'processing_active': True, 'target_cat': cat_name, 'processed_data': [],
                    'current_offset': start - 1, 'total_count': count, 'part_number': 1
                })
                st.rerun()

    # 2. PROCES
    else:
        cat = st.session_state['target_cat']
        offset = st.session_state['current_offset']
        total = st.session_state['total_count']
        
        # --- KONTROLA LIMITU ---
        if len(st.session_state['processed_data']) >= SAFETY_LIMIT:
            st.success(f"📦 Část {st.session_state['part_number']} hotova. Automaticky stahuji a pokračuji...")
            
            safe_name = remove_accents(cat).replace(" ", "_")[:15]
            end_proc = offset
            start_proc = end_proc - len(st.session_state['processed_data']) + 1
            filename = f"export_{safe_name}_P{st.session_state['part_number']}_{start_proc}-{end_proc}.xlsx"
            
            # Automatické stažení
            auto_download_excel(st.session_state['processed_data'], filename)
            
            # Pauza na bezpečné stažení
            time.sleep(4) 
            
            # Vyčištění paměti
            st.session_state['processed_data'] = []
            st.session_state['part_number'] += 1
            gc.collect() # Vynucený úklid RAM
            st.rerun()

        # --- SMYČKA ---
        st.markdown(f"<h3 style='text-align: center'>{cat} (Část {st.session_state['part_number']})</h3>", unsafe_allow_html=True)
        st.progress(min(offset / total, 1.0))
        st.caption(f"Zpracováno {offset}/{total}")
        
        # Pojistka proti pádu - Try/Except okolo celé logiky
        try:
            cat_products = df[df['CATEGORYTEXT'] == cat]
            
            batch = cat_products.iloc[offset : offset + BATCH_SIZE].to_dict('records')
            
            if batch:
                status = st.empty()
                for i, item in enumerate(batch):
                    status.text(f"Generuji ({offset+i+1}/{total}): {item.get('PRODUCT')}")
                    ai_data = generate_descriptions(item, api_key)
                    final = {**item, **ai_data}
                    
                    clean = {
                        "kód": final.get("CODE"), "PRODUCT": final.get("PRODUCT"),
                        "MANUFACTURER": final.get("MANUFACTURER"), "modelClean": final.get("modelClean"),
                        "scale": final.get("scale"), "PRICE_VAT": final.get("PRICE_VAT"),
                        "URL": final.get("URL"), "EAN": final.get("EAN"),
                        "CATEGORYTEXT": final.get("CATEGORYTEXT"), "shortDescription": final.get("shortDescription"),
                        "longDescription": final.get("longDescription"), "metaTitle": final.get("metaTitle"),
                        "metaDescription": final.get("metaDescription")
                    }
                    st.session_state['processed_data'].append(clean)
                    
                    del ai_data
                    del final
                    del clean
                    
                st.session_state['current_offset'] += BATCH_SIZE
                gc.collect() # Úklid po každé malé dávce
                
                if st.session_state['current_offset'] < total:
                    st.rerun()
                else:
                    # KONEC
                    st.success("✅ HOTOVO! Stahuji zbytek...")
                    if st.session_state['processed_data']:
                        safe_name = remove_accents(cat).replace(" ", "_")[:15]
                        filename = f"export_{safe_name}_FINAL.xlsx"
                        auto_download_excel(st.session_state['processed_data'], filename)
                        time.sleep(4)
                    
                    if st.button("Zpracovat jinou kategorii"):
                        st.session_state['processing_active'] = False
                        st.rerun()
            else:
                st.session_state['processing_active'] = False
                st.rerun()
                
        except Exception as e:
            st.error(f"⚠️ Došlo k chybě: {e}")
            st.warning("Aplikace narazila na limit. Použijte tlačítko ZÁCHRANA DAT vlevo.")
            st.stop()

if __name__ == "__main__":
    main()
