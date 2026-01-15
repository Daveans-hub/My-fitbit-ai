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
def ask_ai(txt, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {"contents": [{"parts": [{"text": f"You are a health AI. Data: {txt}. Question: {q}"}]}]}
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIN LOGIC
# Grab the 'code' from the URL
qp = st.query_params
code = qp.get("code")

# Scenario A: Not logged in, no code -> Show Login Link
if not st.session_state.tk and not code:
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")

# Scenario B: We have a code and aren't logged in yet -> Exchange it
elif code and not st.session_state.tk:
    try:
        auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI})
        
        data = r.json()
        if "access_token" in data:
            st.session_state.tk = data["access_token"]
            st.query_params.clear() # Clear the code from the URL
            st.rerun()
        else:
            # Show the ACTUAL error from Fitbit so we can fix it
            st.error(f"Fitbit Login Error: {data.get('errors', 'Unknown error')}")
    except Exception as e:
        st.error(f"Connection Error: {e}")

# 5. MAIN APP (If logged in)
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout / Start Fresh"):
        st.session_state.tk = None
        st.session_state.ms = []
        st.query_params.clear()
        st.rerun()

    hdr = {"Authorization": f"Bearer {st.session_state.tk}"}
    try:
        # Get Sleep (Last 5 logs) and Steps (Last 7 days)
        slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=5", headers=hdr).json()
        stp = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=hdr).json()
        ctx = f"Sleep Data: {slp}, Step Data: {stp}"
    except: ctx = "Vitals syncing..."

    # Chat UI
    for m in st.session_state.ms:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Ask me something about your health..."):
        st.session_state.ms.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            with st.spinner("AI is analyzing..."):
                ans = ask_ai(ctx, p)
                st.markdown(ans)
                st.session_state.ms.append({"role": "assistant", "content": ans})
