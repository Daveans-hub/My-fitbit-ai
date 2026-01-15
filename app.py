import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. UNIVERSAL AI FUNCTION
def ask_ai(txt, q):
    # Using v1beta and gemini-pro which is the most stable combination for AI Studio keys
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GKEY}"
    
    context_snippet = str(txt)[:3000]
    payload = {
        "contents": [{
            "parts": [{"text": f"Context: {context_snippet}\n\nQuestion: {q}"}]
        }]
    }
    
    try:
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in data:
            return f"Google Error: {data['error']['message']}"
        else:
            return "AI failed to respond. Try again."
    except Exception as e:
        return f"System Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIN LOGIC
code = st.query_params.get("code")

if not st.session_state.tk and not code:
    # Removed a stray slash here that might have been causing Fitbit issues
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
        slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=3", headers=hdr).json()
        stp = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=hdr).json()
        ctx = f"Sleep: {slp}, Steps: {stp}"
    except: ctx = "Syncing data..."

    for m in st.session_state.ms:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Ask about your trends..."):
        st.session_state.ms.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            with st.spinner("AI is analyzing..."):
                ans = ask_ai(ctx, p)
                st.markdown(ans)
                st.session_state.ms.append({"role": "assistant", "content": ans})
