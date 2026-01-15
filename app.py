import streamlit as st
import requests
import base64
import json
from datetime import datetime

# 1. SECRETS LOADING
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. BULLETPROOF AI FUNCTION
# Uses the v1beta endpoint which is the most reliable for AI Studio keys
def ask_ai(data_summary, user_query):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    
    # System prompt tells the AI how to behave
    prompt = f"""
    You are a professional health data analyst. 
    Analyze this Fitbit data summary (Most recent dates first):
    {data_summary}
    
    User Question: {user_query}
    
    Note: Fitbit does not provide Menstrual Cycle data to 3rd party apps yet. 
    If the user asks about it, explain this limitation but analyze their Heart Rate/Sleep for correlations.
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, json=payload, timeout=30)
        res_json = res.json()
        if "candidates" in res_json:
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Snag: {res_json.get('error', {}).get('message', 'Safety block or capacity limit.')}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_ctx" not in st.session_state: st.session_state.health_ctx = None

# 4. AUTHENTICATION LOGIC
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        auth_b64 = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": qp["code"], "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
    except: st.error("Login failed. Please clear your URL and try again.")

# 5. THE MAIN APP (Logged In)
if st.session_state.tk:
    st.sidebar.success("✅ Health Data Linked")
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.health_ctx, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # DATA SYNC SECTION
    if not st.session_state.health_ctx:
        st.info("Your data is not yet synced.")
        if st.button("🔄 Sync Everything (Weight, Fat, Sleep, Heart, Steps)"):
            with st.spinner("Processing 12 months of records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Fetching 1-year trends for all categories
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    c = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])
                    
                    # COMPACTING DATA (Converting messy JSON into a clean summary)
                    # We reverse them so the newest data is always at the top
                    w.reverse(); f.reverse(); s.reverse(); c.reverse()
                    
                    summary = f"""
                    LATEST WEIGHT: {w[:10]}
                    LATEST FAT %: {f[:10]}
                    LATEST STEPS: {s[:14]}
                    LATEST CALORIES BURNED: {c[:14]}
                    LATEST SLEEP SESSIONS: {[{"date": i['dateOfSleep'], "hrs": round(i['minutesAsleep']/60, 1)} for i in sl[:10]]}
                    """
                    st.session_state.health_ctx = summary
                    st.success("Sync Complete! All metrics loaded.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # CHAT UI
    if st.session_state.health_ctx:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Ask about any trend..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is analyzing..."):
                    ans = ask_ai(st.session_state.health_ctx, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

# 6. LOGIN SCREEN
else:
    # Scope includes everything Fitbit allows
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")

# --- END OF CODE ---
