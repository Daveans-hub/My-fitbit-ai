import streamlit as st
import requests
import base64
import json

# --- CLOUD CONFIG ---
CLIENT_ID = st.secrets["FITBIT_CLIENT_ID"]
CLIENT_SECRET = st.secrets["FITBIT_CLIENT_SECRET"]
GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
REDIRECT_URI = st.secrets["YOUR_SITE_URL"] 

# --- BULLETPROOF AI FUNCTION (Direct Web Call) ---
def ask_gemini_direct(data_context, user_question):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    prompt = f"You are a professional health analyst. Based on this Fitbit data: {data_context}. User Question: {user_question}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        result = response.json()
        
        # Digging the answer out of the Google response structure
        if "candidates" in result:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"AI Error: {result.get('error', {}).get('message', 'Unknown Error')}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# --- PAGE SETUP ---
st.set_page_config(page_title="Fitbit AI Assistant", layout="wide")
st.title("🏃 My Personal Health AI")

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- AUTH LOGIC ---
code = st.query_params.get("code")

if not st.session_state.access_token and not code:
    scope = "activity%20heartrate%20profile%20sleep%20weight%20nutrition"
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}"
    st.info("Your AI is offline. Please connect your Fitbit.")
    st.markdown(f'### [🔗 Click here to Connect Fitbit]({auth_url})')

elif code and not st.session_state.access_token:
    try:
        token_url = "https://api.fitbit.com/oauth2/token"
        basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        headers = {"Authorization": f"Basic {basic_auth}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
        resp = requests.post(token_url, headers=headers,
