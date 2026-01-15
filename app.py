import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE AI FUNCTION
def ask_ai_dynamic(data_summary, user_query):
    try:
        model_list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
        model_data = requests.get(model_list_url).json()
        available = [m["name"] for m in model_data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        if not available: return "AI Error: Key has no model access."
        selected_model = next((m for m in available if "1.5-flash" in m), available[0])
        
        gen_url = f"https://generativelanguage.googleapis.com/v1/{selected_model}:generateContent?key={GKEY}"
        prompt = f"You are a professional health analyst. Analyze this 1-year Fitbit summary: {data_summary}. User Question: {user_query}."
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(gen_url, json=payload, timeout=30)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_data" not in st.session_state: st.session_state.health_data = None

# 4. LOGIN LOGIC
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        auth_b64 = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/
