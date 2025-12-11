import streamlit as st
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd
import time

# === 1. NASTAVENÍ STRÁNKY ===
st.set_page_config(page_title="Plastic Planet AI", layout="wide")
st.title("🤖 Plastic Planet: Generátor (Full Category)")

# === 2. SIDEBAR A NASTAVENÍ ===
api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Nastavení")
    if not api_key:
        api_key = st.text_input("Vlož Gemini API Key", type="password")
    
    worker_url = st.text_input("Worker URL", value="https://plastic-planet.radim-81e.workers.dev/")
    
    st.markdown("---")
    # TLAČÍTKO TESTU SPOJENÍ JE ZPĚT!
    if st.button("🛠 Otestovat API Klíč"):
        if not api_key:
            st.error("Chybí klíč!")
        else:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                res = model.generate_content("Ahoj")
                st.success(f"✅ Spojení funguje! AI odpověděla: {res.text}")
            except Exception as e:
                st.error(f"❌ Chyba: {e}")

# === 3. FUNKCE ===

@st.cache_data(ttl=600)
def get_categories_list():
    """Stáhne všechny dostupné kategorie pro výběr"""
    try:
        # Ptáme se workeru na seznam kategorií
        r = requests.get(worker_url, params={"fn": "categories", "limit": 2000})
        r.encoding = 'utf-8'
        if r.status_code == 200:
            data = r.json()
            # Vytáhneme 'path' (což je unikátní ID kategorie)
            cats = [item["path"] for item in data.get("items", [])]
            return sorted(list(set(cats)))
        return []
    except:
