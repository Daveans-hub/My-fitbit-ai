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
    payload = {"contents": [{"parts": [{"text": f"You are a health scientist. Analyze this data: {str(ctx)[:10000]}. Question: {q}"}]}]}
    try:
        res = requests.post(url, json=payload, timeout=30)
        result = res.json()
        if "candidates" in result:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Error: {result}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Lifetime Health AI", layout="wide")
st.title("🏃 Lifetime Health Trend Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_ctx" not in st.session_state: st.session_state.health_ctx = None

# 4. LOGIN LOGIC
# We look for 'code' in the URL parameters
code = st.query_params.get("code")

# Case A: Already have a token in memory
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.health_ctx = None
        st.session_state.ms = []
        st.query_params.clear()
        st.rerun()

    # Data Sync
    if not st.session_state.health_ctx:
        if st.button("🔄 Sync 1-Year History"):
            with st.spinner("Fetching records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json()
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=h).json()
                    st.session_state.health_ctx = f"Steps: {steps}, Weight: {weight}"
                    st.success("Sync Complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")
    
    # Chat
    if st.session_state.health_ctx:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("Ask about your trends..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                ans = ask_ai(st.session_state.health_ctx, p)
                st.markdown(ans)
                st.session_state.ms.append({"role": "assistant", "content": ans})

# Case B: We just got a code from Fitbit
elif code:
    try:
        # Trade code for token
        auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI})
        
        token_data = r.json()
        
        if "access_token" in token_data:
            st.session_state.tk = token_data["access_token"]
            st.query_params.clear()
            st.rerun()
        else:
            # THIS WILL TELL US THE REAL ERROR
            st.error("Fitbit Login Failed")
            st.json(token_data)
            st.info("Check if your Redirect URI in Fitbit Dev Portal matches YOUR_SITE_URL in Secrets exactly.")
    except Exception as e:
        st.error(f"System Error: {e}")

# Case C: Not logged in
else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")

# END OF CODE
