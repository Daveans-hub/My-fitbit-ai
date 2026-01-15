import streamlit as st
import requests
import base64
import json

# 1. SETUP SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. STABLE AI FUNCTION (Direct v1 Call)
def ask_ai(ctx, q):
    # We use the 'v1' stable endpoint to avoid the 404 error
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {
        "contents": [{"parts": [{"text": f"You are a health analyst. Analyze this Fitbit data summary: {ctx}. User Question: {q}"}]}]
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        resp = r.json()
        if "candidates" in resp:
            return resp["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Error: {resp.get('error', {}).get('message', 'Unexpected response format')}"
    except Exception as e:
        return f"Connection Error: {e}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. LOGIN LOGIC
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
    except: st.error("Login failed. Refresh and try again.")

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # SYNC 1-YEAR DATA
    if not st.session_state.data:
        if st.button("🔄 Sync Lifetime History (12 Months)"):
            with st.spinner("Analyzing 12 months of health records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Fetching
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=h).json().get('weight', [])
                    sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2020-01-01&limit=50&sort=desc", headers=h).json().get('sleep', [])
                    
                    # DATA SUMMARIZER: To prevent AI "Busy" errors, we condense the 365 days
                    # We send the last 14 days of detail + monthly averages for the rest
                    summary = {
                        "Last_14_Days_Steps": steps[-14:],
                        "Last_10_Sleep_Sessions": [{"date": s['dateOfSleep'], "hrs": round(s['minutesAsleep']/60, 1)} for s in sleep[:10]],
                        "Recent_Weight_Logs": weight[-10:],
                        "Yearly_Step_Total": sum(int(d['value']) for d in steps)
                    }
                    
                    st.session_state.data = str(summary)
                    st.success("12 Months of data condensed and ready!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # CHAT
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Ask about your long-term trends..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is analyzing your history..."):
                    ans = ask_ai(st.session_state.data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# END OF CODE
