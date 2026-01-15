import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. THE AI FUNCTION
def ask_ai(ctx, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {"contents": [{"parts": [{"text": f"You are a health scientist. Analyze this data: {ctx}. Question: {q}"}]}]}
    try:
        res = requests.post(url, json=payload, timeout=30)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Lifetime Health AI", layout="wide")
st.title("📊 Lifetime Health Trend Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. LOGIN LOGIC
code = st.query_params.get("code")

if st.session_state.tk:
    # --- SCREEN 2: LOGGED IN ---
    st.sidebar.success("✅ Connected to Fitbit")
    
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.data = None
        st.session_state.ms = []
        st.rerun()

    # DATA SYNC BUTTON (Prevents timeouts)
    if not st.session_state.data:
        st.warning("Data not synced yet.")
        if st.button("🔄 Sync 1-Year History (Steps, Weight, Sleep, Heart)"):
            with st.spinner("Fetching 12 months of records... this takes about 10 seconds."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pulling the heavy stuff
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json()
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=h).json()
                    sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2020-01-01&limit=50&sort=desc", headers=h).json()
                    heart = requests.get("https://api.fitbit.com/1/user/-/activities/heart/date/today/7d.json", headers=h).json()
                    
                    st.session_state.data = f"Steps_Year: {steps}, Weight_Year: {weight}, Sleep_Logs: {sleep}, Heart_Recent: {heart}"
                    st.success("Sync Complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")
    
    # CHAT INTERFACE
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        if p := st.chat_input("Analyze my trends..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is studying your history..."):
                    ans = ask_ai(st.session_state.data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

elif code:
    # --- SCREEN 3: PROCESSING LOGIN ---
    try:
        auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI})
        
        res_data = r.json()
        if "access_token" in res_data:
            st.session_state.tk = res_data["access_token"]
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Fitbit Login Error: {res_data}")
            st.info("Try deleting the stuff at the end of the URL and starting fresh.")
    except Exception as e:
        st.error(f"Connection Error: {e}")

else:
    # --- SCREEN 1: LOGIN LINK ---
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")
    st.info("Note: When logged in, you will need to click 'Sync' to load your history.")

# END OF CODE
