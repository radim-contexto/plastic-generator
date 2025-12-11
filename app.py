import streamlit as st
import requests
import pandas as pd
import time
import json

# === 1. NASTAVENÍ STRÁNKY ===
st.set_page_config(page_title="Plastic Planet AI", layout="wide")
st.title("🤖 Plastic Planet: Generátor (Direct API + Model Select)")

# === 2. SIDEBAR A NASTAVENÍ ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")
    
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    
    st.markdown("---")
    
    # VÝBĚR MODELU - TOTO JE TA ZÁCHRANA
    st.subheader("🧠 Vyber AI Model")
    selected_model = st.selectbox(
        "Pokud jeden hází chybu 404, zkus jiný:",
        [
            "gemini-1.5-flash",          # Rychlý, nový
            "gemini-1.5-flash-latest",   # Alternativní název
            "gemini-1.5-pro",            # Chytrý, pomalejší
            "gemini-pro",                # Starý, stabilní (funguje skoro vždy)
            "gemini-1.0-pro"             # Jiný název pro starý
        ]
    )
    
    st.markdown("---")

    # TLAČÍTKO TESTU
    if st.button("🛠 Otestovat vybraný model"):
        if not api_key:
            st.error("Chybí klíč!")
        else:
            try:
                # Testovací volání na VYBRANÝ model
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
                headers = {'Content-Type': 'application/json'}
                data = {"contents": [{"parts": [{"text": "Odpověz jen: FUNGUJU"}]}]}
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    ans = response.json()
                    try:
                        text = ans['candidates'][0]['content']['parts'][0]['text']
                        st.success(f"✅ {selected_model} funguje! Odpověď: {text}")
                    except:
                        st.warning("Odpověď přišla, ale má divný formát.")
                else:
                    st.error(f"❌ Chyba {response.status_code}: {response.text}")
            except Exception as e:
                st.error(f"❌ Chyba sítě: {e}")

# === 3. FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_list():
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
    params = {"fn": "products", "path": cat_path, "limit": 5000, "mode": "view"}
    try:
        r = requests.get(worker_url, params=params)
        r.encoding = 'utf-8'
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"Chyba Workeru: {e}")
        return []

def ask_ai_direct(product, api_key, model_name):
    """Volá Google API přímo s vybraným modelem"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    prompt = f"""
    Jsi expertní copywriter. Vytvoř 4 pole pro CSV (oddělovač středník ;).
    VSTUP: Produkt: {product.get('PRODUCT')}, Výrobce: {product.get('MANUFACTURER')}, Měřítko: {product.get('scale')}, Název: {product.get('modelClean')}
    VÝSTUP (jeden řádek): shortDescription;longDescription;metaTitle;metaDescription
    PRAVIDLA:
    1. shortDescription (HTML): 2-3 věty.
    2. longDescription (HTML): <h3>, <h4>. Dohledej fakta.
    3. metaTitle: Max 60 znaků.
    4. metaDescription: Max 160 znaků.
    Nepoužívej Markdown. Odstraň nové řádky.
    """

    payload = {
        "contents": [{ "parts": [{"text": prompt}] }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": { "temperature": 0.4 }
    }
    
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            result = response.json()
            try:
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
            except:
                return "CHYBA PARSINGU;CHYBA;CHYBA;CHYBA"
        else:
            # Vrátíme detail chyby do tabulky
            err_msg = f"HTTP {response.status_code}"
            try:
                err_json = response.json()
                err_msg += f": {err_json['error']['message']}"
            except:
                pass
            return f"{err_msg};CHYBA;CHYBA;CHYBA"
            
    except Exception as e:
        return f"CHYBA SÍTĚ: {str(e)};CHYBA;CHYBA;CHYBA"

# === 4. HLAVNÍ APLIKACE ===

with st.spinner("Načítám kategorie..."):
    all_cats = get_categories_list()

if not all_cats:
    selected_cat = st.text_input("Kategorie ručně", "Modely + | Letadla a vrtulníky | 1:72")
else:
    selected_cat = st.selectbox("📂 Vyber kategorii", all_cats)

if st.button("🚀 Vygenerovat", type="primary"):
    if not api_key:
        st.error("Chybí klíč!")
        st.stop()
        
    with st.status(f"Pracuji (Model: {selected_model})...", expanded=True) as status:
        st.write(f"Stahuji data: {selected_cat}...")
        products = get_all_products_in_category(selected_cat)
        
        if not products:
            status.update(label="Žádná data.", state="error")
            st.stop()
            
        total = len(products)
        st.write(f"Mám {total} produktů. Startuji...")
        
        my_bar = st.progress(0)
        results = []
        
        for i, p in enumerate(products):
            status.update(label=f"Generuji {i+1}/{total}: {p.get('PRODUCT')}")
            
            # VOLÁME FUNKCI S VYBRANÝM MODELEM
            csv_line = ask_ai_direct(p, api_key, selected_model)
            
            parts = csv_line.split(";")
            if len(parts) < 4: parts = [csv_line, "Chyba", "Chyba", "Chyba"]
            
            p["shortDescription"] = parts[0]
            p["longDescription"] = parts[1]
            p["metaTitle"] = parts[2]
            p["metaDescription"] = parts[3]
            results.append(p)
            
            my_bar.progress((i + 1) / total)
            time.sleep(0.1)
            
        status.update(label="Hotovo!", state="complete")
        
    df = pd.DataFrame(results)
    st.success(f"Hotovo {len(df)} ks.")
    st.dataframe(df[["PRODUCT", "shortDescription"]])
    csv = df.to_csv(sep=";", index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("Stáhnout CSV", csv, "export.csv", "text/csv")
