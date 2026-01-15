import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. AI FUNCTION (The "Brain")
def ask_ai(ctx, q):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {
        "contents": [{"parts": [{"text": f"You are a health scientist. Analyze this 1-year Fitbit data: {str(ctx)[:15000]}. Question: {q}"}]}],
        "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return "AI is busy. Please try asking again in a moment."

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. THE AUTHENTICATION ENGINE (Code-Burner Version)
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        code = qp["code"]
        auth_b64 = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI}).json()
        
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear() # Wipes the URL to prevent "Connection issue"
            st.rerun()
        else:
            st.error(f"Fitbit Error: {r.get('errors')}")
            st.info("Try clicking the browser address bar and hitting Enter to clear everything.")
    except: st.error("Authentication failed. Please start fresh.")

# 5. THE MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Health Data Link Active")
    if st.sidebar.button("Logout / Clear All"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # DATA SYNC (The "Everything" Pull)
    if not st.session_state.data:
        if st.button("🔄 Sync Lifetime History (Weight, Fat, Steps, Sleep, Calories)"):
            with st.spinner("Processing 12 months of records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # 1 Year of Weight, Fat, Steps, Calories
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    c = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    # Last 50 sleep logs
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=50&sort=desc", headers=h).json().get('sleep', [])
                    
                    # Package for AI
                    st.session_state.data = {
                        "WEIGHT_HISTORY_1YR": w[-50:], # Last 50 weigh-ins
                        "FAT_PERCENT_1YR": f[-50:],
                        "STEPS_1YR": s[-100:], # Significant samples
                        "CALORIES_BURNED_1YR": c[-50:],
                        "SLEEP_SUMMARY": [{"date": i['dateOfSleep'], "hrs": round(i['minutesAsleep']/60, 1)} for i in sl]
                    }
                    st.success("Sync Complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # CHAT
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("Ask me about any trend..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing lifetime trends..."):
                    ans = ask_ai(st.session_state.data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

# 6. LOGIN SCREEN
else:
    # SCOPE includes activity, weight, nutrition, heartrate, sleep
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit for Full Analysis]({url})")

# END OF CODE
