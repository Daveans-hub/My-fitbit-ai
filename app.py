import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. AI FUNCTION
def ask_ai(ctx, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {
        "contents": [{"parts": [{"text": f"You are a health analyst. Context: {ctx}. Question: {q}"}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    try:
        r = requests.post(url, json=payload, timeout=25)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "AI Error. Check your Gemini Key or safety filters."

# 3. PAGE SETUP
st.set_page_config(page_title="Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. LOGIC ENGINE
# Grab the code from the URL
code = st.query_params.get("code")

# Case A: Already connected (Ignore everything else)
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    if not st.session_state.data:
        if st.button("🔄 Sync My Health Data"):
            with st.spinner("Fetching Weight, Fat, Steps, and Sleep..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                # Fetching Time Series Data
                w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/30d.json", headers=h).json()
                f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/30d.json", headers=h).json()
                s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/30d.json", headers=h).json()
                sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=10&sort=desc", headers=h).json()

                st.session_state.data = {
                    "weight": w.get('body-weight', []),
                    "fat_percent": f.get('body-fat', []),
                    "steps": s.get('activities-steps', []),
                    "sleep": [{"date": i['dateOfSleep'], "hrs": round(i['minutesAsleep']/60, 1)} for i in sl.get('sleep', [])]
                }
                st.success("Synced!")
                st.rerun()

    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("Ask about your trends..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                ans = ask_ai(st.session_state.data, p)
                st.markdown(ans)
                st.session_state.ms.append({"role": "assistant", "content": ans})

# Case B: Just returned from Fitbit with a fresh code
elif code and not st.session_state.tk:
    try:
        auth_b = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Login Error: {r.get('errors')}")
    except:
        st.error("Connection issue. Please start over.")

# Case C: Not logged in
else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# END OF CODE
