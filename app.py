import streamlit as st
import requests
import base64
import json

# --- SETTINGS ---
C_ID = st.secrets["FITBIT_CLIENT_ID"]
C_SEC = st.secrets["FITBIT_CLIENT_SECRET"]
G_KEY = st.secrets["GEMINI_API_KEY"]
R_URI = st.secrets["YOUR_SITE_URL"] 

# --- AI FUNCTION ---
def ask_gemini(context, question):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={G_KEY}"
    prompt = f"You are a health AI. Context: {context}. Question: {question}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        out = res.json()
        return out["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "AI is having trouble thinking. Check your Gemini API Key."

# --- PAGE SETUP ---
st.set_page_config(page_title="Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "token" not in st.session_state: st.session_state.token = None
if "msgs" not in st.session_state: st.session_state.msgs = []

# --- LOGIN ---
code = st.query_params.get("code")

if not st.session_state.token and not code:
    url = f"https://www.fitb
