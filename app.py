import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. IMPROVED AI FUNCTION
def ask_ai(txt, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    # We shorten the data to make sure we don't overwhelm the AI
    short_txt = str(txt)[:5000] 
    payload = {"contents": [{"parts": [{"text": f"You are a health AI. Data: {short_txt}. Question: {q}"}]}]}
    
    try:
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        
        if "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in data:
            return f"Google API Error: {data['error']['message']}"
        else:
            return f"Unexpected AI Response: {data}"
    except Exception as e:
        return f"AI Connection Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIN LOGIC
code = st.query_params.get("code")

if not st.session_state.tk and not code:
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")

elif code and not st.session_state.tk:
    try:
        auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI})
        
        resp_data = r.json()
        if "access_token" in resp_data:
            st.session_state.tk = resp_data["access_token"]
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Fitbit Login Error: {resp_data}")
    except Exception as e:
        st.error(f"Login Connection Error: {e}")

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.ms = []
        st.rerun()

    hdr = {"Authorization": f"Bearer {st.session_state.tk}"}
    try:
        # Pull only essential data to keep the AI focused
        slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=3", headers=hdr).json()
        stp = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=hdr).json()
        ctx = f"SleepLogs: {slp}, StepsLast7Days: {stp}"
    except: ctx = "Vitals syncing..."

    for m in st.session_state.ms:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Ask about your trends..."):
        st.session_state.ms.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                ans = ask_ai(ctx, p)
                st.markdown(ans)
                st.session_state.ms.append({"role": "assistant", "content": ans})
