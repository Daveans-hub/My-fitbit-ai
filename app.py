import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. AI FUNCTION (Now with error reporting)
def ask_ai(ctx, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    # We only send a snippet of the data if it's too huge
    payload = {"contents": [{"parts": [{"text": f"You are a health scientist. Analyze this data: {str(ctx)[:10000]}. Question: {q}"}]}]}
    try:
        res = requests.post(url, json=payload, timeout=30)
        result = res.json()
        if "candidates" in result:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"AI Error: {result.get('error', {}).get('message', 'Safety block or Invalid Key')}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Lifetime Health AI", layout="wide")
st.title("📊 Lifetime Health Trend Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_ctx" not in st.session_state: st.session_state.health_ctx = None

# 4. LOGIN LOGIC
code = st.query_params.get("code")

if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.health_ctx = None
        st.session_state.ms = []
        st.rerun()

    # 5. DATA SYNC SECTION
    if not st.session_state.health_ctx:
        st.warning("Data not loaded. Click sync to pull 1-year history.")
        if st.button("🔄 Sync 1-Year History"):
            with st.spinner("Fetching 12 months of records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # We pull and simplify the data so the AI doesn't choke
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json()
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=h).json()
                    sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2020-01-01&limit=30&sort=desc", headers=h).json()
                    
                    # Extract just the useful bits to save space
                    simple_steps = [f"{day['dateTime']}: {day['value']} steps" for day in steps.get('activities-steps', [])]
                    simple_weight = [f"{w['date']}: {w['weight']}kg" for w in weight.get('weight', [])]
                    
                    st.session_state.health_ctx = f"WEIGHT HISTORY: {simple_weight} | STEP HISTORY: {simple_steps} | RECENT SLEEP: {sleep}"
                    st.success("Sync Complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")
    
    # 6. CHAT INTERFACE
    if st.session_state.health_ctx:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        if p := st.chat_input("Analyze my trends..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is studying your history..."):
                    ans = ask_ai(st.session_state.health_ctx, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

elif code:
    try:
        auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
    except: st.error("Login Error.")

else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")

# END OF CODE
